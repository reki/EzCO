"""対象: ez_co.handlers.file_handler — 同じ cache_key を同時に二重デコードしない。"""
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from ez_co.handlers import file_handler as file_handler_module
from ez_co.handlers.file_handler import FileHandler


def _handler(monkeypatch):
    """プラグイン画像ではない FileHandler を作る。

    Returns:
        その FileHandler。
    """
    monkeypatch.setattr(FileHandler, "_is_plugin_image", lambda self, file: False)
    config = SimpleNamespace(
        cache={"memory_limit": "8MB", "prefetch_pages": 1, "optimize_large_images": False},
        debug={"keep_archive_handles": False, "cache_archive_metadata": True},
        plugins={},
    )
    handler = FileHandler(config)
    return handler


def test_get_image_at_reuses_in_progress_decode(tmp_path, monkeypatch):
    """進行中のデコードがある取得は再デコードせず、その結果をキャッシュする。"""
    handler = _handler(monkeypatch)
    path = tmp_path / "page.png"
    Image.new("RGB", (8, 8), "white").save(path)
    handler.current_files = [path]
    handler.current_index = 0
    cache_key = handler._cache_key_for_file(path)

    gate = threading.Event()
    opened_event = threading.Event()
    opened = []
    real_open = file_handler_module.Image.open

    def slow_open(source, *args, **kwargs):
        """開いた回数を数えてゲートまで待ち、本物の Image.open を返す。

        Args:
            source: 開く画像。
            args: Image.open へ渡す位置引数。
            kwargs: Image.open へ渡すキーワード引数。

        Returns:
            開いた画像。
        """
        opened.append(source)
        opened_event.set()
        gate.wait(2)
        return real_open(source, *args, **kwargs)

    monkeypatch.setattr(file_handler_module.Image, "open", slow_open)

    worker = threading.Thread(
        target=handler._load_image,
        args=(str(path), cache_key, False),
    )
    worker.start()
    assert opened_event.wait(2)

    received = []

    def read_current():
        """表示中ページの取得結果を received に積む。"""
        received.append(handler.get_image_at(0))

    reader = threading.Thread(target=read_current)
    reader.start()
    time.sleep(0.02)
    gate.set()
    worker.join(timeout=3)
    reader.join(timeout=3)
    assert worker.is_alive() is False
    assert reader.is_alive() is False
    assert len(opened) == 1
    assert received[0] is not None
    assert handler._cache_get(cache_key) is not None
    handler.close()


def test_old_session_decode_does_not_enter_cache(tmp_path, monkeypatch):
    """デコード中に読み込みを止めると、その結果はキャッシュに入らない。"""
    handler = _handler(monkeypatch)
    path = tmp_path / "page.png"
    Image.new("RGB", (8, 8), "white").save(path)
    cache_key = handler._cache_key_for_file(path)
    gate = threading.Event()
    opened = threading.Event()
    real_open = file_handler_module.Image.open

    def slow_open(source, *args, **kwargs):
        """開いたことを知らせてゲートまで待ち、本物の Image.open を返す。

        Args:
            source: 開く画像。
            args: Image.open へ渡す位置引数。
            kwargs: Image.open へ渡すキーワード引数。

        Returns:
            開いた画像。
        """
        opened.set()
        gate.wait(2)
        return real_open(source, *args, **kwargs)

    monkeypatch.setattr(file_handler_module.Image, "open", slow_open)
    generation = handler._scheduler.advance_generation()
    handler._scheduler.enqueue(
        file=str(path),
        cache_key=cache_key,
        page_index=0,
        session_id=handler._get_current_session_id(),
        generation=generation,
        priority=1,
    )
    assert opened.wait(2)

    handler.stop_all_loading()
    gate.set()
    for _ in range(100):
        if handler._scheduler.snapshot()["active_workers"] == 0:
            break
        time.sleep(0.01)

    assert handler._cache_get(cache_key) is None
    handler.close()


def test_session_change_between_decode_and_cache_put_discards_result(tmp_path, monkeypatch):
    """デコード後、キャッシュ投入の前にセッションが変わると結果はキャッシュされない。"""
    handler = _handler(monkeypatch)
    path = tmp_path / "page.png"
    Image.new("RGB", (8, 8), "white").save(path)
    cache_key = handler._cache_key_for_file(path)
    before_put = threading.Event()
    continue_put = threading.Event()
    real_put = handler._cache_put_if_session_active

    def paused_put(*args, **kwargs):
        """キャッシュ投入の直前で待ち、再開後に本番の投入を呼ぶ。

        Args:
            args: 本番の投入へ渡す位置引数。
            kwargs: 本番の投入へ渡すキーワード引数。

        Returns:
            本番の投入の結果。
        """
        before_put.set()
        continue_put.wait(2)
        return real_put(*args, **kwargs)

    monkeypatch.setattr(handler, "_cache_put_if_session_active", paused_put)
    generation = handler._scheduler.advance_generation()
    handler._scheduler.enqueue(
        file=str(path),
        cache_key=cache_key,
        page_index=0,
        session_id=handler._get_current_session_id(),
        generation=generation,
        priority=1,
    )
    assert before_put.wait(2)

    handler.stop_all_loading()
    continue_put.set()
    for _ in range(100):
        if handler._scheduler.snapshot()["active_workers"] == 0:
            break
        time.sleep(0.01)

    assert handler._cache_get(cache_key) is None
    handler.close()


def test_cache_completion_between_miss_check_and_claim_is_reused(tmp_path, monkeypatch):
    """ミス確認と確保のあいだにキャッシュへ入った画像を返し、再デコードしない。"""
    handler = _handler(monkeypatch)
    path = tmp_path / "page.png"
    path.write_bytes(b"not decoded")
    handler.current_files = [path]
    handler.current_index = 0
    cache_key = handler._cache_key_for_file(path)
    expected = Image.new("RGB", (8, 8), "white")
    real_claim = handler._scheduler.claim_foreground

    def complete_then_claim(key, session_id):
        """前景の確保の前に期待画像をキャッシュへ入れ、本番の確保を呼ぶ。

        Args:
            key: キャッシュキー。
            session_id: セッション ID。

        Returns:
            本番の確保結果。
        """
        handler._cache_put(key, expected, handler._estimate_image_size(expected))
        return real_claim(key, session_id)

    monkeypatch.setattr(handler._scheduler, "claim_foreground", complete_then_claim)
    monkeypatch.setattr(
        handler,
        "_decode_image",
        lambda _source: (_ for _ in ()).throw(AssertionError("duplicate decode")),
    )

    assert handler.get_image_at(0) is expected
    handler.close()


def test_foreground_session_change_before_cache_put_discards_result(tmp_path, monkeypatch):
    """前景取得のキャッシュ投入前にセッションが変わると、取得結果は None でキャッシュにも残らない。"""
    handler = _handler(monkeypatch)
    path = tmp_path / "page.png"
    Image.new("RGB", (8, 8), "white").save(path)
    handler.current_files = [path]
    handler.current_index = 0
    cache_key = handler._cache_key_for_file(path)
    before_put = threading.Event()
    continue_put = threading.Event()
    real_put = handler._cache_put_if_session_active

    def paused_put(*args, **kwargs):
        """キャッシュ投入の直前で待ち、再開後に本番の投入を呼ぶ。

        Args:
            args: 本番の投入へ渡す位置引数。
            kwargs: 本番の投入へ渡すキーワード引数。

        Returns:
            本番の投入の結果。
        """
        before_put.set()
        continue_put.wait(2)
        return real_put(*args, **kwargs)

    monkeypatch.setattr(handler, "_cache_put_if_session_active", paused_put)
    received = []
    reader = threading.Thread(target=lambda: received.append(handler.get_image_at(0)))
    reader.start()
    assert before_put.wait(2)

    handler.stop_all_loading()
    continue_put.set()
    reader.join(timeout=2)

    assert not reader.is_alive()
    assert received == [None]
    assert handler._cache_get(cache_key) is None
    handler.close()

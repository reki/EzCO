"""対象: ez_co.handlers.file_handler — 同じ cache_key を同時に二重デコードしない。"""
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from ez_co.handlers import file_handler as file_handler_module
from ez_co.handlers.file_handler import FileHandler


def _handler(monkeypatch):
    monkeypatch.setattr(FileHandler, "_is_plugin_image", lambda self, file: False)
    config = SimpleNamespace(
        cache={"memory_limit": "8MB", "prefetch_pages": 1, "optimize_large_images": False},
        debug={"keep_archive_handles": False, "cache_archive_metadata": True},
        plugins={},
    )
    handler = FileHandler(config)
    return handler


def test_get_image_at_reuses_in_progress_decode(tmp_path, monkeypatch):
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
    handler = _handler(monkeypatch)
    path = tmp_path / "page.png"
    Image.new("RGB", (8, 8), "white").save(path)
    cache_key = handler._cache_key_for_file(path)
    gate = threading.Event()
    opened = threading.Event()
    real_open = file_handler_module.Image.open

    def slow_open(source, *args, **kwargs):
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
    handler = _handler(monkeypatch)
    path = tmp_path / "page.png"
    Image.new("RGB", (8, 8), "white").save(path)
    cache_key = handler._cache_key_for_file(path)
    before_put = threading.Event()
    continue_put = threading.Event()
    real_put = handler._cache_put_if_session_active

    def paused_put(*args, **kwargs):
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
    handler = _handler(monkeypatch)
    path = tmp_path / "page.png"
    path.write_bytes(b"not decoded")
    handler.current_files = [path]
    handler.current_index = 0
    cache_key = handler._cache_key_for_file(path)
    expected = Image.new("RGB", (8, 8), "white")
    real_claim = handler._scheduler.claim_foreground

    def complete_then_claim(key, session_id):
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

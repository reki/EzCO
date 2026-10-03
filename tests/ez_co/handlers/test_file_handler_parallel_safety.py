"""対象: ez_co.handlers.file_handler — 並列読込時のmetadataとPlugin排他。"""

import io
import threading
import time
from types import SimpleNamespace

from PIL import Image

from ez_co.handlers.file_handler import FileHandler
from ez_co.plugins.api import FileKind
from ez_co.plugins.manager import HandlerDecision


def _handler(monkeypatch):
    """メタデータキャッシュを有効にした FileHandler を作る。

    Returns:
        その FileHandler。
    """
    monkeypatch.setattr(FileHandler, "_start_workers", lambda self: None)
    config = SimpleNamespace(
        cache={"memory_limit": "8MB", "prefetch_pages": 1, "optimize_large_images": False},
        debug={"enabled": False, "keep_archive_handles": False, "cache_archive_metadata": True},
        plugins={},
    )
    return FileHandler(config)


def _png_bytes():
    """白い小さな PNG のバイト列を作る。

    Returns:
        PNG のバイト列。
    """
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_same_plugin_read_entry_is_serialized_for_all_callers(monkeypatch):
    """同じプラグインの read_entry はハンドラが違っても同時には1つだけ走る。"""
    handler = _handler(monkeypatch)
    other_handler = _handler(monkeypatch)

    class Plugin:
        """同時に read_entry へ入った数の最大を数えるプラグイン。"""

        def __init__(self):
            """同時実行数のカウンタを初期化する。"""
            self.active = 0
            self.max_active = 0
            self.lock = threading.Lock()

        def read_entry(self, _path, _index):
            """同時実行数を更新してから、白い PNG のエントリを返す。

            Args:
                _path: 書庫パス。
                _index: エントリ番号。

            Returns:
                名前と PNG バイト列。
            """
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            time.sleep(0.03)
            with self.lock:
                self.active -= 1
            return ("page.png", _png_bytes())

    plugin = Plugin()
    monkeypatch.setattr(
        handler,
        "_resolve_handler",
        lambda _path: HandlerDecision("plugin.test", FileKind.IMAGE, plugin),
    )
    monkeypatch.setattr(
        other_handler,
        "_resolve_handler",
        lambda _path: HandlerDecision("plugin.test", FileKind.IMAGE, plugin),
    )

    threads = [
        threading.Thread(
            target=(handler if index % 2 == 0 else other_handler)._load_plugin_image,
            args=(f"{index}.probe",),
        )
        for index in range(3)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert all(not thread.is_alive() for thread in threads)
    assert plugin.max_active == 1


def test_same_archive_metadata_is_built_once(tmp_path, monkeypatch):
    """同じ書庫のメタデータ構築は並行しても1回で、全員が同じ一覧を受け取る。"""
    handler = _handler(monkeypatch)
    archive = tmp_path / "book.zip"
    archive.write_bytes(b"archive")
    calls = []

    def loader():
        """呼び出しを数えて少し待ち、ページ名を1件返す。

        Returns:
            ページ名のリスト。
        """
        calls.append(1)
        time.sleep(0.03)
        return ["page.png"]

    results = []
    threads = [
        threading.Thread(target=lambda: results.append(handler._archive_entries(archive, loader)))
        for _ in range(3)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert results == [["page.png"]] * 3
    assert len(calls) == 1


def test_different_archive_metadata_builds_can_run_in_parallel(tmp_path, monkeypatch):
    """別々の書庫のメタデータ構築は同時に完了し、それぞれの書庫名を返す。"""
    handler = _handler(monkeypatch)
    archives = [tmp_path / "a.zip", tmp_path / "b.zip"]
    for archive in archives:
        archive.write_bytes(b"archive")
    barrier = threading.Barrier(2)
    completed = []

    def build(archive):
        """別書庫のメタデータ構築を同時に通す。

        Args:
            archive: 構築する書庫。
        """
        result = handler._archive_entries(
            archive,
            lambda: (barrier.wait(timeout=1), [archive.name])[1],
        )
        completed.append(result)

    threads = [threading.Thread(target=build, args=(archive,)) for archive in archives]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert all(not thread.is_alive() for thread in threads)
    assert sorted(completed) == [["a.zip"], ["b.zip"]]


def test_session_change_keeps_source_lock_and_rejects_old_metadata(tmp_path, monkeypatch):
    """構築中に読み込みを止めても同じソースロックを使い、止めた結果はキャッシュせず次の構築は別呼び出しになる。"""
    handler = _handler(monkeypatch)
    archive = tmp_path / "book.zip"
    archive.write_bytes(b"archive")
    started = threading.Event()
    release = threading.Event()
    calls = []

    def loader():
        """開始を知らせてから解放を待ち、ページ名を返す。

        Returns:
            ページ名のリスト。
        """
        calls.append(1)
        started.set()
        release.wait(2)
        return ["page.png"]

    old_lock = handler._archive_metadata_source_lock(archive)
    worker = threading.Thread(target=handler._archive_entries, args=(archive, loader))
    worker.start()
    assert started.wait(2)

    handler.stop_all_loading()
    assert handler._archive_metadata_source_lock(archive) is old_lock
    release.set()
    worker.join(timeout=2)

    assert handler._cached_archive_entries(archive) is None
    assert handler._archive_entries(archive, loader) == ["page.png"]
    assert len(calls) == 2


def test_metadata_is_not_published_if_archive_changes_during_build(tmp_path, monkeypatch):
    """構築中に書庫が変わるとその結果はキャッシュされず、次の構築結果はキャッシュされる。"""
    handler = _handler(monkeypatch)
    archive = tmp_path / "book.zip"
    archive.write_bytes(b"old")
    calls = []

    def changing_loader():
        """構築中に書庫バイト列を変え、古いページ名を返す。

        Returns:
            古いページ名のリスト。
        """
        calls.append(1)
        archive.write_bytes(b"changed-size")
        return ["old-page.png"]

    assert handler._archive_entries(archive, changing_loader) == ["old-page.png"]
    assert handler._cached_archive_entries(archive) is None

    assert handler._archive_entries(archive, lambda: ["new-page.png"]) == ["new-page.png"]
    assert handler._cached_archive_entries(archive) == ["new-page.png"]

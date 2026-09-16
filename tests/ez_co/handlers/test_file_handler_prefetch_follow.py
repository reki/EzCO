"""対象: ez_co.handlers.file_handler — ページ移動後に先読み窓が追従する。"""
from pathlib import Path
from types import SimpleNamespace

from ez_co.handlers.file_handler import FileHandler
from ez_co.handlers.virtual_path_handler import VirtualPathHandler


def _handler(monkeypatch):
    monkeypatch.setattr(FileHandler, "_start_workers", lambda self: None)
    monkeypatch.setattr(FileHandler, "_is_plugin_image", lambda self, file: False)
    config = SimpleNamespace(
        cache={"memory_limit": "8MB", "prefetch_pages": 3, "optimize_large_images": False},
        debug={"keep_archive_handles": False},
        plugins={},
    )
    handler = FileHandler(config)
    handler._executor.shutdown(wait=False)
    return handler


def _archive_pages(archive_path: Path, count: int):
    return [
        Path(VirtualPathHandler.create_virtual_path(archive_path, f"page_{index:02d}.png"))
        for index in range(count)
    ]


def _queued_indices(handler, files):
    keys = {item[1] for item in list(handler._image_queue.queue)}
    keys.update(handler._prefetch_pending)
    indices = []
    for index, file in enumerate(files):
        if handler._cache_key_for_file(file) in keys:
            indices.append(index)
    return indices


def test_next_file_in_archive_keeps_prefetch_ahead(tmp_path, monkeypatch):
    handler = _handler(monkeypatch)
    archive_path = tmp_path / "book.zip"
    archive_path.write_bytes(b"")
    files = _archive_pages(archive_path, 20)
    handler.current_files = files
    handler.current_index = 0
    handler._prefetch_around(0)

    assert 1 in _queued_indices(handler, files)
    assert 3 in _queued_indices(handler, files)
    assert 10 not in _queued_indices(handler, files)

    for _ in range(10):
        assert handler.next_file()

    queued = _queued_indices(handler, files)
    assert handler.current_index == 10
    assert 11 in queued
    assert 13 in queued


def test_go_to_page_prefetches_around_jump(tmp_path, monkeypatch):
    handler = _handler(monkeypatch)
    archive_path = tmp_path / "book.zip"
    archive_path.write_bytes(b"")
    files = _archive_pages(archive_path, 20)
    handler.current_files = files
    handler.current_index = 0

    assert handler.go_to_page(15)
    queued = _queued_indices(handler, files)
    assert 16 in queued
    assert 14 in queued
    assert 1 not in queued


def test_prev_file_prefetches_around_new_index(tmp_path, monkeypatch):
    handler = _handler(monkeypatch)
    archive_path = tmp_path / "book.zip"
    archive_path.write_bytes(b"")
    files = _archive_pages(archive_path, 20)
    handler.current_files = files
    handler.current_index = 10

    assert handler.prev_file()
    queued = _queued_indices(handler, files)
    assert handler.current_index == 9
    assert 10 in queued
    assert 8 in queued

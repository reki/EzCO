"""対象: ez_co.handlers.file_handler — ページ移動後に先読み窓が追従する。"""
from pathlib import Path
from types import SimpleNamespace

from ez_co.handlers.file_handler import FileHandler
from ez_co.handlers.virtual_path_handler import VirtualPathHandler


class _RecordingScheduler:
    """投入された先読みタスクを順に覚えておくスケジューラ。"""

    def __init__(self):
        """世代とタスク列を空にする。"""
        self.generation = 0
        self.tasks = []

    def advance_generation(self):
        """世代を進め、未実行タスクを捨てて新しい世代を返す。

        Returns:
            新しい世代番号。
        """
        self.generation += 1
        self.tasks.clear()
        return self.generation

    def enqueue(self, **task):
        """タスクを記録して受け付けたことにする。

        Args:
            task: 先読みタスクの項目。

        Returns:
            受け付けたことを表す真。
        """
        self.tasks.append(task)
        return True

    def shutdown(self, *, wait=False):
        """停止要求を受け捨てる。

        Args:
            wait: 終了を待つか。
        """
        del wait

    def cancel_pending(self):
        """未実行タスクを空にする。"""
        self.tasks.clear()


def _handler(monkeypatch):
    """記録用スケジューラを付けた FileHandler を作る。

    Returns:
        その FileHandler。
    """
    monkeypatch.setattr(FileHandler, "_start_workers", lambda self: None)
    monkeypatch.setattr(FileHandler, "_is_plugin_image", lambda self, file: False)
    config = SimpleNamespace(
        cache={"memory_limit": "8MB", "prefetch_pages": 3, "optimize_large_images": False},
        debug={"keep_archive_handles": False},
        plugins={},
    )
    handler = FileHandler(config)
    handler._scheduler = _RecordingScheduler()
    return handler


def _archive_pages(archive_path: Path, count: int):
    """書庫内ページの仮想パスを連番で作る。

    Args:
        archive_path: 書庫パス。
        count: ページ数。

    Returns:
        仮想パスの列。
    """
    return [
        Path(VirtualPathHandler.create_virtual_path(archive_path, f"page_{index:02d}.png"))
        for index in range(count)
    ]


def _queued_indices(handler, files):
    """投入済みタスクに対応するページ番号を集める。

    Args:
        handler: スケジューラを持つハンドラ。
        files: ページ列。

    Returns:
        投入済みのページ番号。
    """
    keys = {item["cache_key"] for item in handler._scheduler.tasks}
    indices = []
    for index, file in enumerate(files):
        if handler._cache_key_for_file(file) in keys:
            indices.append(index)
    return indices


def test_next_file_in_archive_keeps_prefetch_ahead(tmp_path, monkeypatch):
    """開始位置では先読みに 1 と 3 が入り 10 は入らず、10 ページ進むと現在は 10 で先読みに 11 と 13 が入り、先頭タスクは 11 になる。"""
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
    assert handler._scheduler.tasks[0]["page_index"] == 11


def test_go_to_page_prefetches_around_jump(tmp_path, monkeypatch):
    """離れたページへ飛ぶと、その前後だけが先読みされ、先頭は次ページになる。"""
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
    assert handler._scheduler.tasks[0]["page_index"] == 16


def test_prev_file_prefetches_around_new_index(tmp_path, monkeypatch):
    """前ページへ戻ると、新しい位置の前後が先読みされ、先頭は手前のページになる。"""
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
    assert handler._scheduler.tasks[0]["page_index"] == 8

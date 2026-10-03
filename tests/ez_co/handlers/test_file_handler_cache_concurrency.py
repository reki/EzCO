"""対象: ez_co.handlers.file_handler — キャッシュの並行 get/put で落ちない。"""
import threading
from types import SimpleNamespace

from PIL import Image

from ez_co.handlers.file_handler import FileHandler


def test_cache_get_put_from_many_threads(tmp_path, monkeypatch):
    """多数の get と put を同時に走らせても例外が残らない。"""
    monkeypatch.setattr(FileHandler, "_start_workers", lambda self: None)
    config = SimpleNamespace(
        cache={"memory_limit": "8KB", "prefetch_pages": 1, "optimize_large_images": False},
        debug={"keep_archive_handles": False},
    )
    handler = FileHandler(config)
    files = [tmp_path / f"{index}.png" for index in range(8)]
    for path in files:
        path.write_bytes(b"")
    handler.current_files = files
    handler.current_index = 0
    handler.cache_limit = 4000
    errors = []

    def writer():
        """複数ページへ put を繰り返し、例外は errors に積む。"""
        try:
            for index in range(40):
                image = Image.new("L", (12, 12))
                key = handler._cache_key_for_file(files[index % len(files)])
                handler._cache_put(key, image, handler._estimate_image_size(image))
        except Exception as exc:
            errors.append(exc)

    def reader():
        """get と追い出しを繰り返し、例外は errors に積む。"""
        try:
            for index in range(40):
                key = handler._cache_key_for_file(files[index % len(files)])
                handler._cache_get(key)
                handler._evict_cache()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer) for _ in range(4)]
    threads.extend(threading.Thread(target=reader) for _ in range(4))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []


def test_navigation_snapshot_retries_when_index_changes(monkeypatch):
    """走査中にインデックスが変わると、スナップショットは変えたあとのインデックスを返す。"""
    monkeypatch.setattr(FileHandler, "_start_workers", lambda self: None)
    config = SimpleNamespace(
        cache={"memory_limit": "8KB", "prefetch_pages": 1, "optimize_large_images": False},
        debug={"keep_archive_handles": False},
    )
    handler = FileHandler(config)

    class ChangingList(list):
        """走査の途中で current_index を変えるリスト。"""

        changed = False

        def __iter__(self):
            """最初の走査で current_index を 1 にしてから要素を返す。

            Returns:
                要素のイテレータ。
            """
            if not self.changed:
                self.changed = True
                handler.current_index = 1
            return super().__iter__()

    handler.current_files = ChangingList(["a", "b"])
    handler.current_index = 0

    files, index = handler._navigation_snapshot()
    assert files == ("a", "b")
    assert index == 1

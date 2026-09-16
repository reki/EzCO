"""対象: ez_co.handlers.file_handler — キャッシュの並行 get/put で落ちない。"""
import threading
from types import SimpleNamespace

from PIL import Image

from ez_co.handlers.file_handler import FileHandler


def test_cache_get_put_from_many_threads(tmp_path, monkeypatch):
    monkeypatch.setattr(FileHandler, "_start_workers", lambda self: None)
    config = SimpleNamespace(
        cache={"memory_limit": "8KB", "prefetch_pages": 1, "optimize_large_images": False},
        debug={"keep_archive_handles": False},
    )
    handler = FileHandler(config)
    handler._executor.shutdown(wait=False)
    files = [tmp_path / f"{index}.png" for index in range(8)]
    for path in files:
        path.write_bytes(b"")
    handler.current_files = files
    handler.current_index = 0
    handler.cache_limit = 4000
    errors = []

    def writer():
        try:
            for index in range(40):
                image = Image.new("L", (12, 12))
                key = handler._cache_key_for_file(files[index % len(files)])
                handler._cache_put(key, image, handler._estimate_image_size(image))
        except Exception as exc:
            errors.append(exc)

    def reader():
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

"""対象: ez_co.handlers.file_handler — 同じ cache_key を同時に二重デコードしない。"""
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from ez_co.handlers import file_handler as file_handler_module
from ez_co.handlers.file_handler import FileHandler


def _handler(monkeypatch):
    monkeypatch.setattr(FileHandler, "_start_workers", lambda self: None)
    monkeypatch.setattr(FileHandler, "_is_plugin_image", lambda self, file: False)
    config = SimpleNamespace(
        cache={"memory_limit": "8MB", "prefetch_pages": 1, "optimize_large_images": False},
        debug={"keep_archive_handles": False, "cache_archive_metadata": True},
        plugins={},
    )
    handler = FileHandler(config)
    handler._executor.shutdown(wait=False)
    handler._load_wait_timeout = 2.0
    return handler


def test_get_image_at_reuses_in_progress_decode(tmp_path, monkeypatch):
    handler = _handler(monkeypatch)
    path = tmp_path / "page.png"
    Image.new("RGB", (8, 8), "white").save(path)
    handler.current_files = [path]
    handler.current_index = 0
    cache_key = handler._cache_key_for_file(path)

    gate = threading.Event()
    opened = []
    real_open = file_handler_module.Image.open

    def slow_open(source, *args, **kwargs):
        opened.append(source)
        gate.wait(2)
        return real_open(source, *args, **kwargs)

    monkeypatch.setattr(file_handler_module.Image, "open", slow_open)

    worker = threading.Thread(
        target=handler._load_image,
        args=(str(path), cache_key, False),
    )
    worker.start()
    for _ in range(100):
        if cache_key in handler._prefetch_in_progress:
            break
        time.sleep(0.01)
    assert cache_key in handler._prefetch_in_progress

    received = []

    def read_current():
        received.append(handler.get_image_at(0))

    reader = threading.Thread(target=read_current)
    reader.start()
    for _ in range(100):
        if cache_key in handler._load_events:
            break
        time.sleep(0.01)
    gate.set()
    worker.join(timeout=3)
    reader.join(timeout=3)
    assert worker.is_alive() is False
    assert reader.is_alive() is False
    assert len(opened) == 1
    assert received[0] is not None
    assert handler._cache_get(cache_key) is not None

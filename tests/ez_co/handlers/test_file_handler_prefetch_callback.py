"""対象: ez_co.handlers.file_handler — 先読み完了では表示コールバックを呼ばない。"""
from types import SimpleNamespace

from PIL import Image

from ez_co.handlers.file_handler import FileHandler


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


def test_prefetch_load_does_not_call_image_loaded(tmp_path, monkeypatch):
    handler = _handler(monkeypatch)
    path = tmp_path / "page.png"
    Image.new("RGB", (8, 8), "white").save(path)
    called = []
    handler.set_on_image_loaded(lambda file, image: called.append(file))
    cache_key = str(path.resolve())
    handler._load_image(str(path), cache_key, is_current=False)
    assert called == []
    assert handler._cache_get(cache_key) is not None


def test_current_load_schedules_image_loaded(qapp, tmp_path, monkeypatch):
    handler = _handler(monkeypatch)
    path = tmp_path / "page.png"
    Image.new("RGB", (8, 8), "white").save(path)
    called = []
    handler.set_on_image_loaded(lambda file, image: called.append(file))
    cache_key = str(path.resolve())
    handler._load_image(str(path), cache_key, is_current=True)
    qapp.processEvents()
    assert called == [str(path)]

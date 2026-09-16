"""対象: ez_co.handlers.file_handler — アーカイブ entry 一覧をページごとに namelist しない。"""
import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from ez_co.handlers.file_handler import FileHandler
from ez_co.plugins.api import BUILTIN_PROVIDER_ID, FileKind
from ez_co.plugins.manager import HandlerDecision


def _handler(monkeypatch, metadata=True):
    monkeypatch.setattr(FileHandler, "_start_workers", lambda self: None)
    monkeypatch.setattr(FileHandler, "_is_plugin_image", lambda self, file: False)
    monkeypatch.setattr(
        FileHandler,
        "_resolve_handler",
        lambda self, file_path: HandlerDecision(BUILTIN_PROVIDER_ID, FileKind.ARCHIVE),
    )
    config = SimpleNamespace(
        cache={"memory_limit": "8MB", "prefetch_pages": 1, "optimize_large_images": False},
        debug={"keep_archive_handles": False, "cache_archive_metadata": metadata},
        plugins={},
        archive={"enabled": True},
    )
    handler = FileHandler(config)
    handler._executor.shutdown(wait=False)
    return handler


def _make_zip(path: Path, pages: int) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for index in range(pages):
            buffer = io.BytesIO()
            Image.new("RGB", (4, 4), (index * 40, 0, 0)).save(buffer, format="PNG")
            archive.writestr(f"page_{index:02d}.png", buffer.getvalue())


def _count_namelist(monkeypatch):
    from ez_co.handlers import file_handler as module

    real_open = module.open_zip
    calls = {"count": 0}

    def counting_open(*args, **kwargs):
        archive = real_open(*args, **kwargs)
        original = archive.namelist

        def namelist():
            calls["count"] += 1
            return original()

        archive.namelist = namelist
        return archive

    monkeypatch.setattr(module, "open_zip", counting_open)
    return calls


def test_zip_pages_reuse_namelist_from_expand(tmp_path, monkeypatch):
    handler = _handler(monkeypatch)
    zip_path = tmp_path / "book.zip"
    _make_zip(zip_path, 3)
    calls = _count_namelist(monkeypatch)

    files = handler._expand_archive(zip_path)
    assert len(files) == 3
    assert calls["count"] == 1

    handler.current_files = files
    handler.current_index = 0
    first = handler.get_image_at(0)
    second = handler.get_image_at(1)
    assert first is not None
    assert second is not None
    assert calls["count"] == 1


def test_zip_metadata_invalidates_when_file_changes(tmp_path, monkeypatch):
    handler = _handler(monkeypatch)
    zip_path = tmp_path / "book.zip"
    _make_zip(zip_path, 2)
    handler._expand_archive(zip_path)
    assert handler._cached_archive_entries(zip_path) is not None

    _make_zip(zip_path, 2)
    assert handler._cached_archive_entries(zip_path) is None


def test_zip_namelist_every_page_when_metadata_disabled(tmp_path, monkeypatch):
    handler = _handler(monkeypatch, metadata=False)
    zip_path = tmp_path / "book.zip"
    _make_zip(zip_path, 2)
    calls = _count_namelist(monkeypatch)
    files = handler._expand_archive(zip_path)
    handler.current_files = files
    handler.get_image_at(0)
    handler.get_image_at(1)
    assert calls["count"] == 3

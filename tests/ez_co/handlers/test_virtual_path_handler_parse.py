"""対象: ez_co.handlers.virtual_path_handler — archive:// の分解。"""
from pathlib import Path

from ez_co.handlers.virtual_path_handler import VirtualPathHandler


def test_parse_virtual_path_splits_archive_and_name():
    archive, name = VirtualPathHandler.parse_virtual_path("archive://C:/books/a.zip|inner/page.png")
    assert archive == Path("C:/books/a.zip")
    assert name == "inner/page.png"


def test_parse_virtual_path_rejects_plain_path():
    assert VirtualPathHandler.parse_virtual_path("C:/books/a.zip") is None


def test_parse_virtual_path_requires_separator():
    assert VirtualPathHandler.parse_virtual_path("archive://C:/books/a.zip") is None

"""対象: ez_co.filters.builtin — 既定は非破壊。台帳は builtin:basic 1件。"""
from PIL import Image

from ez_co.filters.builtin import (
    BUILTIN_FILTER_ID,
    default_basic_settings,
    process_basic,
    register_builtin,
)
from ez_co.filters.pipeline import FilterContext
from ez_co.filters.registry import FilterRegistry


def _context(settings=None):
    return FilterContext(path="a.png", page=1, size=(8, 8), settings=settings or default_basic_settings())


def _pixels(image):
    return list(image.getdata())


def test_default_settings_are_non_destructive():
    image = Image.new("RGB", (8, 8), (128, 64, 32))
    result = process_basic(image, _context())
    assert result is image
    assert _pixels(result) == _pixels(image)


def test_changing_one_setting_changes_pixels():
    original = Image.new("RGB", (8, 8), (128, 64, 32))
    baseline = _pixels(original)
    settings = default_basic_settings()
    settings["brightness"] = 40
    result = process_basic(original.copy(), _context(settings))
    assert _pixels(result) != baseline


def test_registry_has_single_builtin_basic():
    registry = FilterRegistry()
    register_builtin(registry)
    records = list(registry.iter())
    assert len(records) == 1
    assert records[0].public_id == BUILTIN_FILTER_ID
    assert registry.get(BUILTIN_FILTER_ID) is records[0]

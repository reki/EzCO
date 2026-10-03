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
    """フィルタ処理に渡す FilterContext を組む。

    Args:
        settings: 基本フィルタの設定。省略時は既定値。

    Returns:
        パスとページとサイズを固定した FilterContext。
    """
    return FilterContext(path="a.png", page=1, size=(8, 8), settings=settings or default_basic_settings())


def _pixels(image):
    """画像の画素列を取り出す。

    Args:
        image: 画素を読む画像。

    Returns:
        getdata のリスト。
    """
    return list(image.getdata())


def test_default_settings_are_non_destructive():
    """既定値では画像オブジェクトも画素も変えない。"""
    image = Image.new("RGB", (8, 8), (128, 64, 32))
    result = process_basic(image, _context())
    assert result is image
    assert _pixels(result) == _pixels(image)


def test_changing_one_setting_changes_pixels():
    """明るさだけ変えると、既定の画素列とは一致しなくなる。"""
    original = Image.new("RGB", (8, 8), (128, 64, 32))
    baseline = _pixels(original)
    settings = default_basic_settings()
    settings["brightness"] = 40
    result = process_basic(original.copy(), _context(settings))
    assert _pixels(result) != baseline


def test_registry_has_single_builtin_basic():
    """組み込み登録は builtin:basic の1件だけで、get も同じレコードを返す。"""
    registry = FilterRegistry()
    register_builtin(registry)
    records = list(registry.iter())
    assert len(records) == 1
    assert records[0].public_id == BUILTIN_FILTER_ID
    assert registry.get(BUILTIN_FILTER_ID) is records[0]

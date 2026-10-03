"""対象: ez_co.ui.plugins.plugin_config_dialog — range 項目名の末尾。"""
import pytest

from ez_co.plugins.host import ConfigField
from ez_co.ui.plugins.plugin_config_dialog import config_field_display_name
from ez_co.utils.language_manager import get_text

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


def test_int_range_appends_min_max():
    """整数範囲の表示名が、下限と上限を入れた言語キーの文にならない。"""
    field = ConfigField(
        key="strength",
        value_type="int_range",
        label="強度",
        minimum=0,
        maximum=100,
        step=1,
    )
    assert config_field_display_name(field) == get_text(
        "ui.plugin_config_int_range_name",
        name="強度",
        minimum="0",
        maximum="100",
    )


def test_float_range_appends_min_max_and_step():
    """浮動小数の表示名から下限・上限・刻みのどれかが欠け、上限の末尾ゼロが残る。"""
    field = ConfigField(
        key="gamma",
        value_type="float_range",
        label="ガンマ",
        minimum=0.2,
        maximum=3.0,
        step=0.05,
    )
    assert config_field_display_name(field) == get_text(
        "ui.plugin_config_float_range_name",
        name="ガンマ",
        minimum="0.2",
        maximum="3",
        step="0.05",
    )


def test_non_range_keeps_label():
    """範囲でない項目の表示名に、下限や刻みが足される。"""
    field = ConfigField(key="name", value_type="string", label="名前")
    assert config_field_display_name(field) == "名前"

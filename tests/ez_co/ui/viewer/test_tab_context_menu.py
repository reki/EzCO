"""対象: ez_co.ui.viewer.tab_context_menu"""
import pytest

from ez_co.ui.viewer.tab_context_menu import build_tab_context_menu
from ez_co.utils.language_manager import get_text, set_language

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


def _menu(**kwargs):
    """日本語でタブのコンテキストメニューを組む。

    Args:
        **kwargs: タブ位置、ピン、パス、各操作。省略した項目は空タブの既定。

    Returns:
        組んだメニュー。
    """
    set_language("ja")
    defaults = dict(
        index=0,
        pinned=[False],
        path=None,
        on_close=lambda: None,
        on_close_others=lambda: None,
        on_close_right=lambda: None,
        on_close_left=lambda: None,
        on_pin=lambda: None,
        on_duplicate=lambda: None,
        on_copy_name=lambda: None,
        on_copy_path=lambda: None,
    )
    defaults.update(kwargs)
    return build_tab_context_menu(None, **defaults)


def _labels(menu):
    """区切りを除いた項目の表示文を取り出す。

    Args:
        menu: 表示文を読むメニュー。

    Returns:
        表示文のリスト。
    """
    return [action.text() for action in menu.actions() if not action.isSeparator()]


def test_menu_order_and_disabled_items_match_for_an_empty_tab():
    """空タブの項目順が言語キーとずれ、他を閉じる・左右・コピーが有効になり、ショートカットが付く。"""
    menu = _menu()
    assert _labels(menu) == [
        get_text("ui.close_tab"),
        get_text("ui.close_other_tabs"),
        get_text("ui.close_tabs_to_the_right"),
        get_text("ui.close_tabs_to_the_left"),
        get_text("ui.pin_tab"),
        get_text("ui.duplicate_tab"),
        get_text("ui.copy_file_name"),
        get_text("ui.copy_full_path"),
    ]
    enabled = {
        action.text(): action.isEnabled()
        for action in menu.actions()
        if not action.isSeparator()
    }
    assert enabled[get_text("ui.close_tab")] is True
    assert enabled[get_text("ui.close_other_tabs")] is False
    assert enabled[get_text("ui.close_tabs_to_the_right")] is False
    assert enabled[get_text("ui.close_tabs_to_the_left")] is False
    assert enabled[get_text("ui.copy_file_name")] is False
    assert enabled[get_text("ui.copy_full_path")] is False
    assert all(action.shortcut().isEmpty() for action in menu.actions())


def test_pinned_tab_with_neighbors_enables_close_and_copy():
    """隣があるピンタブがピン留めの文言のまま、他を閉じると左右とパスのコピーが無効のまま。"""
    menu = _menu(index=1, pinned=[False, True, False], path=r"C:\books\a.zip")
    labels = _labels(menu)
    assert labels[4] == get_text("ui.unpin_tab")
    enabled = {
        action.text(): action.isEnabled()
        for action in menu.actions()
        if not action.isSeparator()
    }
    assert enabled[get_text("ui.close_other_tabs")] is True
    assert enabled[get_text("ui.close_tabs_to_the_right")] is True
    assert enabled[get_text("ui.close_tabs_to_the_left")] is True
    assert enabled[get_text("ui.copy_full_path")] is True

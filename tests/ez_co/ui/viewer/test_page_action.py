"""対象: ez_co.ui.viewer.page_action — tab 指定がショートカット対象を変えないこと。"""
from ez_co.ui.viewer.page_action import resolve_page_target


def test_requested_tab_does_not_change_shortcut_target():
    """tab を渡すと、ショートカット対象が別のタブへ変わる。"""
    target, changes = resolve_page_target("a", "b", ("a", "b"))
    assert target == "b"
    assert changes is False


def test_omitted_tab_stays_on_shortcut_target():
    """tab が無いと、ショートカット対象以外を操作する。"""
    target, changes = resolve_page_target("a", None, ("a", "b"))
    assert target == "a"
    assert changes is False


def test_unknown_tab_is_not_operated():
    """開いていない tab へ操作が届く。"""
    target, changes = resolve_page_target("a", "gone", ("a", "b"))
    assert target is None
    assert changes is False

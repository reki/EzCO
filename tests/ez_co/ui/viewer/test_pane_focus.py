"""対象: ez_co.ui.viewer.pane_focus — ショートカットとジェスチャーの対象タブ。"""
from ez_co.ui.viewer.pane_focus import PaneFocus


def test_note_is_what_shortcuts_pages_and_docks_follow():
    """操作を覚えても、ショートカットとページ送りとドックが別のタブを追う。"""
    focus = PaneFocus()
    assert focus.note("opened") == "opened"
    assert focus.shortcut_target() == "opened"
    assert focus.page_target() == "opened"
    assert focus.dock_target() == "opened"


def test_click_on_a_visible_tab_focuses_it_without_replacing():
    """見えているタブのクリックが、別の面の差し替えになる。"""
    focus = PaneFocus()
    focus.note("a")
    assert focus.activate_tab("b", ["a", "b"]) == ("focus", "b")
    assert focus.shortcut_target() == "b"


def test_click_on_a_hidden_tab_replaces_the_last_operated_pane():
    """見えていないタブのクリックが、最後に操作した面以外を差し替える。"""
    focus = PaneFocus()
    focus.note("a")
    assert focus.activate_tab("c", ["a", "b"]) == ("replace", "a", "c")
    assert focus.shortcut_target() == "c"
    assert focus.page_target() == "c"
    assert focus.dock_target() == "c"


def test_gesture_uses_the_start_tab_then_shortcuts_follow_it():
    """ジェスチャーが開始タブ以外に効き、その後のショートカットが元のタブのままになる。"""
    focus = PaneFocus()
    focus.note("a")
    assert focus.gesture_target("b", "a") == "b"
    assert focus.shortcut_target() == "b"
    assert focus.gesture_target(None, "b") == "b"

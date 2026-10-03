"""対象: ez_co.enums.actions — 表示名は残った langs キーを見る。"""
from ez_co.enums import actions
from ez_co.enums.actions import get_action_display_name
from ez_co.utils.language_manager import get_text


def test_close_app_display_uses_ui_exit(monkeypatch):
    """close_app の表示名は ui.exit の文言と一致する。"""
    monkeypatch.setattr(actions, "_plugin_host", lambda: None)
    assert get_action_display_name("close_app") == get_text("ui.exit")


def test_next_page_display_uses_ui_key(monkeypatch):
    """next_page の表示名は ui.next_page の文言と一致する。"""
    monkeypatch.setattr(actions, "_plugin_host", lambda: None)
    assert get_action_display_name("next_page") == get_text("ui.next_page")


def test_first_page_display_uses_actions_key(monkeypatch):
    """first_page の表示名は actions.first_page の文言と一致する。"""
    monkeypatch.setattr(actions, "_plugin_host", lambda: None)
    assert get_action_display_name("first_page") == get_text("actions.first_page")


def test_zoom_navigation_actions_use_menu_labels(monkeypatch):
    """ズーム移動3種の表示名は、それぞれのメニュー文言と一致する。"""
    monkeypatch.setattr(actions, "_plugin_host", lambda: None)
    expected = {
        "zoom_navigation_page": "ui.zoom_navigation_page",
        "zoom_navigation_left": "ui.zoom_navigation_left",
        "zoom_navigation_right": "ui.zoom_navigation_right",
    }
    for action_name, text_key in expected.items():
        assert get_action_display_name(action_name) == get_text(text_key)


def test_hold_mouse_lock_uses_ui_label(monkeypatch):
    """hold_mouse_lock の表示名は ui.hold_mouse_lock の文言と一致する。"""
    monkeypatch.setattr(actions, "_plugin_host", lambda: None)
    assert get_action_display_name("hold_mouse_lock") == get_text("ui.hold_mouse_lock")

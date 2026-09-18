"""対象: ez_co.enums.actions — エイリアスで本体 ID を隠す。"""
from ez_co.enums import actions
from ez_co.enums.actions import (
    ACTION_LIST,
    canonical_action_id,
    list_assignable_actions,
    list_gesture_assignable_actions,
)


class _Action:
    def __init__(self, public_id, aliases):
        self.public_id = public_id
        self.aliases = aliases


class _Host:
    def list_actions(self):
        return [_Action("plugin:com.example.x:go", ("next_page",))]


def test_alias_hides_builtin_action_id(monkeypatch):
    monkeypatch.setattr(actions, "_plugin_host", lambda: _Host())
    assignable = list_assignable_actions()
    assert "next_page" not in assignable
    assert "plugin:com.example.x:go" in assignable
    assert "prev_page" in assignable
    assert set(ACTION_LIST) - {"next_page"} <= set(assignable)


def test_zoom_navigation_actions_are_assignable(monkeypatch):
    monkeypatch.setattr(actions, "_plugin_host", lambda: None)
    assignable = list_assignable_actions()
    assert {
        "zoom_navigation_page",
        "zoom_navigation_left",
        "zoom_navigation_right",
    } <= set(assignable)


def test_hold_mouse_lock_is_shortcut_only(monkeypatch):
    monkeypatch.setattr(actions, "_plugin_host", lambda: None)
    assert "hold_mouse_lock" in list_assignable_actions()
    assert "hold_mouse_lock" not in list_gesture_assignable_actions()


def test_legacy_image_slide_id_is_accepted_but_not_offered(monkeypatch):
    monkeypatch.setattr(actions, "_plugin_host", lambda: None)
    assert "toggle_image_slide_dock" not in ACTION_LIST
    assert "toggle_image_slide_dock" not in list_assignable_actions()
    assert canonical_action_id("toggle_image_slide_dock") == "image_slide_sidebar"
    assert actions.is_known_action("toggle_image_slide_dock")

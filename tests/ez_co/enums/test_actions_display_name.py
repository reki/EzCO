"""対象: ez_co.enums.actions — 表示名は残った langs キーを見る。"""
from ez_co.enums import actions
from ez_co.enums.actions import get_action_display_name
from ez_co.utils.language_manager import get_text


def test_close_app_display_uses_ui_exit(monkeypatch):
    monkeypatch.setattr(actions, "_plugin_host", lambda: None)
    assert get_action_display_name("close_app") == get_text("ui.exit")


def test_next_page_display_uses_ui_key(monkeypatch):
    monkeypatch.setattr(actions, "_plugin_host", lambda: None)
    assert get_action_display_name("next_page") == get_text("ui.next_page")


def test_first_page_display_uses_actions_key(monkeypatch):
    monkeypatch.setattr(actions, "_plugin_host", lambda: None)
    assert get_action_display_name("first_page") == get_text("actions.first_page")

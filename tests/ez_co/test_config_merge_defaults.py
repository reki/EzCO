"""対象: ez_co.config — merge_with_defaults。"""
import pytest

from ez_co.config import Config

pytestmark = pytest.mark.usefixtures("qapp")


def test_merge_keeps_user_shortcuts_without_backfill():
    merged = Config.merge_with_defaults({"shortcuts": {"next_page": ["Space"]}})
    assert merged["shortcuts"] == {"next_page": ["Space"]}
    assert "prev_page" not in merged["shortcuts"]


def test_merge_fills_missing_viewer_keys():
    merged = Config.merge_with_defaults({"viewer": {"background_color": "#111111"}})
    assert merged["viewer"]["background_color"] == "#111111"
    assert "gesture_threshold" in merged["viewer"]
    assert merged["viewer"]["zoom_navigation_mode"] == "page"


def test_merge_keeps_zoom_navigation_mode():
    merged = Config.merge_with_defaults({"viewer": {"zoom_navigation_mode": "right"}})
    assert merged["viewer"]["zoom_navigation_mode"] == "right"


def test_fresh_config_has_temporary_mouse_lock_shortcuts():
    config = Config()
    assert config.shortcuts["hold_mouse_lock"] == ["Ctrl", "MouseMiddle"]

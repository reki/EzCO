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

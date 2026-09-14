"""対象: ez_co.config — last_spread_mode の復元。"""
import pytest

from ez_co.config import Config

pytestmark = pytest.mark.usefixtures("qapp")


def test_last_spread_mode_follows_saved_value():
    config = Config.from_dict(
        {"viewer": {"page_mode": "single", "last_spread_mode": "spread_left"}}
    )
    assert config.viewer["last_spread_mode"] == "spread_left"


def test_last_spread_mode_falls_back_to_current_spread():
    config = Config.from_dict({"viewer": {"page_mode": "spread_left"}})
    assert config.viewer["last_spread_mode"] == "spread_left"


def test_last_spread_mode_defaults_to_right():
    config = Config.from_dict({"viewer": {"page_mode": "single"}})
    assert config.viewer["last_spread_mode"] == "spread_right"

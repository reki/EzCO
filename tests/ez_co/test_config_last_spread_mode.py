"""対象: ez_co.config — last_spread_mode の復元。"""
import pytest

from ez_co.config import Config

pytestmark = pytest.mark.usefixtures("qapp")


def test_last_spread_mode_follows_saved_value():
    """保存された見開き方向は、現在のページモードが単ページでもそのまま残る。"""
    config = Config.from_dict(
        {"viewer": {"page_mode": "single", "last_spread_mode": "spread_left"}}
    )
    assert config.viewer["last_spread_mode"] == "spread_left"


def test_last_spread_mode_falls_back_to_current_spread():
    """見開き方向の保存が無く現在が左見開きなら、復元値も左見開きになる。"""
    config = Config.from_dict({"viewer": {"page_mode": "spread_left"}})
    assert config.viewer["last_spread_mode"] == "spread_left"


def test_last_spread_mode_defaults_to_right():
    """単ページで見開き方向の保存が無いときは右見開きになる。"""
    config = Config.from_dict({"viewer": {"page_mode": "single"}})
    assert config.viewer["last_spread_mode"] == "spread_right"

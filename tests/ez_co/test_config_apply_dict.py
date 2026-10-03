"""対象: ez_co.config — apply_dict。"""
import pytest

from ez_co.config import Config

pytestmark = pytest.mark.usefixtures("qapp")


def test_apply_dict_keeps_runtime_overrides():
    """apply_dict は渡した背景色を反映し、実行中オーバーライドの閾値は読み取りに残り保存辞書には出ない。"""
    config = Config()
    config.set_runtime_override("viewer.gesture_threshold", 9)
    config.apply_dict({"viewer": {"background_color": "#abcdef"}})
    assert config.viewer["background_color"] == "#abcdef"
    assert config.viewer["gesture_threshold"] == 9
    assert config.to_dict()["viewer"]["gesture_threshold"] != 9


def test_strip_profile_section_drops_legacy_key():
    """プロファイル節は落ち、ビューアの閾値は残る。"""
    cleaned = Config.strip_profile_section(
        {"viewer": {"gesture_threshold": 10}, "profile": {"current_profile": "old"}}
    )
    assert "profile" not in cleaned
    assert cleaned["viewer"]["gesture_threshold"] == 10

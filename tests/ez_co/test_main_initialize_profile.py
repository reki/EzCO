"""対象: ez_co.main — initialize_profile。"""
import pytest

from ez_co.config import Config
from ez_co.main import initialize_profile

pytestmark = pytest.mark.usefixtures("qapp")


def test_initialize_profile_switches_and_applies_settings(db_manager):
    """指定プロファイルへ切り替わり、その背景色と実行中のプロファイル名が設定へ入る。"""
    db_manager.create_profile(
        "work",
        settings={"viewer": {"background_color": "#010203"}},
    )
    config = Config()
    name = initialize_profile(db_manager, config, "work")
    assert name == "work"
    assert db_manager.current_profile == "work"
    assert config.viewer["background_color"] == "#010203"
    assert config.get_runtime_override("profile.current_profile") == "work"


def test_initialize_profile_keeps_previous_when_missing(db_manager):
    """存在しないプロファイル名では、現在のプロファイルのままになる。"""
    previous = db_manager.current_profile
    config = Config()
    name = initialize_profile(db_manager, config, "missing")
    assert name == previous
    assert db_manager.current_profile == previous

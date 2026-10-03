"""対象: ez_co.main — load_config_from_db。"""
import pytest

from ez_co.config import Config
from ez_co.main import load_config_from_db

pytestmark = pytest.mark.usefixtures("qapp")


def test_load_config_from_db_reads_saved_profile(db_manager):
    """保存済みの背景色が DB から読み込まれる。"""
    payload = Config().to_dict()
    payload["viewer"]["background_color"] = "#445566"
    db_manager.save_profile_config(db_manager.current_profile, payload)
    config = load_config_from_db(db_manager)
    assert config.viewer["background_color"] == "#445566"


def test_load_config_from_db_creates_defaults_when_empty(db_manager):
    """空の保存からは既定の閾値が入り、その値が DB にも書かれる。"""
    db_manager.save_profile_config(db_manager.current_profile, {})
    config = load_config_from_db(db_manager)
    assert "gesture_threshold" in config.viewer
    stored = db_manager.load_profile_config(db_manager.current_profile)
    assert stored["viewer"]["gesture_threshold"] == config.viewer["gesture_threshold"]

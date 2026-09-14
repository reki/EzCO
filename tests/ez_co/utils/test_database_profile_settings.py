"""対象: ez_co.utils.database — プロファイル設定の保存と読み戻し。"""
import pytest

from ez_co.config import Config
from ez_co.utils.database import DatabaseManager

pytestmark = pytest.mark.usefixtures("qapp")


def test_profile_settings_roundtrip(db_manager):
    profile = db_manager.current_profile
    payload = Config().to_dict()
    payload["viewer"]["background_color"] = "#112233"
    payload["plugins"]["extension_handlers"] = {".png": "none"}
    assert db_manager.save_profile_config(profile, payload) is True
    loaded = db_manager.load_profile_config(profile)
    assert loaded["viewer"]["background_color"] == "#112233"
    assert loaded["plugins"]["extension_handlers"][".png"] == "none"


def test_empty_profile_settings_are_detected(db_manager):
    other = "work"
    assert db_manager.create_profile(other, settings={"viewer": {"background_color": "#abcabc"}}) is True
    assert db_manager.has_profile_settings(other) is True
    loaded = db_manager.load_profile_config(other)
    assert loaded["viewer"]["background_color"] == "#abcabc"


def test_new_database_file_is_created(db_manager):
    assert db_manager.db_path.is_file()
    second = DatabaseManager()
    assert second.db_path == db_manager.db_path
    assert second.current_profile == db_manager.current_profile

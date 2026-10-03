"""対象: ez_co.utils.database — 既定プロファイルと永続化。"""
import pytest

from ez_co.utils.database import DatabaseManager

pytestmark = pytest.mark.usefixtures("qapp")


def test_default_profile_cannot_be_deleted(db_manager):
    """保護された既定プロファイルは削除できず、一覧に残る。"""
    default = db_manager.get_default_protected_profile()
    assert db_manager.is_protected_profile(default) is True
    assert db_manager.delete_profile(default) is False
    assert default in db_manager.get_profiles()


def test_create_and_delete_extra_profile(db_manager):
    """追加プロファイルは作れて、同名の再作成は失敗し、削除すると一覧から消える。"""
    assert db_manager.create_profile("extra") is True
    assert db_manager.create_profile("extra") is False
    assert "extra" in db_manager.get_profiles()
    assert db_manager.delete_profile("extra") is True
    assert "extra" not in db_manager.get_profiles()


def test_current_profile_persists_in_new_manager(db_manager):
    """永続化した現在プロファイルは、開き直した管理オブジェクトでも同じ名前になる。"""
    assert db_manager.create_profile("other") is True
    db_manager.set_current_profile_persistent("other")
    reopened = DatabaseManager()
    assert reopened.current_profile == "other"
    assert reopened.get_persisted_current_profile() == "other"


def test_rename_profile_updates_app_state(db_manager):
    """現在プロファイルの改名は、メモリ上と開き直した永続値の両方に反映される。"""
    db_manager.create_profile("old")
    db_manager.set_current_profile_persistent("old")
    assert db_manager.rename_profile("old", "renamed") is True
    assert db_manager.current_profile == "renamed"
    reopened = DatabaseManager()
    assert reopened.get_persisted_current_profile() == "renamed"

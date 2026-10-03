"""対象: ez_co.utils.database — plugin_settings。"""
import sqlite3

import pytest

from ez_co.plugins.settings_key import hash_plugin_id

pytestmark = pytest.mark.usefixtures("qapp")


def test_plugin_setting_roundtrip(db_manager):
    """プラグイン設定は保存した真偽値を読め、削除後は既定値に戻る。"""
    assert db_manager.set_plugin_setting("com.example.x", "enabled", True) is True
    assert db_manager.get_plugin_setting("com.example.x", "enabled") is True
    assert db_manager.delete_plugin_setting("com.example.x", "enabled") is True
    assert db_manager.get_plugin_setting("com.example.x", "enabled", default=False) is False


def test_plugin_setting_stores_hashed_key(db_manager):
    """保存行のプラグインキーは ID のハッシュで、値は JSON 文字列になる。"""
    db_manager.set_plugin_setting("com.example.x", "color", "#ff00aa")
    with sqlite3.connect(db_manager.db_path) as conn:
        rows = conn.execute("SELECT plugin_key, key, value FROM plugin_settings").fetchall()
    assert rows == [(hash_plugin_id("com.example.x"), "color", '"#ff00aa"')]


def test_copy_plugin_settings_to_new_profile(db_manager):
    """新しいプロファイルへ切り替えても、作成前のプラグイン設定が読める。"""
    db_manager.set_plugin_setting("com.example.x", "n", 3)
    assert db_manager.create_profile("copy") is True
    db_manager.set_current_profile("copy")
    assert db_manager.get_plugin_setting("com.example.x", "n") == 3

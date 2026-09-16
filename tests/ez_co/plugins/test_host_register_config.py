"""対象: ez_co.plugins.host — register_config の範囲・path・sync・reload と password の保存。"""
import pytest

from ez_co.plugins.host import (
    ConfigField,
    PluginHost,
    config_field_syncs,
    config_should_reload,
)


class _MemoryDb:
    def __init__(self):
        self.rows = {}

    def get_plugin_setting(self, plugin_id, key, default=None):
        return self.rows.get((plugin_id, key), default)

    def set_plugin_setting(self, plugin_id, key, value):
        self.rows[(plugin_id, key)] = value
        return True


def test_register_config_keeps_range_bounds_and_sync():
    host = PluginHost()
    host.scoped("com.example.x").register_config(
        "strength",
        "integer_range",
        default=50,
        minimum=0,
        maximum=100,
        step=5,
        sync=True,
        reload=True,
    )
    field = host.configs_for("com.example.x")[0]
    assert field.value_type == "int_range"
    assert field.minimum == 0
    assert field.maximum == 100
    assert field.step == 5
    assert field.sync is True
    assert field.reload is True
    assert config_field_syncs(field) is True
    assert config_should_reload([field]) is True


def test_register_config_rejects_invalid_range_schema():
    host = PluginHost()
    scoped = host.scoped("com.example.x")
    with pytest.raises(ValueError, match="com.example.x"):
        scoped.register_config("n", "int_range", default=1, maximum=10, step=1)
    with pytest.raises(ValueError, match="com.example.x"):
        scoped.register_config("n", "int_range", default=1, minimum=10, maximum=0, step=1)
    with pytest.raises(ValueError, match="com.example.x"):
        scoped.register_config("n", "int_range", default=1, minimum=0, maximum=10, step=0)
    with pytest.raises(ValueError, match="com.example.x"):
        scoped.register_config("n", "float_range", default=1, minimum=0, maximum=1, step="x")
    assert host.configs_for("com.example.x") == []


def test_config_should_reload_requires_sync_and_reload():
    sync_only = ConfigField(key="a", value_type="int_range", sync=True, reload=False)
    both = ConfigField(key="b", value_type="int_range", sync=True, reload=True)
    reload_only = ConfigField(key="c", value_type="int_range", sync=False, reload=True)
    assert config_should_reload([sync_only]) is False
    assert config_should_reload([sync_only, both]) is True
    assert config_should_reload([reload_only]) is False


def test_get_config_clamps_int_range():
    host = PluginHost()
    host._db = _MemoryDb()
    scoped = host.scoped("com.example.x")
    scoped.register_config("n", "int_range", default=50, minimum=0, maximum=10, step=1)
    host._db.rows[("com.example.x", "n")] = 99
    assert scoped.get_config("n") == 10


def test_register_config_path_kind_and_ignored_sync():
    host = PluginHost()
    host.scoped("com.example.x").register_config(
        "output",
        "path",
        default="",
        path_kind="folder",
        path_filter="Images (*.png)",
        sync=True,
        reload=True,
    )
    field = host.configs_for("com.example.x")[0]
    assert field.value_type == "path"
    assert field.path_kind == "directory"
    assert field.path_filter == "Images (*.png)"
    assert field.sync is True
    assert field.reload is True
    assert config_field_syncs(field) is False
    assert config_should_reload([field]) is False


def test_password_roundtrip_uses_protect_helpers(monkeypatch):
    monkeypatch.setattr(
        "ez_co.utils.password_protect.encrypt_secret",
        lambda text: "enc:" + text,
    )
    monkeypatch.setattr(
        "ez_co.utils.password_protect.decrypt_secret",
        lambda token: token[4:] if str(token).startswith("enc:") else None,
    )
    host = PluginHost()
    host._db = _MemoryDb()
    scoped = host.scoped("com.example.x")
    scoped.register_config("secret", "password", default="")
    assert scoped.set_config("secret", "hunter2") is True
    assert host._db.rows[("com.example.x", "secret")] == "enc:hunter2"
    assert scoped.get_config("secret") == "hunter2"


def test_password_decrypt_failure_returns_default(monkeypatch):
    monkeypatch.setattr(
        "ez_co.utils.password_protect.encrypt_secret",
        lambda text: "enc:" + text,
    )
    monkeypatch.setattr(
        "ez_co.utils.password_protect.decrypt_secret",
        lambda _token: None,
    )
    host = PluginHost()
    host._db = _MemoryDb()
    scoped = host.scoped("com.example.x")
    scoped.register_config("secret", "password", default="fallback")
    host._db.rows[("com.example.x", "secret")] = "broken"
    assert scoped.get_config("secret") == "fallback"

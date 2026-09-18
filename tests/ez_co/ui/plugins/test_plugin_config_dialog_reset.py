"""対象: ez_co.ui.plugins.plugin_config_dialog — override削除としてのReset。"""
import pytest

from ez_co.plugins.host import PluginHost
from ez_co.ui.plugins.plugin_config_dialog import PluginConfigDialog

pytestmark = pytest.mark.usefixtures("qapp")


class _MemoryDb:
    def __init__(self):
        self.rows = {}

    def get_plugin_setting(self, plugin_id, key, default=None):
        return self.rows.get((plugin_id, key), default)

    def set_plugin_setting(self, plugin_id, key, value):
        self.rows[(plugin_id, key)] = value
        return True

    def delete_plugin_setting(self, plugin_id, key):
        self.rows.pop((plugin_id, key), None)
        return True


def _dialog(**fields):
    host = PluginHost()
    host._db = _MemoryDb()
    host.enter_phase("com.example.x", "load")
    scoped = host.scoped("com.example.x")
    for key, spec in fields.items():
        scoped.register_config(key, **spec)
    return host, scoped, PluginConfigDialog(host, "com.example.x")


def test_apply_reset_allows_empty_required_default():
    _host, scoped, dialog = _dialog(
        need={"value_type": "string", "default": "", "required": True},
    )
    scoped.set_config("need", "kept")
    dialog._widgets["need"].setText("kept")
    dialog._reset_to_defaults()
    assert dialog._apply_button.isEnabled()
    assert dialog._save()
    assert scoped.get_config("need") == ""


def test_cancel_restores_sync_preview_after_reset():
    _host, scoped, dialog = _dialog(
        level={"value_type": "int", "default": 0, "sync": True},
    )
    scoped.set_config("level", 7)
    dialog._widgets["level"].setValue(7)
    dialog._capture_snapshot()
    dialog._reset_to_defaults()
    assert scoped.get_config("level") == 0
    dialog._restore_preview()
    assert scoped.get_config("level") == 7

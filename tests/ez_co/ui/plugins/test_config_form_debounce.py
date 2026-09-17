"""対象: ez_co.ui.plugins.config_form — 数値は debounce、非数値は即時保存。"""
from __future__ import annotations

import pytest

from ez_co.plugins.host import PluginHost
from ez_co.ui.plugins.config_form import PluginConfigForm
from ez_co.ui.plugins.config_widgets import SYNC_RELOAD_IDLE_MS

pytestmark = pytest.mark.usefixtures("qapp")


class _MemoryDb:
    def __init__(self):
        self.rows = {}

    def get_plugin_setting(self, plugin_id, key, default=None):
        return self.rows.get((plugin_id, key), default)

    def set_plugin_setting(self, plugin_id, key, value):
        self.rows[(plugin_id, key)] = value
        return True


def _form():
    host = PluginHost()
    host.bind(parent=None, db_manager=_MemoryDb())
    host.set_manifest_provides("com.example.x", sidebar=True)
    host.enter_phase("com.example.x", "setup")
    scoped = host.scoped("com.example.x")
    scoped.register_config("flag", "bool", True)
    scoped.register_config("count", "int", 1)
    return host, scoped, PluginConfigForm(host, "com.example.x")


def test_bool_writes_immediately():
    _host, scoped, form = _form()
    form._widgets["flag"].setChecked(False)
    assert scoped.get_config("flag") is False


def test_int_waits_for_idle(qtbot):
    _host, scoped, form = _form()
    form._widgets["count"].setValue(9)
    assert scoped.get_config("count") == 1
    qtbot.wait(SYNC_RELOAD_IDLE_MS + 50)
    assert scoped.get_config("count") == 9

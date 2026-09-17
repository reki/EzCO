"""対象: ez_co.plugins.host — required_setting_sidebar / register_config_sidebar。"""
from __future__ import annotations

import inspect

import pytest

from ez_co.plugins.host import PluginHost, PluginRegistrationDenied
from ez_co.ui.plugins.config_form import PluginConfigForm
from ez_co.utils.language_manager import get_text

pytestmark = pytest.mark.usefixtures("qapp")


class _MemoryDb:
    def __init__(self):
        self.rows = {}

    def get_plugin_setting(self, plugin_id, key, default=None):
        return self.rows.get((plugin_id, key), default)

    def set_plugin_setting(self, plugin_id, key, value):
        self.rows[(plugin_id, key)] = value
        return True


def _host(reloads=None):
    host = PluginHost()
    kwargs = {"parent": None, "db_manager": _MemoryDb()}
    if reloads is not None:
        kwargs["reload_current"] = lambda page: reloads.append(page) or True
    host.bind(**kwargs)
    host.set_manifest_provides("com.example.x", sidebar=True)
    host.enter_phase("com.example.x", "setup")
    return host, host.scoped("com.example.x")


def test_register_config_sidebar_accepts_declared_flag():
    host, scoped = _host()
    scoped.register_config("flag", "bool", True)
    scoped.register_config_sidebar("main", "{title}")
    rows = host.sidebars_for("com.example.x")
    assert len(rows) == 1
    assert rows[0].sidebar_id == "main"
    assert rows[0].title == "{title}"
    assert isinstance(rows[0].widget, PluginConfigForm)


def test_register_config_sidebar_requires_manifest_flag():
    host = PluginHost()
    host.enter_phase("com.example.ui", "setup")
    scoped = host.scoped("com.example.ui")
    scoped.register_config("flag", "bool", True)
    with pytest.raises(PluginRegistrationDenied, match=get_text("ui.plugin_register_not_permitted")):
        scoped.register_config_sidebar("main", "Title")


def test_required_setting_sidebar_rejects_empty_schema():
    _host_obj, scoped = _host()
    with pytest.raises(ValueError, match="com.example.x"):
        scoped.required_setting_sidebar()


def test_required_setting_sidebar_returns_form():
    _host_obj, scoped = _host()
    scoped.register_config("flag", "bool", True)
    widget = scoped.required_setting_sidebar()
    assert isinstance(widget, PluginConfigForm)


def test_register_config_sidebar_writes_bool_immediately():
    host, scoped = _host()
    scoped.register_config("flag", "bool", True)
    scoped.register_config_sidebar("main", "Title")
    form = host.sidebars_for("com.example.x")[0].widget
    form._widgets["flag"].setChecked(False)
    assert scoped.get_config("flag") is False


def test_register_config_sidebar_reloads_only_when_field_reload():
    reloads = []
    host, scoped = _host(reloads)
    scoped.register_config("flag", "bool", True)
    scoped.register_config("keep", "bool", True, reload=True)
    scoped.register_config_sidebar("main", "Title")
    form = host.sidebars_for("com.example.x")[0].widget
    form._widgets["flag"].setChecked(False)
    assert reloads == []
    form._widgets["keep"].setChecked(False)
    assert reloads == [None]


def test_register_config_sidebar_signature_keeps_aliases():
    host = PluginHost()
    params = inspect.signature(host.scoped("com.example.x").register_config_sidebar).parameters
    assert list(params) == ["sidebar_id", "title", "aliases"]

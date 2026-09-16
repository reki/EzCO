"""対象: ez_co.plugins.host — current_changed の非表示ゲート。"""
from __future__ import annotations

import inspect

from ez_co.plugins.host import PluginHost, SidebarRegistration


def _listen(host: PluginHost, plugin_id: str, event: str = "current_changed"):
    got = []
    host.scoped(plugin_id).on(event, lambda payload: got.append((plugin_id, payload)))
    return got


def _add_sidebar(host: PluginHost, plugin_id: str, sidebar_id: str = "main") -> None:
    host._sidebars[(plugin_id, sidebar_id)] = SidebarRegistration(plugin_id, sidebar_id, "t", None)


def test_current_changed_reaches_plugin_without_sidebar():
    host = PluginHost()
    got = _listen(host, "loader.plugin")
    host.emit("current_changed", {"page": 1})
    assert got == [("loader.plugin", {"page": 1})]


def test_hidden_sidebar_skips_current_changed():
    host = PluginHost()
    _add_sidebar(host, "ui.plugin")
    host.bind(parent=None, sidebar_visible=lambda pid: False)
    got = _listen(host, "ui.plugin")
    host.emit("current_changed", {"page": 1})
    assert got == []


def test_visible_sidebar_gets_current_changed():
    host = PluginHost()
    _add_sidebar(host, "ui.plugin")
    host.bind(parent=None, sidebar_visible=lambda pid: pid == "ui.plugin")
    got = _listen(host, "ui.plugin")
    host.emit("current_changed", {"page": 2})
    assert got == [("ui.plugin", {"page": 2})]


def test_inactive_callback_permission_reaches_hidden_sidebar():
    host = PluginHost()
    _add_sidebar(host, "ui.plugin")
    host.bind(parent=None, sidebar_visible=lambda pid: False)
    host.set_manifest_permissions("ui.plugin", {"inactive_callback": True})
    got = _listen(host, "ui.plugin")
    host.emit("current_changed", {"page": 3})
    assert got == [("ui.plugin", {"page": 3})]


def test_runtime_cannot_grant_inactive_callback():
    host = PluginHost()
    _add_sidebar(host, "ui.plugin")
    host.bind(parent=None, sidebar_visible=lambda pid: False)
    host.set_manifest_permissions("ui.plugin", {})
    scoped = host.scoped("ui.plugin")
    assert not hasattr(scoped, "set_manifest_permissions")
    params = inspect.signature(scoped.register_sidebar).parameters
    assert "permissions" not in params
    assert "capabilities" not in params
    got = _listen(host, "ui.plugin")
    host.emit("current_changed", {"page": 4})
    assert got == []


def test_config_changed_is_not_gated():
    host = PluginHost()
    _add_sidebar(host, "ui.plugin")
    host.bind(parent=None, sidebar_visible=lambda pid: False)
    got = _listen(host, "ui.plugin", "config_changed")
    host.emit("config_changed", {"key": "fetch_web"})
    assert got == [("ui.plugin", {"key": "fetch_web"})]


def test_format_plugin_with_hidden_sidebar_is_gated():
    host = PluginHost()
    host.scoped("hybrid.plugin").register_format(".txt", "archive")
    _add_sidebar(host, "hybrid.plugin")
    host.bind(parent=None, sidebar_visible=lambda pid: False)
    got = _listen(host, "hybrid.plugin")
    host.emit("current_changed", {"page": 5})
    assert got == []

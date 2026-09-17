"""対象: ez_co.plugins.host — clear_plugin は off / unregister なしで台帳と listener を外す。"""
from __future__ import annotations

from ez_co.plugins.host import PluginHost, make_plugin_action_id, make_sidebar_action_id


def test_clear_plugin_drops_listeners_sidebars_actions_without_off():
    host = PluginHost()
    host.set_manifest_provides("com.example.x", sidebar=True)
    scoped = host.scoped("com.example.x")
    got = []
    scoped.on("config_changed", lambda payload: got.append(payload))
    scoped.register_sidebar("main", "Title", object())
    scoped.register_action("reload", "Reload", lambda: None)
    assert host.sidebars_for("com.example.x")
    assert host.resolve_action(make_plugin_action_id("com.example.x", "reload")) is not None
    host.emit("config_changed", {"key": "a"})
    assert got == [{"key": "a"}]

    host.clear_plugin("com.example.x")

    assert not host.sidebars_for("com.example.x")
    assert host.resolve_action(make_plugin_action_id("com.example.x", "reload")) is None
    assert host.resolve_action(make_sidebar_action_id("com.example.x", "main")) is None
    got.clear()
    host.emit("config_changed", {"key": "b"})
    assert got == []


def test_clear_plugin_keeps_other_plugin_listeners():
    host = PluginHost()
    kept = []
    host.scoped("com.example.keep").on("config_changed", lambda payload: kept.append(payload))
    host.scoped("com.example.drop").on("config_changed", lambda payload: None)
    host.clear_plugin("com.example.drop")
    host.emit("config_changed", {"key": "left"})
    assert kept == [{"key": "left"}]

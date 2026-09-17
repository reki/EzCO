"""対象: ez_co.plugins.host — register の phase 検査と load 失敗の巻き戻し。"""
from __future__ import annotations

import pytest

from ez_co.plugins.host import PluginHost, PluginRegistrationDenied
from ez_co.utils.language_manager import get_text


def _denied(host: PluginHost, plugin_id: str, action):
    with pytest.raises(PluginRegistrationDenied, match=get_text("ui.plugin_register_wrong_phase")):
        action()


def test_init_rejects_every_register():
    host = PluginHost()
    host.set_manifest_provides("com.example.x", sidebar=True)
    host.set_manifest_permissions("com.example.x", {"filter": True})
    host.enter_phase("com.example.x", "init")
    scoped = host.scoped("com.example.x")
    _denied(host, "com.example.x", lambda: scoped.register_config("flag", "bool", True))
    _denied(host, "com.example.x", lambda: scoped.register_sidebar("main", "Title", object()))
    _denied(host, "com.example.x", lambda: scoped.register_action("reload", "Reload", lambda: None))
    _denied(host, "com.example.x", lambda: scoped.register_filter("sharp", "Sharp", lambda image, context: image))
    _denied(host, "com.example.x", lambda: scoped.on("config_changed", lambda payload: None))


def test_load_allows_config_rejects_ui_register():
    host = PluginHost()
    host.set_manifest_provides("com.example.x", sidebar=True)
    host.set_manifest_permissions("com.example.x", {"filter": True})
    host.enter_phase("com.example.x", "load")
    scoped = host.scoped("com.example.x")
    scoped.register_config("flag", "bool", True)
    assert [field.key for field in host.configs_for("com.example.x")] == ["flag"]
    _denied(host, "com.example.x", lambda: scoped.register_sidebar("main", "Title", object()))
    _denied(host, "com.example.x", lambda: scoped.register_action("reload", "Reload", lambda: None))
    _denied(host, "com.example.x", lambda: scoped.register_filter("sharp", "Sharp", lambda image, context: image))
    _denied(host, "com.example.x", lambda: scoped.on("config_changed", lambda payload: None))


def test_setup_allows_config_and_ui_register():
    host = PluginHost()
    host.set_manifest_provides("com.example.x", sidebar=True)
    host.set_manifest_permissions("com.example.x", {"filter": True})
    host.enter_phase("com.example.x", "setup")
    scoped = host.scoped("com.example.x")
    scoped.register_config("flag", "bool", True)
    scoped.register_sidebar("main", "Title", object())
    scoped.register_action("reload", "Reload", lambda: None)
    scoped.register_filter("sharp", "Sharp", lambda image, context: image)
    scoped.on("config_changed", lambda payload: None)
    assert host.sidebars_for("com.example.x")
    assert host.configs_for("com.example.x")


def test_abort_load_drops_own_schema_keeps_other_plugin():
    host = PluginHost()
    host.enter_phase("com.example.keep", "load")
    host.scoped("com.example.keep").register_config("keep", "bool", True)
    host.enter_phase("com.example.keep", "idle")
    host.enter_phase("com.example.drop", "load")
    host.scoped("com.example.drop").register_config("flag", "bool", True)
    host.abort_load("com.example.drop")
    assert host.configs_for("com.example.drop") == []
    assert [field.key for field in host.configs_for("com.example.keep")] == ["keep"]
    assert host.phase_of("com.example.drop") == "idle"

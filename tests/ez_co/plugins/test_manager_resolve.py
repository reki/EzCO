"""対象: ez_co.plugins.manager — 拡張子優先。"""
from __future__ import annotations

from types import SimpleNamespace

from ez_co.plugins.api import BUILTIN_PROVIDER_ID, SKIP_PROVIDER_ID
from ez_co.plugins.manager import PluginManager


def _config(handlers=None):
    return SimpleNamespace(
        plugins={
            "source_choice": {},
            "extension_handlers": dict(handlers or {}),
            "enabled": {},
        },
        archive={"enabled": True},
    )


def test_resolve_builtin_extension_prefers_builtin(tmp_path, dir_plugin):
    dir_plugin(tmp_path, plugin_id="com.example.png", extension=".png", folder_name="png")
    manager = PluginManager()
    manager.discover(tmp_path)
    manager.load_selected(_config())
    decision = manager.resolve("photo.png", _config())
    assert decision.provider_id == BUILTIN_PROVIDER_ID
    assert decision.plugin is None


def test_resolve_plugin_only_extension_uses_plugin(tmp_path, dir_plugin):
    dir_plugin(tmp_path, plugin_id="com.example.probe", extension=".probe", folder_name="probe")
    manager = PluginManager()
    manager.discover(tmp_path)
    manager.load_selected(_config())
    decision = manager.resolve("page.probe", _config())
    assert decision.is_plugin
    assert decision.plugin.plugin_id == "com.example.probe"


def test_resolve_skip_provider(tmp_path, dir_plugin):
    dir_plugin(tmp_path, plugin_id="com.example.probe", extension=".probe", folder_name="probe")
    manager = PluginManager()
    manager.discover(tmp_path)
    config = _config({".probe": SKIP_PROVIDER_ID})
    manager.load_selected(config)
    decision = manager.resolve("page.probe", config)
    assert decision.is_skipped
    assert decision.plugin is None

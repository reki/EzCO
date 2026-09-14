"""対象: ez_co.plugins.manager — 同じ id、unresolved_groups、record_choices。"""
from __future__ import annotations

from types import SimpleNamespace

from ez_co.plugins.manager import PluginManager


def _config():
    return SimpleNamespace(
        plugins={"source_choice": {}, "extension_handlers": {}, "enabled": {}}
    )


def test_same_id_is_unresolved_until_choice(tmp_path, dir_plugin):
    dir_plugin(tmp_path, plugin_id="com.example.dup", folder_name="one")
    dir_plugin(tmp_path, plugin_id="com.example.dup", folder_name="two", version="2.0.0")
    manager = PluginManager()
    manager.discover(tmp_path)
    config = _config()
    groups = manager.unresolved_groups(config)
    assert "com.example.dup" in groups
    assert len(groups["com.example.dup"]) == 2


def test_record_choices_clears_unresolved(tmp_path, dir_plugin):
    dir_plugin(tmp_path, plugin_id="com.example.dup", folder_name="one")
    dir_plugin(tmp_path, plugin_id="com.example.dup", folder_name="two", version="2.0.0")
    manager = PluginManager()
    manager.discover(tmp_path)
    config = _config()
    manager.record_choices({"com.example.dup": "one"}, config)
    assert manager.unresolved_groups(config) == {}
    stored = config.plugins["source_choice"]["com.example.dup"]
    assert stored["source"] == "one"
    assert set(stored["seen"]) == {"one", "two"}

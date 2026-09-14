"""対象: ez_co.plugins.manager — 1 id 1本。setup() を二重に走らせない。"""
from __future__ import annotations

from types import SimpleNamespace

from ez_co.plugins.manager import PluginManager


def _config():
    return SimpleNamespace(
        plugins={"source_choice": {}, "extension_handlers": {}, "enabled": {}}
    )


def test_load_selected_loads_one_plugin_per_id(tmp_path, dir_plugin):
    dir_plugin(tmp_path, plugin_id="com.example.one", folder_name="solo")
    manager = PluginManager()
    manager.discover(tmp_path)
    manager.load_selected(_config())
    assert len(manager.plugins) == 1
    assert manager.plugins[0].plugin_id == "com.example.one"
    manager.load_selected(_config())
    assert len(manager.plugins) == 1


def test_load_selected_skips_unresolved_duplicates(tmp_path, dir_plugin):
    dir_plugin(tmp_path, plugin_id="com.example.dup", folder_name="one")
    dir_plugin(tmp_path, plugin_id="com.example.dup", folder_name="two", version="2.0.0")
    manager = PluginManager()
    manager.discover(tmp_path)
    manager.load_selected(_config())
    assert manager.plugins == []
    assert len(manager.skipped) == 2


def test_activate_ui_does_not_run_setup_twice(tmp_path, dir_plugin):
    counter = tmp_path / "setup_count.txt"
    dir_plugin(tmp_path, plugin_id="com.example.setup", folder_name="setup", setup_counter=counter)
    manager = PluginManager()
    manager.discover(tmp_path)
    manager.load_selected(_config())
    manager.activate_ui()
    manager.load_selected(_config())
    manager.activate_ui()
    assert counter.read_text(encoding="utf-8") == "1"

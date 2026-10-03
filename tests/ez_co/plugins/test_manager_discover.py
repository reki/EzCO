"""対象: ez_co.plugins.manager — 候補だけ・未ロード。"""
from __future__ import annotations

from ez_co.plugins.manager import PluginManager


def test_discover_lists_candidates_without_loading(tmp_path, dir_plugin):
    """候補の id が揃わず、discover の時点で plugins が載るか _loaded が真になる。"""
    dir_plugin(tmp_path, plugin_id="com.example.a", folder_name="alpha")
    dir_plugin(tmp_path, plugin_id="com.example.b", folder_name="beta")
    manager = PluginManager()
    manager.discover(tmp_path)
    assert {item.plugin_id for item in manager.candidates} == {"com.example.a", "com.example.b"}
    assert manager.plugins == []
    assert manager._loaded is False


def test_discover_missing_directory_is_empty(tmp_path):
    """無いディレクトリで候補や plugins が残り、_discovered が真にならない。"""
    manager = PluginManager()
    manager.discover(tmp_path / "missing")
    assert manager.candidates == []
    assert manager.plugins == []
    assert manager._discovered is True

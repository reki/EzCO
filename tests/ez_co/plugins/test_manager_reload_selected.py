"""対象: ez_co.plugins.manager — reload_selected。"""
from __future__ import annotations

from types import SimpleNamespace

from ez_co.plugins.manager import PluginManager


def _config():
    """選択もハンドラも空のプラグイン設定を返す。

    Returns:
        plugins だけを持つ設定オブジェクト。
    """
    return SimpleNamespace(
        plugins={"source_choice": {}, "extension_handlers": {}, "enabled": {}}
    )


def test_reload_selected_rediscovers_and_loads(tmp_path, dir_plugin):
    """追加したプラグインが載らず、同じ id のインスタンスが作り直されない。"""
    dir_plugin(tmp_path, plugin_id="com.example.first", folder_name="first")
    manager = PluginManager()
    manager.discover(tmp_path)
    manager.load_selected(_config())
    first = manager.plugins[0].instance
    dir_plugin(tmp_path, plugin_id="com.example.second", folder_name="second")
    manager.reload_selected(_config(), directory=tmp_path)
    ids = {plugin.plugin_id for plugin in manager.plugins}
    assert ids == {"com.example.first", "com.example.second"}
    reloaded = next(plugin.instance for plugin in manager.plugins if plugin.plugin_id == "com.example.first")
    assert reloaded is not first


def test_reload_selected_runs_setup_again(tmp_path, dir_plugin):
    """reload のあとの activate で setup がもう一度走らない。"""
    counter = tmp_path / "setup_count.txt"
    dir_plugin(tmp_path, plugin_id="com.example.setup", folder_name="setup", setup_counter=counter)
    manager = PluginManager()
    manager.reload_selected(_config(), directory=tmp_path)
    manager.activate_ui()
    assert counter.read_text(encoding="utf-8") == "1"
    manager.reload_selected(_config(), directory=tmp_path)
    manager.activate_ui()
    assert counter.read_text(encoding="utf-8") == "2"

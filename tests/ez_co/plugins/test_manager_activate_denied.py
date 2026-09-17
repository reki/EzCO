"""対象: ez_co.plugins.manager — 未許可の register_* は読み込み不可。"""
from __future__ import annotations

from types import SimpleNamespace

from ez_co.plugins.manager import PluginManager
from ez_co.utils.language_manager import get_text


def _config():
    return SimpleNamespace(
        plugins={"source_choice": {}, "extension_handlers": {}, "enabled": {}}
    )


def _write_setup(root, body: str) -> None:
    (root / "src" / "plugin.py").write_text(
        "class ProbePlugin:\n"
        "    def __init__(self):\n"
        "        self.host = None\n"
        "    def load(self, root, get_text, host):\n"
        "        self.host = host\n"
        "    def setup(self):\n"
        f"{body}",
        encoding="utf-8",
    )


def test_load_selected_denies_register_in_init(tmp_path, dir_plugin):
    root = dir_plugin(tmp_path, plugin_id="com.example.ui", folder_name="ui")
    (root / "src" / "plugin.py").write_text(
        "class ProbePlugin:\n"
        "    def __init__(self):\n"
        '        host.register_sidebar("main", "Title", object())\n'
        "    def load(self, root, get_text, host):\n"
        "        self.host = host\n",
        encoding="utf-8",
    )
    manager = PluginManager()
    manager.discover(tmp_path)
    manager.load_selected(_config())
    assert manager.plugins == []
    assert len(manager.failed) == 1
    assert manager.failed[0][1] == get_text("ui.plugin_register_wrong_phase")


def test_activate_ui_denies_undeclared_sidebar(tmp_path, dir_plugin):
    root = dir_plugin(tmp_path, plugin_id="com.example.ui", folder_name="ui")
    _write_setup(root, '        self.host.register_sidebar("main", "Title", object())\n')
    manager = PluginManager()
    manager.discover(tmp_path)
    manager.load_selected(_config())
    manager.activate_ui()
    plugin = manager.plugins[0]
    assert plugin.error == get_text("ui.plugin_register_not_permitted")
    assert manager.enabled_plugins(_config()) == []
    assert not manager.host.sidebars_for(plugin.plugin_id)


def test_activate_ui_denies_filter_without_permission(tmp_path, dir_plugin):
    root = dir_plugin(tmp_path, plugin_id="com.example.filter", folder_name="filter")
    _write_setup(
        root,
        "        def _process(image, context):\n"
        "            return image\n"
        '        self.host.register_filter("sharp", "Sharp", _process)\n',
    )
    manager = PluginManager()
    manager.discover(tmp_path)
    manager.load_selected(_config())
    manager.activate_ui()
    plugin = manager.plugins[0]
    assert plugin.error == get_text("ui.plugin_register_not_permitted")
    assert manager.enabled_plugins(_config()) == []

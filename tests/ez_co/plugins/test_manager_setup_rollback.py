"""対象: ez_co.plugins.manager — setup 途中の例外は UI 台帳を戻しスキーマは残す。"""
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


def test_setup_exception_after_sidebar_clears_ui_keeps_schema(tmp_path, dir_plugin):
    """setup の例外のあとエラーが残らず、ui が有効のまま、サイドバーが残るか、load で登録した schema が消える。"""
    root = dir_plugin(
        tmp_path,
        plugin_id="com.example.roll",
        folder_name="roll",
        manifest_extra={"sidebar": True},
    )
    (root / "src" / "plugin.py").write_text(
        "class ProbePlugin:\n"
        "    def __init__(self):\n"
        "        self.host = None\n"
        "    def load(self, root, get_text, host):\n"
        "        self.host = host\n"
        '        host.register_config("flag", "bool", True)\n'
        "    def setup(self):\n"
        '        self.host.register_sidebar("main", "Title", object())\n'
        '        raise RuntimeError("boom")\n',
        encoding="utf-8",
    )
    manager = PluginManager()
    manager.discover(tmp_path)
    manager.load_selected(_config())
    manager.activate_ui()
    plugin = manager.plugins[0]
    assert plugin.error == "boom"
    assert plugin.ui_active is False
    assert not manager.host.sidebars_for(plugin.plugin_id)
    assert [field.key for field in manager.host.configs_for(plugin.plugin_id)] == ["flag"]

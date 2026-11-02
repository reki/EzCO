"""対象: ez_co.ui.plugins.plugin_dialog — 行クリックで設定。"""
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QTableWidget

from ez_co.ui.plugins.plugin_dialog import PLUGIN_COLUMNS, PluginDialog

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


def _dialog(plugins, fields_for):
    """表と、開いたプラグイン ID の記録だけを持つダイアログを返す。

    Args:
        plugins: 読み込み済みの行。
        fields_for: プラグイン ID から設定項目への対応。

    Returns:
        クリックを受けられるダイアログ。
    """
    dialog = PluginDialog.__new__(PluginDialog)
    dialog.plugin_manager = SimpleNamespace(
        plugins=plugins,
        skipped=[],
        failed=[],
        host=SimpleNamespace(configs_for=lambda plugin_id: fields_for.get(plugin_id, [])),
    )
    dialog._enabled = {}
    dialog.plugin_table = QTableWidget(0, len(PLUGIN_COLUMNS))
    dialog._set_action_cells = lambda index, plugin: None
    opened = []
    dialog._open_plugin_config = lambda plugin: opened.append(plugin.plugin_id)
    dialog.opened = opened
    return dialog



def _plugin(plugin_id, error=None):
    """設定の有無を見るためのプラグイン行を返す。

    Args:
        plugin_id: プラグイン ID。
        error: 読み込み失敗の文。成功なら None。

    Returns:
        表に置くプラグイン。
    """
    return SimpleNamespace(
        plugin_id=plugin_id,
        name=plugin_id,
        formats=[],
        has_sidebar=False,
        error=error,
        manifest=SimpleNamespace(version="1.0.0", description=""),
    )



def test_name_click_opens_settings_when_fields_exist():
    """設定項目がある行の名前をクリックしても設定が開かない。"""
    plugin = _plugin("com.example.settings")
    dialog = _dialog([plugin], {"com.example.settings": [object()]})
    dialog._fill_plugin_table()
    dialog._on_plugin_cell_clicked(0, PLUGIN_COLUMNS.index("name"))
    assert dialog.opened == ["com.example.settings"]



def test_license_and_enabled_columns_do_not_open_settings():
    """ライセンス列や有効列のクリックで設定が開く。"""
    plugin = _plugin("com.example.settings")
    dialog = _dialog([plugin], {"com.example.settings": [object()]})
    dialog._fill_plugin_table()
    dialog._on_plugin_cell_clicked(0, PLUGIN_COLUMNS.index("license"))
    dialog._on_plugin_cell_clicked(0, PLUGIN_COLUMNS.index("enabled"))
    assert dialog.opened == []



def test_row_without_fields_does_not_open_settings():
    """設定項目が無い行のクリックで設定が開く。"""
    plugin = _plugin("com.example.plain")
    dialog = _dialog([plugin], {})
    dialog._fill_plugin_table()
    dialog._on_plugin_cell_clicked(0, PLUGIN_COLUMNS.index("name"))
    assert dialog.opened == []



def test_failed_plugin_row_does_not_open_settings():
    """読み込み失敗の行をクリックすると設定が開く。"""
    plugin = _plugin("com.example.broken", error="broken")
    dialog = _dialog([plugin], {"com.example.broken": [object()]})
    dialog._fill_plugin_table()
    dialog._on_plugin_cell_clicked(0, PLUGIN_COLUMNS.index("id"))
    assert dialog.opened == []

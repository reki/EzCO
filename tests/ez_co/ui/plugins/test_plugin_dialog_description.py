"""対象: ez_co.ui.plugins.plugin_dialog — 説明列。"""
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QTableWidget

from ez_co.plugins.manager import SkippedPlugin
from ez_co.ui.plugins.plugin_dialog import (
    PLUGIN_COLUMNS,
    PLUGIN_DEFAULT_WIDTHS,
    PLUGIN_HEADER_KEYS,
    PluginDialog,
)
from ez_co.utils.language_manager import get_text

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


def _table_dialog(plugins, skipped, failed):
    """プラグインマネージャを使わず、表だけ埋めるダイアログを返す。

    Args:
        plugins: 読み込み済みの行。
        skipped: 読み飛ばした行。
        failed: 失敗した行。

    Returns:
        表を埋める直前のダイアログ。
    """
    dialog = PluginDialog.__new__(PluginDialog)
    dialog.plugin_manager = SimpleNamespace(plugins=plugins, skipped=skipped, failed=failed)
    dialog._enabled = {}
    dialog.plugin_table = QTableWidget(0, len(PLUGIN_COLUMNS))
    dialog._set_action_cells = lambda index, plugin: None
    return dialog


def _cell(dialog, row, key):
    """指定列のセルを返す。

    Args:
        dialog: 表を持つダイアログ。
        row: 行番号。
        key: 列のキー。

    Returns:
        そのセル。
    """
    return dialog.plugin_table.item(row, PLUGIN_COLUMNS.index(key))


def _visual_keys(table):
    """見えている列順のキーを返す。

    Args:
        table: プラグイン一覧。

    Returns:
        左から見た列キー。
    """
    header = table.horizontalHeader()
    return [PLUGIN_COLUMNS[header.logicalIndex(index)] for index in range(header.count())]


def test_description_column_follows_version():
    """説明列がバージョンの直後に無い。"""
    version_at = PLUGIN_COLUMNS.index("version")
    assert PLUGIN_COLUMNS[version_at + 1] == "description"
    assert "description" in PLUGIN_DEFAULT_WIDTHS


def test_description_header_key_follows_version():
    """説明の見出しキーがバージョンの次に無く、説明の言語キーと違う。"""
    version_at = PLUGIN_COLUMNS.index("version")
    assert PLUGIN_HEADER_KEYS[PLUGIN_COLUMNS[version_at + 1]] == "ui.plugin_description"
    assert set(PLUGIN_HEADER_KEYS) == set(PLUGIN_COLUMNS)
    assert get_text("ui.plugin_description") != "ui.plugin_description"


def test_saved_order_inserts_description_after_version():
    """保存した列順に説明が無いと、説明がバージョンの直後に戻らない。"""
    dialog = PluginDialog.__new__(PluginDialog)
    dialog.config = SimpleNamespace(
        plugins={
            "dialog": {
                "plugin_table": {
                    "order": [
                        "enabled",
                        "name",
                        "id",
                        "version",
                        "kind",
                        "extensions",
                        "status",
                        "settings",
                        "license",
                    ],
                    "widths": {},
                }
            }
        }
    )
    table = QTableWidget(0, len(PLUGIN_COLUMNS))
    dialog._restore_table_layout(table, PLUGIN_COLUMNS, PLUGIN_DEFAULT_WIDTHS, "plugin_table")
    visual = _visual_keys(table)
    assert visual[visual.index("version") + 1] == "description"


def test_loaded_row_shows_manifest_description_and_tooltip():
    """読み込んだ行の説明とホバー全文が、manifest の description と違う。"""
    text = "Turns pages on a timer for each visible tab."
    plugin = SimpleNamespace(
        plugin_id="com.example.desc",
        name="Desc",
        formats=[],
        has_sidebar=False,
        error=None,
        manifest=SimpleNamespace(version="1.0.0", description=text),
    )
    dialog = _table_dialog([plugin], [], [])
    dialog._fill_plugin_table()
    item = _cell(dialog, 0, "description")
    assert item.text() == text
    assert item.toolTip() == text


def test_empty_description_stays_blank():
    """description が空の行にハイフンが入る。"""
    plugin = SimpleNamespace(
        plugin_id="com.example.blank",
        name="Blank",
        formats=[],
        has_sidebar=False,
        error=None,
        manifest=SimpleNamespace(version="1.0.0", description=""),
    )
    dialog = _table_dialog([plugin], [], [])
    dialog._fill_plugin_table()
    item = _cell(dialog, 0, "description")
    assert item.text() == ""
    assert item.toolTip() == ""


def test_skipped_row_shows_manifest_description():
    """読み飛ばした行の説明とホバー全文が、manifest の description と違う。"""
    skipped = SkippedPlugin(
        path=Path("one"),
        plugin_id="com.example.dup",
        name="One",
        version="1.0.0",
        reason="not_selected",
        description="Kept aside.",
    )
    dialog = _table_dialog([], [skipped], [])
    dialog._fill_plugin_table()
    item = _cell(dialog, 0, "description")
    assert item.text() == "Kept aside."
    assert item.toolTip() == "Kept aside."


def test_failed_row_description_is_dash():
    """読み込み失敗の説明がハイフンにならない。"""
    dialog = _table_dialog([], [], [(Path("bad.zip"), "broken")])
    dialog._fill_plugin_table()
    item = _cell(dialog, 0, "description")
    assert item.text() == "-"
    assert item.toolTip() == "-"

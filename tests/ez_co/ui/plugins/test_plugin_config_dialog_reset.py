"""対象: ez_co.ui.plugins.plugin_config_dialog — override削除としてのReset。"""
import pytest

from ez_co.plugins.host import PluginHost
from ez_co.ui.plugins.plugin_config_dialog import PluginConfigDialog

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


class _MemoryDb:
    """プラグイン設定をプロセス内の辞書だけに置く。"""

    def __init__(self):
        """空の行を用意する。"""
        self.rows = {}

    def get_plugin_setting(self, plugin_id, key, default=None):
        """保存済みの値を返す。無ければ default。

        Args:
            plugin_id: プラグイン ID。
            key: 設定キー。
            default: 未保存のときの値。

        Returns:
            保存値、または default。
        """
        return self.rows.get((plugin_id, key), default)

    def set_plugin_setting(self, plugin_id, key, value):
        """設定を辞書へ上書きする。

        Args:
            plugin_id: プラグイン ID。
            key: 設定キー。
            value: 保存する値。

        Returns:
            保存できたとき True。
        """
        self.rows[(plugin_id, key)] = value
        return True

    def delete_plugin_setting(self, plugin_id, key):
        """設定の行を消す。無くても失敗にしない。

        Args:
            plugin_id: プラグイン ID。
            key: 設定キー。

        Returns:
            消す処理を終えたとき True。
        """
        self.rows.pop((plugin_id, key), None)
        return True


def _dialog(**fields):
    """項目を登録したプラグイン設定ダイアログを開く。

    Args:
        **fields: キーから register_config の引数への対応。

    Returns:
        host、scoped、ダイアログ。
    """
    host = PluginHost()
    host._db = _MemoryDb()
    host.enter_phase("com.example.x", "load")
    scoped = host.scoped("com.example.x")
    for key, spec in fields.items():
        scoped.register_config(key, **spec)
    return host, scoped, PluginConfigDialog(host, "com.example.x")


def test_apply_reset_allows_empty_required_default():
    """必須の空既定へ初期化したあと適用できず、保存しても空文字が設定値にならない。"""
    _host, scoped, dialog = _dialog(
        need={"value_type": "string", "default": "", "required": True},
    )
    scoped.set_config("need", "kept")
    dialog._widgets["need"].setText("kept")
    dialog._reset_to_defaults()
    assert dialog._apply_button.isEnabled()
    assert dialog._save()
    assert scoped.get_config("need") == ""


def test_cancel_restores_sync_preview_after_reset():
    """sync 項目の初期化が即時の 0 にならず、プレビュー復元で初期化前の 7 に戻らない。"""
    _host, scoped, dialog = _dialog(
        level={"value_type": "int", "default": 0, "sync": True},
    )
    scoped.set_config("level", 7)
    dialog._widgets["level"].setValue(7)
    dialog._capture_snapshot()
    dialog._reset_to_defaults()
    assert scoped.get_config("level") == 0
    dialog._restore_preview()
    assert scoped.get_config("level") == 7

"""対象: ez_co.ui.plugins.config_form — 数値は debounce、非数値は即時保存。"""
from __future__ import annotations

import pytest

from ez_co.plugins.host import PluginHost
from ez_co.ui.plugins.config_form import PluginConfigForm
from ez_co.ui.plugins.config_widgets import SYNC_RELOAD_IDLE_MS

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


def _form():
    """bool と int を登録した設定フォームを組む。

    Returns:
        host、scoped、フォーム。
    """
    host = PluginHost()
    host.bind(parent=None, db_manager=_MemoryDb())
    host.set_manifest_provides("com.example.x", sidebar=True)
    host.enter_phase("com.example.x", "setup")
    scoped = host.scoped("com.example.x")
    scoped.register_config("flag", "bool", True)
    scoped.register_config("count", "int", 1)
    return host, scoped, PluginConfigForm(host, "com.example.x")


def test_bool_writes_immediately():
    """チェックを外した直後に bool が保存されず、待ち時間が要る。"""
    _host, scoped, form = _form()
    form._widgets["flag"].setChecked(False)
    assert scoped.get_config("flag") is False


def test_int_waits_for_idle(qtbot):
    """整数が変更直後に新しい値になり、アイドル後も旧値のまま。"""
    _host, scoped, form = _form()
    form._widgets["count"].setValue(9)
    assert scoped.get_config("count") == 1
    qtbot.wait(SYNC_RELOAD_IDLE_MS + 50)
    assert scoped.get_config("count") == 9

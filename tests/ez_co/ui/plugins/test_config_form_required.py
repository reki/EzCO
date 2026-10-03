"""対象: ez_co.ui.plugins.config_form — required の空は保存しない。"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from ez_co.plugins.host import PluginHost
from ez_co.ui.plugins.config_form import PluginConfigForm

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


def _form(reloads=None, **fields):
    """項目を登録したサイドバー用の設定フォームを組む。

    Args:
        reloads: 再読み込みのたびにページを足すリスト。無ければ再読み込みしない。
        **fields: キーから register_config の引数への対応。

    Returns:
        host、scoped、フォーム。
    """
    host = PluginHost()
    kwargs = {"parent": None, "db_manager": _MemoryDb()}
    if reloads is not None:
        kwargs["reload_current"] = lambda page: reloads.append(page) or True
    host.bind(**kwargs)
    host.set_manifest_provides("com.example.x", sidebar=True)
    host.enter_phase("com.example.x", "setup")
    scoped = host.scoped("com.example.x")
    for key, spec in fields.items():
        scoped.register_config(key, **spec)
    return host, scoped, PluginConfigForm(host, "com.example.x")


def test_empty_required_string_is_not_saved():
    """必須文字列を空にして編集を終えると保存され、表示が保存済みの値に戻らない。"""
    _host, scoped, form = _form(
        need={"value_type": "string", "default": "", "required": True},
    )
    scoped.set_config("need", "kept")
    form._widgets["need"].setText("")
    form._widgets["need"].editingFinished.emit()
    assert scoped.get_config("need") == "kept"
    assert form._widgets["need"].text() == "kept"


def test_reset_removes_override_for_empty_required_default(monkeypatch):
    """初期化後も必須の空既定に上書きが残り、必須でない項目が既定の x に戻らない。"""
    monkeypatch.setattr(
        "ez_co.ui.plugins.config_form.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    _host, scoped, form = _form(
        need={"value_type": "string", "default": "", "required": True},
        label={"value_type": "string", "default": "x"},
    )
    scoped.set_config("need", "kept")
    scoped.set_config("label", "edited")
    form._reset_to_defaults()
    assert scoped.get_config("need") == ""
    assert form._widgets["need"].text() == ""
    assert scoped.get_config("label") == "x"


def test_reset_reloads_once_only_after_saved_reload_fields(monkeypatch):
    """reload 項目が複数あると初期化の再読み込みが1回以外になり、既定へ戻らない。"""
    monkeypatch.setattr(
        "ez_co.ui.plugins.config_form.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    reloads = []
    _host, scoped, form = _form(
        reloads,
        need={"value_type": "string", "default": "", "required": True, "reload": True},
        flag={"value_type": "bool", "default": False, "reload": True},
    )
    scoped.set_config("need", "kept")
    scoped.set_config("flag", True)
    form._reset_to_defaults()
    assert scoped.get_config("need") == ""
    assert scoped.get_config("flag") is False
    assert reloads == [None]


def test_reset_removes_override_for_empty_required_multiple(monkeypatch):
    """必須の複数文字列を初期化しても、保存済みの配列が空にならない。"""
    monkeypatch.setattr(
        "ez_co.ui.plugins.config_form.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    _host, scoped, form = _form(
        needs={"value_type": "string", "default": [], "multiple": True, "required": True},
    )
    scoped.set_config("needs", ["x"])
    form._reset_to_defaults()
    assert scoped.get_config("needs") == []

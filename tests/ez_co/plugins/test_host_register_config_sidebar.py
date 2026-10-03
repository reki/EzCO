"""対象: ez_co.plugins.host — required_setting_sidebar / register_config_sidebar。"""
from __future__ import annotations

import inspect

import pytest

from ez_co.plugins.host import PluginHost, PluginRegistrationDenied
from ez_co.ui.plugins.config_form import PluginConfigForm
from ez_co.utils.language_manager import get_text

pytestmark = pytest.mark.usefixtures("qapp")


class _MemoryDb:
    """プラグイン設定を辞書に持つ、テスト用の DB。"""

    def __init__(self):
        """行の辞書を空にする。"""
        self.rows = {}

    def get_plugin_setting(self, plugin_id, key, default=None):
        """保存済みの値を返す。

        Args:
            plugin_id: プラグイン ID。
            key: 設定キー。
            default: 行が無いときの値。

        Returns:
            保存値。無ければ default。
        """
        return self.rows.get((plugin_id, key), default)

    def set_plugin_setting(self, plugin_id, key, value):
        """設定を辞書へ書く。

        Args:
            plugin_id: プラグイン ID。
            key: 設定キー。
            value: 保存する値。

        Returns:
            常に真。
        """
        self.rows[(plugin_id, key)] = value
        return True


def _host(reloads=None):
    """サイドバー宣言済みで setup 中のホストとスコープを返す。

    Args:
        reloads: 再読み込みのたびにページを足すリスト。無ければ再読み込みは結ばない。

    Returns:
        ホストと com.example.x のスコープ。
    """
    host = PluginHost()
    kwargs = {"parent": None, "db_manager": _MemoryDb()}
    if reloads is not None:
        kwargs["reload_current"] = lambda page: reloads.append(page) or True
    host.bind(**kwargs)
    host.set_manifest_provides("com.example.x", sidebar=True)
    host.enter_phase("com.example.x", "setup")
    return host, host.scoped("com.example.x")


def test_register_config_sidebar_accepts_declared_flag():
    """宣言済み sidebar で config サイドバーが1件載らず、title がテンプレートでなく、中身が PluginConfigForm でない。"""
    host, scoped = _host()
    scoped.register_config("flag", "bool", True)
    scoped.register_config_sidebar("main", "{title}")
    rows = host.sidebars_for("com.example.x")
    assert len(rows) == 1
    assert rows[0].sidebar_id == "main"
    assert rows[0].title == "{title}"
    assert isinstance(rows[0].widget, PluginConfigForm)


def test_register_config_sidebar_requires_manifest_flag():
    """sidebar 未宣言でも register_config_sidebar が権限不足で拒否されない。"""
    host = PluginHost()
    host.enter_phase("com.example.ui", "setup")
    scoped = host.scoped("com.example.ui")
    scoped.register_config("flag", "bool", True)
    with pytest.raises(PluginRegistrationDenied, match=get_text("ui.plugin_register_not_permitted")):
        scoped.register_config_sidebar("main", "Title")


def test_required_setting_sidebar_rejects_empty_schema():
    """設定が空でも required_setting_sidebar がプラグイン ID 付きの ValueError にならない。"""
    _host_obj, scoped = _host()
    with pytest.raises(ValueError, match="com.example.x"):
        scoped.required_setting_sidebar()


def test_required_setting_sidebar_returns_form():
    """設定があるとき required_setting_sidebar が PluginConfigForm を返さない。"""
    _host_obj, scoped = _host()
    scoped.register_config("flag", "bool", True)
    widget = scoped.required_setting_sidebar()
    assert isinstance(widget, PluginConfigForm)


def test_register_config_sidebar_writes_bool_immediately():
    """チェックを外しても bool がすぐに false として保存されない。"""
    host, scoped = _host()
    scoped.register_config("flag", "bool", True)
    scoped.register_config_sidebar("main", "Title")
    form = host.sidebars_for("com.example.x")[0].widget
    form._widgets["flag"].setChecked(False)
    assert scoped.get_config("flag") is False


def test_register_config_sidebar_reloads_only_when_field_reload():
    """reload の無い項目の変更で再読み込みが走り、reload のある項目でページ None の再読み込みが走らない。"""
    reloads = []
    host, scoped = _host(reloads)
    scoped.register_config("flag", "bool", True)
    scoped.register_config("keep", "bool", True, reload=True)
    scoped.register_config_sidebar("main", "Title")
    form = host.sidebars_for("com.example.x")[0].widget
    form._widgets["flag"].setChecked(False)
    assert reloads == []
    form._widgets["keep"].setChecked(False)
    assert reloads == [None]


def test_register_config_sidebar_signature_keeps_aliases():
    """引数名と順が sidebar_id、title、aliases から変わる。"""
    host = PluginHost()
    params = inspect.signature(host.scoped("com.example.x").register_config_sidebar).parameters
    assert list(params) == ["sidebar_id", "title", "aliases"]

"""対象: ez_co.ui.plugins.config_form — required の空は保存しない。"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from ez_co.plugins.host import PluginHost
from ez_co.ui.plugins.config_form import PluginConfigForm

pytestmark = pytest.mark.usefixtures("qapp")


class _MemoryDb:
    def __init__(self):
        self.rows = {}

    def get_plugin_setting(self, plugin_id, key, default=None):
        return self.rows.get((plugin_id, key), default)

    def set_plugin_setting(self, plugin_id, key, value):
        self.rows[(plugin_id, key)] = value
        return True


def _form(reloads=None, **fields):
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
    _host, scoped, form = _form(
        need={"value_type": "string", "default": "", "required": True},
    )
    scoped.set_config("need", "kept")
    form._widgets["need"].setText("")
    form._widgets["need"].editingFinished.emit()
    assert scoped.get_config("need") == "kept"
    assert form._widgets["need"].text() == "kept"


def test_reset_skips_empty_required_default(monkeypatch):
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
    assert scoped.get_config("need") == "kept"
    assert form._widgets["need"].text() == "kept"
    assert scoped.get_config("label") == "x"


def test_reset_reloads_once_only_after_saved_reload_fields(monkeypatch):
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
    assert scoped.get_config("need") == "kept"
    assert scoped.get_config("flag") is False
    assert reloads == [None]

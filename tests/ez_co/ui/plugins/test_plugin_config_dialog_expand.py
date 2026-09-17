"""対象: ez_co.ui.plugins.plugin_config_dialog — 開くときに {key} を項目名へ展開する。"""
import pytest

from ez_co.plugins.host import PluginHost
from ez_co.ui.plugins.plugin_config_dialog import PluginConfigDialog, config_field_display_name

pytestmark = pytest.mark.usefixtures("qapp")


def _host_with_label(mapping):
    host = PluginHost()
    host.enter_phase("com.example.x", "load")
    scoped = host.scoped("com.example.x")
    scoped.bind_plugin(None, lambda key, **kwargs: mapping.get(key, key))
    scoped.register_config("flag", "bool", True, label="{title}")
    return host


def test_dialog_expands_whole_string_key_as_item_name():
    host = _host_with_label({"title": "題名"})
    dialog = PluginConfigDialog(host, "com.example.x", "Name")
    try:
        assert dialog._table.item(0, 0).text() == "題名"
        assert host.configs_for("com.example.x")[0].label == "{title}"
    finally:
        dialog.close()


def test_reopen_picks_up_new_language():
    host = _host_with_label({"title": "題名"})
    first = PluginConfigDialog(host, "com.example.x", "Name")
    try:
        assert first._table.item(0, 0).text() == "題名"
    finally:
        first.close()
    host.scoped("com.example.x").bind_plugin(None, lambda key, **kwargs: {"title": "Title"}.get(key, key))
    second = PluginConfigDialog(host, "com.example.x", "Name")
    try:
        assert second._table.item(0, 0).text() == "Title"
        assert host.configs_for("com.example.x")[0].label == "{title}"
    finally:
        second.close()


def test_range_name_expands_before_bounds_suffix():
    host = PluginHost()
    host.enter_phase("com.example.x", "load")
    scoped = host.scoped("com.example.x")
    scoped.bind_plugin(None, lambda key, **kwargs: {"strength": "強度"}.get(key, key))
    scoped.register_config(
        "strength",
        "int_range",
        50,
        label="{strength}",
        minimum=0,
        maximum=100,
        step=1,
    )
    field = host.configs_for("com.example.x")[0]
    name = config_field_display_name(field, expand=scoped.expand_text)
    assert name.startswith("強度")
    assert "0" in name and "100" in name

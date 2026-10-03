"""対象: ez_co.plugins.host — register_filter と clear_plugin は台帳だけ。"""
from __future__ import annotations

import pytest

from ez_co.filters.registry import get_filter_registry
from ez_co.plugins.host import PluginHost, PluginRegistrationDenied, make_plugin_filter_id
from ez_co.utils.language_manager import get_text


def _process(image, context):
    """渡された画像をそのまま返す。

    Args:
        image: 処理対象。
        context: フィルター文脈。未使用。

    Returns:
        渡された画像。
    """
    return image


def test_register_filter_requires_permission():
    """filter 権限が無くても登録が通り、台帳に ID が残る。"""
    host = PluginHost()
    with pytest.raises(PluginRegistrationDenied, match=get_text("ui.plugin_register_not_permitted")):
        host.scoped("com.example.x").register_filter("sharp", "Sharp", _process)
    assert get_filter_registry().get(make_plugin_filter_id("com.example.x", "sharp")) is None


def test_register_filter_rejects_non_callable():
    """process が None でも、プラグイン ID を含む ValueError にならない。"""
    host = PluginHost()
    host.set_manifest_permissions("com.example.x", {"filter": True})
    with pytest.raises(ValueError, match="com.example.x"):
        host.scoped("com.example.x").register_filter("sharp", "Sharp", None)


def test_register_filter_accepts_permission():
    """権限があっても台帳にタイトルとプラグイン ID が残らない。"""
    host = PluginHost()
    host.set_manifest_permissions("com.example.x", {"filter": True})
    host.scoped("com.example.x").register_filter("sharp", "Sharp", _process)
    record = get_filter_registry().get(make_plugin_filter_id("com.example.x", "sharp"))
    assert record is not None
    assert record.title == "Sharp"
    assert record.plugin_id == "com.example.x"


def test_clear_plugin_drops_registry_keeps_pipe():
    """clear_plugin のあと台帳にフィルターが残るか、呼び出し側の pipe まで書き換わる。"""
    host = PluginHost()
    host.set_manifest_permissions("com.example.x", {"filter": True})
    host.scoped("com.example.x").register_filter("sharp", "Sharp", _process)
    public_id = make_plugin_filter_id("com.example.x", "sharp")
    pipe = [public_id]
    host.clear_plugin("com.example.x")
    assert get_filter_registry().get(public_id) is None
    assert pipe == [public_id]


def test_unregister_filter_drops_one_keeps_pipe():
    """unregister が指定した1件以外も消し、pipe まで書き換わる。"""
    host = PluginHost()
    host.set_manifest_permissions("com.example.x", {"filter": True})
    host.scoped("com.example.x").register_filter("sharp", "Sharp", _process)
    host.scoped("com.example.x").register_filter("blur", "Blur", _process)
    sharp = make_plugin_filter_id("com.example.x", "sharp")
    blur = make_plugin_filter_id("com.example.x", "blur")
    pipe = [sharp, blur]
    host.scoped("com.example.x").unregister_filter("sharp")
    assert get_filter_registry().get(sharp) is None
    assert get_filter_registry().get(blur) is not None
    assert pipe == [sharp, blur]

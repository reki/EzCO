"""対象: ez_co.plugins.host — 未宣言の register_format / register_sidebar。"""
from __future__ import annotations

import inspect

import pytest

from ez_co.plugins.api import FileKind, FormatSpec
from ez_co.plugins.host import PluginHost


def test_register_format_requires_manifest_declaration():
    host = PluginHost()
    with pytest.raises(ValueError, match="com.example.x"):
        host.scoped("com.example.x").register_format(".txt", "archive")


def test_register_format_accepts_declared_pair():
    host = PluginHost()
    host.set_manifest_provides("com.example.x", [FormatSpec(".txt", FileKind.ARCHIVE)])
    host.scoped("com.example.x").register_format(".txt", "archive")
    specs = host.formats_for("com.example.x")
    assert [(item.extension, item.kind) for item in specs] == [(".txt", FileKind.ARCHIVE)]


def test_register_format_rejects_kind_mismatch():
    host = PluginHost()
    host.set_manifest_provides("com.example.x", [FormatSpec(".txt", FileKind.ARCHIVE)])
    with pytest.raises(ValueError, match="com.example.x"):
        host.scoped("com.example.x").register_format(".txt", "image")


def test_register_sidebar_requires_manifest_flag():
    host = PluginHost()
    with pytest.raises(ValueError, match="com.example.ui"):
        host.scoped("com.example.ui").register_sidebar("main", "Title", object())


def test_register_sidebar_accepts_declared_flag():
    host = PluginHost()
    host.set_manifest_provides("com.example.ui", sidebar=True)
    host.scoped("com.example.ui").register_sidebar("main", "Title", object())
    assert host.sidebars_for("com.example.ui")


def test_scoped_host_cannot_set_manifest_provides():
    host = PluginHost()
    scoped = host.scoped("com.example.x")
    assert not hasattr(scoped, "set_manifest_provides")
    params = inspect.signature(scoped.register_format).parameters
    assert "formats" not in params

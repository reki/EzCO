"""対象: ez_co.plugins.host — register_config_json はファイル名。途中失敗は load 側で破棄。"""
from __future__ import annotations

import json

import pytest

from ez_co.plugins.host import PluginHost, PluginRegistrationDenied
from ez_co.utils.language_manager import get_text


class _Root:
    def __init__(self, files: dict[str, bytes]):
        self.files = files
        self.read_config_calls = []

    def read_bytes(self, name: str) -> bytes:
        if name not in self.files:
            raise KeyError(name)
        return self.files[name]

    def read_config(self, name: str) -> bytes:
        self.read_config_calls.append(name)
        raise AssertionError("register_config_json must not call read_config")


def test_register_config_json_reads_filename_keeps_template_label():
    host = PluginHost()
    host.enter_phase("com.example.x", "load")
    scoped = host.scoped("com.example.x")
    root = _Root(
        {
            "resources/config/fields.json": json.dumps(
                [
                    {
                        "key": "flag",
                        "value_type": "bool",
                        "default": True,
                        "label": "{flag}",
                        "description": "{flag_help}",
                    }
                ]
            ).encode("utf-8")
        }
    )
    scoped.bind_plugin(root, lambda key, **kwargs: key)
    scoped.register_config_json("fields.json")
    field = host.configs_for("com.example.x")[0]
    assert field.key == "flag"
    assert field.label == "{flag}"
    assert field.description == "{flag_help}"
    assert root.read_config_calls == []


def test_register_config_json_partial_failure_leaves_rows_until_abort():
    host = PluginHost()
    host.enter_phase("com.example.x", "load")
    scoped = host.scoped("com.example.x")
    payload = [
        {"key": "ok", "value_type": "bool", "default": True, "label": "{ok}"},
        {"key": "bad", "value_type": "int_range", "default": 1, "maximum": 10, "step": 1},
    ]
    scoped.bind_plugin(
        _Root({"resources/config/fields.json": json.dumps(payload).encode("utf-8")}),
        lambda key, **kwargs: key,
    )
    with pytest.raises(ValueError, match="com.example.x"):
        scoped.register_config_json("fields.json")
    assert [field.key for field in host.configs_for("com.example.x")] == ["ok"]
    host.abort_load("com.example.x")
    assert host.configs_for("com.example.x") == []


def test_register_config_json_denied_in_init():
    host = PluginHost()
    host.enter_phase("com.example.x", "init")
    scoped = host.scoped("com.example.x")
    scoped.bind_plugin(_Root({"resources/config/fields.json": b"[]"}), lambda key, **kwargs: key)
    with pytest.raises(PluginRegistrationDenied, match=get_text("ui.plugin_register_wrong_phase")):
        scoped.register_config_json("fields.json")


def test_register_config_json_denied_in_language():
    host = PluginHost()
    host.enter_phase("com.example.x", "language")
    scoped = host.scoped("com.example.x")
    scoped.bind_plugin(_Root({"resources/config/fields.json": b"[]"}), lambda key, **kwargs: key)
    with pytest.raises(PluginRegistrationDenied, match=get_text("ui.plugin_register_wrong_phase")):
        scoped.register_config_json("fields.json")

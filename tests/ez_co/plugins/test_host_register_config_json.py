"""対象: ez_co.plugins.host — register_config_json はファイル名。途中失敗は load 側で破棄。"""
from __future__ import annotations

import json

import pytest

from ez_co.plugins.host import PluginHost, PluginRegistrationDenied
from ez_co.utils.language_manager import get_text


class _Root:
    """設定ファイルのバイト列を持ち、read_config が呼ばれたら失敗する root。"""

    def __init__(self, files: dict[str, bytes]):
        """ファイルと、read_config の呼び出し記録を空で持つ。

        Args:
            files: 相対パスからバイト列への対応。
        """
        self.files = files
        self.read_config_calls = []

    def read_bytes(self, name: str) -> bytes:
        """その名前のバイト列を返す。

        Args:
            name: 相対パス。

        Returns:
            保存してあるバイト列。

        Raises:
            KeyError: 名前が無いとき。
        """
        if name not in self.files:
            raise KeyError(name)
        return self.files[name]

    def read_config(self, name: str) -> bytes:
        """read_config が呼ばれた事実を残して失敗させる。

        Args:
            name: 設定ファイル名。

        Raises:
            AssertionError: register_config_json が read_config を呼んだとき。
        """
        self.read_config_calls.append(name)
        raise AssertionError("register_config_json must not call read_config")


def test_register_config_json_reads_filename_keeps_template_label():
    """fields.json の label と description がテンプレートのまま残らず、read_config が呼ばれる。"""
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
    """途中失敗の時点で先の ok が消えているか、abort_load のあと schema が残る。"""
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
    """init の register_config_json が phase 違反で拒否されない。"""
    host = PluginHost()
    host.enter_phase("com.example.x", "init")
    scoped = host.scoped("com.example.x")
    scoped.bind_plugin(_Root({"resources/config/fields.json": b"[]"}), lambda key, **kwargs: key)
    with pytest.raises(PluginRegistrationDenied, match=get_text("ui.plugin_register_wrong_phase")):
        scoped.register_config_json("fields.json")


def test_register_config_json_denied_in_language():
    """language の register_config_json が phase 違反で拒否されない。"""
    host = PluginHost()
    host.enter_phase("com.example.x", "language")
    scoped = host.scoped("com.example.x")
    scoped.bind_plugin(_Root({"resources/config/fields.json": b"[]"}), lambda key, **kwargs: key)
    with pytest.raises(PluginRegistrationDenied, match=get_text("ui.plugin_register_wrong_phase")):
        scoped.register_config_json("fields.json")

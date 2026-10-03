"""対象: ez_co.plugins.zip_loader — Class() のあと load(root, get_text, host)。"""
from __future__ import annotations

import pytest

from ez_co.plugins.host import PluginHost
from ez_co.plugins.zip_loader import load_plugin
from ez_co.utils.language_manager import get_text


def test_load_plugin_calls_load_once(tmp_path, dir_plugin):
    """load が1回で終わらず、host がスコープしたものでなく、root が渡らない。"""
    root = dir_plugin(tmp_path, plugin_id="com.example.load", folder_name="once")
    (root / "src" / "plugin.py").write_text(
        "class ProbePlugin:\n"
        "    calls = 0\n"
        "    def __init__(self):\n"
        "        self.root = None\n"
        "        self.host = None\n"
        "    def load(self, root, get_text, host):\n"
        "        ProbePlugin.calls += 1\n"
        "        self.root = root\n"
        "        self.host = host\n",
        encoding="utf-8",
    )
    host = PluginHost()
    _manifest, instance, _root, _archive = load_plugin(root, host=host)
    assert type(instance).calls == 1
    assert instance.host is host.scoped("com.example.load")
    assert instance.root is not None


def test_old_constructor_signature_fails(tmp_path, dir_plugin):
    """root、get_text、host を取る古い __init__ が TypeError にならない。"""
    root = dir_plugin(tmp_path, plugin_id="com.example.old", folder_name="old")
    (root / "src" / "plugin.py").write_text(
        "class ProbePlugin:\n"
        "    def __init__(self, root, get_text, host):\n"
        "        self.host = host\n"
        "    def load(self, root, get_text, host):\n"
        "        pass\n",
        encoding="utf-8",
    )
    with pytest.raises(TypeError):
        load_plugin(root, host=PluginHost())


def test_register_config_in_init_fails(tmp_path, dir_plugin):
    """__init__ の register_config が phase 違反で落ちず、schema が残る。"""
    root = dir_plugin(tmp_path, plugin_id="com.example.initcfg", folder_name="initcfg")
    (root / "src" / "plugin.py").write_text(
        "class ProbePlugin:\n"
        "    def __init__(self):\n"
        '        host.register_config("flag", "bool", True)\n'
        "    def load(self, root, get_text, host):\n"
        "        self.host = host\n",
        encoding="utf-8",
    )
    host = PluginHost()
    with pytest.raises(Exception, match=get_text("ui.plugin_register_wrong_phase")):
        load_plugin(root, host=host)
    assert host.configs_for("com.example.initcfg") == []


def test_register_sidebar_in_load_fails(tmp_path, dir_plugin):
    """load 中の register_sidebar が phase 違反で落ちず、サイドバーが残る。"""
    root = dir_plugin(
        tmp_path,
        plugin_id="com.example.ui",
        folder_name="ui",
        manifest_extra={"sidebar": True},
    )
    (root / "src" / "plugin.py").write_text(
        "class ProbePlugin:\n"
        "    def __init__(self):\n"
        "        self.host = None\n"
        "    def load(self, root, get_text, host):\n"
        "        self.host = host\n"
        '        host.register_sidebar("main", "Title", object())\n',
        encoding="utf-8",
    )
    host = PluginHost()
    with pytest.raises(Exception, match=get_text("ui.plugin_register_wrong_phase")):
        load_plugin(root, host=host)
    assert not host.sidebars_for("com.example.ui")


def test_missing_load_fails(tmp_path, dir_plugin):
    """load が無いクラスが、プラグイン ID を含む ValueError にならない。"""
    root = dir_plugin(tmp_path, plugin_id="com.example.noload", folder_name="noload")
    (root / "src" / "plugin.py").write_text(
        "class ProbePlugin:\n"
        "    def __init__(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="com.example.noload"):
        load_plugin(root, host=PluginHost())


def test_register_config_json_failure_aborts_schema(tmp_path, dir_plugin):
    """JSON の途中失敗で load が落ちず、途中までの schema が残る。"""
    root = dir_plugin(tmp_path, plugin_id="com.example.cfgjson", folder_name="cfgjson")
    config_dir = root / "resources" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "fields.json").write_text(
        '[{"key": "ok", "value_type": "bool", "default": true},'
        ' {"key": "bad", "value_type": "int_range", "default": 1, "maximum": 10, "step": 1}]',
        encoding="utf-8",
    )
    (root / "src" / "plugin.py").write_text(
        "class ProbePlugin:\n"
        "    def __init__(self):\n"
        "        self.host = None\n"
        "    def load(self, root, get_text, host):\n"
        "        self.host = host\n"
        '        host.register_config_json("fields.json")\n',
        encoding="utf-8",
    )
    host = PluginHost()
    with pytest.raises(ValueError, match="com.example.cfgjson"):
        load_plugin(root, host=host)
    assert host.configs_for("com.example.cfgjson") == []


def test_register_config_json_keeps_template_on_load(tmp_path, dir_plugin):
    """load で読んだ label が {flag} のテンプレートのまま残らない。"""
    root = dir_plugin(tmp_path, plugin_id="com.example.cfgok", folder_name="cfgok")
    config_dir = root / "resources" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "fields.json").write_text(
        '[{"key": "flag", "value_type": "bool", "default": true, "label": "{flag}"}]',
        encoding="utf-8",
    )
    (root / "src" / "plugin.py").write_text(
        "class ProbePlugin:\n"
        "    def __init__(self):\n"
        "        self.host = None\n"
        "    def load(self, root, get_text, host):\n"
        "        self.host = host\n"
        '        host.register_config_json("fields.json")\n',
        encoding="utf-8",
    )
    host = PluginHost()
    load_plugin(root, host=host)
    field = host.configs_for("com.example.cfgok")[0]
    assert field.key == "flag"
    assert field.label == "{flag}"

"""対象: ez_co.plugins.config_schema — JSON 配列のパース。展開は持たない。"""
import pytest

from ez_co.plugins import config_schema
from ez_co.plugins.config_schema import parse_config_json
from ez_co.utils.language_manager import get_log_text


def test_parse_config_json_array_of_fields():
    rows = parse_config_json(
        b'[{"key": "flag", "value_type": "bool", "default": true, "label": "{flag}"}]',
        plugin_id="com.example.x",
    )
    assert rows == [
        {"key": "flag", "value_type": "bool", "default": True, "label": "{flag}"}
    ]


def test_parse_config_json_rejects_unknown_key():
    with pytest.raises(ValueError, match="com.example.x"):
        parse_config_json(
            '[{"key": "flag", "value_type": "bool", "foo": 1}]',
            plugin_id="com.example.x",
        )


def test_parse_config_json_rejects_enum_key():
    with pytest.raises(ValueError, match="com.example.x"):
        parse_config_json(
            '[{"key": "style", "value_type": "choice", "enum_type": "Style"}]',
            plugin_id="com.example.x",
        )


def test_parse_config_json_rejects_string_choices():
    with pytest.raises(ValueError, match=get_log_text("plugin_config_enum_invalid", plugin_id="com.example.x", field_key="style")):
        parse_config_json(
            '[{"key": "style", "value_type": "choice", "choices": "Style"}]',
            plugin_id="com.example.x",
        )


def test_parse_config_json_rejects_object_root():
    with pytest.raises(ValueError, match="com.example.x"):
        parse_config_json('{"key": "flag"}', plugin_id="com.example.x")


def test_config_schema_has_no_expand():
    assert [name for name in dir(config_schema) if "expand" in name.lower()] == []

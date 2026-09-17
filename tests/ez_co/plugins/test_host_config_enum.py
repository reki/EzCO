"""対象: ez_co.plugins.host — choice の Enum（DB は name、get_config は member）。"""
from enum import Enum, IntEnum, StrEnum

import pytest

from ez_co.plugins.host import PluginHost, parse_config_choices


class _MemoryDb:
    def __init__(self):
        self.rows = {}

    def get_plugin_setting(self, plugin_id, key, default=None):
        return self.rows.get((plugin_id, key), default)

    def set_plugin_setting(self, plugin_id, key, value):
        self.rows[(plugin_id, key)] = value
        return True


class Style(Enum):
    PLAIN = "plain"
    BOLD = "bold"
    EMPHASIS = BOLD


class Count(IntEnum):
    ONE = 1
    TWO = 2


class Kind(StrEnum):
    PLAIN = "plain"
    BOLD = "bold"


class Other(Enum):
    X = "x"


def _scoped():
    host = PluginHost()
    host._db = _MemoryDb()
    return host, host.scoped("com.example.x")


def test_parse_strenum_members_before_strings():
    rows, enum_type = parse_config_choices([Kind.PLAIN, Kind.BOLD])
    assert enum_type is Kind
    assert rows == (("PLAIN", "PLAIN"), ("BOLD", "BOLD"))


def test_register_enum_class_and_member_default():
    _host, scoped = _scoped()
    scoped.register_config("style", "choice", default=Style.PLAIN, choices=Style)
    field = _host.configs_for("com.example.x")[0]
    assert field.enum_type is Style
    assert field.default is Style.PLAIN
    assert scoped.get_config("style") is Style.PLAIN


def test_set_config_stores_canonical_name(monkeypatch):
    host, scoped = _scoped()
    scoped.register_config("style", "choice", default=Style.PLAIN, choices=Style)
    seen = []
    scoped.on("config_changed", lambda payload: seen.append(payload))
    assert scoped.set_config("style", Style.EMPHASIS) is True
    assert host._db.rows[("com.example.x", "style")] == "BOLD"
    assert scoped.get_config("style") is Style.BOLD
    assert seen[-1]["value"] is Style.BOLD


def test_restore_unknown_name_uses_default():
    host, scoped = _scoped()
    scoped.register_config("style", "choice", default=Style.PLAIN, choices=Style)
    host._db.rows[("com.example.x", "style")] = "GONE"
    assert scoped.get_config("style") is Style.PLAIN


def test_missing_row_uses_default():
    _host, scoped = _scoped()
    scoped.register_config("style", "choice", default=Style.BOLD, choices=Style)
    assert scoped.get_config("style") is Style.BOLD


def test_intenum_stores_name_not_value():
    host, scoped = _scoped()
    scoped.register_config("count", "choice", default=Count.ONE, choices=Count)
    scoped.set_config("count", Count.TWO)
    assert host._db.rows[("com.example.x", "count")] == "TWO"
    assert scoped.get_config("count") is Count.TWO


def test_invalid_default_rejected():
    _host, scoped = _scoped()
    with pytest.raises(ValueError, match="com.example.x"):
        scoped.register_config("style", "choice", default="NOPE", choices=Style)
    assert _host.configs_for("com.example.x") == []


def test_mixed_enums_rejected():
    _host, scoped = _scoped()
    with pytest.raises(ValueError, match="com.example.x"):
        scoped.register_config("style", "choice", choices=[Style.PLAIN, Other.X])


def test_empty_enum_rejected():
    class Empty(Enum):
        pass

    _host, scoped = _scoped()
    with pytest.raises(ValueError, match="com.example.x"):
        scoped.register_config("style", "choice", choices=Empty)


def test_list_choice_still_returns_string():
    host, scoped = _scoped()
    scoped.register_config(
        "mode",
        "choice",
        default="plain",
        choices=[("plain", "Plain"), ("bold", "Bold")],
    )
    scoped.set_config("mode", "bold")
    assert host._db.rows[("com.example.x", "mode")] == "bold"
    assert scoped.get_config("mode") == "bold"


def test_multiple_enum_roundtrip_and_invalid_resets_all():
    host, scoped = _scoped()
    scoped.register_config(
        "styles",
        "choice",
        default=[Style.PLAIN],
        choices=Style,
        multiple=True,
    )
    scoped.set_config("styles", [Style.PLAIN, Style.BOLD])
    assert host._db.rows[("com.example.x", "styles")] == ["PLAIN", "BOLD"]
    assert scoped.get_config("styles") == [Style.PLAIN, Style.BOLD]
    host._db.rows[("com.example.x", "styles")] = ["PLAIN", "GONE"]
    assert scoped.get_config("styles") == [Style.PLAIN]

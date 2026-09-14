"""対象: ez_co.plugins.api — make_provider_id / parse_provider_id。"""
from ez_co.plugins.api import BUILTIN_PROVIDER_ID, SKIP_PROVIDER_ID, make_provider_id, parse_provider_id


def test_make_provider_id_uses_ver_form():
    assert make_provider_id("com.example.x", "1.2.3") == "com.example.x(ver:1.2.3)"


def test_parse_provider_id_current_form():
    assert parse_provider_id("com.example.x(ver:1.2.3)") == ("com.example.x", "1.2.3")


def test_parse_provider_id_legacy_form():
    assert parse_provider_id("com.example.x+(1.0.0)") == ("com.example.x", "1.0.0")


def test_parse_provider_id_builtin_and_skip():
    assert parse_provider_id(BUILTIN_PROVIDER_ID) == (BUILTIN_PROVIDER_ID, None)
    assert parse_provider_id(SKIP_PROVIDER_ID) == (SKIP_PROVIDER_ID, None)


def test_parse_provider_id_plain_id():
    assert parse_provider_id("com.example.x") == ("com.example.x", None)

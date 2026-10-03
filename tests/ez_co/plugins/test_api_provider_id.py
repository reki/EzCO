"""対象: ez_co.plugins.api — make_provider_id / parse_provider_id。"""
from ez_co.plugins.api import BUILTIN_PROVIDER_ID, SKIP_PROVIDER_ID, make_provider_id, parse_provider_id


def test_make_provider_id_uses_ver_form():
    """公開用のキーが id(ver:版) にならず、括弧や区切りが違う。"""
    assert make_provider_id("com.example.x", "1.2.3") == "com.example.x(ver:1.2.3)"


def test_parse_provider_id_current_form():
    """(ver:版) からプラグイン ID と版が分かれない。"""
    assert parse_provider_id("com.example.x(ver:1.2.3)") == ("com.example.x", "1.2.3")


def test_parse_provider_id_legacy_form():
    """旧い id+(版) からプラグイン ID と版が分かれない。"""
    assert parse_provider_id("com.example.x+(1.0.0)") == ("com.example.x", "1.0.0")


def test_parse_provider_id_builtin_and_skip():
    """builtin と none に版が付き、ID 自体が変わる。"""
    assert parse_provider_id(BUILTIN_PROVIDER_ID) == (BUILTIN_PROVIDER_ID, None)
    assert parse_provider_id(SKIP_PROVIDER_ID) == (SKIP_PROVIDER_ID, None)


def test_parse_provider_id_plain_id():
    """版の付いていない ID に版が入る。"""
    assert parse_provider_id("com.example.x") == ("com.example.x", None)

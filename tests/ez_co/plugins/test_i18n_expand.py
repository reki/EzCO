"""対象: ez_co.plugins.i18n — 文字列全体が {key} のときだけ展開する。"""
from ez_co.plugins.i18n import expand_plugin_text


def _get_text(key, **kwargs):
    mapping = {
        "title": "題名",
        "config.fetch_web": "Web取得",
        " title ": "trimmed-not",
    }
    return mapping.get(key, key)


def test_whole_string_key_expands():
    assert expand_plugin_text("{title}", _get_text) == "題名"


def test_dotted_key_is_passed_whole():
    assert expand_plugin_text("{config.fetch_web}", _get_text) == "Web取得"


def test_mixed_placeholders_stay_literal():
    assert expand_plugin_text("A{title}", _get_text) == "A{title}"
    assert expand_plugin_text("{title}B", _get_text) == "{title}B"
    assert expand_plugin_text("A{title}B", _get_text) == "A{title}B"
    assert expand_plugin_text("{title} ({hint})", _get_text) == "{title} ({hint})"


def test_inner_spaces_are_a_different_key():
    assert expand_plugin_text("{ title }", _get_text) == "trimmed-not"


def test_broken_braces_stay_literal():
    assert expand_plugin_text("{title", _get_text) == "{title"
    assert expand_plugin_text("title}", _get_text) == "title}"
    assert expand_plugin_text("{}", _get_text) == "{}"
    assert expand_plugin_text("{ti{tle}", _get_text) == "{ti{tle}"


def test_plain_text_stays():
    assert expand_plugin_text("px", _get_text) == "px"
    assert expand_plugin_text(None, _get_text) == ""

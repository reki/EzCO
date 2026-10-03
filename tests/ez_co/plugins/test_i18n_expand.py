"""対象: ez_co.plugins.i18n — 文字列全体が {key} のときだけ展開する。"""
from ez_co.plugins.i18n import expand_plugin_text


def _get_text(key, **kwargs):
    """決まったキーだけ訳し、それ以外はキーを返す。

    Args:
        key: 言語キー。
        **kwargs: 訳語の追加引数。未使用。

    Returns:
        訳語。対応が無ければキー。
    """
    mapping = {
        "title": "題名",
        "config.fetch_web": "Web取得",
        " title ": "trimmed-not",
    }
    return mapping.get(key, key)


def test_whole_string_key_expands():
    """文字列全体が {title} のとき、題名に置き換わらない。"""
    assert expand_plugin_text("{title}", _get_text) == "題名"


def test_dotted_key_is_passed_whole():
    """{config.fetch_web} がドットで分割され、Web取得にならない。"""
    assert expand_plugin_text("{config.fetch_web}", _get_text) == "Web取得"


def test_mixed_placeholders_stay_literal():
    """前後に文字がある {title} まで展開される。"""
    assert expand_plugin_text("A{title}", _get_text) == "A{title}"
    assert expand_plugin_text("{title}B", _get_text) == "{title}B"
    assert expand_plugin_text("A{title}B", _get_text) == "A{title}B"
    assert expand_plugin_text("{title} ({hint})", _get_text) == "{title} ({hint})"


def test_inner_spaces_are_a_different_key():
    """{ title } が trim されて、title の訳になる。"""
    assert expand_plugin_text("{ title }", _get_text) == "trimmed-not"


def test_broken_braces_stay_literal():
    """閉じ括弧が無い、空、入れ子の括弧まで展開される。"""
    assert expand_plugin_text("{title", _get_text) == "{title"
    assert expand_plugin_text("title}", _get_text) == "title}"
    assert expand_plugin_text("{}", _get_text) == "{}"
    assert expand_plugin_text("{ti{tle}", _get_text) == "{ti{tle}"


def test_plain_text_stays():
    """プレースホルダの無い文字列が変わり、None が空文字にならない。"""
    assert expand_plugin_text("px", _get_text) == "px"
    assert expand_plugin_text(None, _get_text) == ""

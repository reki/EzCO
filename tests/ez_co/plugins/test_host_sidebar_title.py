"""対象: ez_co.plugins.host"""
import json
from importlib import resources

from ez_co.plugins.host import sidebar_title_stem, sidebar_toggle_label
from ez_co.utils.language_manager import language_manager


def _languages(*items):
    """言語コードとファイルパスから available_languages の形を作る。

    Args:
        *items: 言語コードとパスの組。

    Returns:
        コードをキーにした言語情報。
    """
    return {
        code: {"name": code, "code": code, "file": path}
        for code, path in items
    }


def test_stem_strips_prefix_and_suffix_from_each_loaded_language(tmp_path, monkeypatch):
    """読み込んだ各言語のトグル文言の前後が残るか、大小文字の違いで剥がれず、素のタイトルまで欠ける。"""
    ja = tmp_path / "ja.json"
    en = tmp_path / "en.json"
    de = tmp_path / "de.json"
    ja.write_text(
        json.dumps({"ui": {"plugin_sidebar_toggle": "{title}サイドバー 表示/非表示"}}),
        encoding="utf-8",
    )
    en.write_text(
        json.dumps({"ui": {"plugin_sidebar_toggle": "Show/Hide {title} Sidebar"}}),
        encoding="utf-8",
    )
    de.write_text(
        json.dumps({"ui": {"plugin_sidebar_toggle": "{title} Leiste"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        language_manager,
        "available_languages",
        {
            **_languages(("ja", ja), ("en", en), ("de", de)),
            "system": {"name": "", "code": "ja", "file": None},
        },
    )

    assert sidebar_title_stem("商品情報") == "商品情報"
    assert sidebar_title_stem("商品情報サイドバー 表示/非表示") == "商品情報"
    assert sidebar_title_stem("Show/Hide Info Sidebar") == "Info"
    assert sidebar_title_stem("show/hide Info sidebar") == "Info"
    assert sidebar_title_stem("Info Leiste") == "Info"


def test_stem_ignores_language_file_without_template(tmp_path, monkeypatch):
    """トグル文言の無い言語ファイルがあると、剥がせないタイトルまで変わる。"""
    bare = tmp_path / "fr.json"
    bare.write_text(json.dumps({"ui": {"other": "x"}}), encoding="utf-8")
    monkeypatch.setattr(
        language_manager,
        "available_languages",
        _languages(("fr", bare)),
    )

    assert sidebar_title_stem("Info Sidebar") == "Info Sidebar"


def test_bundled_ja_en_templates_strip(monkeypatch):
    """同梱の ja と en のトグル文言が、日本語と英語のタイトルから剥がれない。"""
    langs = resources.files("ez_co.resources").joinpath("langs")
    monkeypatch.setattr(
        language_manager,
        "available_languages",
        _languages(
            ("ja", langs.joinpath("ja.json")),
            ("en", langs.joinpath("en.json")),
        ),
    )

    assert sidebar_title_stem("商品情報サイドバー 表示/非表示") == "商品情報"
    assert sidebar_title_stem("Show/Hide Info Sidebar") == "Info"


def test_toggle_label_wraps_stem(monkeypatch):
    """空のタイトルが sidebar に置き換わらず、stem がトグル文言の title に入らない。"""
    monkeypatch.setattr(
        "ez_co.plugins.host.get_text",
        lambda key, **kwargs: f"wrap:{kwargs.get('title')}",
    )
    monkeypatch.setattr(language_manager, "available_languages", {})

    assert sidebar_toggle_label("商品情報") == "wrap:商品情報"
    assert sidebar_toggle_label("") == "wrap:sidebar"

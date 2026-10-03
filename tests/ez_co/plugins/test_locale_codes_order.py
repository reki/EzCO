"""対象: ez_co.plugins.locale_codes — 言語・国の先頭順と母語ラベル。"""
from ez_co.plugins.locale_codes import country_choices, language_choices


def test_language_choices_put_ja_en_first():
    """ja と en が先頭でなく、母語のラベルが無く、残りが大文字小文字を無視した順でない。"""
    rows = language_choices()
    assert rows[0][0] == "ja"
    assert rows[1][0] == "en"
    assert "日本語" in rows[0][1]
    assert "English" in rows[1][1]
    rest = [code for code, _label in rows[2:]]
    assert rest == sorted(rest, key=str.casefold)


def test_country_choices_put_jp_first():
    """JP が先頭でなく日本のラベルが無く、残りが順不同で、US が欠ける。"""
    rows = country_choices()
    assert rows[0][0] == "JP"
    assert "日本" in rows[0][1]
    rest = [code for code, _label in rows[1:]]
    assert rest == sorted(rest, key=str.casefold)
    codes = [code for code, _label in rows]
    assert "US" in codes

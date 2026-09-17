"""対象: ez_co.plugins.charset — codec 名の先頭順。"""
from ez_co.plugins.charset import charset_names


def test_charset_names_put_common_codecs_first():
    names = charset_names()
    assert names[:4] == ("utf-8", "cp932", "shift_jis", "latin_1")
    rest = names[4:]
    assert rest == tuple(sorted(rest))
    assert names.count("utf-8") == 1
    assert "cp932" in names

"""対象: ez_co.enums.fonts"""
from ez_co.enums.fonts import FontInfo


def test_font_file_filter_uses_language_key(monkeypatch):
    """フォント選択の表示は言語キーのまま始まり、ttf と otf を含む。"""
    monkeypatch.setattr("ez_co.enums.fonts.get_text", lambda key, **kwargs: key)

    text = FontInfo.get_file_filter_string()

    assert text.startswith("ui.font_files (")
    assert "*.ttf" in text
    assert "*.otf" in text

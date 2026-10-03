"""対象: ez_co.handlers.session_file — is_session_file。"""
from ez_co.handlers.session_file import is_session_file


def test_is_session_file_by_extension():
    """拡張子 ezs は大文字でもセッションファイルで、json と png は違う。"""
    assert is_session_file("tabs.ezs") is True
    assert is_session_file("TABS.EZS") is True
    assert is_session_file("tabs.json") is False
    assert is_session_file("photo.png") is False

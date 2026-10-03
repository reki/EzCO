"""対象: ez_co.utils.language_manager"""

from ez_co.utils.language_manager import LanguageManager


def test_bundled_languages_load_from_data_subdirectory(monkeypatch):
    """同梱言語は ja と en を含み、app_name は EzCo、システム言語名は日本語の既定文言になる。"""
    monkeypatch.setattr(LanguageManager, "_load_external_language_dirs", lambda self: None)
    monkeypatch.setattr(
        "ez_co.utils.language_manager.locale.getdefaultlocale",
        lambda: ("ja_JP", "UTF-8"),
    )

    manager = LanguageManager()

    assert {"ja", "en"} <= manager.get_available_languages().keys()
    assert manager.get_text("app_name") == "EzCo"
    assert manager.get_available_languages()["system"]["name"] == "システムのデフォルト言語"


def test_system_language_name_follows_selected_language(monkeypatch):
    """システム言語名は選択中の言語に従い、英語環境では英語、ja へ切り替えると日本語になる。"""
    monkeypatch.setattr(LanguageManager, "_load_external_language_dirs", lambda self: None)
    monkeypatch.setattr(
        "ez_co.utils.language_manager.locale.getdefaultlocale",
        lambda: ("en_US", "UTF-8"),
    )

    manager = LanguageManager()

    assert manager.get_available_languages()["system"]["name"] == "System Default Language"
    manager.set_language("ja")
    assert manager.get_available_languages()["system"]["name"] == "システムのデフォルト言語"

"""対象: ez_co.utils.language_manager"""

from ez_co.utils.language_manager import LanguageManager


def test_bundled_languages_load_from_data_subdirectory(monkeypatch):
    monkeypatch.setattr(LanguageManager, "_load_external_language_dirs", lambda self: None)
    monkeypatch.setattr(
        "ez_co.utils.language_manager.locale.getdefaultlocale",
        lambda: ("ja_JP", "UTF-8"),
    )

    manager = LanguageManager()

    assert {"ja", "en"} <= manager.get_available_languages().keys()
    assert manager.get_text("app_name") == "EzCo"

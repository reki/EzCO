"""対象: ez_co.ui.dialogs.settings_dialog"""
import pytest

from ez_co.config import Config
from ez_co.ui.dialogs import settings_dialog
from ez_co.ui.dialogs.settings_dialog import SettingsDialog
from ez_co.utils.language_manager import language_manager, set_language


# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


def test_size_placeholders_follow_selected_language(monkeypatch):
    """英語を選んでも、キャッシュ上限と最適化しきい値のプレースホルダが英語の例にならない。"""
    monkeypatch.setattr(
        settings_dialog,
        "load_location_settings",
        lambda: {"data_location": "user", "custom_path": ""},
    )
    previous = language_manager.get_current_language()
    set_language("en")
    config = Config()
    config.freeze_image_loader_workers(logical_cpu_count=4)
    dialog = SettingsDialog(config)
    try:
        assert dialog.cache_memory_limit.placeholderText() == "256MB, 1GB, 2.5GB etc."
        assert dialog.optimize_threshold.placeholderText() == "50MB, 100MB etc."
    finally:
        dialog.close()
        set_language(previous)

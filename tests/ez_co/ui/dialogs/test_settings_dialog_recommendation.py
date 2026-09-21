"""対象: ez_co.ui.dialogs.settings_dialog"""
import pytest

from ez_co.config import Config
from ez_co.ui.dialogs import settings_dialog
from ez_co.ui.dialogs.settings_dialog import SettingsDialog

GIB = 1024**3

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.fixture(autouse=True)
def stub_location_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        settings_dialog,
        "load_location_settings",
        lambda: {"data_location": "user", "custom_path": ""},
    )


@pytest.fixture
def large_ram(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings_dialog, "logical_cpu_count", lambda: 24)
    monkeypatch.setattr(settings_dialog, "physical_memory_bytes", lambda: 32 * GIB)


def _dialog(config):
    config.freeze_image_loader_workers(logical_cpu_count=24)
    return SettingsDialog(config)


def test_recommended_button_only_changes_widgets(large_ram):
    config = Config.from_dict(
        {
            "cache": {
                "memory_limit": "1GB",
                "prefetch_pages": 30,
                "image_loader_workers": 8,
            }
        }
    )
    dialog = _dialog(config)
    try:
        dialog.apply_recommended_cache_settings()

        assert dialog.cache_memory_limit.text() == "512MB"
        assert dialog.cache_prefetch_pages.value() == 5
        assert dialog.cache_image_loader_workers.currentData() == "auto"
        assert config.cache["memory_limit"] == "1GB"
        assert config.cache["prefetch_pages"] == 30
        assert config.cache["image_loader_workers"] == 8
    finally:
        dialog.close()


def test_recommended_button_keeps_runtime_overridden_values(large_ram):
    config = Config.from_dict({"cache": {"memory_limit": "1GB", "prefetch_pages": 30}})
    config.set_runtime_override("cache.memory_limit", "128MB")
    dialog = _dialog(config)
    try:
        before = dialog.cache_memory_limit.text()

        dialog.apply_recommended_cache_settings()

        assert dialog.cache_memory_limit.text() == before
        assert dialog.cache_prefetch_pages.value() == 5
    finally:
        dialog.close()


def test_recommended_label_shows_auto_effective_workers_for_manual_setting(large_ram):
    config = Config.from_dict({"cache": {"image_loader_workers": 8}})
    dialog = _dialog(config)
    try:
        text = dialog.cache_recommendation_label.text()

        assert "8" in text.splitlines()[0]
        assert "512MB" in text
        assert "4" in text.splitlines()[1]
    finally:
        dialog.close()


def test_recommendation_label_survives_unknown_memory(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings_dialog, "logical_cpu_count", lambda: None)
    monkeypatch.setattr(settings_dialog, "physical_memory_bytes", lambda: None)
    config = Config()
    dialog = _dialog(config)
    try:
        text = dialog.cache_recommendation_label.text()

        assert "256MB" in text
        assert text.splitlines()[-1]
        dialog.apply_recommended_cache_settings()
        assert dialog.cache_memory_limit.text() == "256MB"
        assert dialog.cache_prefetch_pages.value() == 5
    finally:
        dialog.close()


def test_recommendation_label_follows_widget_edits(large_ram):
    config = Config()
    dialog = _dialog(config)
    try:
        dialog.cache_prefetch_pages.setValue(22)

        assert "22" in dialog.cache_recommendation_label.text().splitlines()[0]
    finally:
        dialog.close()

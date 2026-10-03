"""対象: ez_co.ui.dialogs.settings_dialog"""
import pytest

from ez_co.config import Config
from ez_co.ui.dialogs import settings_dialog
from ez_co.ui.dialogs.settings_dialog import SettingsDialog

# 1GiB のバイト数。
GIB = 1024**3

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


@pytest.fixture(autouse=True)
def stub_location_settings(monkeypatch: pytest.MonkeyPatch):
    """データ位置の読み込みをユーザー固定にし、実ファイルを触らせない。"""
    monkeypatch.setattr(
        settings_dialog,
        "load_location_settings",
        lambda: {"data_location": "user", "custom_path": ""},
    )


@pytest.fixture
def large_ram(monkeypatch: pytest.MonkeyPatch):
    """論理 CPU 24 と 32GiB を返し、大きいメモリの推奨に乗せる。"""
    monkeypatch.setattr(settings_dialog, "logical_cpu_count", lambda: 24)
    monkeypatch.setattr(settings_dialog, "physical_memory_bytes", lambda: 32 * GIB)


def _dialog(config):
    """ワーカー数を固定した設定ダイアログを開く。

    Args:
        config: ダイアログへ渡す設定。

    Returns:
        開いた設定ダイアログ。
    """
    config.freeze_image_loader_workers(logical_cpu_count=24)
    return SettingsDialog(config)


def test_recommended_button_only_changes_widgets(large_ram):
    """推奨ボタンが設定オブジェクトまで書き、ウィジェットが 512MB・先読み5・auto にならない。"""
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
    """実行時上書きのメモリ上限が推奨で変わり、上書きされていない先読みが推奨値にならない。"""
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
    """手動の 8 が現状行から消え、推奨行から 512MB か auto の実効数 4 が欠ける。"""
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
    """CPU とメモリが不明だと推奨ラベルが空になり、適用しても 256MB と先読み 5 にならない。"""
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
    """先読みを 22 に変えても、推奨ラベルの現状行にその値が入らない。"""
    config = Config()
    dialog = _dialog(config)
    try:
        dialog.cache_prefetch_pages.setValue(22)

        assert "22" in dialog.cache_recommendation_label.text().splitlines()[0]
    finally:
        dialog.close()

"""対象: ez_co.ui.dialogs.settings_dialog"""
import pytest

from ez_co.config import Config
from ez_co.ui.dialogs import settings_dialog
from ez_co.ui.dialogs.settings_dialog import SettingsDialog


# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


def test_worker_combo_matches_all_valid_config_values(monkeypatch):
    """ワーカー候補が auto と 1 から 8 以外になり、7 を選べず、実効数の表示から 4 が消える。"""
    monkeypatch.setattr(
        settings_dialog,
        "load_location_settings",
        lambda: {"data_location": "user", "custom_path": ""},
    )
    config = Config()
    config.freeze_image_loader_workers(logical_cpu_count=24)
    dialog = SettingsDialog(config)
    try:
        values = [
            dialog.cache_image_loader_workers.itemData(index)
            for index in range(dialog.cache_image_loader_workers.count())
        ]
        assert values == ["auto", 1, 2, 3, 4, 5, 6, 7, 8]
        assert "4" in dialog.cache_image_loader_workers_effective.text()

        dialog._update_ui_with_config(
            {"cache": {"image_loader_workers": 7}}
        )
        assert dialog.cache_image_loader_workers.currentData() == 7
    finally:
        dialog.close()

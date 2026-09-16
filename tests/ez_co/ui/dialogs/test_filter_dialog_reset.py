"""対象: ez_co.ui.dialogs.filter_dialog — 初期化で既定値に戻す。"""
from types import SimpleNamespace

from PySide6.QtWidgets import QWidget

import pytest

from ez_co.filters.builtin import BUILTIN_FILTER_ID, default_basic_settings
from ez_co.ui.dialogs.filter_dialog import FilterDialog
from ez_co.utils.language_manager import get_text

pytestmark = pytest.mark.usefixtures("qapp")

_CHANGED = {
    "brightness": 40,
    "contrast": -20,
    "gamma": 1.4,
    "grayscale": True,
}


class _Window(QWidget):
    def __init__(self, *, in_pipe: bool):
        super().__init__()
        self.config = SimpleNamespace(
            filters={
                "pipe": [BUILTIN_FILTER_ID] if in_pipe else [],
                "settings": {BUILTIN_FILTER_ID: dict(_CHANGED)},
            }
        )
        self.updates = 0
        self.saves = 0

    def update_image(self):
        self.updates += 1

    def save_config(self):
        self.saves += 1


def test_reset_button_uses_ui_reset():
    dialog = FilterDialog(_Window(in_pipe=False))
    assert dialog._reset_button.text() == get_text("ui.reset")


def test_reset_restores_defaults_and_previews_when_in_pipe():
    window = _Window(in_pipe=True)
    dialog = FilterDialog(window)
    dialog._reset_to_defaults()
    assert window.config.filters["settings"][BUILTIN_FILTER_ID] == default_basic_settings()
    assert dialog._brightness.value() == 0
    assert dialog._contrast.value() == 0
    assert dialog._gamma.value() == pytest.approx(1.0)
    assert dialog._grayscale.isChecked() is False
    assert window.updates == 1
    assert window.saves == 0


def test_reset_then_cancel_restores_snapshot():
    window = _Window(in_pipe=True)
    dialog = FilterDialog(window)
    dialog._reset_to_defaults()
    dialog.reject()
    assert window.config.filters["settings"][BUILTIN_FILTER_ID] == _CHANGED
    assert window.updates == 2

"""対象: ez_co.ui.dialogs.filter_dialog — 初期化で既定値に戻す。"""
from types import SimpleNamespace

from PySide6.QtWidgets import QWidget

import pytest

from ez_co.filters.builtin import BUILTIN_FILTER_ID, default_basic_settings
from ez_co.ui.dialogs.filter_dialog import FilterDialog
from ez_co.utils.language_manager import get_text

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")

# 初期化前に入っている変更済みの基本設定。
_CHANGED = {
    "brightness": 40,
    "contrast": -20,
    "gamma": 1.4,
    "grayscale": True,
}


class _Window(QWidget):
    """フィルター設定と、プレビューと保存の回数を持つ親。"""

    def __init__(self, *, in_pipe: bool):
        """pipe の有無と、変更済みの基本設定を載せる。

        Args:
            in_pipe: 基本フィルターを pipe に入れるか。
        """
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
        """プレビュー更新の回数を増やす。"""
        self.updates += 1

    def save_config(self):
        """設定保存の回数を増やす。"""
        self.saves += 1


def test_reset_button_uses_ui_reset():
    """初期化ボタンの文言が ui.reset 以外になる。"""
    dialog = FilterDialog(_Window(in_pipe=False))
    assert dialog._reset_button.text() == get_text("ui.reset")


def test_reset_restores_defaults_and_previews_when_in_pipe():
    """pipe 中の初期化で既定値かウィジェットが戻らず、プレビューが1回以外、または保存してしまう。"""
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
    """初期化のあとキャンセルしても変更値が残る、またはプレビューが戻し分を含めて2回にならない。"""
    window = _Window(in_pipe=True)
    dialog = FilterDialog(window)
    dialog._reset_to_defaults()
    dialog.reject()
    assert window.config.filters["settings"][BUILTIN_FILTER_ID] == _CHANGED
    assert window.updates == 2

"""対象: ez_co.ui.dialogs.page_slider_dialog — 空タブと handler 差し替え。"""
from types import SimpleNamespace

from PySide6.QtWidgets import QWidget

import pytest

from ez_co.ui.dialogs.page_slider_dialog import PageSliderDialog

pytestmark = pytest.mark.usefixtures("qapp")


def _handler(page_count: int, current_index: int = 0):
    return SimpleNamespace(
        current_files=[f"page_{i}" for i in range(page_count)],
        current_index=current_index,
    )


def _dialog(file_handler=None):
    return PageSliderDialog(QWidget(), file_handler)


def test_empty_handler_disables_and_clears_label():
    dialog = _dialog(SimpleNamespace(current_files=[], current_index=0))
    assert dialog.isEnabled() is False
    assert dialog.page_info_label.text() == ""
    assert dialog.page_slider.maximum() == 1
    assert dialog.page_spinbox.maximum() == 1


def test_refresh_from_book_to_empty_drops_old_page_count():
    dialog = _dialog(_handler(40, current_index=11))
    assert dialog.isEnabled() is True
    assert dialog.page_slider.maximum() == 40
    assert "12" in dialog.page_info_label.text()

    dialog.file_handler = SimpleNamespace(current_files=[], current_index=0)
    dialog.refresh()
    assert dialog.isEnabled() is False
    assert dialog.page_info_label.text() == ""
    assert dialog.page_slider.maximum() == 1
    assert dialog.page_spinbox.maximum() == 1
    assert dialog.page_slider.value() == 1


def test_refresh_rebinding_handler_shows_new_book():
    dialog = _dialog(_handler(10, current_index=0))
    dialog.file_handler = _handler(25, current_index=4)
    dialog.refresh()
    assert dialog.isEnabled() is True
    assert dialog.page_slider.maximum() == 25
    assert dialog.page_spinbox.maximum() == 25
    assert dialog.page_slider.value() == 5
    assert dialog.page_spinbox.value() == 5
    assert "5" in dialog.page_info_label.text()
    assert "25" in dialog.page_info_label.text()

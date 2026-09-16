"""対象: ez_co.ui.docks.page_slider — 結合1行と浮き窓3段。"""
from types import SimpleNamespace

from PySide6.QtWidgets import QWidget, QSizePolicy

import pytest

from ez_co.ui.docks.page_slider import PageSlider, _COMPACT_HEIGHT, _FLOATING_SIZE, _SPIN_WIDTH

pytestmark = pytest.mark.usefixtures("qapp")


def _slider():
    handler = SimpleNamespace(current_files=["a", "b", "c"], current_index=1)
    return PageSlider(QWidget(), handler)


def test_compact_is_one_row_slider_stretch_controls_fixed():
    slider = _slider()
    slider.set_compact(True)
    assert slider._compact is True
    assert slider.page_info_label.isHidden()
    assert slider.height() == _COMPACT_HEIGHT
    slider_index = slider._row.indexOf(slider.page_slider)
    spin_index = slider._row.indexOf(slider.page_spinbox)
    assert slider_index == 0
    assert spin_index == 1
    assert slider._row.stretch(slider_index) == 1
    assert slider._row.stretch(spin_index) == 0
    assert slider.page_spinbox.width() == _SPIN_WIDTH
    assert slider.page_slider.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert slider.first_button.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed
    assert slider.last_button.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed


def test_floating_keeps_three_rows_and_fixed_size():
    slider = _slider()
    slider.set_compact(False)
    assert slider.page_info_label.isHidden() is False
    assert slider._root.count() == 3
    assert slider.width() == _FLOATING_SIZE[0]
    assert slider.height() == _FLOATING_SIZE[1]
    assert slider._row.indexOf(slider.page_spinbox) == 0
    assert slider._row.indexOf(slider.page_slider) == 1


def test_compact_then_floating_does_not_raise():
    slider = _slider()
    slider.set_compact(True)
    slider.set_compact(False)
    slider.set_compact(True)
    assert slider._compact is True
    assert slider.page_info_label.isHidden()

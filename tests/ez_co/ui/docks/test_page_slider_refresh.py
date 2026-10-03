"""対象: ez_co.ui.docks.page_slider — 空タブと handler 差し替え。"""
from types import SimpleNamespace

from PySide6.QtWidgets import QWidget

import pytest

from ez_co.ui.docks.page_slider import PageSlider

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


def _handler(page_count: int, current_index: int = 0):
    """ページ数と現在位置だけを持つ handler の代わりを作る。

    Args:
        page_count: ページ数。
        current_index: 現在ページの 0 始まり添字。

    Returns:
        current_files と current_index を持つオブジェクト。
    """
    return SimpleNamespace(
        current_files=[f"page_{i}" for i in range(page_count)],
        current_index=current_index,
    )


def _slider(file_handler=None):
    """handler を載せて PageSlider を組む。

    Args:
        file_handler: 載せる handler。無ければ空。

    Returns:
        refresh を見るためのスライダー。
    """
    return PageSlider(QWidget(), file_handler)


def test_empty_handler_disables_and_clears_label():
    """ページが無いのに操作でき、ラベルや範囲に前のページ数が残る。"""
    slider = _slider(SimpleNamespace(current_files=[], current_index=0))
    assert slider.isEnabled() is False
    assert slider.page_info_label.text() == ""
    assert slider.page_slider.maximum() == 1
    assert slider.page_spinbox.maximum() == 1


def test_refresh_from_book_to_empty_drops_old_page_count():
    """本から空へ差し替えて refresh しても、以前のページ数とラベルが残る。"""
    slider = _slider(_handler(40, current_index=11))
    assert slider.isEnabled() is True
    assert slider.page_slider.maximum() == 40
    assert "12" in slider.page_info_label.text()

    slider.file_handler = SimpleNamespace(current_files=[], current_index=0)
    slider.refresh()
    assert slider.isEnabled() is False
    assert slider.page_info_label.text() == ""
    assert slider.page_slider.maximum() == 1
    assert slider.page_spinbox.maximum() == 1
    assert slider.page_slider.value() == 1


def test_refresh_rebinding_handler_shows_new_book():
    """別の本へ差し替えて refresh しても、新しいページ数と現在位置が出ない。"""
    slider = _slider(_handler(10, current_index=0))
    slider.file_handler = _handler(25, current_index=4)
    slider.refresh()
    assert slider.isEnabled() is True
    assert slider.page_slider.maximum() == 25
    assert slider.page_spinbox.maximum() == 25
    assert slider.page_slider.value() == 5
    assert slider.page_spinbox.value() == 5
    assert "5" in slider.page_info_label.text()
    assert "25" in slider.page_info_label.text()

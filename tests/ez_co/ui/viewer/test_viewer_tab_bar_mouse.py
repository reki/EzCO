"""対象: ez_co.ui.viewer.viewer_tab_bar — 右クリックはタブを選ばず親へ渡さない。"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QTabWidget, QWidget

from ez_co.ui.viewer.viewer_tab_bar import ViewerTabBar

pytestmark = pytest.mark.usefixtures("qapp")


class _Parent(QWidget):
    def __init__(self):
        super().__init__()
        self.presses = 0

    def mousePressEvent(self, event):
        self.presses += 1
        event.accept()


def test_right_click_keeps_the_current_tab_and_opens_the_menu_only(qapp):
    parent = _Parent()
    tabs = QTabWidget(parent)
    bar = ViewerTabBar()
    tabs.setTabBar(bar)
    tabs.addTab(QWidget(), "a")
    tabs.addTab(QWidget(), "b")
    menus = []
    bar.customContextMenuRequested.connect(lambda pos: menus.append(bar.tabAt(pos)))
    parent.resize(400, 200)
    tabs.resize(400, 200)
    parent.show()
    qapp.processEvents()

    QTest.mouseClick(
        bar,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
        bar.tabRect(1).center(),
    )
    qapp.processEvents()

    assert tabs.currentIndex() == 0
    assert parent.presses == 0
    assert menus == [1]

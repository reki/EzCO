"""対象: ez_co.ui.viewer.viewer_tab_bar — 右クリックはタブを選ばず親へ渡さない。"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QTabWidget, QWidget

from ez_co.ui.viewer.viewer_tab_bar import ViewerTabBar

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


class _Parent(QWidget):
    """子の右クリックが届いた回数を数える親。"""

    def __init__(self):
        """押下回数を 0 にする。"""
        super().__init__()
        self.presses = 0

    def mousePressEvent(self, event):
        """親が押下を受けた回数を増やして受け入れる。

        Args:
            event: 届いたマウス押下。
        """
        self.presses += 1
        event.accept()


def test_right_click_keeps_the_current_tab_and_opens_the_menu_only(qapp):
    """タブ1の右クリックで現在タブが移る、親が押下を受ける、またはメニュー位置がタブ1以外。"""
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

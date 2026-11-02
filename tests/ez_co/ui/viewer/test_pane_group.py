"""対象: ez_co.ui.viewer.pane_group — 1面のタブ選択。"""
import pytest
from PySide6.QtWidgets import QWidget

from ez_co.ui.viewer.pane_group import PaneGroup

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


def test_select_shows_only_that_pane():
    """選んでいないタブの画像も、同じ面に残る。"""
    group = PaneGroup()
    first = QWidget()
    second = QWidget()
    group.add_pane(first, "a")
    group.add_pane(second, "b")
    assert group.selected() is first
    assert first.parent() is not None
    assert second.parent() is None
    group.select(second)
    assert group.selected() is second
    assert second.parent() is not None
    assert first.parent() is None
    assert group.panes() == [first, second]

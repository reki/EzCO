"""対象: ez_co.ui.viewer.pane_layout — 最大4面の分割とドロップ位置。"""
import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from ez_co.ui.viewer.pane_layout import PaneLayout, zone_for_point

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


def _panes(count):
    """数だけ空のウィジェットを作る。

    Args:
        count: 作る数。

    Returns:
        ウィジェットの列。
    """
    return [QWidget() for _ in range(count)]


def test_split_right_and_down_place_the_new_pane_on_that_side():
    """右分割で新しいタブが左に残り、下分割で新しいタブが上に残る。"""
    layout = PaneLayout()
    first, second, third = _panes(3)
    layout.set_single(first)
    assert layout.split(first, "right", second) is True
    assert layout.visible_panes() == [first, second]
    assert layout.split(first, "down", third) is True
    assert layout.visible_panes() == [first, third, second]


def test_arrange_reads_left_to_right_and_drops_duplicates_and_a_fifth():
    """4分割で並びが崩れ、同じタブが2面に残り、5つ目が残る。"""
    layout = PaneLayout()
    panes = _panes(5)
    layout.arrange([panes[0], panes[2], panes[1], panes[2], panes[3], panes[4]])
    assert layout.visible_panes() == [panes[0], panes[2], panes[1], panes[3]]
    assert layout.visible_count() == 4


def test_fifth_new_pane_is_refused_but_a_visible_pane_can_move():
    """5面目が増え、すでに見えているタブを動かしても複製が残る。"""
    layout = PaneLayout()
    panes = _panes(5)
    layout.arrange(panes[:4])
    assert layout.split(panes[0], "right", panes[4]) is False
    assert layout.visible_count() == 4
    assert layout.split(panes[0], "right", panes[3]) is True
    assert layout.visible_count() == 4
    assert layout.visible_panes().count(panes[3]) == 1


def test_detach_collapses_the_empty_side():
    """面を外しても空の分割が残り、残ったタブが見えなくなる。"""
    layout = PaneLayout()
    first, second = _panes(2)
    layout.set_single(first)
    layout.split(first, "right", second)
    layout.detach(second)
    assert layout.visible_panes() == [first]


def test_replace_moves_a_visible_pane_instead_of_copying_it():
    """中央への差し替えで元の面にタブが残り、新しいタブが出ない。"""
    layout = PaneLayout()
    first, second, third = _panes(3)
    layout.set_single(first)
    layout.split(first, "right", second)
    assert layout.replace(first, third) is True
    assert layout.visible_panes() == [third, second]
    assert layout.replace(third, second) is True
    assert layout.visible_panes() == [second]


def test_zone_for_point_uses_the_center():
    """中央より右が左になり、中央の点が下になる。"""
    assert zone_for_point(100, 100, 0, 50) == "left"
    assert zone_for_point(100, 100, 99, 50) == "right"
    assert zone_for_point(100, 100, 50, 0) == "up"
    assert zone_for_point(100, 100, 50, 99) == "down"
    assert zone_for_point(100, 100, 50, 50) == "right"
    assert zone_for_point(100, 100, 40, 80) == "down"


def test_neighbor_is_the_adjacent_pane():
    """右隣が左の面になり、端の側にも隣がある。"""
    layout = PaneLayout()
    first, second = _panes(2)
    layout.set_single(first)
    layout.split(first, "right", second)
    assert layout.neighbor(first, "right") is second
    assert layout.neighbor(second, "left") is first
    assert layout.neighbor(first, "left") is None
    assert layout.neighbor(second, "right") is None


def test_pane_at_hits_the_pane_under_the_point():
    """座標の下にあるタブと違うタブを返す。"""
    layout = PaneLayout()
    first, second = _panes(2)
    layout.resize(400, 200)
    layout.set_single(first)
    layout.split(first, "right", second)
    leaves = layout._leaves()
    leaves[0].setGeometry(0, 0, 200, 200)
    leaves[1].setGeometry(200, 0, 200, 200)
    assert layout.pane_at(QPoint(20, 100)) is first
    assert layout.pane_at(QPoint(380, 100)) is second

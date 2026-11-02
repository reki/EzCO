"""対象: ez_co.ui.viewer.tab_host — 面ごとのタブ選択と分割。"""
import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from ez_co.ui.viewer.tab_host import TabHost

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


def _host(count):
    """タブを並べたホストを作る。最初の1枚だけ見えている。

    Args:
        count: タブの数。

    Returns:
        ホストと、追加した順のタブ。
    """
    host = TabHost()
    panes = [QWidget() for _ in range(count)]
    for pane in panes:
        host.addTab(pane, "tab")
    return host, panes


def test_single_pane_switch_hides_the_previous_tab():
    """1面の切り替えで、前のタブの画像も残る。"""
    host, panes = _host(3)
    host.setCurrentIndex(1)
    assert host.shown_panes() == [panes[1]]
    assert host.currentWidget() is panes[1]
    assert host._group_of(panes[0]) is host._group_of(panes[2])


def test_selecting_a_tab_does_not_replace_another_pane():
    """別の面のタブを選ぶと、その面の選択が差し替わる。"""
    host, panes = _host(3)
    assert host.split_toward("right") is True
    host.setCurrentIndex(host.indexOf(panes[2]))
    assert host.shown_panes() == [panes[2], panes[1]]
    assert host.shown_panes().count(panes[2]) == 1
    assert host.currentWidget() is panes[2]
    assert host._group_of(panes[1]).selected() is panes[1]


def test_visible_tab_becomes_the_shortcut_target_without_moving():
    """見えているタブを選ぶと、面の位置が入れ替わる。"""
    host, panes = _host(3)
    host.split_toward("right")
    host.setCurrentIndex(host.indexOf(panes[1]))
    assert host.shown_panes() == [panes[0], panes[1]]
    assert host.currentWidget() is panes[1]


def test_closing_an_unselected_tab_does_not_change_the_shortcut_target():
    """選ばれていないタブを閉じると、ショートカット対象が別のタブへ移る。"""
    host, panes = _host(3)
    host.split_toward("right")
    emitted = []
    host.currentChanged.connect(emitted.append)
    host.removeTab(host.indexOf(panes[2]))
    assert host.currentWidget() is panes[0]
    assert host.shown_panes() == [panes[0], panes[1]]
    assert emitted == []


def test_blocked_selection_keeps_the_visible_panes():
    """信号を止めた選択が、見えている面を差し替える。"""
    host, panes = _host(3)
    host.split_toward("right")
    host.blockSignals(True)
    host.setCurrentIndex(host.indexOf(panes[2]))
    host.blockSignals(False)
    assert host.shown_panes() == [panes[0], panes[1]]
    assert host.currentWidget() is panes[2]


def test_gesture_selects_its_tab_before_the_next_split():
    """ジェスチャーの開始タブが、その面で選ばれない。"""
    host, panes = _host(4)
    host.split_toward("right")
    host.note_gesture_tab(host.indexOf(panes[2]))
    assert host.shown_panes() == [panes[2], panes[1]]
    assert host.currentWidget() is panes[2]
    assert host.split_toward("down") is True
    visible = host.shown_panes()
    assert panes[2] in visible
    assert panes[3] in visible
    assert host.currentWidget() is panes[2]
    assert len(visible) == 3


def test_edge_drop_moves_only_the_dragged_tab():
    """別のタブを端へ落とすと、元の面の選択が変わる。"""
    host, panes = _host(3)
    source = host._group_of(panes[0])
    host._on_edge_drop(str(id(panes[1])), "right", source)
    assert host.shown_panes() == [panes[0], panes[1]]
    assert host._group_of(panes[0]).selected() is panes[0]
    assert panes[2] in host._group_of(panes[0]).panes()
    assert host.currentWidget() is panes[1]


def test_edge_drop_of_the_visible_tab_uses_the_left_or_right_partner():
    """見えているタブを端へ落とすと、左が無いのに右のタブと分かれない。"""
    host, panes = _host(3)
    source = host._group_of(panes[0])
    host._on_edge_drop(str(id(panes[0])), "right", source)
    assert host.shown_panes() == [panes[1], panes[0]]
    assert host._group_of(panes[1]).selected() is panes[1]
    assert panes[2] in host._group_of(panes[1]).panes()
    assert host.currentWidget() is panes[0]


def test_edge_drop_of_the_visible_tab_prefers_the_left_partner():
    """見えているタブの左にタブがあっても、右のタブと分かれる。"""
    host, panes = _host(3)
    host.setCurrentIndex(1)
    source = host._group_of(panes[1])
    host._on_edge_drop(str(id(panes[1])), "right", source)
    assert host._group_of(panes[0]).selected() is panes[0]
    assert panes[2] in host._group_of(panes[0]).panes()
    assert host.shown_panes() == [panes[0], panes[1]]
    assert host.currentWidget() is panes[1]


def test_edge_drop_without_a_partner_does_nothing():
    """相手のタブが無いのに、見えているタブの端ドロップで面が増える。"""
    host, panes = _host(1)
    host._on_edge_drop(str(id(panes[0])), "right", host._group_of(panes[0]))
    assert host.shown_panes() == [panes[0]]
    assert len(host._groups()) == 1


def test_drop_toward_an_existing_pane_adds_to_its_bar():
    """隣の面がある方向へ落とすと、新しい面が増える。"""
    host, panes = _host(3)
    source = host._group_of(panes[0])
    host._on_edge_drop(str(id(panes[1])), "right", source)
    host._on_edge_drop(str(id(panes[2])), "right", host._group_of(panes[0]))
    assert len(host._groups()) == 2
    assert host._group_of(panes[2]) is host._group_of(panes[1])
    assert host._group_of(panes[1]).selected() is panes[2]
    assert host._group_of(panes[0]).selected() is panes[0]


def test_clicking_the_selected_tab_makes_it_current():
    """選択中のタブをクリックしても、カレントが別の面のまま残る。"""
    host, panes = _host(3)
    host.split_toward("right")
    host._on_group_clicked(host._group_of(panes[1]), 0)
    assert host.currentWidget() is panes[1]
    assert host._group_of(panes[0]).selected() is panes[0]
    assert host._group_of(panes[1]).selected() is panes[1]


def test_bar_drop_moves_the_tab_and_collapses_an_empty_group():
    """別のタブバーへ落とすと、タブが複製されるか空の面が残る。"""
    host, panes = _host(2)
    host._on_edge_drop(str(id(panes[1])), "right", host._group_of(panes[0]))
    right = host._group_of(panes[1])
    host._on_bar_drop(str(id(panes[0])), right, 0)
    assert len(host._groups()) == 1
    assert host._group_of(panes[0]).panes() == [panes[0], panes[1]]
    assert host.shown_panes() == [panes[0]]


def test_split_refuses_a_fifth_pane():
    """5枚目のタブが、新しい面として出る。"""
    host, panes = _host(5)
    host.split_grid()
    assert len(host._groups()) == 4
    assert panes[4] not in host.shown_panes()
    assert host.split_toward("right") is False
    assert len(host._groups()) == 4


def test_mark_is_on_the_current_tab_before_a_split():
    """1面でタブが複数でも、カレントタブに色が付かない。"""
    host, panes = _host(3)
    host.set_current_tab_mark("#112233", 90, True)
    bar = host._group_of(panes[0]).tab_bar()
    assert bar._mark_color is not None
    assert bar._mark_color.alpha() == 90
    assert bar._mark_gradient is True
    alone, _ = _host(1)
    alone.set_current_tab_mark("#112233", 90, True)
    assert alone._groups()[0].tab_bar()._mark_color is None


def test_split_mark_is_only_on_the_shortcut_tab():
    """選ばれているだけの別の面にも、カレント色が塗られる。"""
    host, panes = _host(3)
    host.set_current_tab_mark("#112233", 90, True)
    host.split_toward("right")
    marked = host._group_of(panes[0]).tab_bar()
    other = host._group_of(panes[1]).tab_bar()
    assert marked._mark_color is not None
    assert marked._mark_color.alpha() == 90
    assert marked._mark_gradient is True
    assert other._mark_color is None


def test_one_pane_hides_a_single_tab_and_split_shows_every_bar():
    """1枚の面でタブバーが出るか、分割中なのにタブバーが隠れる。"""
    host, panes = _host(1)
    assert host._groups()[0].tab_bar().isHidden() is True
    host.addTab(QWidget(), "b")
    assert host._groups()[0].tab_bar().isHidden() is False
    host.split_toward("right")
    assert panes[0] in host.shown_panes()
    assert all(group.tab_bar().isHidden() is False for group in host._groups())
    host.set_tab_bars_allowed(False)
    assert all(group.tab_bar().isHidden() is True for group in host._groups())


def _place_panes(host, widths):
    """面の枠とタブバーへ、当たり判定に使う座標を置く。

    Args:
        host: 分割済みのホスト。
        widths: 左からの面の幅。
    """
    layout = host._layout_panes
    layout.resize(sum(widths), 200)
    x = 0
    for leaf, width in zip(layout._leaves(), widths):
        leaf.setGeometry(x, 0, width, 200)
        group = leaf.pane
        group.setGeometry(0, 0, width, 200)
        group.tab_bar().setGeometry(0, 0, width, 32)
        x += width


def test_image_drop_hits_the_tab_shown_on_that_pane():
    """画像の上なのに、別の面のタブを返す。"""
    host, panes = _host(2)
    host.split_toward("right")
    _place_panes(host, [200, 200])
    assert host.tab_at_local(QPoint(20, 100)) is panes[0]
    assert host.tab_at_local(QPoint(300, 100)) is panes[1]


def test_tab_bar_drop_hits_that_tab_and_focus_leaves_the_other_pane():
    """タブバーの別タブの上なのに見えているタブを返し、別の面の選択も変わる。"""
    host, panes = _host(3)
    host.split_toward("right")
    _place_panes(host, [400, 200])
    bar = host._group_of(panes[0]).tab_bar()
    point = bar.mapTo(host._layout_panes, bar.tabRect(1).center())
    assert host.tab_at_local(point) is panes[2]
    assert host.focus_tab_at(point) is True
    assert host.currentWidget() is panes[2]
    assert host._group_of(panes[1]).selected() is panes[1]


def test_drop_outside_the_panes_or_on_empty_bar_hits_nothing():
    """面の外やタブバーの空きが、タブを返す。"""
    host, panes = _host(2)
    host.split_toward("right")
    _place_panes(host, [400, 200])
    assert host.tab_at_local(QPoint(700, 40)) is None
    bar = host._group_of(panes[0]).tab_bar()
    empty = bar.mapTo(host._layout_panes, QPoint(360, 8))
    assert host.tab_at_local(empty) is None
    assert host.focus_tab_at(empty) is False
    assert host.currentWidget() is panes[0]

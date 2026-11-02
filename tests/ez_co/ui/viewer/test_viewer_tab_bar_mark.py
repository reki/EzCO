"""対象: ez_co.ui.viewer.viewer_tab_bar — カレントタブの色。"""
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor

from ez_co.ui.viewer.viewer_tab_bar import (
    ViewerTabBar,
    current_tab_mark_brush,
    current_tab_mark_color,
)


def test_mark_color_uses_the_configured_color_and_alpha():
    """カレントタブの色か透過度が、設定と違う。"""
    color = current_tab_mark_color("#3a7bd5", 170)
    assert color is not None
    assert color.alpha() == 170
    color = current_tab_mark_color("#112233", 90)
    assert color is not None
    assert color.name() == QColor("#112233").name()
    assert color.alpha() == 90


def test_invalid_mark_falls_back_and_alpha_is_clamped():
    """読めない色や範囲外の透過度が、そのまま塗る値になる。"""
    color = current_tab_mark_color("not-a-color", 999)
    assert color is not None
    assert color.name() == QColor("#3a7bd5").name()
    assert color.alpha() == 255
    assert current_tab_mark_color("#112233", "nope").alpha() == 170


def test_marked_tab_paints_without_error(qapp):
    """分割中の色を塗る途中で描画が例外になる。"""
    bar = ViewerTabBar()
    bar.addTab("a")
    bar.addTab("b")
    bar.set_current_mark(current_tab_mark_color("#112233", 90))
    bar.resize(400, 40)
    bar.grab()


def test_gradient_brush_fades_to_clear_on_the_right():
    """グラデーションの右端が、設定の透過度のまま残る。"""
    color = QColor("#112233")
    color.setAlpha(90)
    brush = current_tab_mark_brush(QRect(0, 0, 100, 20), color, True)
    stops = brush.gradient().stops()
    assert stops[0][1].alpha() == 90
    assert stops[-1][1].alpha() == 0


def test_solid_brush_keeps_one_color():
    """グラデーションを切ると、塗る色が無くなる。"""
    color = QColor("#112233")
    color.setAlpha(90)
    brush = current_tab_mark_brush(QRect(0, 0, 100, 20), color, False)
    assert brush.gradient() is None
    assert brush.color().alpha() == 90


def test_gradient_mark_paints_without_error(qapp):
    """グラデーションを塗る途中で描画が例外になる。"""
    bar = ViewerTabBar()
    bar.addTab("a")
    bar.set_current_mark(current_tab_mark_color("#112233", 90), True)
    bar.resize(200, 40)
    bar.grab()

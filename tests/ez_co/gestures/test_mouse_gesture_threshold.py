"""対象: ez_co.gestures.mouse_gesture — 閾値未満は方向なし。"""
from PySide6.QtCore import QPoint

from ez_co.gestures.mouse_gesture import MouseGesture


def test_below_threshold_has_no_direction():
    gesture = MouseGesture()
    gesture.start(QPoint(0, 0))
    gesture.update(QPoint(10, 10))
    assert gesture.end() is None
    assert gesture.directions == []


def test_exactly_threshold_counts():
    gesture = MouseGesture()
    gesture.start(QPoint(0, 0))
    gesture.update(QPoint(50, 0))
    assert gesture.end() is not None

"""対象: ez_co.gestures.mouse_gesture — 閾値超えの ←→↑↓。"""
from PySide6.QtCore import QPoint

from ez_co.enums.arrows import Arrow
from ez_co.gestures.mouse_gesture import MouseGesture


def _stroke(dx, dy):
    gesture = MouseGesture()
    gesture.start(QPoint(0, 0))
    gesture.update(QPoint(dx, dy))
    return gesture.end()


def test_direction_right():
    assert _stroke(60, 0) == Arrow.RIGHT.value


def test_direction_left():
    assert _stroke(-60, 0) == Arrow.LEFT.value


def test_direction_down():
    assert _stroke(0, 60) == Arrow.DOWN.value


def test_direction_up():
    assert _stroke(0, -60) == Arrow.UP.value

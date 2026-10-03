"""対象: ez_co.gestures.mouse_gesture — 閾値超えの ←→↑↓。"""
from PySide6.QtCore import QPoint

from ez_co.enums.arrows import Arrow
from ez_co.gestures.mouse_gesture import MouseGesture


def _stroke(dx, dy):
    """原点から差分だけ動かしたジェスチャの終了結果を返す。

    Args:
        dx: 横方向の移動量。
        dy: 縦方向の移動量。

    Returns:
        終了時の方向。方向が無ければ None。
    """
    gesture = MouseGesture()
    gesture.start(QPoint(0, 0))
    gesture.update(QPoint(dx, dy))
    return gesture.end()


def test_direction_right():
    """右へ閾値を超えると右矢印になる。"""
    assert _stroke(60, 0) == Arrow.RIGHT.value


def test_direction_left():
    """左へ閾値を超えると左矢印になる。"""
    assert _stroke(-60, 0) == Arrow.LEFT.value


def test_direction_down():
    """下へ閾値を超えると下矢印になる。"""
    assert _stroke(0, 60) == Arrow.DOWN.value


def test_direction_up():
    """上へ閾値を超えると上矢印になる。"""
    assert _stroke(0, -60) == Arrow.UP.value

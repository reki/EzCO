"""対象: ez_co.enums.keyboard_keys — 修飾キー単体。"""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from ez_co.enums.keyboard_keys import key_to_string


def test_control_press_and_release_are_standalone_shortcuts():
    press = QKeyEvent(QEvent.KeyPress, Qt.Key_Control, Qt.ControlModifier)
    release = QKeyEvent(QEvent.KeyRelease, Qt.Key_Control, Qt.NoModifier)
    assert key_to_string(press) == "Ctrl"
    assert key_to_string(release) == "Ctrl"

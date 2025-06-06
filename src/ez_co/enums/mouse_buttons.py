from enum import Enum

class MouseButtons(Enum):
    """マウスボタンとイベントの定数"""
    LEFT = "MouseLeft"
    RIGHT = "MouseRight"
    MIDDLE = "MouseMiddle"
    X1 = "MouseX1"
    X2 = "MouseX2"
    WHEEL_UP = "MouseWheelUp"
    WHEEL_DOWN = "MouseWheelDown"
    DOUBLE = "MouseDouble"

# 後方互換性のためのリスト
MOUSE_BUTTON_LIST = [button.value for button in MouseButtons]
MOUSE_BUTTON_VALUES = set(MOUSE_BUTTON_LIST) 
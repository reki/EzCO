"""マウスボタンとホイールイベントの定数。"""
from enum import Enum

class MouseButtons(Enum):
    """マウスボタンとイベントの定数"""
    # 左ボタン
    LEFT = "MouseLeft"
    # 右ボタン
    RIGHT = "MouseRight"
    # 中ボタン
    MIDDLE = "MouseMiddle"
    # 拡張ボタン 1
    X1 = "MouseX1"
    # 拡張ボタン 2
    X2 = "MouseX2"
    # ホイール上
    WHEEL_UP = "MouseWheelUp"
    # ホイール下
    WHEEL_DOWN = "MouseWheelDown"
    # ダブルクリック
    DOUBLE = "MouseDouble"

# 後方互換性のためのリスト
MOUSE_BUTTON_LIST = [button.value for button in MouseButtons]
# マウスボタン値の集合
MOUSE_BUTTON_VALUES = set(MOUSE_BUTTON_LIST)

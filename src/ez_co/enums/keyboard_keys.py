from enum import Enum
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

class ModifierKeys(Enum):
    """修飾キーの定数"""
    CTRL = "Ctrl"
    ALT = "Alt"
    SHIFT = "Shift"
    META = "Meta"

class KeyboardKeys(Enum):
    """キーボードキーの定数"""
    # 矢印キー
    LEFT = "Left"
    RIGHT = "Right"
    UP = "Up"
    DOWN = "Down"
    
    # 特殊キー
    RETURN = "Return"
    ESCAPE = "Escape"
    SPACE = "Space"
    TAB = "Tab"
    BACKSPACE = "Backspace"
    DELETE = "Delete"
    HOME = "Home"
    END = "End"
    PAGE_UP = "PageUp"
    PAGE_DOWN = "PageDown"
    
    # ファンクションキー
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"
    F5 = "F5"
    F6 = "F6"
    F7 = "F7"
    F8 = "F8"
    F9 = "F9"
    F10 = "F10"
    F11 = "F11"
    F12 = "F12"
    
    # 記号キー
    PLUS = "+"
    MINUS = "-"
    EQUAL = "="
    
    # 数字キー
    KEY_0 = "0"
    KEY_1 = "1"
    KEY_2 = "2"
    KEY_3 = "3"
    KEY_4 = "4"
    KEY_5 = "5"
    KEY_6 = "6"
    KEY_7 = "7"
    KEY_8 = "8"
    KEY_9 = "9"
    
    # アルファベットキー
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    H = "H"
    I = "I"
    J = "J"
    K = "K"
    L = "L"
    M = "M"
    N = "N"
    O = "O"
    P = "P"
    Q = "Q"
    R = "R"
    S = "S"
    T = "T"
    U = "U"
    V = "V"
    W = "W"
    X = "X"
    Y = "Y"
    Z = "Z"

# QtキーからKeyboardKeysへのマッピング
QT_KEY_TO_KEYBOARD_KEY = {
    Qt.Key_Left: KeyboardKeys.LEFT,
    Qt.Key_Right: KeyboardKeys.RIGHT,
    Qt.Key_Up: KeyboardKeys.UP,
    Qt.Key_Down: KeyboardKeys.DOWN,
    Qt.Key_Return: KeyboardKeys.RETURN,
    Qt.Key_Escape: KeyboardKeys.ESCAPE,
    Qt.Key_Space: KeyboardKeys.SPACE,
    Qt.Key_Tab: KeyboardKeys.TAB,
    Qt.Key_Backspace: KeyboardKeys.BACKSPACE,
    Qt.Key_Delete: KeyboardKeys.DELETE,
    Qt.Key_Home: KeyboardKeys.HOME,
    Qt.Key_End: KeyboardKeys.END,
    Qt.Key_PageUp: KeyboardKeys.PAGE_UP,
    Qt.Key_PageDown: KeyboardKeys.PAGE_DOWN,
    Qt.Key_F1: KeyboardKeys.F1,
    Qt.Key_F2: KeyboardKeys.F2,
    Qt.Key_F3: KeyboardKeys.F3,
    Qt.Key_F4: KeyboardKeys.F4,
    Qt.Key_F5: KeyboardKeys.F5,
    Qt.Key_F6: KeyboardKeys.F6,
    Qt.Key_F7: KeyboardKeys.F7,
    Qt.Key_F8: KeyboardKeys.F8,
    Qt.Key_F9: KeyboardKeys.F9,
    Qt.Key_F10: KeyboardKeys.F10,
    Qt.Key_F11: KeyboardKeys.F11,
    Qt.Key_F12: KeyboardKeys.F12,
    Qt.Key_Plus: KeyboardKeys.PLUS,
    Qt.Key_Minus: KeyboardKeys.MINUS,
    Qt.Key_Equal: KeyboardKeys.EQUAL,
    Qt.Key_0: KeyboardKeys.KEY_0,
    Qt.Key_1: KeyboardKeys.KEY_1,
    Qt.Key_2: KeyboardKeys.KEY_2,
    Qt.Key_3: KeyboardKeys.KEY_3,
    Qt.Key_4: KeyboardKeys.KEY_4,
    Qt.Key_5: KeyboardKeys.KEY_5,
    Qt.Key_6: KeyboardKeys.KEY_6,
    Qt.Key_7: KeyboardKeys.KEY_7,
    Qt.Key_8: KeyboardKeys.KEY_8,
    Qt.Key_9: KeyboardKeys.KEY_9,
    Qt.Key_A: KeyboardKeys.A,
    Qt.Key_B: KeyboardKeys.B,
    Qt.Key_C: KeyboardKeys.C,
    Qt.Key_D: KeyboardKeys.D,
    Qt.Key_E: KeyboardKeys.E,
    Qt.Key_F: KeyboardKeys.F,
    Qt.Key_G: KeyboardKeys.G,
    Qt.Key_H: KeyboardKeys.H,
    Qt.Key_I: KeyboardKeys.I,
    Qt.Key_J: KeyboardKeys.J,
    Qt.Key_K: KeyboardKeys.K,
    Qt.Key_L: KeyboardKeys.L,
    Qt.Key_M: KeyboardKeys.M,
    Qt.Key_N: KeyboardKeys.N,
    Qt.Key_O: KeyboardKeys.O,
    Qt.Key_P: KeyboardKeys.P,
    Qt.Key_Q: KeyboardKeys.Q,
    Qt.Key_R: KeyboardKeys.R,
    Qt.Key_S: KeyboardKeys.S,
    Qt.Key_T: KeyboardKeys.T,
    Qt.Key_U: KeyboardKeys.U,
    Qt.Key_V: KeyboardKeys.V,
    Qt.Key_W: KeyboardKeys.W,
    Qt.Key_X: KeyboardKeys.X,
    Qt.Key_Y: KeyboardKeys.Y,
    Qt.Key_Z: KeyboardKeys.Z,
}

def key_to_string(event: QKeyEvent) -> str:
    """統一されたキーイベントを文字列に変換するメソッド"""
    modifiers = []
    if event.modifiers() & Qt.ControlModifier:
        modifiers.append(ModifierKeys.CTRL.value)
    if event.modifiers() & Qt.AltModifier:
        modifiers.append(ModifierKeys.ALT.value)
    if event.modifiers() & Qt.ShiftModifier:
        modifiers.append(ModifierKeys.SHIFT.value)
    if event.modifiers() & Qt.MetaModifier:
        modifiers.append(ModifierKeys.META.value)
    
    key = event.key()
    
    # QTキーからKeyboardKeysにマッピング
    if key in QT_KEY_TO_KEYBOARD_KEY:
        key_text = QT_KEY_TO_KEYBOARD_KEY[key].value
    else:
        return ""
    
    if modifiers:
        return "+".join(modifiers + [key_text])
    else:
        return key_text

# 後方互換性のためのリスト
KEYBOARD_KEY_LIST = [key.value for key in KeyboardKeys]
MODIFIER_KEY_LIST = [key.value for key in ModifierKeys] 
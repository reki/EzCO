"""方向を表す矢印。"""
from enum import Enum
class Arrow(Enum):
    """上下左右の矢印。"""
    # 左向きの矢印
    LEFT = '←'
    # 右向きの矢印
    RIGHT = '→'
    # 上向きの矢印
    UP = '↑'
    # 下向きの矢印
    DOWN = '↓'

"""タブの閉じる対象、固定の並び、コピー文字列。Qt は使わない。"""
from __future__ import annotations

from pathlib import Path


def close_other_indexes(index: int, pinned: list[bool]) -> list[int]:
    """このタブ以外の未固定タブを、大きい番号から返す。

    Args:
        index: 残すタブの番号。
        pinned: 各タブが固定されているか。

    Returns:
        閉じるタブの番号。範囲外、またはタブが1つ以下なら空。
    """
    count = len(pinned)
    if count <= 1 or not 0 <= index < count:
        return []
    return [
        item
        for item in range(count - 1, -1, -1)
        if item != index and not pinned[item]
    ]


def close_right_indexes(index: int, pinned: list[bool]) -> list[int]:
    """右側の未固定タブを、大きい番号から返す。

    Args:
        index: 基準にするタブの番号。
        pinned: 各タブが固定されているか。

    Returns:
        右側の未固定タブの番号。範囲外なら空。
    """
    count = len(pinned)
    if not 0 <= index < count:
        return []
    return [item for item in range(count - 1, index, -1) if not pinned[item]]


def close_left_indexes(index: int, pinned: list[bool]) -> list[int]:
    """左側の未固定タブを、大きい番号から返す。

    Args:
        index: 基準にするタブの番号。
        pinned: 各タブが固定されているか。

    Returns:
        左側の未固定タブの番号。範囲外なら空。
    """
    count = len(pinned)
    if not 0 <= index < count:
        return []
    return [item for item in range(index - 1, -1, -1) if not pinned[item]]


def tab_menu_state(index: int, pinned: list[bool], path: str | None) -> dict:
    """右クリック項目の有効状態。閉じる対象が無い項目は無効。

    Args:
        index: 対象タブの番号。
        pinned: 各タブが固定されているか。
        path: コピーに使うパス。無ければ None。

    Returns:
        close_others_enabled、close_right_enabled、close_left_enabled、pinned、copy_enabled を持つ辞書。
    """
    in_range = 0 <= index < len(pinned)
    return {
        "close_others_enabled": bool(close_other_indexes(index, pinned)),
        "close_right_enabled": bool(close_right_indexes(index, pinned)),
        "close_left_enabled": bool(close_left_indexes(index, pinned)),
        "pinned": bool(pinned[index]) if in_range else False,
        "copy_enabled": bool(path),
    }


def tab_copy_texts(path: str | None) -> tuple[str, str] | None:
    """ファイル名と、渡されたパス文字列。パスが無ければ None。

    Args:
        path: コピーするパス。無ければ None。

    Returns:
        ファイル名とパス文字列の組。path が空なら None。
    """
    if not path:
        return None
    return (Path(path).name, str(path))


def regroup_order(pinned: list[bool]) -> list[int]:
    """固定を左、未固定を右にしたときの、元の番号の並び。それぞれの相対順は保つ。

    Args:
        pinned: 各タブが固定されているか。

    Returns:
        並べ直したあとの、元の番号。
    """
    pinned_indexes = [item for item, flag in enumerate(pinned) if flag]
    unpinned_indexes = [item for item, flag in enumerate(pinned) if not flag]
    return pinned_indexes + unpinned_indexes


def pin_selection(operated_index: int, current_index: int) -> int:
    """固定のあと選ぶ元の番号。操作したタブが現在タブでなければ現在タブ。

    Args:
        operated_index: 固定を切り替えたタブの番号。
        current_index: 現在のタブの番号。

    Returns:
        操作したタブが現在タブならその番号。そうでなければ現在タブの番号。
    """
    if operated_index == current_index:
        return operated_index
    return current_index


def regroup_current(pinned: list[bool], current: int) -> int:
    """並べ直したあとの、同じタブの番号。

    Args:
        pinned: 並べ直す前の固定状態。
        current: 並べ直す前の現在タブの番号。

    Returns:
        並べ直したあとの同じタブの番号。範囲外なら 0。
    """
    order = regroup_order(pinned)
    if not order or not 0 <= current < len(order):
        return 0
    return order.index(current)


def snap_pinned_drop(pinned_after: list[bool], to_index: int) -> int | None:
    """ドラッグ後の位置が固定グループの外なら、戻す先の番号。正しければ None。

    Args:
        pinned_after: ドロップ直後の固定状態。
        to_index: ドロップ先の番号。

    Returns:
        戻す先の番号。範囲外、または位置が正しいときは None。
    """
    count = len(pinned_after)
    if not 0 <= to_index < count:
        return None
    moving_pinned = bool(pinned_after[to_index])
    pin_count = sum(
        1 for item, flag in enumerate(pinned_after) if item != to_index and flag
    )
    if moving_pinned:
        if to_index <= pin_count:
            return None
        return pin_count
    if to_index >= pin_count:
        return None
    return pin_count

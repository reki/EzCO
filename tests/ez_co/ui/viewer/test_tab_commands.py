"""対象: ez_co.ui.viewer.tab_commands"""
from ez_co.ui.viewer.tab_commands import (
    close_left_indexes,
    close_other_indexes,
    close_right_indexes,
    pin_selection,
    regroup_current,
    regroup_order,
    snap_pinned_drop,
    tab_copy_texts,
    tab_menu_state,
)


def test_close_indexes_run_from_high_to_low():
    """一括閉じの添字が昇順になり、端や1枚だけでも閉じる対象が残る。"""
    unpinned = [False, False, False, False]
    assert close_other_indexes(1, unpinned) == [3, 2, 0]
    assert close_right_indexes(1, unpinned) == [3, 2]
    assert close_left_indexes(1, unpinned) == [0]
    assert close_other_indexes(0, [False]) == []
    assert close_right_indexes(3, unpinned) == []
    assert close_left_indexes(0, unpinned) == []


def test_bulk_close_skips_pinned_tabs():
    """ピン留めのタブが一括閉じの添字に入る。"""
    pinned = [True, False, True, False]
    assert close_other_indexes(1, pinned) == [3]
    assert close_right_indexes(1, pinned) == [3]
    assert close_left_indexes(1, pinned) == []
    assert close_other_indexes(0, [True, True, False, False]) == [3, 2]
    assert close_right_indexes(0, [True, True, False]) == [2]
    assert close_left_indexes(3, pinned) == [1]


def test_menu_state_disables_edges_and_empty_copy():
    """端や唯一の未ピン、空パスで一括閉じとコピーが有効になり、中央のピンで無効のまま。"""
    only = tab_menu_state(0, [False], None)
    assert only["close_others_enabled"] is False
    assert only["close_right_enabled"] is False
    assert only["close_left_enabled"] is False
    assert only["copy_enabled"] is False

    middle = tab_menu_state(1, [False, True, False], r"C:\books\a.zip")
    assert middle["close_others_enabled"] is True
    assert middle["close_right_enabled"] is True
    assert middle["close_left_enabled"] is True
    assert middle["pinned"] is True
    assert middle["copy_enabled"] is True

    only_pins_beside = tab_menu_state(1, [True, False], None)
    assert only_pins_beside["close_others_enabled"] is False
    assert only_pins_beside["close_left_enabled"] is False
    assert only_pins_beside["close_right_enabled"] is False


def test_copy_texts_use_the_given_path():
    """空パスでもコピー文が出て、パスがあるときはファイル名とフルパスが欠ける。"""
    assert tab_copy_texts(None) is None
    assert tab_copy_texts("") is None
    assert tab_copy_texts(r"C:\books\a.zip") == ("a.zip", r"C:\books\a.zip")


def test_pin_keeps_another_tab_current():
    """ピンするタブが現在タブでも別タブでも、現在位置の添字が変わる。"""
    assert pin_selection(2, 0) == 0
    assert pin_selection(0, 0) == 0


def test_regroup_keeps_relative_order_and_current_tab():
    """ピンを前へ集めるとき、ピン同士か未ピン同士の並び、または現在タブの新しい位置が崩れる。"""
    pinned = [False, True, False, True]
    assert regroup_order(pinned) == [1, 3, 0, 2]
    assert regroup_current(pinned, 0) == 2
    assert regroup_current(pinned, 1) == 0
    assert regroup_order([True, True, False]) == [0, 1, 2]


def test_snap_returns_the_edge_of_the_pin_group():
    """未ピンをピン群へ落とす位置が端以外になり、ピン同士や未ピン同士でも吸着する。"""
    assert snap_pinned_drop([False, True, True, False], 0) == 2
    assert snap_pinned_drop([True, False, True], 2) == 1
    assert snap_pinned_drop([True, False, False], 2) is None
    assert snap_pinned_drop([True, True, False], 1) is None
    assert snap_pinned_drop([False, False], 1) is None
    assert snap_pinned_drop([True, True], 0) is None

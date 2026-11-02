"""対象: ez_co.enums.config_defaults — 同じ値のメンバーと、生成後の代入。"""
import pytest

from ez_co.enums.config_defaults import ViewerDefaults


def test_same_value_members_stay_distinct():
    """同じ初期値のメンバーが、一つのメンバーに潰れる。"""
    left = ViewerDefaults.FIT_TO_WINDOW
    right = ViewerDefaults.MOUSE_LOCK
    assert left is not right
    assert left.name == "FIT_TO_WINDOW"
    assert right.name == "MOUSE_LOCK"
    assert left.default is False
    assert right.default is False


def test_current_tab_defaults_are_orange_and_45():
    """カレントタブの初期色か透過度が、指定と違う。"""
    assert ViewerDefaults.CURRENT_TAB_COLOR.default == "#d5822f"
    assert ViewerDefaults.CURRENT_TAB_ALPHA.default == 45


def test_member_reassignment_is_rejected():
    """生成後にメンバーを別の値へ代入できる。"""
    with pytest.raises(AttributeError):
        ViewerDefaults.CURRENT_TAB_COLOR = "#ffffff"


def test_default_reassignment_is_rejected():
    """生成後に初期値へ代入できる。"""
    with pytest.raises(AttributeError):
        ViewerDefaults.CURRENT_TAB_COLOR.default = "#ffffff"

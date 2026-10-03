"""対象: ez_co.plugins.host — coerce_config_value（bool / int / color / date / choice / range）。"""
from datetime import datetime, timezone

from ez_co.plugins.host import coerce_config_value


def test_coerce_bool():
    """yes が真にならず、0 が偽にならず、解釈できない値が default に戻らない。"""
    assert coerce_config_value("bool", True) is True
    assert coerce_config_value("bool", "yes") is True
    assert coerce_config_value("bool", "0") is False
    assert coerce_config_value("bool", "maybe", default=True) is True


def test_coerce_int():
    """数字の文字列が int にならず、解釈できない値が default、無ければ 0 に戻らない。"""
    assert coerce_config_value("int", "12") == 12
    assert coerce_config_value("int", "x", default=3) == 3
    assert coerce_config_value("int", "x") == 0


def test_coerce_color():
    """#ABC が #aabbcc にならず、ff00aa に # が付かず、不正な色が #000000 にならない。"""
    assert coerce_config_value("color", "#ABC") == "#aabbcc"
    assert coerce_config_value("color", "ff00aa") == "#ff00aa"
    assert coerce_config_value("color", "nope") == "#000000"


def test_coerce_date_to_utc_midnight():
    """日付文字列が UTC のその日 0 時にならない。"""
    seconds = coerce_config_value("date", "2020-01-02")
    moment = datetime.fromtimestamp(seconds, tz=timezone.utc)
    assert moment.year == 2020
    assert moment.month == 1
    assert moment.day == 2
    assert moment.hour == 0


def test_coerce_choice():
    """候補外の値が default、無ければ先頭の候補に戻らない。"""
    choices = [("a", "A"), ("b", "B")]
    assert coerce_config_value("choice", "b", choices=choices) == "b"
    assert coerce_config_value("choice", "z", default="a", choices=choices) == "a"
    assert coerce_config_value("choice", "z", choices=choices) == "a"


def test_coerce_charset_falls_back_to_default_then_utf8():
    """候補にある cp932 が通り、候補外が default、それも無ければ utf-8 にならない。"""
    choices = [("utf-8", "utf-8"), ("cp932", "cp932")]
    assert coerce_config_value("charset", "cp932", choices=choices) == "cp932"
    assert coerce_config_value("charset", "nope", default="cp932", choices=choices) == "cp932"
    assert coerce_config_value("charset", "nope", choices=choices) == "utf-8"


def test_coerce_int_range_clamps_and_snaps():
    """上限超えが最大、下限未満が最小、刻みから外れた値が近い刻みに寄らない。"""
    assert coerce_config_value("int_range", 150, minimum=0, maximum=100, step=1) == 100
    assert coerce_config_value("int_range", -4, minimum=0, maximum=100, step=1) == 0
    assert coerce_config_value("int_range", 5, minimum=0, maximum=10, step=3) == 6


def test_coerce_int_range_missing_bounds_defaults():
    """範囲を省略した 200 が 100 にならず、解釈できない値が default に戻らない。"""
    assert coerce_config_value("int_range", 200) == 100
    assert coerce_config_value("int_range", "nope", default=12) == 12


def test_coerce_float_range_snaps():
    """1.03 が刻み 0.05 の 1.05 に寄らない。"""
    value = coerce_config_value(
        "float_range", 1.03, minimum=0.2, maximum=3.0, step=0.05
    )
    assert value == 1.05


def test_coerce_float_range_rounds_to_step_decimals():
    """刻みの小数桁に揃わず、1.19 と 1.21 が 1.2 にならない。"""
    assert coerce_config_value("float_range", 1.19, minimum=0.0, maximum=3.0, step=0.05) == 1.2
    assert coerce_config_value("float_range", 1.21, minimum=0.0, maximum=3.0, step=0.05) == 1.2
    assert coerce_config_value("float_range", 1.2, minimum=0.0, maximum=3.0, step=0.05) == 1.2


def test_coerce_path_and_password_are_strings():
    """path の None が default にならず、password の None が空文字、数値が文字列にならない。"""
    assert coerce_config_value("path", None, default="/tmp") == "/tmp"
    assert coerce_config_value("password", None) == ""
    assert coerce_config_value("password", 12) == "12"

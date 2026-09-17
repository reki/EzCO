"""対象: ez_co.plugins.host — coerce_config_value（bool / int / color / date / choice / range）。"""
from datetime import datetime, timezone

from ez_co.plugins.host import coerce_config_value


def test_coerce_bool():
    assert coerce_config_value("bool", True) is True
    assert coerce_config_value("bool", "yes") is True
    assert coerce_config_value("bool", "0") is False
    assert coerce_config_value("bool", "maybe", default=True) is True


def test_coerce_int():
    assert coerce_config_value("int", "12") == 12
    assert coerce_config_value("int", "x", default=3) == 3
    assert coerce_config_value("int", "x") == 0


def test_coerce_color():
    assert coerce_config_value("color", "#ABC") == "#aabbcc"
    assert coerce_config_value("color", "ff00aa") == "#ff00aa"
    assert coerce_config_value("color", "nope") == "#000000"


def test_coerce_date_to_utc_midnight():
    seconds = coerce_config_value("date", "2020-01-02")
    moment = datetime.fromtimestamp(seconds, tz=timezone.utc)
    assert moment.year == 2020
    assert moment.month == 1
    assert moment.day == 2
    assert moment.hour == 0


def test_coerce_choice():
    choices = [("a", "A"), ("b", "B")]
    assert coerce_config_value("choice", "b", choices=choices) == "b"
    assert coerce_config_value("choice", "z", default="a", choices=choices) == "a"
    assert coerce_config_value("choice", "z", choices=choices) == "a"


def test_coerce_charset_falls_back_to_default_then_utf8():
    choices = [("utf-8", "utf-8"), ("cp932", "cp932")]
    assert coerce_config_value("charset", "cp932", choices=choices) == "cp932"
    assert coerce_config_value("charset", "nope", default="cp932", choices=choices) == "cp932"
    assert coerce_config_value("charset", "nope", choices=choices) == "utf-8"


def test_coerce_int_range_clamps_and_snaps():
    assert coerce_config_value("int_range", 150, minimum=0, maximum=100, step=1) == 100
    assert coerce_config_value("int_range", -4, minimum=0, maximum=100, step=1) == 0
    assert coerce_config_value("int_range", 5, minimum=0, maximum=10, step=3) == 6


def test_coerce_int_range_missing_bounds_defaults():
    assert coerce_config_value("int_range", 200) == 100
    assert coerce_config_value("int_range", "nope", default=12) == 12


def test_coerce_float_range_snaps():
    value = coerce_config_value(
        "float_range", 1.03, minimum=0.2, maximum=3.0, step=0.05
    )
    assert value == 1.05


def test_coerce_float_range_rounds_to_step_decimals():
    assert coerce_config_value("float_range", 1.19, minimum=0.0, maximum=3.0, step=0.05) == 1.2
    assert coerce_config_value("float_range", 1.21, minimum=0.0, maximum=3.0, step=0.05) == 1.2
    assert coerce_config_value("float_range", 1.2, minimum=0.0, maximum=3.0, step=0.05) == 1.2


def test_coerce_path_and_password_are_strings():
    assert coerce_config_value("path", None, default="/tmp") == "/tmp"
    assert coerce_config_value("password", None) == ""
    assert coerce_config_value("password", 12) == "12"

"""対象: ez_co.plugins.host — coerce_config_value（bool / int / color / date / choice）。"""
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

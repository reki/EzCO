"""対象: ez_co.utils.image_loader_workers"""
import pytest

from ez_co.utils.image_loader_workers import (
    normalize_image_loader_workers,
    resolve_image_loader_workers,
)


@pytest.mark.parametrize(
    ("cpu_count", "expected"),
    [(2, 1), (8, 2), (12, 3), (24, 4), (28, 5), (40, 6)],
)
def test_auto_uses_conservative_cpu_buckets(cpu_count, expected):
    assert resolve_image_loader_workers("auto", cpu_count) == expected


@pytest.mark.parametrize("workers", range(1, 9))
def test_all_manual_values_are_preserved(workers):
    assert normalize_image_loader_workers(workers) == workers
    assert resolve_image_loader_workers(workers, 2) == workers


@pytest.mark.parametrize(
    "value",
    [None, "", "invalid", 0, -1, 9, True, False, 1.5],
)
def test_invalid_values_fall_back_to_auto(value):
    assert normalize_image_loader_workers(value) == "auto"


def test_numeric_string_is_normalized_for_command_line_input():
    assert normalize_image_loader_workers(" 7 ") == 7


def test_unknown_cpu_count_uses_three_workers():
    assert resolve_image_loader_workers("auto", None) == 3

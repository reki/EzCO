"""対象: ez_co.utils.system_resources"""
import sys

import pytest

from ez_co.utils import system_resources


def test_logical_cpu_count_returns_positive_or_none():
    count = system_resources.logical_cpu_count()
    assert count is None or count >= 1


def test_logical_cpu_count_is_none_when_os_reports_zero(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(system_resources.os, "cpu_count", lambda: 0)
    assert system_resources.logical_cpu_count() is None


def test_logical_cpu_count_is_none_when_os_raises(monkeypatch: pytest.MonkeyPatch):
    def raise_os_error():
        raise OSError("unavailable")

    monkeypatch.setattr(system_resources.os, "cpu_count", raise_os_error)
    assert system_resources.logical_cpu_count() is None


def test_memory_and_rss_are_none_on_non_windows(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(system_resources.sys, "platform", "linux")
    assert system_resources.physical_memory_bytes() is None
    assert system_resources.process_resident_bytes() is None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows API only")
def test_physical_memory_and_rss_are_positive_on_windows():
    total = system_resources.physical_memory_bytes()
    resident = system_resources.process_resident_bytes()
    assert total is not None and total > 0
    assert resident is not None and resident > 0


@pytest.mark.skipif(sys.platform != "win32", reason="Windows API only")
def test_physical_memory_is_none_when_api_fails(monkeypatch: pytest.MonkeyPatch):
    class FailingKernel32:
        def __getattr__(self, name):
            raise AttributeError(name)

    monkeypatch.setattr(
        system_resources.ctypes,
        "windll",
        type("Windll", (), {"kernel32": FailingKernel32()})(),
        raising=False,
    )
    assert system_resources.physical_memory_bytes() is None

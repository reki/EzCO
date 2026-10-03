"""対象: ez_co.utils.system_resources"""
import sys

import pytest

from ez_co.utils import system_resources


def test_logical_cpu_count_returns_positive_or_none():
    """論理 CPU 数は 1 以上か、取れなければ None になる。"""
    count = system_resources.logical_cpu_count()
    assert count is None or count >= 1


def test_logical_cpu_count_is_none_when_os_reports_zero(monkeypatch: pytest.MonkeyPatch):
    """OS が 0 を返したときは論理 CPU 数を None にする。"""
    monkeypatch.setattr(system_resources.os, "cpu_count", lambda: 0)
    assert system_resources.logical_cpu_count() is None


def test_logical_cpu_count_is_none_when_os_raises(monkeypatch: pytest.MonkeyPatch):
    """OS が OSError を送出したときは論理 CPU 数を None にする。"""
    def raise_os_error():
        """CPU 数取得の失敗として OSError を送出する。

        Raises:
            OSError: CPU 数が取れないとき。
        """
        raise OSError("unavailable")

    monkeypatch.setattr(system_resources.os, "cpu_count", raise_os_error)
    assert system_resources.logical_cpu_count() is None


def test_memory_and_rss_are_none_on_non_windows(monkeypatch: pytest.MonkeyPatch):
    """Windows 以外では物理メモリも RSS も None になる。"""
    monkeypatch.setattr(system_resources.sys, "platform", "linux")
    assert system_resources.physical_memory_bytes() is None
    assert system_resources.process_resident_bytes() is None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows API only")
def test_physical_memory_and_rss_are_positive_on_windows():
    """Windows では物理メモリと RSS が正のバイト数になる。"""
    total = system_resources.physical_memory_bytes()
    resident = system_resources.process_resident_bytes()
    assert total is not None and total > 0
    assert resident is not None and resident > 0


@pytest.mark.skipif(sys.platform != "win32", reason="Windows API only")
def test_physical_memory_is_none_when_api_fails(monkeypatch: pytest.MonkeyPatch):
    """kernel32 の参照に失敗すると物理メモリは None になる。"""
    class FailingKernel32:
        """属性参照をすべて失敗させる kernel32 の代用品。"""

        def __getattr__(self, name):
            """どの属性でも AttributeError を送出する。

            Args:
                name: 参照された属性名。

            Raises:
                AttributeError: どの属性でも。
            """
            raise AttributeError(name)

    monkeypatch.setattr(
        system_resources.ctypes,
        "windll",
        type("Windll", (), {"kernel32": FailingKernel32()})(),
        raising=False,
    )
    assert system_resources.physical_memory_bytes() is None

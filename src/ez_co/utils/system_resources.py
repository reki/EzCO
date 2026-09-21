"""OSから論理CPU数・物理メモリ量・自processのRSSを取得する。"""
from __future__ import annotations

import ctypes
import os
import sys


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def logical_cpu_count() -> int | None:
    """論理CPU数。取得できなければNone。"""
    try:
        count = os.cpu_count()
    except (OSError, NotImplementedError):
        return None
    if not count or count < 1:
        return None
    return int(count)


def physical_memory_bytes() -> int | None:
    """物理メモリ総量のbytes。取得できなければNone。"""
    if sys.platform != "win32":
        return None
    try:
        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        global_memory_status = ctypes.windll.kernel32.GlobalMemoryStatusEx
        global_memory_status.argtypes = [ctypes.POINTER(_MemoryStatusEx)]
        global_memory_status.restype = ctypes.c_bool
        if not global_memory_status(ctypes.byref(status)):
            return None
        total = int(status.ullTotalPhys)
        return total if total > 0 else None
    except (AttributeError, OSError, ValueError):
        return None


def process_resident_bytes() -> int | None:
    """自processのworking set bytes。取得できなければNone。"""
    if sys.platform != "win32":
        return None
    try:
        counters = _ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_current_process = ctypes.windll.kernel32.GetCurrentProcess
        get_current_process.restype = ctypes.c_void_p
        get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_ProcessMemoryCounters),
            ctypes.c_ulong,
        ]
        get_process_memory_info.restype = ctypes.c_bool
        if not get_process_memory_info(
            get_current_process(),
            ctypes.byref(counters),
            counters.cb,
        ):
            return None
        return int(counters.WorkingSetSize)
    except (AttributeError, OSError, ValueError):
        return None

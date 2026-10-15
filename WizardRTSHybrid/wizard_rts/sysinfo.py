"""Process facts that differ between Windows and POSIX (the scripts must run on both)."""
from __future__ import annotations

import sys


def _psutil_mb() -> int:
    import psutil
    info = psutil.Process().memory_info()
    peak = getattr(info, "peak_wset", None)  # Windows only: peak working set
    return round((peak if peak else info.rss) / 2 ** 20)


def _resource_mb() -> int:
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(peak / (2 ** 20 if sys.platform == "darwin" else 1024))  # bytes on macOS, KB elsewhere


def _ctypes_mb() -> int:
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    c = Counters()
    c.cb = ctypes.sizeof(c)
    if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
        return -1
    return round(c.PeakWorkingSetSize / 2 ** 20)


def rss_mb() -> int:
    """Peak or current resident memory in MB; -1 if unknown. psutil, then resource (POSIX), then ctypes GetProcessMemoryInfo (Windows)."""
    for probe in (_psutil_mb, _resource_mb, _ctypes_mb):
        try:
            return probe()
        except (ImportError, OSError, AttributeError, ValueError):
            continue
    return -1

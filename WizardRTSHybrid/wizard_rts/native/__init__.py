"""Optional C kernels, loaded through ctypes. Everything here has a pure-Python twin that gives byte-identical results
(tests/test_native_astar.py); if no compiler is present, or DMB_NO_NATIVE=1, the Python code runs and nothing else changes."""
from __future__ import annotations

import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_lib = None
_tried = False


def _cache_dir() -> Path:
    base = Path(os.environ.get("DMB_NATIVE_CACHE", Path.home() / ".cache" / "dmb_native"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def astar_lib():
    """The compiled kernel, building it on first use (content-hashed so a source edit rebuilds), or None."""
    global _lib, _tried
    if _tried:
        return _lib
    _tried = True
    if os.environ.get("DMB_NO_NATIVE"):
        return None
    src = _HERE / "astar.c"
    ext = ".dll" if sys.platform == "win32" else ".so"
    try:
        out = _cache_dir() / f"astar_{hashlib.sha1(src.read_bytes()).hexdigest()[:12]}{ext}"
        if not out.exists():
            cc = shutil.which("gcc") or shutil.which("cc") or shutil.which("clang")
            if cc is None:
                return None
            tmp = out.with_suffix(f".tmp{os.getpid()}{ext}")
            subprocess.run([cc, "-O2", "-shared", "-fPIC", "-ffp-contract=off", str(src), "-o", str(tmp)], check=True, capture_output=True, timeout=120)
            os.replace(tmp, out)
        lib = ctypes.CDLL(str(out))
        lib.dmb_astar.restype = ctypes.c_int
        lib.dmb_astar.argtypes = [ctypes.c_int] * 2 + [ctypes.c_void_p] * 3 + [ctypes.c_int] * 7 + [ctypes.c_int64, ctypes.c_int,
                                  ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        _lib = lib
    except Exception:  # noqa: BLE001 - any build or load problem means "use Python"
        _lib = None
    return _lib

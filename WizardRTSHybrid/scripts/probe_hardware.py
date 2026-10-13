"""Hardware and toolchain probe (plan v2 section 2.3). Standard library only.

    python3 scripts/probe_hardware.py --out hardware_<machine>.json [--bench]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:  # noqa: BLE001 - a missing tool is data, not an error
        return ""


def cpu_model() -> str:
    if platform.system() == "Linux":
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    if platform.system() == "Windows":
        out = _run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"])
        if out:
            return out.splitlines()[0]
    return platform.processor()


def ram_gb() -> float:
    if platform.system() == "Linux":
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                return round(int(line.split()[1]) / 1048576, 1)
    if platform.system() == "Windows":
        out = _run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
        if out.strip().isdigit():
            return round(int(out) / 2**30, 1)
    return 0.0


def gpus() -> list[str]:
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
    if out:
        return out.splitlines()
    if platform.system() == "Windows":
        out = _run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"])
        return out.splitlines()
    return _run(["sh", "-c", "lspci 2>/dev/null | grep -i -E 'vga|3d'"]).splitlines()


def disks() -> dict:
    roots = [Path.home(), Path.cwd()]
    if platform.system() == "Windows":
        roots = [Path(f"{c}:/") for c in "CDEFG" if Path(f"{c}:/").exists()]
    return {str(r): round(shutil.disk_usage(r).free / 2**30, 1) for r in roots}


def tools() -> dict:
    names = ["python3", "python", "py", "pypy3", "godot", "dotnet", "gcc", "cc", "cargo", "rustc", "nvidia-smi", "git", "wine"]
    out = {n: shutil.which(n) for n in names}
    mods = {}
    for m in ("numpy", "torch", "numba", "pytest", "scipy"):
        try:
            mod = __import__(m)
            mods[m] = getattr(mod, "__version__", "yes")
        except Exception:  # noqa: BLE001
            mods[m] = None
    return {"binaries": out, "python_modules": mods}


def bench() -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    os.environ.setdefault("HYBRID_AI", "1")
    from wizard_rts.world import HybridWorld

    w = HybridWorld(507, terrain=True, map_size="standard")
    t0 = time.time()
    for i in range(300):
        w.advance(1000, i + 1, snapshot=False)
    return {"sim_5min_wall_s": round(time.time() - t0, 1), "x_realtime": round(300 / (time.time() - t0), 1), "hash": w.state_hash()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--bench", action="store_true")
    a = ap.parse_args()
    doc = {
        "host": platform.node(), "system": platform.platform(), "python": sys.version.split()[0], "cpu": cpu_model(),
        "logical_cores": os.cpu_count(), "ram_gb": ram_gb(), "gpus": gpus(), "free_disk_gb": disks(), "toolchain": tools(),
        "taken_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if a.bench:
        doc["bench"] = bench()
    text = json.dumps(doc, indent=1)
    if a.out:
        Path(a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()

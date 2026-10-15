"""Performance gate (plan v2 10.1): throughput of the standard scenarios against a stored baseline.

    python3 scripts/perf_gate.py record [--out docs/perf/baseline.json]     # run on an otherwise idle machine
    python3 scripts/perf_gate.py check  [--baseline docs/perf/baseline.json] [--tolerance 0.25]

Scenarios: early (minutes 0-15, six plus AIs, standard map, seed 507) and mid (nocards civilisation, minutes 40-50 after an unprofiled warm-up).
Reports game-seconds per wall-second and peak RSS; `check` fails if either scenario is slower than baseline by more than the tolerance, or memory
grew by more than 25%. Wall-clock numbers are only comparable on the same machine with nothing else running: the baseline carries the host name.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))
os.environ.setdefault("HYBRID_AI", "1")

from wizard_rts import sysinfo  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def scenario(name: str) -> dict:
    nocards = name == "mid"
    w = HybridWorld(507, terrain=True, map_size="standard", profile="campaign" if nocards else "test_showcase")
    w.nocards = nocards
    warm, window = (40 * 60, 10 * 60) if nocards else (0, 15 * 60)
    for i in range(warm):
        w.advance(1000, i + 1, snapshot=False)
    t0 = time.time()
    for i in range(warm, warm + window):
        w.advance(1000, i + 1, snapshot=False)
    wall = time.time() - t0
    return {"scenario": name, "game_s": window, "wall_s": round(wall, 1), "x_realtime": round(window / wall, 1), "buildings": len(w.buildings),
            "peak_rss_mb": sysinfo.rss_mb(), "state_hash": w.state_hash()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["record", "check"])
    ap.add_argument("--out", default=str(HYB / "docs" / "perf" / "baseline.json"))
    ap.add_argument("--baseline", default=str(HYB / "docs" / "perf" / "baseline.json"))
    ap.add_argument("--tolerance", type=float, default=0.25)
    ap.add_argument("--scenarios", nargs="+", default=["early", "mid"])
    a = ap.parse_args()
    res = [scenario(s) for s in a.scenarios]
    for r in res:
        print(r)
    if a.mode == "record":
        Path(a.out).write_text(json.dumps({"host": platform.node(), "python": platform.python_version(), "cpus": os.cpu_count(), "recorded": time.strftime("%Y-%m-%d %H:%M"),
                                           "loadavg": os.getloadavg() if hasattr(os, "getloadavg") else None, "scenarios": res}, indent=1))
        return 0
    base = json.loads(Path(a.baseline).read_text())
    if base["host"] != platform.node():
        print("baseline is from another host: numbers are not comparable, check skipped")
        return 0
    bad = 0
    for r in res:
        b = next((x for x in base["scenarios"] if x["scenario"] == r["scenario"]), None)
        if b is None:
            continue
        slow = r["x_realtime"] < b["x_realtime"] * (1 - a.tolerance)
        mem = r["peak_rss_mb"] > b["peak_rss_mb"] * 1.25
        same = r["state_hash"] == b["state_hash"]
        print(f"{r['scenario']}: {b['x_realtime']}x -> {r['x_realtime']}x {'SLOW' if slow else 'ok'}; rss {b['peak_rss_mb']} -> {r['peak_rss_mb']} MB {'GROWN' if mem else 'ok'}; state hash {'same' if same else 'DIFFERENT'}")
        bad += slow or mem
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

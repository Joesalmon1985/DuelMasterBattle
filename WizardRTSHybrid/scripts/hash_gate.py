"""State-hash equality gate for behaviour-preserving optimisations (plan v2 section 10.2).

    python3 scripts/hash_gate.py record --out docs/perf/hash_baseline.json [--seeds 507 11 23] [--minutes 20]
    python3 scripts/hash_gate.py check  --baseline docs/perf/hash_baseline.json

Runs HybridWorld with the faction AIs on, advancing one game second per call, and records world.state_hash() every
game minute. `check` re-runs the same seeds and fails on the first minute whose hash differs, so an optimisation that
changes behaviour is caught at the minute it diverges. Also reports x-realtime so speed-ups are measured in one place.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))
os.environ.setdefault("HYBRID_AI", "1")

from wizard_rts.world import HybridWorld  # noqa: E402


def run(seed: int, minutes: int, map_size: str) -> dict:
    w = HybridWorld(seed, terrain=True, map_size=map_size)
    hashes = []
    t0 = time.time()
    for i in range(minutes * 60):
        w.advance(1000, i + 1, snapshot=False)
        if (i + 1) % 60 == 0:
            hashes.append(w.state_hash())
    wall = time.time() - t0
    return {"seed": seed, "hashes": hashes, "wall_s": round(wall, 1), "x_realtime": round(minutes * 60 / wall, 1),
            "buildings": len(w.buildings)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["record", "check"])
    ap.add_argument("--out")
    ap.add_argument("--baseline")
    ap.add_argument("--seeds", type=int, nargs="*", default=[507, 11, 23])
    ap.add_argument("--minutes", type=int, default=20)
    ap.add_argument("--map", default="standard")
    a = ap.parse_args()
    if a.mode == "record":
        res = [run(s, a.minutes, a.map) for s in a.seeds]
        doc = {"map": a.map, "minutes": a.minutes, "runs": res}
        Path(a.out).write_text(json.dumps(doc, indent=1))
        for r in res:
            print(r["seed"], r["x_realtime"], "x", r["hashes"][-1])
        return 0
    base = json.loads(Path(a.baseline).read_text())
    bad = 0
    for b in base["runs"]:
        r = run(b["seed"], base["minutes"], base["map"])
        div = next((i for i, (x, y) in enumerate(zip(r["hashes"], b["hashes"])) if x != y), None)
        status = "OK" if div is None else f"DIVERGED at minute {div + 1}"
        bad += div is not None
        print(f"seed {b['seed']}: {status}  {b['x_realtime']}x -> {r['x_realtime']}x  ({b['wall_s']}s -> {r['wall_s']}s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

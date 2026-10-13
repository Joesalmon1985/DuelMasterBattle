"""Profile the late game: run N minutes unprofiled, then profile a window. Prints top functions by own time and cumulative time.

    python3 scripts/profile_late.py --warm 100 --window 3 [--seed 507] [--nocards]
"""
from __future__ import annotations

import argparse
import cProfile
import os
import pstats
import sys
import time
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))
os.environ.setdefault("HYBRID_AI", "1")

from wizard_rts.world import HybridWorld  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--warm", type=int, default=100)
    ap.add_argument("--window", type=int, default=3)
    ap.add_argument("--seed", type=int, default=507)
    ap.add_argument("--nocards", action="store_true")
    ap.add_argument("--top", type=int, default=35)
    a = ap.parse_args()
    w = HybridWorld(a.seed, terrain=True, map_size="standard", profile="campaign")
    w.nocards = a.nocards
    t0 = time.time()
    for i in range(a.warm * 60):
        w.advance(1000, i + 1, snapshot=False)
    print(f"warm {a.warm} min in {time.time() - t0:.0f} s; buildings {len(w.buildings)} units {len(w.units)} workers {len(w.workers)} carriers {len(w.carriers)} trees {len(w.trees)}")
    pr = cProfile.Profile()
    t1 = time.time()
    pr.enable()
    for i in range(a.warm * 60, (a.warm + a.window) * 60):
        w.advance(1000, i + 1, snapshot=False)
    pr.disable()
    print(f"window {a.window} min profiled in {time.time() - t1:.0f} s")
    for key in ("tottime", "cumulative"):
        pstats.Stats(pr).sort_stats(key).print_stats(a.top)


if __name__ == "__main__":
    main()

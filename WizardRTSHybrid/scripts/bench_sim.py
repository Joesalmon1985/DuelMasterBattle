"""Headless throughput benchmark: no Godot, no display.

    python3 scripts/bench_sim.py [--map standard] [--minutes 10] [--seed 507] [--profile] [--env]

Prints generation time, game-seconds per wall-second (x realtime), peak memory and the final state hash, so two
machines or two commits can be compared and determinism can be checked by eye (same seed, same hash).
Budgets for this ThinkPad (proposal): standard map >= 20x realtime with six AI factions; large >= 6x.
"""
from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
import pstats
import resource
import sys
import time
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))
os.environ.setdefault("HYBRID_AI", "1")

from wizard_rts.sim_api import HybridEnv  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="standard")
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--seed", type=int, default=507)
    ap.add_argument("--profile", action="store_true")
    ap.add_argument("--env", action="store_true", help="drive it through HybridEnv.step (what a trainer would call)")
    ap.add_argument("--legacy", action="store_true", help="flat legacy world, for comparison")
    args = ap.parse_args()
    t0 = time.time()
    if args.env:
        env = HybridEnv(args.seed, args.map, agent_factions=("Red",), step_ms=5000, terrain=not args.legacy)
        env.reset()
        w = env.world
    else:
        w = HybridWorld(args.seed, terrain=not args.legacy, map_size=args.map)
        env = None
    gen = time.time() - t0
    prof = cProfile.Profile() if args.profile else None
    t1 = time.time()
    if prof:
        prof.enable()
    seconds = int(args.minutes * 60)
    if env:
        for _ in range(seconds // 5):
            env.step({})
    else:
        for i in range(seconds):
            w.advance(1000, i + 1, snapshot=False)
    if prof:
        prof.disable()
    wall = time.time() - t1
    snap = time.time()
    s = json.dumps(w.snapshot())
    snap_ms = (time.time() - snap) * 1000
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    out = {
        "map": "legacy" if args.legacy else args.map, "seed": args.seed, "generate_s": round(gen, 2), "game_s": seconds, "wall_s": round(wall, 2),
        "x_realtime": round(seconds / wall, 1), "snapshot_kb": len(s) // 1024, "snapshot_ms": round(snap_ms, 1), "peak_rss_mb": round(rss),
        "buildings": len(w.buildings), "units": sum(1 for u in w.units.values() if u.get("alive", True)), "trees": len(w.trees),
        "state_hash": w.state_hash(),
    }
    print(json.dumps(out))
    if prof:
        st = io.StringIO()
        pstats.Stats(prof, stream=st).sort_stats("tottime").print_stats(14)
        print(st.getvalue())


if __name__ == "__main__":
    main()

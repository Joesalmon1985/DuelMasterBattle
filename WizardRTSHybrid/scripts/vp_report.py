#!/usr/bin/env python3
"""Measure VP and era timing instead of assuming the 10-VP threshold is balanced (roadmap M4, S04).

Runs the AI world for N game minutes on several seeds and prints, per seed: VP of every faction every `--every` minutes, the time the
highest faction first reached 3, 5 and 10 VP, settlements founded and conquered, and the era the world would have reached.
Usage: python3 scripts/vp_report.py --minutes 40 --seeds 507 11 23 [--profile test_showcase|campaign] [--peace]
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wizard_rts import vp  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=40)
    ap.add_argument("--seeds", type=int, nargs="+", default=[507, 11, 23])
    ap.add_argument("--profile", default="test_showcase")
    ap.add_argument("--every", type=int, default=5)
    ap.add_argument("--peace", action="store_true")
    ap.add_argument("--threshold", type=int, default=10)
    args = ap.parse_args()
    out = []
    for seed in args.seeds:
        w = HybridWorld(seed, profile=args.profile)
        w.ai_enabled = True
        w.ai_aggressive = not args.peace
        w.era_vp_threshold = args.threshold
        t0 = time.time()
        first = {}
        series = []
        for s in range(args.minutes * 60):
            w.advance(1000, s + 1, snapshot=False)
            if s % 10 == 9:
                top = max(vp.totals(w).values())
                for mark in (3, 5, 10):
                    if top >= mark and mark not in first:
                        first[mark] = (s + 1) // 60
            if (s + 1) % (args.every * 60) == 0:
                series.append({"min": (s + 1) // 60, "vp": vp.totals(w), "era": vp.snapshot(w)["era"]})
        led = vp.ledger(w)
        row = {"seed": seed, "minutes": args.minutes, "first_minute_top_vp_reached": first, "settlements_founded": sum(1 for e in led.values() if e["event"] == "founded"),
               "conquests": sum(1 for e in led.values() if e["event"] == "destroyed" and e.get("winner")), "final_vp": vp.totals(w),
               "era_log": vp.era_state(w)["log"], "wall_s": round(time.time() - t0, 1), "series": series}
        out.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "series"}), flush=True)
    Path(args.__dict__.get("out", "/dev/null"))


if __name__ == "__main__":
    main()

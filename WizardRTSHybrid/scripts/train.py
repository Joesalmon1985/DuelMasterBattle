#!/usr/bin/env python3
"""Opt-in training and held-out evaluation. Nothing here is needed to play; nothing downloads anything; budgets are bounded.

  python3 scripts/train.py --domain duel dungeon outbreak quest fullgame rts --budget smoke|standard|long [--seed 0]

Results (curves, held-out numbers with paired statistics, checkpoints) go to $DMB_RUNS_DIR (default ~/dmb_runs/<domain>/<time>/) and a
summary to stdout; copy the numbers you want to keep into docs/evidence/training/ (scripts/make_training_report.py does it).
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wizard_rts.learn.domains import DOMAINS  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", nargs="+", default=["duel"], choices=sorted(DOMAINS))
    ap.add_argument("--budget", default="smoke", choices=["smoke", "standard", "long"])
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    for d in a.domain:
        t = time.time()
        print(f"== {d} ({a.budget})", flush=True)
        res = DOMAINS[d](a.budget, seed=a.seed)
        res = {k: v for k, v in res.items() if k != "per_episode"}
        print(json.dumps(res, indent=1, default=str)[:6000], flush=True)
        print(f"== {d} done in {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()

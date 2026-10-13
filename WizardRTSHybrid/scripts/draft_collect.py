"""Collect imitation samples from the heuristic drafter (plan v2 9.3 step 1).

    python3 scripts/draft_collect.py --seeds 1000-1039 --minutes 45 --jobs 2 --out ~/dmb_runs/draft_data

One game per seed (six plus AIs, cards v2, drafting v2); every pick of the heuristic drafter is stored with the state and card features
(wizard_rts/learn/draft_module.py). One JSONL file per seed so a stopped run resumes by skipping finished seeds.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))


def play(job: tuple[int, int, str]) -> tuple[int, int, float]:
    seed, minutes, out = job
    os.environ["HYBRID_AI"] = "1"
    os.environ["HYBRID_AI_POLICY"] = "plus"
    from wizard_rts.world import HybridWorld

    t0 = time.time()
    w = HybridWorld(seed, terrain=True, map_size="standard", profile="campaign")
    w.cardset, w.draft_v2 = "v2", True
    w.draft_recorder = []
    for i in range(minutes * 60):
        w.advance(1000, i + 1, snapshot=False)
    path = Path(out) / f"seed_{seed}.jsonl"
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(json.dumps(s) for s in w.draft_recorder))
    tmp.replace(path)
    return seed, len(w.draft_recorder), time.time() - t0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1000-1039")
    ap.add_argument("--minutes", type=int, default=45)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--out", default=str(Path.home() / "dmb_runs" / "draft_data"))
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split("-"))
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(s, a.minutes, str(out)) for s in range(lo, hi + 1) if not (out / f"seed_{s}.jsonl").exists()]
    print(f"{len(jobs)} games to play", flush=True)
    with mp.get_context("spawn").Pool(a.jobs) as pool:
        for seed, n, wall in pool.imap_unordered(play, jobs):
            print(f"seed {seed}: {n} samples in {wall:.0f} s", flush=True)


if __name__ == "__main__":
    main()

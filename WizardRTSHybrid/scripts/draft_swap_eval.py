"""Module-swap test of the neural drafter (plan v2 9.3 step 2): same seed twice, once with every faction on the heuristic drafter and once
with ONE faction (rotating with the seed) drafting by the learned scorer; everything else is identical code. Compares that faction's outcome
metrics between the two legs, paired by seed.

    python3 scripts/draft_swap_eval.py --model ~/dmb_runs/draft_models/scorer_v1.json --seeds 3000-3011 --minutes 45 --jobs 2 --out ~/dmb_runs/draft_swap

Outcome metrics (never training reward): VP, settlements, buildings, share of unlocked entities actually produced (cards-used), cards held.
Reports mean paired difference (neural - heuristic) with a 95% bootstrap interval; the plan's gate for stage 1 is "no worse than the heuristic".
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

import numpy as np

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))

FACTIONS = ["Red", "Blue", "Green", "Yellow", "Purple", "Orange"]


def play(job: dict) -> dict:
    os.environ["HYBRID_AI"] = "1"
    os.environ["HYBRID_AI_POLICY"] = "plus"
    from wizard_rts import inspector, vp
    from wizard_rts.learn.draft_module import DraftScorer
    from wizard_rts.world import HybridWorld

    t0 = time.time()
    w = HybridWorld(job["seed"], terrain=True, map_size="standard", profile="campaign")
    w.cardset, w.draft_v2 = "v2", True
    target = FACTIONS[job["seed"] % 6]
    if job["neural"]:
        w.neural_drafters = {target: DraftScorer.load(job["model"])}
    for i in range(job["minutes"] * 60):
        w.advance(1000, i + 1, snapshot=False)
    view = inspector.factions(w)[target]
    ents = [e for h in view["cards"] for e in h["entities"]]
    mine = [b for b in w.buildings.values() if b["faction_name"] == target and "hp" in b and int(b["hp"]) > 0]
    return {"seed": job["seed"], "neural": job["neural"], "faction": target, "vp": vp.totals(w).get(target, 0), "buildings": len(mine),
            "cards": len(w.tech[target]["cards"]), "entities": len(ents), "used": sum(1 for e in ents if e["produced"]),
            "used_rate": round(sum(1 for e in ents if e["produced"]) / max(1, len(ents)), 3), "wall_s": round(time.time() - t0, 1)}


def boot(vals: np.ndarray, n: int = 4000, seed: int = 1) -> tuple[float, float]:
    rng = np.random.RandomState(seed)
    means = [rng.choice(vals, len(vals)).mean() for _ in range(n)]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--seeds", default="3000-3011")
    ap.add_argument("--minutes", type=int, default=45)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--out", default=str(Path.home() / "dmb_runs" / "draft_swap"))
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split("-"))
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    done_file = out / "games.jsonl"
    done = {(r["seed"], r["neural"]): r for r in map(json.loads, done_file.read_text().splitlines())} if done_file.exists() else {}
    jobs = [{"seed": s, "neural": n, "minutes": a.minutes, "model": str(Path(a.model).expanduser())} for s in range(lo, hi + 1) for n in (False, True) if (s, n) not in done]
    print(len(jobs), "games to play", flush=True)
    with mp.get_context("spawn").Pool(a.jobs) as pool, done_file.open("a") as fh:
        for r in pool.imap_unordered(play, jobs):
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            done[(r["seed"], r["neural"])] = r
            print(r, flush=True)
    seeds = sorted({s for s, _n in done})
    lines = [f"Module swap, {len(seeds)} paired seeds, {a.minutes} game minutes, one faction (rotating by seed) drafts with the learned scorer.\n",
             "| metric | heuristic mean | neural mean | paired diff (neural - heuristic) | 95% bootstrap CI |", "| --- | --- | --- | --- | --- |"]
    for k in ("vp", "buildings", "cards", "used_rate"):
        pairs = [(done[(s, False)][k], done[(s, True)][k]) for s in seeds if (s, False) in done and (s, True) in done]
        if not pairs:
            continue
        d = np.array([n - h for h, n in pairs], dtype=float)
        lo_ci, hi_ci = boot(d)
        lines.append(f"| {k} | {np.mean([h for h, _ in pairs]):.2f} | {np.mean([n for _, n in pairs]):.2f} | {d.mean():+.2f} | [{lo_ci:+.2f}, {hi_ci:+.2f}] |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

"""Catastrophe calibration study (plan v2 7.4): how often does the world end in collective loss under each policy and threshold pair?

    python3 scripts/catastrophe_study.py --seeds 1 2 3 4 5 6 --minutes 60 --jobs 2 --out ~/dmb_runs/cat_study

Cells = nest policy (ignore | selfish | coop) x (per-era limit, cumulative limit). One game per (cell, seed), all six factions plus AIs, outbreak cadence
scaled by --scale, the game stops at collective loss. Writes cells.csv and summary.md (loss probability, median minutes to loss, outbreaks, cubes cleared).
`ignore` and `selfish` play without diplomacy; `coop` plays with the cooperative truce rule (world.diplomacy_enabled).
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import multiprocessing as mp
import os
import statistics
import sys
import time
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))


def play(job: dict) -> dict:
    os.environ["HYBRID_AI"] = "1"
    os.environ["HYBRID_AI_POLICY"] = "plus"
    from wizard_rts import diplomacy, regions
    from wizard_rts.world import HybridWorld

    t0 = time.time()
    w = HybridWorld(job["seed"], terrain=True, map_size="standard", profile="campaign")
    w.outbreak_interval_scale = job["scale"]
    w.loss_outbreaks_per_era, w.loss_outbreaks_total = job["era_limit"], job["total_limit"]
    w.nest_policy = {n: job["policy"] for n in w.faction_info}
    w.diplomacy_enabled = job["policy"] == "coop"
    cleared = truces = 0
    lost_at = None
    for i in range(job["minutes"] * 60):
        w.advance(1000, i + 1, snapshot=False)
        for e in w.events:
            cleared += e["kind"] == "nest_cube_cleared"
            truces += e["kind"] == "relation_changed" and e["to"] == "truce"
        w.events.clear()
        if getattr(w, "collective_loss", False):
            lost_at = (i + 1) / 60.0
            break
    s = regions.state(w)
    return {**{k: job[k] for k in ("policy", "era_limit", "total_limit", "seed")}, "lost": lost_at is not None, "minutes_to_loss": lost_at or "", "outbreaks": s.outbreaks,
            "cubes_cleared": cleared, "truces": truces, "pressure_end": round(diplomacy.pressure(w), 2), "wall_s": round(time.time() - t0, 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5, 6])
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--scale", type=float, default=0.35)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--policies", nargs="+", default=["ignore", "selfish", "coop"])
    ap.add_argument("--limits", nargs="+", default=["99:8", "6:12", "4:8"], help="era:total pairs")
    ap.add_argument("--out", default=str(Path.home() / "dmb_runs" / "cat_study"))
    a = ap.parse_args()
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    done = {}
    cells = out / "cells.jsonl"
    if cells.exists():
        for line in cells.read_text().splitlines():
            r = json.loads(line)
            done[(r["policy"], r["era_limit"], r["total_limit"], r["seed"])] = r
    jobs = []
    for pol, lim, seed in itertools.product(a.policies, a.limits, a.seeds):
        e, t = (int(x) for x in lim.split(":"))
        if (pol, e, t, seed) not in done:
            jobs.append({"policy": pol, "era_limit": e, "total_limit": t, "seed": seed, "minutes": a.minutes, "scale": a.scale})
    print(len(jobs), "games to play", flush=True)
    with mp.get_context("spawn").Pool(a.jobs) as pool, cells.open("a") as fh:
        for r in pool.imap_unordered(play, jobs):
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            print(r, flush=True)
    rows = [json.loads(line) for line in cells.read_text().splitlines()]
    with (out / "cells.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = ["| policy | era limit | total limit | games | P(collective loss) | median minutes to loss | mean outbreaks | mean cubes cleared | mean truces |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for pol, lim in itertools.product(a.policies, a.limits):
        e, t = (int(x) for x in lim.split(":"))
        rs = [r for r in rows if r["policy"] == pol and r["era_limit"] == e and r["total_limit"] == t]
        if not rs:
            continue
        lost = [r["minutes_to_loss"] for r in rs if r["lost"]]
        lines.append(f"| {pol} | {e} | {t} | {len(rs)} | {sum(r['lost'] for r in rs) / len(rs):.2f} | {statistics.median(lost) if lost else '-'} | {statistics.mean(r['outbreaks'] for r in rs):.1f} | "
                     f"{statistics.mean(r['cubes_cleared'] for r in rs):.1f} | {statistics.mean(r['truces'] for r in rs):.1f} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

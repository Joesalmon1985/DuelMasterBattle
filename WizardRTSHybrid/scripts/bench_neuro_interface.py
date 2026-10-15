"""Measure the neural interface (features and candidates) on developed games: timing per faction, candidate counts per head, simulator acceptance per head.

    py -3 scripts/bench_neuro_interface.py --minutes 20 60 120 --out docs/evidence/neuroevo/m2_interface [--cap 6]

Builds one campaign game (seed 7, the plus AI in every seat, generated cards, diplomacy) and stops at each requested minute. At each stop, for all six factions:
the mean wall time of `FactionObserver.observe` and of `CandidateGenerator.all` over 10 consecutive decisions 60 game seconds apart (the first decision of a
faction pays its caches and is reported separately), the candidates generated per head, and the fraction the simulator accepts when each of up to `--cap` evenly
spaced candidates per head is applied to an isolated copy of the world. Writes summary.json and summary.md.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import pickle
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HYB = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HYB), str(HYB.parent)]
os.environ.setdefault("HYBRID_AI", "1")

from neuro.candidates import CandidateGenerator  # noqa: E402
from neuro.observer import FactionObserver  # noqa: E402
from wizard_rts.sim_api import HybridEnv  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402

FACTIONS = ("Red", "Blue", "Green", "Yellow", "Purple", "Orange")


def measure(world, minute: int, cap: int) -> dict:
    blob = pickle.dumps(world, protocol=5)
    rows, rates, reasons, made = {}, collections.defaultdict(lambda: [0, 0]), collections.defaultdict(collections.Counter), collections.defaultdict(list)
    t_game = int(world.dmb.clock.get("game_ms", 0)) // 1000
    for f in FACTIONS:
        w = pickle.loads(blob)
        ob = FactionObserver(w, f)
        gen = CandidateGenerator(SimpleNamespace(world=w), f, ob)
        t = time.perf_counter()
        obs = ob.observe(t_game)
        first_obs = (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        cands = gen.all(obs)
        first_cand = (time.perf_counter() - t) * 1000
        fo, fc = [], []
        for i in range(10):
            t = time.perf_counter()
            obs = ob.observe(t_game + 60 * (i + 1))
            fo.append((time.perf_counter() - t) * 1000)
            t = time.perf_counter()
            cands = gen.all(obs)
            fc.append((time.perf_counter() - t) * 1000)
        rows[f] = {"observe_first_ms": round(first_obs, 2), "candidates_first_ms": round(first_cand, 2), "observe_ms": round(sum(fo) / 10, 2), "candidates_ms": round(sum(fc) / 10, 2),
                   "observe_max_ms": round(max(fo), 2), "candidates_max_ms": round(max(fc), 2), "buildings": len(obs.b_ids), "units": len(obs.u_ids), "settlements": len(obs.s_ids)}
        for head, lst in cands.items():
            made[head].append(len(lst))
            step = max(1, len(lst) // cap)
            for c in lst[::step][:cap]:
                w2 = pickle.loads(blob)
                env = HybridEnv(seed=1, map_size="standard", agent_factions=(f,), step_ms=1000, profile="campaign")
                env.world = w2
                r = env.apply(f, c.action)
                rates[head][1] += 1
                if r.get("status") == "ok":
                    rates[head][0] += 1
                else:
                    reasons[head][r.get("reason")] += 1
    mean = lambda k: round(sum(r[k] for r in rows.values()) / len(rows), 2)  # noqa: E731
    return {"minute": minute, "per_faction": rows, "mean_observe_ms": mean("observe_ms"), "mean_candidates_ms": mean("candidates_ms"),
            "max_observe_ms": max(r["observe_max_ms"] for r in rows.values()), "max_candidates_ms": max(r["candidates_max_ms"] for r in rows.values()),
            "candidates_per_head_mean": {h: round(sum(v) / len(v), 1) for h, v in sorted(made.items())},
            "acceptance": {h: {"accepted": a, "tried": t, "rate": round(a / max(1, t), 3), "reasons": dict(reasons[h])} for h, (a, t) in sorted(rates.items())},
            "world": {"buildings": len(world.buildings), "units": len(world.units), "pickle_mb": round(len(blob) / 1e6, 1)}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, nargs="+", default=[20, 60, 120])
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--cap", type=int, default=6)
    ap.add_argument("--out", default=str(HYB.parent / "docs" / "evidence" / "neuroevo" / "m2_interface"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    w = HybridWorld(a.seed, terrain=True, map_size="standard", profile="campaign")
    w.cardset, w.draft_v2, w.diplomacy_enabled = "v2", True, True
    w.nest_policy = {n: "coop" for n in w.faction_info}
    w.ai_policy = {n: "plus" for n in w.faction_info}
    results = []
    sec = 0
    for minute in sorted(a.minutes):
        while sec < minute * 60:
            sec += 1
            w.advance(1000, sec, snapshot=False)
        t = time.time()
        results.append(measure(w, minute, a.cap))
        print(f"minute {minute}: observe {results[-1]['mean_observe_ms']} ms, candidates {results[-1]['mean_candidates_ms']} ms ({time.time() - t:.0f} s to measure)", flush=True)
    (out / "summary.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    md = ["# Neural interface benchmark (generated by scripts/bench_neuro_interface.py)", "", f"Seed {a.seed}, campaign profile, plus AI in all six seats, standard map; acceptance sampled with up to {a.cap} candidates per head and faction.", "",
          "| minute | buildings | units | observe mean (max) ms | candidates mean (max) ms | targets |", "| --- | ---: | ---: | --- | --- | --- |"]
    for r in results:
        md.append(f"| {r['minute']} | {r['world']['buildings']} | {r['world']['units']} | {r['mean_observe_ms']} ({r['max_observe_ms']}) | {r['mean_candidates_ms']} ({r['max_candidates_ms']}) | 15 / 10 |")
    for r in results:
        md += ["", f"## Minute {r['minute']}", "", "| head | candidates (mean per faction) | accepted / tried | rate | refusal reasons |", "| --- | ---: | ---: | ---: | --- |"]
        for h in sorted(r["candidates_per_head_mean"]):
            acc = r["acceptance"].get(h, {"accepted": 0, "tried": 0, "rate": 0, "reasons": {}})
            md.append(f"| {h} | {r['candidates_per_head_mean'][h]} | {acc['accepted']} / {acc['tried']} | {acc['rate']:.0%} | {acc['reasons'] or ''} |")
        md += ["", "| faction | buildings | units | settlements | observe first / mean ms | candidates first / mean ms |", "| --- | ---: | ---: | ---: | --- | --- |"]
        for f, row in r["per_faction"].items():
            md.append(f"| {f} | {row['buildings']} | {row['units']} | {row['settlements']} | {row['observe_first_ms']} / {row['observe_ms']} | {row['candidates_first_ms']} / {row['candidates_ms']} |")
    (out / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

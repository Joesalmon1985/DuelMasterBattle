"""Paired held-out evaluation (design 7.5; execution plan T5.2, T6.2): a candidate genome against a reference on seeds the training never uses.

`paired_heldout(pool, out_dir, candidate, reference, seeds, ...)` plays, for each seed and each leg (A = Red/Green/Purple, B = Blue/Yellow/Orange), the candidate in the
leg's three seats against three `plus` heuristic opponents. The reference is either another genome (played the same way: same seed, leg and opponents) or, when None,
the all-`plus` control game of that seed (so the advantage is over the heuristic AI). A pair's advantage is the mean over the three seats of F_candidate - F_reference.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from neuro import league as L
from neuro.workers import GamePool, make_job


def episode_dict(seed: int, game_minutes: int, map_size: str, level: str, scale: float, wall_cap_s: int, tactical: bool = False) -> dict:
    return {"seed": int(seed), "game_minutes": int(game_minutes), "map_size": map_size, "outbreak_interval_scale": float(scale), "catastrophe_level": level,
            "wall_cap_s": int(wall_cap_s), "checkpoint_game_minutes": 10 ** 6, "tactical": bool(tactical)}


def seat_values(res: dict, seats: tuple[str, ...], key: str = "seats") -> dict[str, tuple[float, str]]:
    out = {}
    for s in res["result"][key]:
        if s["faction"] in seats:
            out[s["faction"]] = (float(s["fitness"]), s["tier"])
    return out


def paired_heldout(pool: GamePool, out_dir: Path, candidate: Path, reference: Path | None, seeds: list[int], game_minutes: int, map_size: str, level: str = "C0",
                   scale: float = 1.0, wall_cap_s: int = 7200, tactical: bool = False, stop: Any = None, log_decisions: bool = False) -> list[dict]:
    out_dir = Path(out_dir)
    jobs = []
    for s in seeds:
        ep = episode_dict(s, game_minutes, map_size, level, scale, wall_cap_s, tactical)
        if reference is None:
            jobs.append(make_job(f"ctl_{s}", out_dir / f"ctl_{s}", ep, {}, {"kind": "control", "seed": s}))
        for leg in ("A", "B"):
            mine, theirs = L.seats_for(leg)
            seats = {x: f"genome:{candidate}" for x in mine} | {x: "plus" for x in theirs}
            jobs.append(make_job(f"cand_{s}_{leg}", out_dir / f"cand_{s}_{leg}", ep, seats, {"kind": "candidate", "seed": s, "leg": leg}, log_decisions=log_decisions and leg == "A"))
            if reference is not None:
                seats = {x: f"genome:{reference}" for x in mine} | {x: "plus" for x in theirs}
                jobs.append(make_job(f"ref_{s}_{leg}", out_dir / f"ref_{s}_{leg}", ep, seats, {"kind": "reference", "seed": s, "leg": leg}))
    res = pool.run(jobs, stop=stop)
    pairs = []
    for s in seeds:
        for leg in ("A", "B"):
            mine, _theirs = L.seats_for(leg)
            c = res.get(f"cand_{s}_{leg}")
            r = res.get(f"ctl_{s}" if reference is None else f"ref_{s}_{leg}")
            if not c or not r or c.get("voided") or r.get("voided"):
                continue
            fc = seat_values(c, mine)
            fr = seat_values(r, mine, "control_seats" if reference is None else "seats")
            if any(t == "V" for _f, t in list(fc.values()) + list(fr.values())) or set(fc) != set(mine) or set(fr) != set(mine):
                continue
            adv = float(np.mean([fc[x][0] - fr[x][0] for x in mine]))
            pairs.append({"seed": s, "leg": leg, "adv": adv, "cand_lost": c["result"]["end_reason"] == "collective_loss", "champ_lost": r["result"]["end_reason"] == "collective_loss",
                          "f_cand": float(np.mean([fc[x][0] for x in mine])), "f_ref": float(np.mean([fr[x][0] for x in mine])), "end_cand": c["result"]["end_reason"],
                          "metrics": [x["metrics"] for x in c["result"]["seats"] if x["faction"] in mine], "stats": c.get("stats", {})})
    return pairs


def summarize(pairs: list[dict]) -> dict:
    """Mean advantage with its 90% bootstrap bounds, loss rates, and per-seed wins (a seed is won when the mean of its legs is above 0)."""
    from neuro.league import bootstrap_mean_interval

    mean, lo, hi = bootstrap_mean_interval([p["adv"] for p in pairs])
    by_seed: dict[int, list[float]] = {}
    for p in pairs:
        by_seed.setdefault(p["seed"], []).append(p["adv"])
    wins = sum(1 for v in by_seed.values() if np.mean(v) > 0)
    n = max(1, len(pairs))
    return {"n_pairs": len(pairs), "mean_advantage": mean, "lower90": lo, "upper90": hi, "seeds": len(by_seed), "seed_wins": wins,
            "loss_rate_candidate": sum(1 for p in pairs if p["cand_lost"]) / n, "loss_rate_reference": sum(1 for p in pairs if p["champ_lost"]) / n,
            "mean_f_candidate": float(np.mean([p["f_cand"] for p in pairs])) if pairs else 0.0, "mean_f_reference": float(np.mean([p["f_ref"] for p in pairs])) if pairs else 0.0}

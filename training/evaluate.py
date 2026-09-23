"""Held-out paired policy evaluation (C14 / T148)."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

from sim.dmb.ai.heuristic import HeuristicBrain
from sim.dmb.ai.neural import NeuralBrain
from sim.dmb.ai.policy import PolicyService, register_neural_artifact
from sim.dmb.construction.scoring import ScoreService
from training.collect import PROMOTION_SEEDS
from training.environment import TrainingEnvironment, schema_hash

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "policy_evaluations"


def _binomial_uncertainty(successes: int, n: int) -> dict[str, float]:
    if n <= 0:
        return {"rate": 0.0, "se": 0.0}
    p = successes / n
    se = math.sqrt(p * (1 - p) / n)
    return {"rate": p, "se": se, "ci95_low": max(0.0, p - 1.96 * se), "ci95_high": min(1.0, p + 1.96 * se)}


def _run_seed(
    *,
    seed: int,
    policy_id: str,
    artifact: Path | None,
    max_steps: int,
    seat_index: int,
    fixture: str = "FX-ERA",
) -> dict[str, Any]:
    env = TrainingEnvironment(seed=seed, max_turns=max_steps, fixture=fixture)
    try:
        env.reset(seed)
    except Exception as exc:  # noqa: BLE001
        return {
            "seed": seed,
            "crashed": True,
            "error": f"fixture_load:{exc}",
            "policy_id": policy_id,
            "faction_id": None,
        }
    assert env.sim is not None
    factions = sorted(env.sim.state.factions)
    # Balance seats: alternate which faction gets the candidate policy.
    candidate_faction = factions[seat_index % len(factions)]
    policy = PolicyService(env.sim.state)
    for fid in factions:
        if fid == candidate_faction and artifact is not None and policy_id != "heuristic":
            register_neural_artifact(policy_id, str(artifact))
            policy.assign_brain(fid, policy_id)
        else:
            policy.assign_brain(fid, "heuristic")

    inference_ms: list[float] = []
    illegal_accepts = 0
    action_families: dict[str, int] = {
        "build": 0,
        "trade": 0,
        "war": 0,
        "other": 0,
    }
    crashed = False
    try:
        for _ in range(max_steps):
            if env._terminal:
                break
            batch = env.step()
            for rec in batch:
                if rec.faction_id != candidate_faction:
                    continue
                # Timing from last neural choose is not on StepRecord; approximate via PolicyService selections.
                sels = (env.sim.state.factions.get(candidate_faction) or {}).get("policy", {}).get("selections") or []
                if sels:
                    last = sels[-1]
                    if last.get("inference_ms") is not None:
                        inference_ms.append(float(last["inference_ms"]))
                    for sid in last.get("selected_ids") or []:
                        kind = "other"
                        for c in rec.candidates:
                            if c.get("id") == sid:
                                ak = str(c.get("action_kind") or "")
                                if ak == "construct":
                                    kind = "build"
                                elif ak == "trade_propose":
                                    kind = "trade"
                                elif ak.startswith("military"):
                                    kind = "war"
                                break
                        action_families[kind] = action_families.get(kind, 0) + 1
            if env._terminal:
                break
    except Exception as exc:  # noqa: BLE001
        crashed = True
        return {
            "seed": seed,
            "crashed": True,
            "error": str(exc),
            "policy_id": policy_id,
            "faction_id": candidate_faction,
        }

    scores = ScoreService(env.sim.state)
    vp = {fid: scores.score(fid) for fid in factions}
    reached_10 = any(v >= 10 for v in vp.values())
    candidate_vp = int(vp.get(candidate_faction) or 0)
    catastrophe = 1 if env._terminal_reason == "catastrophe" else 0
    p95 = 0.0
    if inference_ms:
        ordered = sorted(inference_ms)
        p95 = ordered[min(len(ordered) - 1, int(math.ceil(0.95 * len(ordered)) - 1))]

    return {
        "seed": seed,
        "crashed": crashed,
        "policy_id": policy_id,
        "faction_id": candidate_faction,
        "terminal_reason": env._terminal_reason,
        "scores": vp,
        "candidate_vp": candidate_vp,
        "reached_10_vp": reached_10,
        "candidate_reached_10": candidate_vp >= 10,
        "catastrophe": catastrophe,
        "illegal_accepts": illegal_accepts,
        "inference_p95_ms": p95,
        "inference_samples": len(inference_ms),
        "action_families": action_families,
        "turns": int(env.sim.state.clock.get("turn") or 0),
    }


def evaluate_policy(
    *,
    policy_id: str,
    artifact: Path | None,
    seeds: list[int] | None = None,
    max_steps: int = 40,
    label: str = "candidate",
    fixture: str = "FX-ERA",
) -> dict[str, Any]:
    seeds = list(seeds or PROMOTION_SEEDS)
    rows = []
    started = time.monotonic()
    for i, seed in enumerate(seeds):
        rows.append(
            _run_seed(
                seed=seed,
                policy_id=policy_id,
                artifact=artifact,
                max_steps=max_steps,
                seat_index=i,
                fixture=fixture,
            )
        )
    n = len(rows)
    wins = sum(1 for r in rows if r.get("candidate_reached_10"))
    cat = sum(int(r.get("catastrophe") or 0) for r in rows)
    crashes = sum(1 for r in rows if r.get("crashed"))
    illegal = sum(int(r.get("illegal_accepts") or 0) for r in rows)
    families = {"build": 0, "trade": 0, "war": 0, "other": 0}
    for r in rows:
        for k, v in (r.get("action_families") or {}).items():
            families[k] = families.get(k, 0) + int(v)
    total_actions = sum(families.values()) or 1
    family_share = {k: v / total_actions for k, v in families.items()}
    p95_vals = [float(r["inference_p95_ms"]) for r in rows if r.get("inference_samples")]
    report = {
        "label": label,
        "policy_id": policy_id,
        "artifact": str(artifact) if artifact else None,
        "fixture": fixture,
        "schema_hash": schema_hash(),
        "seed_count": n,
        "seeds": seeds,
        "wins_10vp": wins,
        "win_uncertainty": _binomial_uncertainty(wins, n),
        "catastrophe_count": cat,
        "crashes": crashes,
        "illegal_accepts": illegal,
        "action_family_share": family_share,
        "action_family_counts": families,
        "inference_p95_ms_mean": float(sum(p95_vals) / len(p95_vals)) if p95_vals else None,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "rows": rows,
    }
    return report


def paired_promotion_check(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """C14 promotion criteria from actual paired results."""
    n = baseline["seed_count"]
    assert n == candidate["seed_count"]
    assert baseline["seeds"] == candidate["seeds"]
    base_rate = baseline["wins_10vp"] / n if n else 0.0
    cand_rate = candidate["wins_10vp"] / n if n else 0.0
    reasons: list[str] = []
    ok = True
    if baseline["wins_10vp"] <= 0:
        ok = False
        reasons.append("baseline_zero_competence")
    if candidate["crashes"] or candidate["illegal_accepts"]:
        ok = False
        reasons.append("crashes_or_illegal")
    if candidate["catastrophe_count"] > baseline["catastrophe_count"]:
        ok = False
        reasons.append("worsened_catastrophe")
    if base_rate > 0 and cand_rate < 0.9 * base_rate:
        ok = False
        reasons.append("below_90pct_baseline_win_rate")
    p95 = candidate.get("inference_p95_ms_mean")
    if p95 is not None and p95 > 20.0:
        ok = False
        reasons.append("inference_p95_above_20ms")
    return {
        "promoted": ok,
        "reasons": reasons,
        "baseline_wins": baseline["wins_10vp"],
        "candidate_wins": candidate["wins_10vp"],
        "baseline_catastrophe": baseline["catastrophe_count"],
        "candidate_catastrophe": candidate["catastrophe_count"],
        "baseline_win_rate": base_rate,
        "candidate_win_rate": cand_rate,
        "required_candidate_rate": 0.9 * base_rate if base_rate > 0 else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=None)
    parser.add_argument("--policy-id", default="candidate")
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--seed-count", type=int, default=200)
    parser.add_argument("--out-name", default="eval_candidate")
    args = parser.parse_args(argv)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    seeds = PROMOTION_SEEDS[: args.seed_count]
    baseline = evaluate_policy(
        policy_id="heuristic",
        artifact=None,
        seeds=seeds,
        max_steps=args.max_steps,
        label="heuristic_baseline",
    )
    (EVAL_DIR / f"{args.out_name}_baseline.json").write_text(
        json.dumps({k: v for k, v in baseline.items() if k != "rows"}, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.artifact:
        candidate = evaluate_policy(
            policy_id=args.policy_id,
            artifact=args.artifact,
            seeds=seeds,
            max_steps=args.max_steps,
            label=args.policy_id,
        )
        promo = paired_promotion_check(baseline, candidate)
        out = {
            "baseline": {k: v for k, v in baseline.items() if k != "rows"},
            "candidate": {k: v for k, v in candidate.items() if k != "rows"},
            "promotion": promo,
        }
        (EVAL_DIR / f"{args.out_name}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"promoted": promo["promoted"], "reasons": promo["reasons"]}))
        return 0 if promo["promoted"] else 2
    print(json.dumps({"baseline_wins": baseline["wins_10vp"], "seeds": len(seeds)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

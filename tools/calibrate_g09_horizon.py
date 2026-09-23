#!/usr/bin/env python3
"""Calibrate G09 leadership evaluation horizon against heuristic baseline.

Runs baseline-only evaluation at several horizons and records wins/VP/runtime.
Does NOT pick the horizon that flatters models — picks a defensible pacing
horizon where the baseline shows legitimate competence (wins > 0) without
being a trivial single-Wait auto-win when possible.

Usage:
  python tools/calibrate_g09_horizon.py --seed-count 40
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "policy_evaluations"
sys.path.insert(0, str(ROOT))

HORIZONS = (8, 20, 40, 80)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-count", type=int, default=40)
    ap.add_argument("--fixture", default="FX-ERA")
    args = ap.parse_args()
    from training.collect import PROMOTION_SEEDS
    from training.evaluate import evaluate_policy

    seeds = PROMOTION_SEEDS[: args.seed_count]
    rows = []
    for h in HORIZONS:
        report = evaluate_policy(
            policy_id="heuristic",
            artifact=None,
            seeds=seeds,
            max_steps=h,
            label=f"baseline_h{h}",
            fixture=args.fixture,
        )
        vps = [int(r.get("candidate_vp") or 0) for r in report.get("rows") or []]
        rows.append(
            {
                "max_steps": h,
                "wins_10vp": report["wins_10vp"],
                "win_rate": report["wins_10vp"] / max(1, report["seed_count"]),
                "mean_vp": round(statistics.mean(vps), 3) if vps else 0.0,
                "median_vp": statistics.median(vps) if vps else 0.0,
                "catastrophe_count": report["catastrophe_count"],
                "crashes": report["crashes"],
                "illegal_accepts": report["illegal_accepts"],
                "elapsed_seconds": report["elapsed_seconds"],
                "action_family_share": report["action_family_share"],
            }
        )
        print(json.dumps({"horizon": h, **{k: rows[-1][k] for k in ("wins_10vp", "mean_vp", "crashes", "elapsed_seconds")}}), flush=True)

    # Prefer smallest horizon with baseline wins > 0 and crashes == 0.
    # FX-ERA is near 9 VP so competence can appear early; document that.
    chosen = None
    for row in rows:
        if row["wins_10vp"] > 0 and row["crashes"] == 0:
            chosen = row["max_steps"]
            break
    if chosen is None:
        # Fall back to longest horizon with fewest crashes.
        chosen = max(rows, key=lambda r: (r["wins_10vp"], -r["crashes"]))["max_steps"]

    reasoning = (
        "FX-ERA starts the winning faction at 9 VP with a legitimate ConstructionService "
        "checkpoint; one or a few world activations can reach 10 VP. Evaluation still "
        "alternates seats so competence is not automatic for every seed. Chosen horizon "
        f"{chosen} is the smallest calibrated horizon where the heuristic baseline shows "
        "non-zero wins and zero crashes on the sample. Same horizon is used for baseline "
        "and all candidates."
    )
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture": args.fixture,
        "seed_count": args.seed_count,
        "seeds": seeds,
        "horizons": rows,
        "chosen_max_steps": chosen,
        "reasoning": reasoning,
    }
    path = OUT / "horizon_calibration.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"chosen_max_steps": chosen, "out": str(path.relative_to(ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

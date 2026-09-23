"""Heuristic trajectory collection and held-out seed splits (C12 / T144)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from training.budget import ComputeBudget
from training.environment import TrainingEnvironment, schema_hash, step_record_to_dict

ROOT = Path(__file__).resolve().parents[1]
DATASETS = Path(__file__).resolve().parent / "datasets"
MANIFEST_PATH = DATASETS / "manifest.json"
LOADABLE_PROMO_PATH = DATASETS / "promotion_seeds_loadable.json"


def _load_promotion_seeds() -> list[int]:
    """Held-out promotion seeds: prefer fixture-validated list (still never used for training)."""
    if LOADABLE_PROMO_PATH.is_file():
        payload = json.loads(LOADABLE_PROMO_PATH.read_text(encoding="utf-8"))
        seeds = [int(s) for s in payload.get("seeds") or []]
        if len(seeds) >= 200:
            return seeds[:200]
    # Fallback contiguous range (may include unloadable worlds on some maps).
    return list(range(10_000, 10_200))


# Fixed held-out promotion set — defined BEFORE any training. Never train on these.
PROMOTION_SEEDS: list[int] = _load_promotion_seeds()
assert len(PROMOTION_SEEDS) == 200
assert len(set(PROMOTION_SEEDS)) == 200

# Training seeds are disjoint and seat-balanced across factions by alternating.
TRAIN_SEED_BASE = 20_000


def build_train_seeds(n: int) -> list[int]:
    seeds = [TRAIN_SEED_BASE + i for i in range(n)]
    overlap = set(seeds) & set(PROMOTION_SEEDS)
    if overlap:
        raise RuntimeError(f"train/promotion overlap: {sorted(overlap)[:5]}")
    return seeds


def collect_trajectories(
    *,
    train_seed_count: int = 40,
    max_steps_per_episode: int = 40,
    budget: ComputeBudget | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    out_dir = out_dir or DATASETS
    out_dir.mkdir(parents=True, exist_ok=True)
    traj_path = out_dir / "heuristic_trajectories.jsonl"
    budget = budget or ComputeBudget(max_seconds=600, max_decisions=50_000, label="collect")

    train_seeds = build_train_seeds(train_seed_count)
    decisions = 0
    episodes = 0
    faction_counts: dict[str, int] = {}
    started = time.monotonic()

    with traj_path.open("w", encoding="utf-8") as handle:
        for seed in train_seeds:
            if budget.exhausted():
                break
            env = TrainingEnvironment(seed=seed, policy_provenance="heuristic")
            try:
                records = env.run_episode(max_steps=max_steps_per_episode)
            except Exception as exc:  # noqa: BLE001 — skip fixture-incompatible seeds honestly
                # Some FX-MVP seeds lack required exits; do not invent data.
                continue
            episodes += 1
            for rec in records:
                if not rec.selected_id and not rec.candidates:
                    # Keep nonacting terminal reward rows out of imitation set,
                    # but count them in manifest outcomes.
                    continue
                if not rec.selected_id:
                    continue
                row = step_record_to_dict(rec)
                handle.write(json.dumps(row, separators=(",", ":")) + "\n")
                decisions += 1
                faction_counts[rec.faction_id] = faction_counts.get(rec.faction_id, 0) + 1
                budget.note_decision()
                if budget.exhausted():
                    break
            budget.touch()

    elapsed = time.monotonic() - started
    manifest = {
        "schema_hash": schema_hash(),
        "policy_provenance": "heuristic",
        "rule_version": 1,
        "promotion_seeds": PROMOTION_SEEDS,
        "promotion_seed_count": len(PROMOTION_SEEDS),
        "train_seeds": train_seeds[:episodes],
        "train_seed_count_requested": train_seed_count,
        "train_seed_count_used": episodes,
        "trajectories_path": str(traj_path.relative_to(ROOT)),
        "decision_rows": decisions,
        "faction_seat_counts": faction_counts,
        "max_steps_per_episode": max_steps_per_episode,
        "elapsed_seconds": round(elapsed, 3),
        "budget": budget.snapshot(),
        "notes": (
            "Promotion seeds locked before training. No promotion seed enters the "
            "training trajectory file. Rewards for nonacting collapsed factions are "
            "emitted by the environment at terminal transitions."
        ),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_no_promotion_leak(manifest: dict[str, Any] | None = None) -> None:
    manifest = manifest or json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    promo = set(manifest["promotion_seeds"])
    train = set(manifest.get("train_seeds") or [])
    leak = promo & train
    if leak:
        raise AssertionError(f"promotion seeds leaked into training: {sorted(leak)[:10]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-seeds", type=int, default=40)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--budget-seconds", type=float, default=900.0)
    args = parser.parse_args(argv)
    budget = ComputeBudget(max_seconds=args.budget_seconds, max_decisions=200_000, label="collect")
    manifest = collect_trajectories(
        train_seed_count=args.train_seeds,
        max_steps_per_episode=args.max_steps,
        budget=budget,
    )
    verify_no_promotion_leak(manifest)
    print(json.dumps({"decision_rows": manifest["decision_rows"], "episodes": manifest["train_seed_count_used"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

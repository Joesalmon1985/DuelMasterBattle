"""Imitation training for candidate scorer (C12 / T145)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from training.budget import ComputeBudget
from training.collect import MANIFEST_PATH, verify_no_promotion_leak
from training.environment import schema_hash
from training.features import encode_candidates, encode_observation
from training.model import CandidateScorer, apply_grads, imitation_loss_and_grads

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINTS = Path(__file__).resolve().parent / "checkpoints"
DEFAULT_TARGET_DECISIONS = 10_000


def _load_rows(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def train_imitation(
    *,
    target_decisions: int = DEFAULT_TARGET_DECISIONS,
    budget_seconds: float = 3600.0,
    lr: float = 0.05,
    seed: int = 1,
    checkpoint_name: str = "imitation_v1",
) -> dict[str, Any]:
    verify_no_promotion_leak()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    traj = ROOT / manifest["trajectories_path"]
    rows = _load_rows(traj)
    if not rows:
        raise RuntimeError("no trajectory rows — run training/collect.py first")

    model = CandidateScorer.create(seed=seed, trained=False)
    init_digest = model.weights_digest()
    budget = ComputeBudget(max_seconds=budget_seconds, max_decisions=target_decisions, label="imitation")
    rng = np.random.default_rng(seed)
    losses: list[float] = []
    seen = 0
    started = time.monotonic()
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    optim_state = {"lr": lr, "seed": seed, "rng_state": rng.bit_generator.state}

    # Repeat over dataset until target or budget.
    order = np.arange(len(rows))
    while not budget.exhausted() and seen < target_decisions:
        rng.shuffle(order)
        for idx in order:
            if budget.exhausted() or seen >= target_decisions:
                break
            row = rows[int(idx)]
            cands = row.get("candidates") or []
            selected = row.get("selected_id")
            if not cands or not selected:
                continue
            ids = [c["id"] for c in cands]
            if selected not in ids:
                continue
            target_index = ids.index(selected)
            obs_vec = encode_observation(row["observation"])
            cand_mat = encode_candidates(cands)
            loss, grads, _value = imitation_loss_and_grads(model, obs_vec, cand_mat, target_index)
            apply_grads(model, grads, lr=lr)
            losses.append(loss)
            seen += 1
            budget.note_decision()
            if seen % 500 == 0:
                _checkpoint(model, CHECKPOINTS / f"{checkpoint_name}.partial.json", optim_state, seen, losses)

    model.trained = seen > 0 and model.weights_digest() != init_digest
    model.provenance = {
        "kind": "imitation",
        "init_seed": seed,
        "decisions_trained": seen,
        "target_decisions": target_decisions,
        "init_digest": init_digest,
        "final_digest": model.weights_digest(),
        "mean_loss": float(np.mean(losses[-200:])) if losses else None,
        "schema_hash": schema_hash(),
        "dataset_manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "budget": budget.snapshot(),
        "trained_beyond_random": model.trained,
    }
    out_path = CHECKPOINTS / f"{checkpoint_name}.json"
    model.save(out_path)
    report = {
        "checkpoint": str(out_path.relative_to(ROOT)),
        "trained": model.trained,
        "decisions_trained": seen,
        "target_decisions": target_decisions,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "budget": budget.snapshot(),
        "weights_digest": model.weights_digest(),
        "init_digest": init_digest,
        "mean_loss_tail": model.provenance["mean_loss"],
        "incomplete_batch": bool(budget.stopped_reason) and seen < target_decisions,
    }
    (CHECKPOINTS / f"{checkpoint_name}_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _checkpoint(
    model: CandidateScorer,
    path: Path,
    optim_state: dict[str, Any],
    seen: int,
    losses: list[float],
) -> None:
    model.provenance = {
        **(model.provenance or {}),
        "partial": True,
        "decisions_trained": seen,
        "optim": {"lr": optim_state["lr"], "seed": optim_state["seed"]},
        "mean_loss_tail": float(np.mean(losses[-100:])) if losses else None,
    }
    model.trained = True
    model.save(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-decisions", type=int, default=10_000)
    parser.add_argument("--budget-seconds", type=float, default=3600.0)
    parser.add_argument("--lr", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--name", default="imitation_v1")
    args = parser.parse_args(argv)
    report = train_imitation(
        target_decisions=args.target_decisions,
        budget_seconds=args.budget_seconds,
        lr=args.lr,
        seed=args.seed,
        checkpoint_name=args.name,
    )
    print(json.dumps(report))
    return 0 if report["trained"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Bounded actor-critic improvement (C12 / T146)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from training.budget import ComputeBudget
from training.collect import PROMOTION_SEEDS, build_train_seeds
from training.environment import TrainingEnvironment, schema_hash
from training.features import encode_candidates, encode_observation
from training.model import CandidateScorer, apply_grads, softmax

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINTS = Path(__file__).resolve().parent / "checkpoints"
DEFAULT_TARGET = 20_000


def train_actor_critic(
    *,
    init_checkpoint: Path,
    target_decisions: int = DEFAULT_TARGET,
    budget_seconds: float = 3600.0,
    lr: float = 0.01,
    seed: int = 2,
    max_steps_per_episode: int = 30,
    checkpoint_name: str = "actor_critic_v1",
) -> dict[str, Any]:
    model = CandidateScorer.load(init_checkpoint)
    if not model.trained:
        # Allow continuing from imitation that marked trained; reject pure random.
        raise RuntimeError("refusing actor-critic from untrained weights")
    init_digest = model.weights_digest()
    budget = ComputeBudget(max_seconds=budget_seconds, max_decisions=target_decisions, label="actor_critic")
    rng = np.random.default_rng(seed)
    train_seeds = build_train_seeds(500)
    # Ensure no promotion seeds.
    assert not (set(train_seeds) & set(PROMOTION_SEEDS))

    seen = 0
    returns: list[float] = []
    started = time.monotonic()
    seed_i = 0
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)

    while not budget.exhausted() and seen < target_decisions:
        ep_seed = int(train_seeds[seed_i % len(train_seeds)])
        seed_i += 1
        env = TrainingEnvironment(seed=ep_seed, policy_provenance="neural_training")
        try:
            batch = env.run_episode(max_steps=max_steps_per_episode)
        except Exception:
            continue
        for rec in batch:
            if budget.exhausted() or seen >= target_decisions:
                break
            if not rec.candidates or not rec.selected_id:
                continue
            ids = [c["id"] for c in rec.candidates]
            if rec.selected_id not in ids:
                continue
            obs_vec = encode_observation(rec.observation)
            cand_mat = encode_candidates(rec.candidates)
            scores, value, cache = model.forward(obs_vec, cand_mat)
            probs = softmax(scores)
            idx = ids.index(rec.selected_id)
            advantage = float(rec.reward) - float(value)
            # Policy gradient: -log π(a) * advantage; value MSE.
            ds = probs.copy()
            # d(-log p_i)/ds = p - one_hot for CE; times advantage for REINFORCE
            one_hot = np.zeros_like(probs)
            one_hot[idx] = 1.0
            d_ce = probs - one_hot
            ds = d_ce * (-advantage)  # minimize -A*logp ⇒ grad = -A*(p-onehot)? Wait:
            # L = -A * log p_i ; dL/ds = -A * (one_hot - p) = A * (p - one_hot)
            ds = advantage * (probs - one_hot)

            h = cache["h"]
            concat = cache["concat"]
            h_obs = cache["h_obs"]
            h_cand = cache["h_cand"]
            dW_score2 = h.T @ ds.reshape(-1, 1)
            db_score2 = ds.reshape(-1, 1).sum(axis=0)
            dh = ds.reshape(-1, 1) @ model.params["W_score2"].T
            dh *= (h > 0).astype(np.float64)
            dW_score1 = concat.T @ dh
            db_score1 = dh.sum(axis=0)
            dconcat = dh @ model.params["W_score1"].T
            dh_obs = dconcat[:, :64].sum(axis=0)
            dh_cand = dconcat[:, 64:] * (h_cand > 0).astype(np.float64)
            dW_cand1 = cand_mat.T @ dh_cand
            db_cand1 = dh_cand.sum(axis=0)
            # Value loss: 0.5 (V - R)^2 ; dV = (V - R)
            dvalue = float(value) - float(rec.reward)
            dW_value = np.outer(h_obs, np.array([dvalue]))
            db_value = np.array([dvalue], dtype=np.float64)
            dh_obs = dh_obs + (model.params["W_value"] @ np.array([dvalue])).reshape(-1)
            dh_obs_relu = dh_obs * (h_obs > 0).astype(np.float64)
            dW_obs1 = np.outer(obs_vec, dh_obs_relu)
            db_obs1 = dh_obs_relu
            grads = {
                "W_obs1": dW_obs1,
                "b_obs1": db_obs1,
                "W_cand1": dW_cand1,
                "b_cand1": db_cand1,
                "W_score1": dW_score1,
                "b_score1": db_score1,
                "W_score2": dW_score2,
                "b_score2": db_score2,
                "W_value": dW_value,
                "b_value": db_value,
            }
            apply_grads(model, grads, lr=lr)
            returns.append(float(rec.reward))
            seen += 1
            budget.note_decision()
            # No endless stock/activity reward: rewards come from env contract only.
        # Persist resume state periodically.
        if seen and seen % 400 == 0:
            model.provenance = {
                **(model.provenance or {}),
                "kind": "actor_critic_partial",
                "decisions_trained": seen,
                "rng_seed": seed,
                "seed_i": seed_i,
            }
            model.save(CHECKPOINTS / f"{checkpoint_name}.partial.json")
            budget.save(CHECKPOINTS / f"{checkpoint_name}.budget.json")

    model.trained = True
    model.provenance = {
        "kind": "actor_critic",
        "parent_checkpoint": str(Path(init_checkpoint).name),
        "parent_digest": init_digest,
        "decisions_trained": seen,
        "target_decisions": target_decisions,
        "final_digest": model.weights_digest(),
        "schema_hash": schema_hash(),
        "mean_reward_tail": float(np.mean(returns[-200:])) if returns else None,
        "budget": budget.snapshot(),
        "trained_beyond_parent": model.weights_digest() != init_digest,
    }
    out_path = CHECKPOINTS / f"{checkpoint_name}.json"
    model.save(out_path)
    report = {
        "checkpoint": str(out_path.relative_to(ROOT)),
        "decisions_trained": seen,
        "target_decisions": target_decisions,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "budget": budget.snapshot(),
        "weights_digest": model.weights_digest(),
        "parent_digest": init_digest,
        "incomplete_batch": bool(budget.snapshot().get("incomplete_batch")),
        "promotion_claimed": False,
        "notes": "Reaching the decision target is complete; premature stops are incomplete_batch.",
    }
    (CHECKPOINTS / f"{checkpoint_name}_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", type=Path, default=CHECKPOINTS / "imitation_v1.json")
    parser.add_argument("--target-decisions", type=int, default=20_000)
    parser.add_argument("--budget-seconds", type=float, default=3600.0)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--name", default="actor_critic_v1")
    args = parser.parse_args(argv)
    report = train_actor_critic(
        init_checkpoint=args.init,
        target_decisions=args.target_decisions,
        budget_seconds=args.budget_seconds,
        lr=args.lr,
        seed=args.seed,
        max_steps_per_episode=args.max_steps,
        checkpoint_name=args.name,
    )
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

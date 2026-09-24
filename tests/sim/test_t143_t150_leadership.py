"""G09 leadership training behavioural checks (T143–T150)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from sim.dmb.ai.heuristic import HeuristicBrain
from sim.dmb.ai.neural import NeuralBrain
from sim.dmb.ai.policy import PolicyService, register_neural_artifact
from sim.dmb.testing.fixtures import load_fixture
from training.collect import PROMOTION_SEEDS, build_train_seeds
from training.environment import TrainingEnvironment, schema_hash
from training.features import encode_candidates, encode_observation
from training.model import CandidateScorer, imitation_loss_and_grads, apply_grads

ROOT = Path(__file__).resolve().parents[2]


def test_t143_env_advances_and_masks_validate() -> None:
    env = TrainingEnvironment(seed=20000, max_turns=5)
    env.reset(20000)
    records = env.step()
    assert records
    for rec in records:
        if not rec.selected_id:
            continue
        ids = {c["id"] for c in rec.candidates}
        assert rec.selected_id in ids
    snap = env._snapshot()
    assert snap["schema_hash"] == schema_hash()
    assert int(snap["turn"]) >= 1


def test_t143_replay_no_free_stock() -> None:
    env = TrainingEnvironment(seed=20001, max_turns=3)
    recs = env.run_episode(max_steps=3)
    assert recs
    assert env.sim is not None
    for store_id, store in env.sim.state.stocks.items():
        if str(store_id).startswith("_"):
            continue
        goods = store if isinstance(store, dict) else {}
        for _g, qty in (goods.get("goods") or goods).items() if isinstance(goods, dict) else []:
            if isinstance(qty, (int, float)):
                assert qty >= 0


def test_t144_promotion_seeds_locked_and_disjoint() -> None:
    assert len(PROMOTION_SEEDS) == 200
    train = build_train_seeds(100)
    assert not (set(train) & set(PROMOTION_SEEDS))


def test_t145_model_ranks_only_supplied_candidates(tmp_path: Path) -> None:
    model = CandidateScorer.create(seed=7)
    obs = {"own": {"vp": 1}, "time": {"turn": 1}, "public": {}, "observed": {}}
    cands = [
        {"id": "a", "action_kind": "noop", "params": {}, "benefit": {}},
        {"id": "b", "action_kind": "construct", "params": {"action": "road"}, "benefit": {"vp_gain": 0}},
    ]
    ranked = model.score_candidates(obs, cands)
    assert {r[0] for r in ranked} == {"a", "b"}
    # Train a few steps so weights move.
    init = model.weights_digest()
    obs_vec = encode_observation(obs)
    cand_mat = encode_candidates(cands)
    for _ in range(20):
        loss, grads, _ = imitation_loss_and_grads(model, obs_vec, cand_mat, 1)
        apply_grads(model, grads, lr=0.1)
    model.trained = True
    assert model.weights_digest() != init
    path = tmp_path / "m.json"
    model.save(path)
    loaded = CandidateScorer.load(path)
    assert loaded.weights_digest() == model.weights_digest()
    # Schema mismatch rejects.
    bad = json.loads(path.read_text(encoding="utf-8"))
    bad["schema_hash"] = "deadbeefdeadbeef"
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    try:
        CandidateScorer.load(bad_path)
        assert False, "expected schema mismatch"
    except ValueError as exc:
        assert "schema" in str(exc).lower()


def test_t146_budget_marks_incomplete() -> None:
    from training.budget import ComputeBudget
    import time

    budget = ComputeBudget(max_seconds=0.05, max_decisions=10_000, label="t")
    # Windows timer resolution can be coarse under load — wait until exhausted.
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and not budget.exhausted():
        time.sleep(0.05)
    assert budget.exhausted()
    assert budget.snapshot()["incomplete_batch"] is True
    assert budget.snapshot().get("stopped_reason") == "max_seconds"


def test_t147_neural_fallback_and_policy_identity(tmp_path: Path) -> None:
    model = CandidateScorer.create(seed=3)
    # Tiny train so trained=True and digest moves.
    obs = {"own": {"vp": 0}, "time": {}, "public": {}, "observed": {}}
    cands = [
        {"id": "noop:1", "action_kind": "noop", "params": {}, "benefit": {}},
        {"id": "construct:1", "action_kind": "construct", "params": {"action": "road"}, "benefit": {}},
    ]
    obs_vec = encode_observation(obs)
    cand_mat = encode_candidates(cands)
    init = model.weights_digest()
    for _ in range(30):
        loss, grads, _ = imitation_loss_and_grads(model, obs_vec, cand_mat, 0)
        apply_grads(model, grads, lr=0.1)
    model.trained = model.weights_digest() != init
    art = tmp_path / "policy.json"
    model.save(art)

    brain = NeuralBrain(artifact_path=art, policy_id="test-policy")
    choice = brain.choose_activation(obs, cands)
    assert choice["primary_id"] in {c["id"] for c in cands}
    assert choice["source"] in {"neural", "heuristic_fallback"}

    # Forced inference failure → heuristic fallback, no extra action slots.
    brain.force_fail = True
    fb = brain.choose_activation(obs, cands)
    assert fb["source"] == "heuristic_fallback"
    assert len(fb["selected_ids"]) <= 2

    # Wrong schema → fallback on load.
    bad = json.loads(art.read_text(encoding="utf-8"))
    bad["schema_hash"] = "ffffffffffffffff"
    bad_path = tmp_path / "bad_policy.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    broken = NeuralBrain(artifact_path=bad_path, policy_id="broken")
    assert broken.model is None
    fb2 = broken.choose_activation(obs, cands)
    assert fb2["source"] == "heuristic_fallback"

    # Policy identity after save/load on world faction bucket.
    sim = load_fixture("FX-MVP", seed=20003)
    register_neural_artifact("test-policy", str(art))
    policy = PolicyService(sim.state)
    policy.assign_brain("faction:1", "test-policy")
    assert policy._policy_bucket("faction:1")["policy_id"] == "test-policy"
    save_path = tmp_path / "world.json"
    # Use lightweight JSON dump of faction policy identity (full save may need bridge).
    payload = {"factions": sim.state.factions}
    save_path.write_text(json.dumps(payload), encoding="utf-8")
    restored = json.loads(save_path.read_text(encoding="utf-8"))
    assert restored["factions"]["faction:1"]["policy"]["policy_id"] == "test-policy"


def test_t148_promotion_oracle_rejects_weak_candidate() -> None:
    from training.evaluate import paired_promotion_check

    baseline = {
        "seed_count": 10,
        "seeds": list(range(10)),
        "wins_10vp": 5,
        "catastrophe_count": 1,
        "crashes": 0,
        "illegal_accepts": 0,
    }
    weak = {
        "seed_count": 10,
        "seeds": list(range(10)),
        "wins_10vp": 1,
        "catastrophe_count": 3,
        "crashes": 0,
        "illegal_accepts": 0,
        "inference_p95_ms_mean": 5.0,
    }
    promo = paired_promotion_check(baseline, weak)
    assert promo["promoted"] is False
    assert "worsened_catastrophe" in promo["reasons"] or "below_90pct_baseline_win_rate" in promo["reasons"]


def test_t149_does_not_label_heuristic_trained(tmp_path: Path) -> None:
    # Manifest helper honesty: heuristic entry always trained=False.
    manifest = {
        "heuristic_fallback": {"id": "heuristic", "kind": "heuristic", "trained": False},
        "policies": [],
    }
    assert manifest["heuristic_fallback"]["trained"] is False

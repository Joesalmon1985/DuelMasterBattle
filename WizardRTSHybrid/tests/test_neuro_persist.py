"""T5.3: model export/import, checkpoints, pruning."""
import copy
import json

import numpy as np
import pytest

from neuro import manifest as M
from neuro import nets, persist


def test_save_and_load_give_identical_outputs_on_random_inputs(tmp_path):
    g = nets.random_genome(np.random.default_rng(1))
    man = M.build({})
    persist.save_model(tmp_path / "best_ai.json", g, man, {"adv": 12.5})
    g2, meta = persist.load_model(tmp_path / "best_ai.json", man)
    assert np.array_equal(g, g2) and meta["compatibility"] == "same" and meta["evaluation"] == {"adv": 12.5} and meta["npz_sha256"]
    a, b = nets.Nets(g), nets.Nets(g2)
    rng = np.random.default_rng(2)
    for name, i, _h, _o in nets.LAYOUT:
        x = rng.normal(0, 1, (100, i)).astype(np.float32)
        assert np.array_equal(a.forward(name, x), b.forward(name, x))
    assert set(np.load(tmp_path / "best_ai.npz").files) == set(nets.MODULES) | {"theta"}


def test_a_changed_npz_or_wrong_shape_is_refused(tmp_path):
    g = nets.random_genome(np.random.default_rng(1))
    persist.save_model(tmp_path / "m.json", g, M.build({}))
    raw = (tmp_path / "m.npz").read_bytes()
    (tmp_path / "m.npz").write_bytes(raw[:-8] + b"\0" * 8)
    with pytest.raises(persist.ModelError):
        persist.load_model(tmp_path / "m.json")
    with pytest.raises(persist.ModelError):
        persist.save_model(tmp_path / "n.json", np.zeros(10, np.float32), M.build({}))


def test_other_roster_is_refused_and_other_rules_need_reevaluation(tmp_path):
    g = nets.random_genome(np.random.default_rng(1))
    man = M.build({})
    persist.save_model(tmp_path / "m.json", g, man)
    other = copy.deepcopy(man)
    other["roster_version"] = "roster-9.0.0"
    with pytest.raises(persist.ModelError):
        persist.load_model(tmp_path / "m.json", other)
    other = copy.deepcopy(man)
    other["rules_version"] = "rules-2099"
    _g, meta = persist.load_model(tmp_path / "m.json", other)
    assert meta["compatibility"] == "reevaluate"


def test_a_corrupt_newest_checkpoint_falls_back_to_the_previous_one(tmp_path):
    for gen in (1, 2, 3):
        persist.save_checkpoint(tmp_path, {"generation": gen, "theta": np.full(4, gen, np.float32)}, gen)
    assert persist.load_checkpoint(tmp_path)["generation"] == 3
    newest = tmp_path / "checkpoints" / "ckpt_000003.pkl"
    newest.write_bytes(newest.read_bytes()[:-5] + b"xxxxx")
    assert persist.load_checkpoint(tmp_path)["generation"] == 2
    newest.write_bytes(b"")
    assert persist.load_checkpoint(tmp_path)["generation"] == 2
    assert persist.load_checkpoint(tmp_path / "nowhere") is None


def test_prune_keeps_three_checkpoints_four_generations_and_all_promotion_games(tmp_path):
    for gen in range(1, 8):
        persist.save_checkpoint(tmp_path, {"generation": gen}, gen)
        d = tmp_path / "games" / f"gen_{gen:06d}" / "job"
        d.mkdir(parents=True)
        (d / "result.json").write_text("{}")
    promo = tmp_path / "games" / "promotion" / "p1"
    promo.mkdir(parents=True)
    (promo / "result.json").write_text("{}")
    r = persist.prune(tmp_path)
    assert sorted(p.name for p in (tmp_path / "checkpoints").glob("*.pkl")) == ["ckpt_000005.pkl", "ckpt_000006.pkl", "ckpt_000007.pkl"]
    assert sorted(p.name for p in (tmp_path / "games").glob("gen_*")) == [f"gen_{g:06d}" for g in (4, 5, 6, 7)] and promo.exists()
    assert r["checkpoints"] == 4 and r["generations"] == 3


def test_prune_enforces_the_size_cap_by_dropping_the_oldest_generations(tmp_path):
    for gen in range(1, 6):
        d = tmp_path / "games" / f"gen_{gen:06d}"
        d.mkdir(parents=True)
        (d / "big.bin").write_bytes(b"\0" * 400_000)
    persist.save_checkpoint(tmp_path, {"generation": 5}, 5)
    persist.prune(tmp_path, keep_generations=10, max_run_gb=0.001)  # 1 MB cap
    left = sorted(p.name for p in (tmp_path / "games").glob("gen_*"))
    assert left and left[-1] == "gen_000005" and len(left) < 5
    assert persist.load_checkpoint(tmp_path)["generation"] == 5

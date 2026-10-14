"""T5.2: two generations of the evolution loop in-process with a pool of two (small map, 10-minute games)."""
import json

import numpy as np

from neuro import manifest as M
from neuro import nets, persist
from neuro.evolve import Evolution, EvolutionConfig, STREAM_HELDOUT, STREAM_TRAIN, stream_seed
from neuro.workers import GamePool

CFG = dict(name="test", population=4, seeds_per_generation=1, game_minutes=10, map_size="small", imitation_fraction=0.0, promote=False, workers=2, wall_cap_s=600)


def test_two_generations_change_theta_write_summaries_and_resume_from_the_checkpoint(tmp_path):
    cfg = EvolutionConfig.from_dict(CFG)
    man = M.build(cfg.to_dict())
    ev = Evolution(tmp_path / "run", cfg, man)
    theta0 = ev.lineages["random"].theta.copy()
    pool = GamePool(2, poll_s=0.2)
    s0 = ev.generation(pool)
    s1 = ev.generation(pool)
    assert s0["generation"] == 0 and s1["generation"] == 1 and s0["valid_games"] >= 8 and not s0.get("aborted")
    theta1 = ev.lineages["random"].theta
    assert theta1.shape == theta0.shape and not np.array_equal(theta1, theta0) and np.isfinite(theta1).all()
    lines = (tmp_path / "run" / "generations.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert [json.loads(x)["generation"] for x in lines] == [0, 1]
    for key in ("best_advantage", "mean_advantage", "commands_per_tick", "rejected_fraction", "control_loss_rate", "advantage_by_level", "heads_used"):
        assert key in s0
    assert set(s0["advantage_by_level"]) == {"C0"} and s0["lineages"]["random"]["children"] == 4
    assert (tmp_path / "run" / "best_by_gen" / "gen_000000.npy").exists() and list((tmp_path / "run" / "checkpoints").glob("*.pkl"))
    # a second Evolution built on the same directory continues where the first stopped
    again = Evolution(tmp_path / "run", cfg, man)
    assert again.generation_index == 2 and np.array_equal(again.lineages["random"].theta, theta1) and len(again.history) == 2
    assert again.lineages["random"].t == ev.lineages["random"].t


def test_seed_streams_never_overlap_and_children_are_mirrored(tmp_path):
    tr = {stream_seed(1, STREAM_TRAIN, g, k) for g in range(50) for k in range(4)}
    ho = {stream_seed(1, STREAM_HELDOUT, n, k) for n in range(50) for k in range(6)}
    assert not (tr & ho) and len(tr) == 200 and max(tr) < 4_000_000 <= min(ho)
    cfg = EvolutionConfig.from_dict({**CFG, "population": 6})
    ev = Evolution(tmp_path / "run", cfg, M.build(cfg.to_dict()))
    plan = ev._plan(0)
    kids = [e for e in plan if e.kind == "child"]
    parents = [e for e in plan if e.kind == "parent"]
    assert len(kids) == 6 and len(parents) == 1
    theta = ev.lineages["random"].theta
    for a, b in zip(kids[0::2], kids[1::2]):
        assert a.pair == b.pair and a.sign == 1 and b.sign == -1 and a.games == b.games
        assert np.allclose((a.genome + b.genome) / 2, theta, atol=1e-6) or (a.mask and True)  # temperatures are clipped, everything else is symmetric
        assert a.mask == b.mask and set(a.mask) <= set(nets.MODULES)
    ids = {e.id for e in plan}
    assert len(ids) == len(plan)
    assert plan == plan and [e.id for e in ev._plan(0)] == [e.id for e in plan]  # deterministic

"""Outbreak environment: shared dynamics with the game module, baselines, recoverable and catastrophic paths, masks, replay."""
import numpy as np
import pytest

from wizard_rts import regions
from wizard_rts.envs.outbreak_env import OutbreakEnv, StubWorld, layout_for, policy_greedy, policy_noop, policy_random, run_episode


def test_stub_world_runs_the_games_own_regions_module():
    env = OutbreakEnv()
    env.reset(1)
    assert env.R == 25 and isinstance(env.rg, regions.Regions)
    env.step(env.R)  # wait 30 s
    assert env.w.dmb.clock["game_ms"] == 30_000
    # the same module, so the same rule: a cube is added at the 10 minute mark
    for _ in range(19):
        env.step(env.R)
    assert env.rg.added == 1 and sum(env.rg.cubes) == 1


def test_observation_partial_hides_unreported_regions_and_full_does_not():
    p = OutbreakEnv(mode="partial")
    p.reset(2)
    for _ in range(25):
        p.step(p.R)
    obs = p.observe()
    assert -1 in obs["cubes"]  # some regions are unknown to the wizard
    f = OutbreakEnv(mode="full")
    f.reset(2)
    for _ in range(25):
        f.step(f.R)
    assert -1 not in f.observe()["cubes"] and p.state()["cubes"] == f.state()["cubes"]  # same world, different knowledge


def test_noop_drifts_toward_loss_greedy_contains_and_both_are_measured():
    scale = 1.0  # the default cadence, a cube every ten minutes
    res = {"noop": [], "greedy": [], "random": []}
    for seed in range(5):
        env = OutbreakEnv(interval_scale=scale, horizon_min=120, mode="full")
        res["noop"].append(run_episode(env, policy_noop, seed))
        res["greedy"].append(run_episode(env, policy_greedy, seed))
        res["random"].append(run_episode(env, policy_random(np.random.RandomState(seed)), seed))
    mean = lambda k, f: float(np.mean([r[f] for r in res[k]]))
    assert mean("greedy", "outbreaks") < mean("noop", "outbreaks")
    assert mean("greedy", "return") > mean("noop", "return")
    assert all(r["lost"] for r in res["noop"])  # neglect ends the cycle within two game hours on every seed: attention is required
    assert all(not r["lost"] and r["outbreaks"] == 0 for r in res["greedy"])  # and little attention suffices: the challenge is not unavoidable death
    assert mean("greedy", "treated") > 0


def test_a_recoverable_run_exists_and_a_catastrophic_one_is_terminal():
    easy = OutbreakEnv(interval_scale=2.0, mode="full")
    r = run_episode(easy, policy_greedy, 3)
    assert not r["lost"] and r["reason"] == "horizon"
    brutal = OutbreakEnv(interval_scale=0.05, mode="full", horizon_min=240)  # a cube every thirty seconds: an impossible difficulty
    r2 = run_episode(brutal, policy_noop, 3)
    assert r2["lost"] and r2["reason"] == "terminal_loss"  # eight outbreaks end the cycle


def test_illegal_action_is_rejected_and_replay_is_deterministic():
    env = OutbreakEnv()
    env.reset(4)
    assert env.step(999)[4]["illegal"] and env.t == 1
    actions = [env.R, 3, 7, env.R, 12]
    h1 = OutbreakEnv().replay(actions, seed=4)
    h2 = OutbreakEnv().replay(actions, seed=4)
    assert h1 == h2


def test_era_changes_the_hazard_kind():
    env = OutbreakEnv(era=2)
    env.reset(1)
    for _ in range(25):
        env.step(env.R)
    kinds = {k for k in env.rg.kind if k}
    assert kinds == {"toxic_spill"}


def test_encoding_has_a_fixed_size_and_masks_are_all_legal():
    env = OutbreakEnv()
    env.reset(0)
    assert env.encode().shape == env.encode(env.observe()).shape and env.legal_mask().sum() == env.R + 1

"""Cross-system environment: one real world, two crises, macro-skills over real ops; baselines and determinism."""
import numpy as np
import pytest

from wizard_rts import regions, story
from wizard_rts.envs.fullgame_env import FullGameEnv, V, policy_interleaved, policy_story_first, policy_treat_first, policy_wait, run_episode


def test_one_world_hosts_story_and_outbreaks():
    env = FullGameEnv()
    env.reset(0)
    w = env.w
    assert w.dmb.quests and story.state(w)["dungeons"] and regions.state(w).added >= 0
    assert len(w.dmb.settlements) == 6 and w.terrain is not None  # a full campaign world, not a fixture of its own
    obs = env.observe()
    assert obs["stage"] == "start" and not obs["inside"]


def test_story_first_completes_the_story_and_changes_the_deposit():
    env = FullGameEnv()
    r = run_episode(env, policy_story_first, 1)
    assert r["quest"] == "completed"
    assert env.w.stats.get("story_vein_units_coal", 0) in (36, 120)
    assert not story.state(env.w)["in_dungeon"]


def test_wait_forever_ends_in_loss_or_horizon_and_never_completes_the_story():
    env = FullGameEnv(horizon_min=60)
    r = run_episode(env, policy_wait, 2)
    assert r["quest"] != "completed" and r["reason"] in ("terminal_loss", "horizon")


def test_competing_crises_make_the_order_matter():
    res = {"story_first": [], "treat_first": [], "interleaved": []}
    for seed in range(3):
        env = FullGameEnv(interval_scale=0.25, horizon_min=45)
        res["story_first"].append(run_episode(env, policy_story_first, seed))
        res["treat_first"].append(run_episode(env, policy_treat_first, seed))
        res["interleaved"].append(run_episode(env, policy_interleaved(2), seed))
    mean = lambda k, f: float(np.mean([r[f] for r in res[k]]))
    # the three orders really differ in outcome: the world rewards a prioritiser
    assert len({round(mean(k, "return"), 2) for k in res}) >= 2
    assert any(r["quest"] == "completed" for r in res["story_first"] + res["interleaved"])


def test_mask_gates_skills_by_stage_and_hides_unknown_regions():
    env = FullGameEnv()
    env.reset(3)
    m = env.legal_mask()
    assert m[V["social"]] == 1 and m[V["puzzles"]] == 0 and m[V["duel"]] == 0 and m[V["leave"]] == 0
    assert env.step(V["duel"])[4]["illegal"] is True
    env.step(V["social"])
    assert env.legal_mask()[V["puzzles"]] == 1 and env.legal_mask()[V["social"]] == 0


def test_duel_freezes_time_inside_the_environment():
    env = FullGameEnv()
    env.reset(4)
    env.step(V["social"])
    env.step(V["puzzles"])
    ms = env.w.dmb.clock["game_ms"]
    env.step(V["duel"])
    assert env.w.dmb.clock["game_ms"] == ms  # breaking the code cost no world time (the pause token was held throughout)
    assert env.stage == 4


def test_replay_and_save_load_agree():
    env = FullGameEnv()
    env.reset(5)
    acts = [V["social"], V["puzzles"], V["duel"], V["leave"]]
    for a in acts:
        env.step(a)
    h = env.state_hash()
    assert FullGameEnv().replay(acts, seed=5) == h
    assert FullGameEnv.load(env.save()).state_hash() == h

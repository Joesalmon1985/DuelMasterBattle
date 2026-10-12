"""Quest/social environment on the real settlement: knowledge limits, scripted expert, changing world conditions, idempotence, save/load."""
import numpy as np
import pytest

from wizard_rts import story
from wizard_rts.envs.quest_env import N, V, VERBS, QuestEnv


def run_expert(env, seed, **scenario):
    env.reset(seed, **scenario)
    for _ in range(60):
        env.step(env.expert_action())
        if env.done:
            break
    return env


def test_expert_learns_takes_the_sigil_and_reaches_the_gallery():
    env = run_expert(QuestEnv(), 1)
    assert env.reason == "reached_dungeon_with_the_sigil" and env.return_ > 1.0
    assert {"ask_cause", "ask_gallery", "accept_help", "persuade"} <= env.learned
    assert any(i.startswith("sigil_") for i in story.state(env.w)["inventory"])
    q = next(iter(env.w.dmb.quests.values()))
    assert q["status"] == "active"  # accepted, not yet finished: the rest of the story belongs to the dungeon and the duel


def test_observation_holds_only_what_the_wizard_knows():
    env = QuestEnv()
    o = env.reset(2)
    text = str(o)
    assert "puzzles" not in text and "secret" not in text and "needs" not in text and "effect_receipts" not in text
    assert o["dialogue"] is None and o["learned"] == [] and o["inventory"] == []
    assert any(e["kind"] == "npc" and e["marker"] for e in o["seen"])  # the quest marker over the person is visible
    env.step(V["go_npc0"])
    env.step(V["talk"])
    o = env.observe()
    assert any("The seam under" in line for line in o["dialogue"]["lines"])  # he now knows what the miner told him


def test_mask_follows_position_and_dialogue():
    env = QuestEnv()
    env.reset(0)
    m = env.legal_mask()
    assert m[V["talk"]] == 0 and m[V["leave_dialogue"]] == 0 and m[V["enter_gallery"]] == 0 and m[V["wait"]] == 1
    assert env.step(V["talk"])[4]["illegal"] is True  # not next to anyone
    env.step(V["go_npc0"])
    assert env.legal_mask()[V["talk"]] == 1
    env.step(V["talk"])
    m = env.legal_mask()
    assert m[V["choose_ask_cause"]] == 1 and m[V["choose_accept_help"]] == 0  # he has not learned about the gallery yet
    assert m[V["choose_persuade"]] == 0  # persuasion needs the sigil first


def test_giving_up_closes_the_quest_with_a_consequence():
    env = QuestEnv()
    env.reset(3)
    env.step(V["go_npc0"])
    env.step(V["talk"])
    _o, r, term, _tr, info = env.step(V["choose_give_up"])
    assert env.done and env.reason == "failed_with_consequence" and r < -0.5


@pytest.mark.parametrize("kind,reason", [("world_fix_first", "resolved_by_world"), ("mine_destroyed", "failed_with_consequence"), ("npc_dead", "suspended")])
def test_changing_world_conditions_close_or_suspend_the_quest(kind, reason):
    env = QuestEnv()
    env.reset(4, kind=kind, at_step=2)
    env.step(V["go_npc0"])
    env.step(V["wait"])
    env.step(V["wait"])
    for _ in range(4):
        if env.done:
            break
        env.step(V["wait"])
    assert env.reason == reason, (kind, env.reason)


def test_reload_in_the_middle_changes_nothing_and_effects_stay_idempotent():
    plain = run_expert(QuestEnv(), 5)
    again = run_expert(QuestEnv(), 5, kind="reload", at_step=4)
    assert plain.reason == again.reason == "reached_dungeon_with_the_sigil"
    assert plain.state()["quest"] == again.state()["quest"]
    q = next(iter(again.w.dmb.quests.values()))
    assert q["effect_receipts"] == [] and len(again.w.dmb.quests) == 1  # no reward and no duplicate quest from the reload


def test_replay_save_load_and_determinism():
    env = QuestEnv()
    env.reset(6)
    acts = []
    for _ in range(6):
        a = env.expert_action()
        acts.append(a)
        env.step(a)
    h = env.state_hash()
    assert QuestEnv().replay(acts, seed=6) == h
    assert QuestEnv.load(env.save()).state_hash() == h


def test_encoding_is_fixed_size_and_a_random_policy_never_breaks_the_world():
    env = QuestEnv()
    rng = np.random.RandomState(0)
    for seed in range(3):
        env.reset(seed)
        sizes = {env.encode().size}
        for _ in range(30):
            legal = env.legal_actions()
            env.step(int(rng.choice(legal)))
            sizes.add(env.encode().size)
            if env.done:
                break
        assert len(sizes) == 1
        assert len(env.w.dmb.quests) == 1

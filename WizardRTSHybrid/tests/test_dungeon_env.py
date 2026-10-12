"""Dungeon environment: expert reachability over many generated dungeons, mask legality, soft-lock detection, replay and save/load."""
import pickle

import numpy as np
import pytest

from wizard_rts.envs.dungeon_env import DIRS, N_VERBS, V_CLEAR, V_INTERACT, DungeonEnv, make_dungeon, reachability, split_seeds
from wizard_rts.puzzle import gen


def test_splits_are_disjoint():
    a, b, c = set(split_seeds("train")), set(split_seeds("val")), set(split_seeds("test"))
    assert not (a & b) and not (a & c) and not (b & c)


def test_every_generated_dungeon_is_completable_by_the_expert_with_the_sigil():
    kinds = set()
    steps = []
    for seed in range(60):
        r = reachability(seed)
        assert r["solved"], r
        kinds.update(r["types"])
        steps.append(r["steps"])
    assert kinds == set(gen.TEMPLATES)  # every template occurred in the sample
    assert max(steps) < 500  # within the episode bound


def test_without_the_imported_sigil_the_dependency_room_is_unsolvable_and_detected():
    r = reachability(3, with_sigil=False)
    assert r["solved"] is False and r["why"] in ("planner_failed", "truncated")
    env = DungeonEnv(with_sigil=False)
    env.reset(3)
    assert not any(it.startswith("sigil_") for it in env.inv)  # the soft-lock is a missing dependency, not a bug in the puzzle


def test_mask_matches_the_real_rules_and_illegal_actions_do_nothing():
    env = DungeonEnv()
    env.reset(1)
    m = env.legal_mask()
    assert m.shape == (N_VERBS,) and m[V_CLEAR] == 1 and m[V_INTERACT] == 0  # nothing within reach at the start
    for k, (dx, dy) in enumerate(DIRS):
        x, y = env.run.state["pos"]
        assert bool(m[k]) == env.run.walkable(x + dx, y + dy)
    pos = list(env.run.state["pos"])
    _o, r, _t, _tr, info = env.step(V_INTERACT)
    assert info["illegal"] and r < 0 and env.run.state["pos"] == pos
    walls = [k for k in range(4) if not m[k]]
    if walls:
        assert env.step(walls[0])[4]["illegal"]


def test_observation_never_contains_puzzle_records_and_encoding_has_fixed_size():
    env = DungeonEnv()
    sizes = set()
    for seed in range(5):
        o = env.reset(seed)
        assert "puzzles" not in str(o) and "order" not in o and "solution" not in str(o)
        sizes.add(env.encode().size)
        for _ in range(30):
            a = env.expert_action()
            env.step(a)
            sizes.add(env.encode().size)
    assert len(sizes) == 1


def test_expert_actions_replay_to_the_same_state_hash_and_save_load_agree():
    env = DungeonEnv()
    env.reset(7)
    actions = []
    for _ in range(80):
        a = env.expert_action()
        actions.append(a)
        env.step(a)
        if env.done:
            break
    h = env.state_hash()
    twin = DungeonEnv()
    assert twin.replay(actions, seed=7) == h
    again = pickle.loads(env.save())
    assert again.state_hash() == h


def test_random_policy_rarely_solves_but_never_breaks_an_invariant():
    rng = np.random.RandomState(0)
    solved = 0
    for seed in range(5):
        env = DungeonEnv()
        env.reset(seed)
        for _ in range(300):
            legal = env.legal_actions()
            env.step(int(rng.choice(legal)))
            assert 0 <= env.run.state["pos"][0] < 13 and 0 <= env.run.state["pos"][1] < 33
            if env.done:
                break
        solved += env.reason == "solved"
    assert solved <= 1


def test_recovery_after_a_world_change_the_inventory_item_is_lost():
    """The sigil is dropped halfway: the expert re-plans from the new state and the dependency room reports unsolvable only if it has not been answered yet."""
    env = DungeonEnv()
    env.reset(4)
    for _ in range(25):
        env.step(env.expert_action())
    solved_rooms = list(env.run.view()["solved"])
    env.inv.clear()  # the world took the item away
    env._plan = []
    r = None
    for _ in range(300):
        a = env.expert_action()
        if a is None:
            r = "stuck"
            break
        env.step(a)
        if env.done:
            r = "solved"
            break
    assert r in ("stuck", "solved")
    if r == "stuck":
        assert not all(env.run.view()["solved"])

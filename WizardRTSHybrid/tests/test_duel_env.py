"""Duel environments: canonical-rules parity, no leakage, invariants, adversarial and rule-based opponents, replay and save/load."""
import random

import numpy as np
import pytest

from sim.dmb.adventure.mastermind import MastermindDuel
from wizard_rts.envs.duel_env import MastermindEnv, WardDuelEnv
from wizard_rts.mastermind_solvers import ConsistentSolver, MinimaxSolver


def play(env, solver, seed):
    env.reset(seed)
    hist = []
    while not env.done:
        g = solver.next_guess(hist)
        _o, _r, _t, _tr, info = env.step(g)
        last = env.history[-1]
        hist.append((g, last["exact"], last["colour_only"]))
    return env.reason, len(env.history)


def test_canonical_configuration_reproduces_the_games_own_duel_exactly():
    for seed in range(40):
        env = MastermindEnv()
        env.reset(seed)
        duel: dict = {}
        MastermindDuel.attach(duel, rng=random.Random(seed))  # the game's own secret for the same seed
        assert duel["mastermind"]["secret"] == env.secret
        rng = random.Random(seed + 500)
        for _ in range(10):
            g = [rng.randrange(6) for _ in range(4)]
            res = MastermindDuel.submit_guess(duel, g)
            if res["status"] in ("solved", "exhausted") and env.done:
                break
            env.step(g)
            fb = res["feedback"]
            assert (env.history[-1]["exact"], env.history[-1]["colour_only"]) == (fb["exact"], fb["colour_only"])
            assert {"solved": "solved", "exhausted": "exhausted"}.get(res["status"], "") == (env.reason if env.done else "")
            if env.done:
                break


def test_observations_never_contain_the_secret():
    env = MastermindEnv()
    env.reset(3)
    secret = list(env.secret)
    env.step([0, 1, 2, 3])
    blob = str(env.observe()) + str(env.encode())
    assert str(secret) not in str(env.observe()) and "secret" not in blob
    obs = env.observe()
    assert set(obs) == {"slots", "colours", "max_casts", "casts_used", "history"}


def test_illegal_actions_are_rejected_and_do_not_consume_a_cast():
    env = MastermindEnv()
    env.reset(1)
    for bad in ([0, 1, 2], [0, 1, 2, 9], [0, 1, 2, 3, 4], "abcd"):
        _o, r, _t, _tr, info = env.step(bad)
        assert info["illegal"] is True and r < 0
    assert env.history == [] and not env.done


def test_bounded_episode_terminates_with_a_reason_and_rejects_further_steps():
    env = MastermindEnv(max_casts=3)
    env.reset(5)
    reasons = set()
    for _ in range(5):
        _o, _r, term, _tr, info = env.step([5, 5, 5, 5])
        reasons.add(info["reason"])
    assert env.done and env.reason in ("solved", "exhausted") and len(env.history) <= 3
    assert env.step([0, 0, 0, 0])[4]["reason"] == "already_done"


@pytest.mark.parametrize("slots,colours,casts", [(4, 6, 10), (3, 5, 8), (5, 6, 12), (4, 8, 12)])
def test_exact_solver_wins_on_every_configuration_and_invariants_hold(slots, colours, casts):
    env = MastermindEnv(slots, colours, casts)
    wins = 0
    for seed in range(12):
        reason, n = play(env, ConsistentSolver(slots, colours), seed)
        assert env.check_invariants() == []
        wins += reason == "solved"
    assert wins >= 11  # an exact deduction solver essentially always breaks the code within the limit


def test_adversarial_opponent_is_consistent_hardest_and_still_beatable():
    env = MastermindEnv(opponent="adversarial", max_casts=10)
    rand_counts, adv_counts = [], []
    for seed in range(6):
        r, n = play(env, MinimaxSolver(), seed)
        assert env.check_invariants() == []  # every answer is consistent with some secret: no impossible state
        adv_counts.append(n)
        assert r == "solved"
    renv = MastermindEnv(opponent="random")
    for seed in range(6):
        play(renv, MinimaxSolver(), seed)
        rand_counts.append(len(renv.history))
    assert np.mean(adv_counts) >= np.mean(rand_counts)  # the adaptive opponent costs the solver at least as many casts


def test_rule_based_opponent_uses_patterned_codes():
    seen = set()
    env = MastermindEnv(opponent="rule_based")
    for s in range(60):
        env.reset(s)
        sec = env.secret
        assert len(sec) == 4 and all(0 <= c < 6 for c in sec)
        seen.add(("repeat" if len(set(sec)) == 1 else "pal" if sec == sec[::-1] else "run" if all((sec[i + 1] - sec[i]) % 6 == 1 for i in range(3)) else "pair"))
    assert len(seen) >= 3


def test_replay_and_save_load_reproduce_the_state_hash():
    env = MastermindEnv()
    env.reset(9)
    actions = [[0, 0, 1, 1], [2, 2, 3, 3], [4, 5, 0, 1]]
    for a in actions:
        env.step(a)
    h = env.state_hash()
    blob = env.save()
    again = MastermindEnv.load(blob)
    assert again.state_hash() == h
    twin = MastermindEnv()
    assert twin.replay(actions, seed=9) == h


def test_ward_duel_env_hides_the_enemy_ward_and_uses_the_ported_rules():
    env = WardDuelEnv()
    env.reset(4)
    assert str(env.duel.enemy_ward) not in str(env.observe())
    o, r, term, tr, info = env.step([0, 1, 3, 4])
    assert "fracture" in info and r == -0.01
    assert env.step([0, 0, 0, 2])[4]["illegal"] is True
    n = 0
    while not env.done and n < 12:
        env.step([0, 1, 3, 4])
        n += 1
    assert env.done and env.reason == "finished"

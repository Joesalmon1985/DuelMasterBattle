"""T4.1: the fitness tiers of design 8.2, table-driven."""
import itertools

import pytest

from neuro.fitness import FitnessConfig, advantage, seat_fitness

CFG = FitnessConfig()


def f(end="horizon", t=240.0, vp=0, state="active", at=None, others=(0, 0, 0, 0, 0)):
    return seat_fitness(CFG, end, t, vp, state, at, list(others))


@pytest.mark.parametrize("case,expected", [
    (dict(vp=10, others=(10, 10, 10, 10, 10)), (1000 + 100 + 0, "S")),
    (dict(vp=14, others=(10, 10, 12, 8, 6)), (1000 + 140 + 3 * (14 - 10), "S")),  # median of others is 10
    (dict(vp=0, others=(10, 10, 12, 8, 6)), (1000 + 0 + 3 * (0 - 10), "S")),
    (dict(vp=7, others=()), (1000 + 70 + 3 * 7, "S")),
    (dict(state="collapsed", at=60.0, vp=2), (100 + 400 * 60 / 240 + 20, "E")),
    (dict(state="collapsed", at=None, t=120.0, vp=0), (100 + 400 * 120 / 240, "E")),
    (dict(end="collective_loss", t=120.0, vp=40), (-1000 + 500 * 120 / 240, "C")),  # VP is ignored in tier C
    (dict(end="collective_loss", t=120.0, vp=0, state="collapsed", at=30.0), (-1000 + 500 * 120 / 240, "C")),
    (dict(end="collective_loss", t=1.0), (-1000 + 500 * 1 / 240, "C")),
])
def test_the_tiers_follow_the_design_formulas(case, expected):
    got = f(**case)
    assert got[1] == expected[1] and got[0] == pytest.approx(expected[0])


def test_every_survivor_beats_every_eliminated_seat_beats_every_collective_loss():
    survivors = [f(vp=v, others=o)[0] for v in (0, 5, 30) for o in ((0,) * 5, (10,) * 5, (25, 25, 25, 25, 25))]
    eliminated = [f(state="collapsed", at=t, vp=v)[0] for t in (0.0, 120.0, 239.0) for v in (0, 10, 25)]
    losses = [f(end="collective_loss", t=t, vp=v)[0] for t in (1.0, 120.0, 240.0) for v in (0, 40)]
    assert min(survivors) > max(eliminated) > min(eliminated) > max(losses)


def test_a_later_loss_is_better_and_a_later_elimination_is_better():
    assert f(end="collective_loss", t=200.0)[0] > f(end="collective_loss", t=100.0)[0] > f(end="collective_loss", t=10.0)[0]
    assert f(state="collapsed", at=200.0)[0] > f(state="collapsed", at=100.0)[0]
    assert f(state="collapsed", at=100.0, vp=5)[0] > f(state="collapsed", at=100.0, vp=0)[0]


def test_vp_never_matters_in_the_loss_tier_and_the_horizon_caps_the_time_term():
    assert f(end="collective_loss", t=90.0, vp=0)[0] == f(end="collective_loss", t=90.0, vp=99)[0]
    assert f(end="collective_loss", t=500.0)[0] == f(end="collective_loss", t=240.0)[0] == pytest.approx(-500.0)
    assert f(state="collapsed", at=900.0)[0] == f(state="collapsed", at=240.0)[0]


def test_completing_the_cycle_counts_as_survival_at_the_horizon_and_other_early_ends_score_the_survivors():
    assert f(end="horizon")[1] == "S" and f(end="last_standing", t=100.0)[1] == "S" and f(end="agent_collapsed", t=100.0)[1] == "S"
    short = FitnessConfig(horizon_min=60.0)
    assert seat_fitness(short, "collective_loss", 30.0, 3, "active", None, [1, 2])[0] == pytest.approx(-1000 + 500 * 0.5)  # the horizon is the game length


def test_advantage_is_the_difference_and_ties_give_zero():
    assert advantage(1100.0, 1000.0) == 100.0 and advantage(900.0, 1000.0) == -100.0 and advantage(1000.0, 1000.0) == 0.0
    a = f(vp=10, others=(10,) * 5)[0]
    assert advantage(a, a) == 0.0


def test_the_median_is_of_the_other_root_factions_not_the_mean():
    assert f(vp=10, others=(0, 0, 0, 100, 100))[0] == pytest.approx(1000 + 100 + 3 * (10 - 0))

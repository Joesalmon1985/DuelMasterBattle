"""T4.4: the catastrophe curriculum configuration (decision N10)."""
import numpy as np
import pytest

from neuro.curriculum import Curriculum
from neuro.episode import EpisodeConfig, run_episode
from neuro.random_controller import RandomController
from wizard_rts import freeze


def test_one_level_every_draw_is_c0_scale_one():
    c = Curriculum()
    rng = np.random.default_rng(0)
    assert {c.draw(rng) for _ in range(200)} == {"C0"} and c.scale_of("C0") == 1.0 and c.earlier() == []


def test_unknown_level_and_invalid_ladders_are_rejected():
    c = Curriculum()
    with pytest.raises(ValueError):
        c.scale_of("C9")
    for bad in ({"levels": {"C0": 0.9}}, {"levels": {"C0": 1.0, "C1": 1.0}}, {"levels": {"C0": 1.0, "C1": 0.5, "C2": 0.7}}, {"levels": {"C0": 1.0, "C1": 0.0}},
                {"levels": {"C0": 1.0, "C1": 1.5}}, {"levels": {"C0": 1.0}, "current": "C3"}, {"levels": {}}, {"levels": {"C0": 1.0}, "retention_fraction": 2.0}):
        with pytest.raises(ValueError):
            Curriculum.from_json(bad)


def test_two_levels_retention_draws_are_deterministic_and_about_the_retention_fraction():
    c = Curriculum(levels={"C0": 1.0, "C1": 0.5}, current="C1")
    a = [c.draw(np.random.default_rng(5)) for _ in range(3)]
    assert len(set(a)) == 1
    rng = np.random.default_rng(1)
    draws = [c.draw(rng) for _ in range(2000)]
    assert 0.20 < draws.count("C0") / 2000 < 0.30 and set(draws) == {"C0", "C1"}
    rng = np.random.default_rng(1)
    assert draws == [c.draw(rng) for _ in range(2000)]
    assert c.earlier() == ["C0"] and Curriculum.from_json(c.to_json()).to_json() == c.to_json()


def test_the_level_and_scale_appear_in_the_result_and_applying_a_level_leaves_the_roster_alone():
    before = (freeze.roster_hash(), freeze.check())
    c = Curriculum(levels={"C0": 1.0, "C1": 0.5}, current="C1")
    cfg = EpisodeConfig(seed=3, game_minutes=2, map_size="small", agent_seats=("Red",), catastrophe_level="C1", outbreak_interval_scale=c.scale_of("C1"))
    res = run_episode(cfg, {"Red": RandomController("Red", cfg, seed=1)})
    assert res.catastrophe_level == "C1" and res.outbreak_interval_scale == 0.5
    assert (freeze.roster_hash(), freeze.check()) == before

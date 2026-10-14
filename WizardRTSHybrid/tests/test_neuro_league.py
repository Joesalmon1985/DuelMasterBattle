"""T4.3: opponent mixer, champion archive, behaviour grid, promotion rule."""
import numpy as np

from neuro import league as L


def games(advs, cand_lost=0, champ_lost=0):
    out = []
    for i, a in enumerate(advs):
        out.append({"adv": a, "cand_lost": i < cand_lost, "champ_lost": i < champ_lost})
    return out


def test_a_candidate_better_in_training_but_without_a_held_out_record_is_not_promoted():
    # training looked good (not an input here); on held-out games the candidate loses on average
    r = L.promotion_decision(games([-30, 10, -50, -20, -10, 5, -40, -15, 0, -25, -35, -5]))
    assert r["decided"] and not r["promote"] and r["n"] == 12
    # noisy positive mean whose lower bound is not above zero is not enough either
    r = L.promotion_decision(games([200, -150, 180, -170, 160, -140, 150, -120, 140, -100, 130, -90]))
    assert r["decided"] and not r["promote"] and r["lower"] < 0 < r["mean_advantage"]


def test_a_clear_winner_is_promoted_early_and_a_clear_loser_is_rejected_early():
    r = L.promotion_decision(games([100, 120, 90, 110, 130, 95]))
    assert r["decided"] and r["promote"] and r["n"] == 6 and "early" in r["reason"]
    r = L.promotion_decision(games([-100, -120, -90, -110, -130, -95]))
    assert r["decided"] and not r["promote"] and "early" in r["reason"]
    r = L.promotion_decision(games([100, 120, 90]))
    assert not r["decided"] and not r["promote"]  # fewer than 6 games: nothing is decided
    r = L.promotion_decision(games([100, -80, 90, -60, 120, -40]))
    assert not r["decided"]  # six games, not decisive: play on


def test_a_higher_collective_loss_rate_blocks_promotion():
    r = L.promotion_decision(games([100] * 12, cand_lost=3, champ_lost=0))
    assert r["decided"] and not r["promote"] and "loss" in r["reason"]
    assert L.promotion_decision(games([100] * 12, cand_lost=1, champ_lost=2))["promote"]


def test_a_candidate_better_now_but_significantly_worse_at_an_earlier_level_is_not_promoted():
    now = games([100, 120, 90, 110, 130, 95, 105, 115, 100, 90, 110, 120])
    assert L.promotion_decision(now, retention={"C0": games([20, -10, 15, 5, -5, 10, 0, 5, -10, 15, 10, 0])})["promote"]  # within tolerance
    r = L.promotion_decision(now, retention={"C0": games([-200, -180, -220, -190, -210, -170, -200, -230, -190, -180, -200, -210])})
    assert r["decided"] and not r["promote"] and "forgetting" in r["reason"] and r["retention"]["C0"]["ok"] is False


def test_the_archive_never_shrinks_and_keeps_every_champion(tmp_path):
    arch = L.ChampionArchive(tmp_path / "champions")
    assert arch.current() is None and len(arch) == 0
    g = [np.full(5, i, dtype=np.float32) for i in range(3)]
    ids = [arch.add(g[i], {"catastrophe_level": "C0" if i < 2 else "C1"}, {"adv": i}) for i in range(3)]
    assert ids == ["c0001", "c0002", "c0003"] and arch.current() == "c0003" and len(arch) == 3
    assert np.array_equal(arch.genome("c0002"), g[1]) and arch.record("c0003")["evaluation"] == {"adv": 2}
    assert arch.champion_of_level("C0") == "c0002" and arch.champion_of_level("C1") == "c0003" and arch.champion_of_level("C9") is None
    again = L.ChampionArchive(tmp_path / "champions")  # reopening keeps everything
    assert again.ids() == ids and again.current() == "c0003"
    arch.add(g[0], {}, {})
    assert len(arch) == 4


def test_the_mixer_is_deterministic_mirrored_and_falls_back_to_heuristics(tmp_path):
    m = L.OpponentMixer(base_seed=3)
    assert m.draw(5, "A") == m.draw(5, "A") and set(m.draw(5, "A")) == set(L.LEG_B) and set(m.draw(5, "B")) == set(L.LEG_A)
    assert set(m.draw(5, "A").values()) <= {"plus", "baseline"}  # no champion or archive yet
    arch = L.ChampionArchive(tmp_path)
    arch.add(np.zeros(3, np.float32), {}, {})
    m = L.OpponentMixer(base_seed=3, archive=arch)
    seen = [v for s in range(300) for v in m.draw(s, "A").values()]
    share = lambda k: sum(1 for v in seen if v == k or v.startswith(k)) / len(seen)  # noqa: E731
    assert 0.33 < share("plus") < 0.47 and 0.05 < share("baseline") < 0.15 and 0.19 < share("champion") < 0.31 and 0.19 < share("archive") < 0.31
    assert L.seats_for("A") == (L.LEG_A, L.LEG_B) and L.seats_for("B") == (L.LEG_B, L.LEG_A)


def test_the_behaviour_grid_keeps_the_best_per_cell_and_round_trips():
    g = L.BehaviourGrid()
    cell = L.descriptor(conquest_vp=0, total_vp=10, founded=0, cured_and_aid=0)
    assert cell == (0, 0, 0) and L.descriptor(8, 10, 5, 3) == (2, 2, 1) and L.descriptor(2, 10, 2, 0) == (1, 1, 0) and L.descriptor(0, 0, 0, 0) == (0, 0, 0)
    assert g.offer(cell, 100.0, "a") and not g.offer(cell, 90.0, "b") and g.offer(cell, 110.0, "c")
    assert g.offer((2, 2, 1), 5.0, "d") and g.filled() == 2 and g.total() == 18
    back = L.BehaviourGrid.from_json(g.to_json())
    assert back.cells == g.cells

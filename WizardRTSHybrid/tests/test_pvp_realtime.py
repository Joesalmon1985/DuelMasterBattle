"""Real-time, independent Ward casting for human-versus-human duels (`wizard_rts/net/pvp.py`).

Both players guess at once, each with their own history, counter and allowance. The first legal breaking cast ends the duel on
the host; nothing a client sends can win it, gain an extra guess or reorder the casts."""

from __future__ import annotations

import pytest

from wizard_rts.duel.ward import score_attack
from wizard_rts.net import pvp

FMT = pvp.make_format({"slots": 3, "colours": 3, "max_casts": 5})
WARD_A = [0, 1, 6]  # A's hidden ward (B is attacking it)
WARD_B = [6, 6, 0]


def make(max_casts: int = 5, now: float = 0.0) -> pvp.PvpDuel:
    fmt = pvp.make_format({"slots": 3, "colours": 3, "max_casts": max_casts})
    d = pvp.PvpDuel("d1", "A", "B", {"A": "Ann", "B": "Bob"}, fmt, 7, now)
    assert d.submit_ward("A", WARD_A, now)["state"] == "setup"
    assert d.submit_ward("B", WARD_B, now)["state"] == "active"
    return d


def seq(d: pvp.PvpDuel, pid: str) -> int:
    return d.cast_seq[pid] + 1


def test_player_a_makes_three_successive_guesses_while_b_makes_none() -> None:
    d = make()
    for attack in ([0, 0, 0], [1, 1, 1], [6, 0, 0]):
        r = d.cast("A", attack, seq(d, "A"), 1.0)
        assert r["status"] == "ok" and r["done"] is False
    va, vb = d.view("A", 2.0), d.view("B", 2.0)
    assert (va["your_casts"], va["rival_casts"]) == (3, 0)
    assert (vb["your_casts"], vb["rival_casts"]) == (0, 3)
    assert [h["n"] for h in va["your_history"]] == [1, 2, 3] and va["rival_history"] == []
    assert len(vb["rival_history"]) == 3 and vb["your_history"] == []
    # nobody is told to wait for anybody
    assert va["your_cast_pending"] and vb["your_cast_pending"] and va["state"] == "active"
    # B may now start at any time, from the beginning of their own count
    assert d.cast("B", [0, 0, 0], 1, 3.0)["status"] == "ok"
    assert d.view("A", 3.0)["rival_casts"] == 1


def test_feedback_is_the_existing_ward_scoring() -> None:
    d = make()
    for attack in ([6, 0, 0], [0, 1, 1], [1, 6, 6], [0, 0, 0]):
        r = d.cast("A", attack, seq(d, "A"), 1.0)
        want = score_attack(WARD_B, attack)
        assert (r["fracture"], r["echo"], r["fade"], r["broken"]) == (want["fracture"], want["echo"], want["fade"], bool(want["broken"]))
    assert d.state == "active"


@pytest.mark.parametrize("winner,other_casts", [("A", 0), ("A", 3), ("B", 0), ("B", 4)])
def test_either_player_wins_independently_of_the_others_cast_count(winner: str, other_casts: int) -> None:
    d = make(max_casts=6)
    loser = "B" if winner == "A" else "A"
    for i in range(other_casts):
        assert d.cast(loser, [1, 1, 1] if i % 2 else [0, 0, 0], seq(d, loser), 1.0)["done"] is False
    solution = WARD_B if winner == "A" else WARD_A
    r = d.cast(winner, solution, seq(d, winner), 2.0)
    assert r["broken"] is True and r["done"] is True
    assert d.state == "finished" and d.result["winner"] == winner and d.result["reason"] == "solved"
    assert d.outcome_for(winner) == "victory" and d.outcome_for(loser) == "defeat"
    assert len(d.history[loser]) == other_casts  # the loser's count is whatever it was


def test_first_winning_cast_ends_the_duel_and_later_casts_are_rejected() -> None:
    d = make()
    assert d.cast("A", WARD_B, 1, 1.0)["done"] is True
    late = d.cast("B", WARD_A, 1, 1.0)  # even a winning guess arriving second is too late
    assert late["status"] == "rejected" and late["reason"] == "finished"
    assert d.history["B"] == [] and d.result["winner"] == "A"
    # the winner re-sending the winning cast gets the same answer, not a second cast and not a changed result
    again = d.cast("A", WARD_B, 1, 2.0)
    assert again["status"] == "ok" and again["idempotent"] is True and again["broken"] is True
    assert len(d.history["A"]) == 1 and d.result["winner"] == "A"
    assert d.cast("A", [0, 0, 0], 2, 2.0)["reason"] == "finished"


def test_max_casts_apply_to_each_player_separately() -> None:
    d = make(max_casts=3)
    for i in range(3):
        assert d.cast("A", [0, 0, 0], seq(d, "A"), 1.0)["status"] == "ok"
    over = d.cast("A", [0, 0, 0], seq(d, "A"), 1.0)
    assert over["status"] == "rejected" and over["reason"] == "no_casts_left"
    assert len(d.history["A"]) == 3 and d.state == "active"  # B still has a full allowance
    view = d.view("A", 2.0)
    assert view["your_cast_pending"] is False and view["rival_cast_pending"] is True and view["your_casts_left"] == 0
    for i in range(3):
        assert d.state == "active"
        assert d.cast("B", [1, 1, 1], seq(d, "B"), 2.0)["status"] == "ok"
    assert d.state == "finished" and d.reason == "both_exhausted" and d.result["winner"] in ("", "A", "B")
    assert d.cast("B", [1, 1, 1], 4, 3.0)["reason"] == "finished"


def test_the_exhausted_player_cannot_stop_the_other_from_winning() -> None:
    d = make(max_casts=2)
    d.cast("A", [0, 0, 0], 1, 1.0)
    d.cast("A", [0, 0, 0], 2, 1.0)
    assert d.state == "active"
    r = d.cast("B", WARD_A, 1, 2.0)
    assert r["done"] is True and d.result["winner"] == "B"


def test_duplicates_and_bad_sequence_numbers_never_buy_a_guess() -> None:
    d = make()
    first = d.cast("A", [0, 0, 0], 1, 1.0)
    for _ in range(5):
        dup = d.cast("A", [6, 6, 0], 1, 1.0)  # the replay carries a different pattern: it is ignored, the original answer returns
        assert dup["status"] == "ok" and dup["idempotent"] is True and dup["fracture"] == first["fracture"]
    assert len(d.history["A"]) == 1
    assert d.cast("A", [0, 0, 0], 3, 1.0)["reason"] == "bad_cast_seq"   # skipping ahead
    assert d.cast("A", [0, 0, 0], 0, 1.0)["reason"] == "bad_cast_seq"   # going back before the first
    assert d.cast("A", [0, 0, 0], "x", 1.0)["reason"] == "bad_cast_seq"  # nonsense
    assert d.cast("A", [9, 9, 9], 2, 1.0)["reason"] == "illegal_attack"
    assert len(d.history["A"]) == 1
    assert d.cast("A", [0, 0, 0], 2, 1.0)["status"] == "ok" and len(d.history["A"]) == 2


def test_no_casts_before_both_wards_are_locked() -> None:
    d = pvp.PvpDuel("d2", "A", "B", {}, FMT, 1, 0.0)
    assert d.submit_ward("A", WARD_A, 0.0)["state"] == "setup"
    assert d.cast("A", [0, 0, 0], 1, 0.0)["reason"] == "not_active"
    assert d.cast("B", [0, 0, 0], 1, 0.0)["reason"] == "not_active"


def test_the_rival_ward_stays_hidden_until_the_end() -> None:
    d = make()
    d.cast("A", [0, 0, 0], 1, 1.0)
    for pid in ("A", "B"):
        v = d.view(pid, 1.0)
        assert "rival_ward" not in v and "result" not in v
    d.cast("B", WARD_A, 1, 1.0)
    v = d.view("A", 1.0)
    assert v["rival_ward"] == WARD_B and v["result"]["outcome"] == "defeat" and v["result"]["rival_casts"] == 1


def test_per_player_cast_timeout_casts_for_the_idle_player_only() -> None:
    d = make(now=0.0)
    d.cast("A", [0, 0, 0], 1, 50.0)  # A is active at t=50, B has been idle since the start
    overdue = d.auto_cast_overdue(61.0, 60.0)
    assert overdue == ["B"]
    r = d.auto_cast("B", 61.0)
    assert r["status"] == "ok" and d.history["B"][0]["auto"] is True and len(d.history["B"]) == 1
    assert d.auto_cast_overdue(61.0, 60.0) == []  # B's clock restarted
    assert d.view("A", 61.0)["cast_deadline_s"] == pytest.approx(49.0)
    # an exhausted player has no clock
    d2 = make(max_casts=1)
    d2.cast("A", [0, 0, 0], 1, 1.0)
    assert d2.auto_cast_overdue(500.0, 60.0) == ["B"]


def test_forfeit_still_wins_for_the_rival() -> None:
    d = make()
    d.cast("A", [0, 0, 0], 1, 1.0)
    d.forfeit("B", "forfeit", 2.0)
    assert d.state == "finished" and d.result["winner"] == "A" and d.reason == "forfeit"
    assert d.cast("A", [1, 1, 1], 2, 3.0)["reason"] == "finished"

"""T013 turn seats, interrupts and drafts."""

from __future__ import annotations

from sim.dmb.core.world import bootstrap_world
from sim.dmb.time.runner import TurnRunner
from sim.dmb.time.turns import TurnScheduler


def test_ab_get_one_seat_each() -> None:
    clock = {
        "turn": 0,
        "round": 0,
        "scheduled_faction_ids": ["faction:A", "faction:B"],
        "completed_seats": [],
        "removed_faction_ids": [],
    }
    sched = TurnScheduler(clock)
    sched.begin_turn("Wait")
    first = sched.finish_seat()
    second = sched.finish_seat()
    assert first["active_faction_id"] == "faction:B"
    assert second["round_complete"] is True
    assert clock["completed_seats"] == ["faction:A", "faction:B"]
    assert clock["draft"] is not None


def test_removed_b_is_skipped() -> None:
    clock = {
        "turn": 0,
        "round": 0,
        "scheduled_faction_ids": ["faction:A", "faction:B"],
        "completed_seats": [],
        "removed_faction_ids": [],
    }
    sched = TurnScheduler(clock)
    sched.begin_turn("Wait")
    sched.remove_faction("faction:B")
    result = sched.finish_seat()
    assert result["round_complete"] is True
    assert clock["completed_seats"] == ["faction:A"]


def test_interrupt_after_score_skips_follow_on() -> None:
    sim = bootstrap_world()
    sim.state.clock["interrupt_after_score"] = True
    runner = TurnRunner(sim.state, TurnScheduler(sim.state.clock))
    result = runner.execute_travel("node:1", "node:2")
    assert result["interrupted"] is True
    assert "2_score" in result["stages"]
    assert "3_follow_on" not in result["stages"]
    assert "9_seat_end" not in result["stages"]


def test_unfinished_round_produces_no_draft() -> None:
    clock = {
        "turn": 0,
        "round": 0,
        "scheduled_faction_ids": ["faction:A", "faction:B"],
        "completed_seats": [],
        "removed_faction_ids": [],
        "draft": None,
    }
    sched = TurnScheduler(clock)
    sched.begin_turn("Wait")
    partial = sched.finish_seat()
    assert partial["round_complete"] is False
    assert clock["draft"] is None


def test_begin_turn_preserves_mid_round_seats() -> None:
    clock = {
        "turn": 0,
        "round": 0,
        "scheduled_faction_ids": ["faction:A", "faction:B"],
        "completed_seats": [],
        "removed_faction_ids": [],
        "round_complete": False,
    }
    sched = TurnScheduler(clock)
    sched.begin_turn("Wait")
    assert clock["active_faction_id"] == "faction:A"
    first = sched.finish_seat()
    assert first["round_complete"] is False
    # Second World Turn must continue with B, not reset to A.
    sched.begin_turn("Wait")
    assert clock["active_faction_id"] == "faction:B"
    assert clock["completed_seats"] == ["faction:A"]
    second = sched.finish_seat()
    assert second["round_complete"] is True
    sched.begin_turn("Wait")
    assert clock["completed_seats"] == []
    assert clock["active_faction_id"] == "faction:A"

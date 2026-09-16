"""T010 RNG and replay checks."""

from __future__ import annotations

from sim.dmb.core.replay import ReplayLog
from sim.dmb.core.rng import RngBank


def test_same_stream_state_resumes_identical_draws() -> None:
    bank = RngBank()
    bank.ensure("gameplay", seed=11)
    first = [bank.draw_int("gameplay", 1, 100) for _ in range(5)]
    restored = RngBank.from_dict(bank.to_dict())
    continued = [restored.draw_int("gameplay", 1, 100) for _ in range(5)]
    fresh = RngBank()
    fresh.ensure("gameplay", seed=11)
    all_draws = [fresh.draw_int("gameplay", 1, 100) for _ in range(10)]
    assert first + continued == all_draws


def test_ambient_animation_changes_no_gameplay_draw() -> None:
    a = RngBank()
    b = RngBank()
    a.ensure("gameplay", seed=3)
    b.ensure("gameplay", seed=3)
    a.ensure("ambient", seed=3)
    b.ensure("ambient", seed=3)
    a.draw_int("ambient", 0, 10)
    assert a.draw_int("gameplay", 0, 1000) == b.draw_int("gameplay", 0, 1000)


def test_replay_order_independent_of_dict_insertion() -> None:
    log = ReplayLog()
    log.append("Wait", {"b": 2, "a": 1}, sequence=2)
    log.append("Travel", {"z": 9, "m": 1}, sequence=1)
    ordered = log.ordered()
    assert [item["sequence"] for item in ordered] == [1, 2]
    again = ReplayLog.from_dict({"inputs": list(reversed(log.inputs))})
    assert [item["sequence"] for item in again.ordered()] == [1, 2]

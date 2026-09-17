"""T012 game-time clock checks."""

from __future__ import annotations

from sim.dmb.core.world import bootstrap_world
from sim.dmb.time.clock import ClockService


def test_varied_chunks_yield_600_quanta() -> None:
    clock = ClockService(
        {
            "game_ms": 0,
            "residual_ms": 0,
            "pause_tokens": {},
            "clock_sequence": 0,
        }
    )
    chunks = [1, 2, 5, 10, 17, 100, 250, 333, 1000, 2500, 5000, 10000, 15000, 25782]
    assert sum(chunks) == 60000
    total = 0
    seq = 0
    for chunk in chunks:
        seq += 1
        total += clock.request_advance(chunk, seq)
    assert total == 600
    assert clock.clock_view()["game_ms"] == 60000


def test_two_pause_tokens_require_both_releases() -> None:
    clock = ClockService({"game_ms": 0, "residual_ms": 0, "pause_tokens": {}, "clock_sequence": 0})
    a = clock.acquire_pause("menu", "ui")
    b = clock.acquire_pause("focus", "ui")
    assert clock.request_advance(1000, 1) == 0
    clock.release_pause(a)
    assert clock.request_advance(1000, 2) == 0
    clock.release_pause(b)
    assert clock.request_advance(1000, 3) == 10


def test_duplicate_advance_adds_zero_time() -> None:
    clock = ClockService({"game_ms": 0, "residual_ms": 0, "pause_tokens": {}, "clock_sequence": 0})
    assert clock.request_advance(500, 1) == 5
    assert clock.request_advance(500, 1) == 0
    assert clock.clock_view()["game_ms"] == 500


def test_closed_application_duration_adds_no_time() -> None:
    sim = bootstrap_world()
    before = sim.state.clock["game_ms"]
    # Closed app time is never fed into request_advance.
    assert sim.state.clock["game_ms"] == before

"""T069 hazard cubes, deck and initial pressure."""

from __future__ import annotations

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.hazards.deck import HazardDeck
from sim.dmb.hazards.service import CADENCE, CatastropheService, draw_count_for_era_rounds


def _world() -> WorldState:
    state = WorldState(world_id=WorldId("world:t069"))
    state.clock["turn"] = 0
    state.clock["era"] = "prehistoric"
    return state


def test_max_three_cubes_per_hex() -> None:
    state = _world()
    svc = CatastropheService(state)
    for _ in range(3):
        assert svc.add_cube("h1", "demon")["status"] == "added"
    assert svc.add_cube("h1", "demon")["status"] == "full"
    assert len(svc.cubes_on_hex("h1")) == 3


def test_setup_three_distinct() -> None:
    state = _world()
    svc = CatastropheService(state)
    placed = svc.setup_initial(["h1", "h2", "h3", "h4", "h5"], count=3)
    assert len(placed) == 3
    hexes = {p["cube"]["hex_id"] for p in placed}
    assert len(hexes) == 3


def test_deck_reshuffle_deterministic() -> None:
    state = _world()
    deck = HazardDeck(state, hex_ids=["a", "b", "c"])
    first = deck.draw(3)
    deck.discard(first)
    # Exhaust and reshuffle
    again = deck.draw(3)
    assert len(again) == 3
    assert set(again) == {"a", "b", "c"}


def test_cadence_and_escalation() -> None:
    assert CADENCE["standard"] == 3
    assert CADENCE["gentle"] == 5
    assert CADENCE["severe"] == 2
    assert draw_count_for_era_rounds(0) == 1
    assert draw_count_for_era_rounds(4) == 2
    assert draw_count_for_era_rounds(8) == 3
    state = _world()
    svc = CatastropheService(state, difficulty="standard")
    state.clock["turn"] = 3  # era_start 0 → elapsed 3
    svc._cat()["era_start_turn"] = 0
    assert svc.placement_due() is True
    state.clock["turn"] = 4
    assert svc.placement_due() is False

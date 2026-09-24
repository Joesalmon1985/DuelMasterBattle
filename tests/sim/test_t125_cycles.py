"""T125 — full-cycle political reseeding."""

from __future__ import annotations

from sim.dmb.eras.service import EraService
from sim.dmb.military.units import MilitaryService
from sim.dmb.testing.fixtures import load_fixture


def test_reseed_increments_cycle_and_retires_army() -> None:
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    mil = MilitaryService(state)
    future_unit = mil.spawn(
        "unit.future.heavy",
        home_node_id="node:35",
        faction_id=state.board["fx_era"]["winner_faction_id"],
        era="future",
        factory_id="f:future",
    )
    people0 = set(state.people)
    state.clock["era"] = "future"
    state.clock["cycle"] = 0
    out = EraService(state).reseed_cycle(plan_id="t125", faction_count=6)
    receipt = out["receipt"]
    assert receipt["cycle"] == 1
    assert len(receipt["new_faction_ids"]) == 6
    assert set(state.people) == people0
    assert state.clock.get("era") == "prehistoric"
    assert state.units[future_unit["id"]]["alive"] is False
    assert state.units[future_unit["id"]].get("faction_id") is None
    # Idempotent
    again = EraService(state).reseed_cycle(plan_id="t125", faction_count=6)
    assert again["idempotent"] is True

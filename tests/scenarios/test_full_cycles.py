"""T130 — FX-CYCLE multi-cycle reseeds and save continuation."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from sim.dmb.eras.service import EraService
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.core.state import WorldState

ROOT = Path(__file__).resolve().parents[2]
FX = ROOT / "godot_project/content/fixtures/cycles/fx_cycle.json"


def test_three_reseeds_preserve_board_and_people() -> None:
    meta = json.loads(FX.read_text())
    assert meta["fixture_id"] == "FX-CYCLE"
    sim = load_fixture("FX-ERA", seed=int(meta["seed"]))
    state = sim.state
    people0 = set(state.people)
    hexes0 = deepcopy((state.board.get("topology") or {}).get("hexes"))
    state.clock["era"] = "future"
    state.clock["cycle"] = 0
    cycles = []
    for i in range(3):
        out = EraService(state).reseed_cycle(plan_id=f"fx-cycle-{i}", faction_count=6)
        cycles.append(out["receipt"]["cycle"])
        state.clock["era"] = "future"
    assert cycles == [1, 2, 3]
    assert set(state.people) == people0
    assert (state.board.get("topology") or {}).get("hexes") == hexes0
    # Mid-cycle save continuation
    snap = deepcopy(state.to_dict())
    reloaded = WorldState.from_dict(snap)
    assert reloaded.clock.get("cycle") == 3
    assert set(reloaded.people) == people0

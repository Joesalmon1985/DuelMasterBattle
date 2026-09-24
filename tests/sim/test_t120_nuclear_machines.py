"""T120 — nuclear and hostile-machine Future hazards."""

from __future__ import annotations

import json
from pathlib import Path

from sim.dmb.adventure.duels import HazardDuelService
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.hazards.responders import HazardResponder
from sim.dmb.hazards.service import CatastropheService, MAX_CUBES_PER_HEX
from sim.dmb.military.units import MilitaryService
from sim.dmb.player.visits import VisitService

ROOT = Path(__file__).resolve().parents[2]


def test_future_content_distinct() -> None:
    nuclear = json.loads((ROOT / "godot_project/content/source/hazards/nuclear.json").read_text())
    machine = json.loads((ROOT / "godot_project/content/source/hazards/machines.json").read_text())
    assert nuclear["hazard_type"] == "nuclear"
    assert machine["hazard_type"] == "machine"
    assert nuclear["semantic_id"] != machine["semantic_id"]
    assert nuclear["duel_allowed"] and machine["duel_allowed"]


def test_future_alternation_deterministic() -> None:
    state = WorldState(world_id=WorldId("world:t120"))
    state.clock["era"] = "future"
    cat = state.hazards.setdefault("catastrophe", {})
    svc = CatastropheService(state)
    seen = []
    for ordinal in range(4):
        cat["placement_ordinal"] = ordinal
        seen.append(svc._next_type())
    assert seen == ["nuclear", "machine", "nuclear", "machine"]


def test_mixed_hex_still_max_three() -> None:
    state = WorldState(world_id=WorldId("world:t120b"))
    state.clock["era"] = "future"
    svc = CatastropheService(state)
    assert svc.add_cube("h1", "nuclear")["status"] == "added"
    assert svc.add_cube("h1", "machine")["status"] == "added"
    assert svc.add_cube("h1", "demon")["status"] == "added"
    full = svc.add_cube("h1", "nuclear")
    assert full["status"] == "full"
    assert full["count"] == MAX_CUBES_PER_HEX


def test_each_type_has_eligible_response() -> None:
    state = WorldState(world_id=WorldId("world:t120c"))
    state.clock["era"] = "future"
    state.clock["active_faction_id"] = "faction:a"
    state.clock["turn"] = 1
    state.board["node_hexes"] = {"n1": ["h1"], "n2": ["h2"]}
    VisitService(state).arrive("n1", "travel", 1)
    mil = MilitaryService(state)
    heavy = mil.spawn(
        "unit.future.heavy",
        home_node_id="n1",
        faction_id="faction:a",
        era="future",
        factory_id="f1",
    )
    line = mil.spawn(
        "unit.future.line",
        home_node_id="n2",
        faction_id="faction:a",
        era="future",
        factory_id="f2",
    )
    svc = CatastropheService(state)
    nuclear = svc.add_cube("h1", "nuclear")["cube"]
    machine = svc.add_cube("h2", "machine")["cube"]
    responder = HazardResponder(state)
    assert responder.treat(str(heavy["formation_id"]), nuclear["id"])["status"] == "treated"
    state.clock["turn"] = 2
    assert responder.treat(str(line["formation_id"]), machine["id"])["status"] == "treated"
    n2 = svc.add_cube("h1", "nuclear")["cube"]
    m2 = svc.add_cube("h2", "machine")["cube"]
    VisitService(state).arrive("n1", "travel", 3)
    assert HazardDuelService(state).can_start(n2["id"])["ok"] is True
    VisitService(state).arrive("n2", "travel", 3)
    assert HazardDuelService(state).can_start(m2["id"])["ok"] is True

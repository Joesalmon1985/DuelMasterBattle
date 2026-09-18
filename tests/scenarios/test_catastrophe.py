"""T075 FX-HAZARD pressure, failure and terminal scenarios."""

from __future__ import annotations

import json
from pathlib import Path

from sim.dmb.adventure.duels import HazardDuelService
from sim.dmb.core.state import WorldState
from sim.dmb.core.terminal import TerminalService
from sim.dmb.core.types import WorldId
from sim.dmb.hazards.propagation import PropagationEngine
from sim.dmb.hazards.responders import HazardResponder
from sim.dmb.hazards.service import CatastropheService
from sim.dmb.military.formations import FormationDirector
from sim.dmb.military.units import MilitaryService
from sim.dmb.player.visits import VisitService

FIXTURE = Path(__file__).resolve().parents[2] / "godot_project" / "content" / "fixtures" / "hazards" / "fx_hazard_v1.json"


def _seed() -> WorldState:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    state = WorldState(world_id=WorldId("world:fx_hazard"))
    node = data["node_id"]
    state.board = {
        "nodes": {node: {"id": node, "exits": []}},
        "node_hexes": {node: list(data["adjacent_hexes"])},
        "hex_adjacency": {
            "hex:a": ["hex:b"],
            "hex:b": ["hex:a", "hex:c"],
            "hex:c": ["hex:b"],
        },
    }
    state.player["node_id"] = node
    state.clock["active_faction_id"] = "faction:a"
    state.clock["era"] = "prehistoric"
    state.clock["turn"] = 1
    svc = CatastropheService(state)
    for spec in data["cubes"]:
        svc.add_cube(spec["hex_id"], spec["type"])
    VisitService(state).arrive(node, "travel", 1)
    return state


def test_ordinary_duel_failure_nonterminal() -> None:
    state = _seed()
    cube_id = next(iter(state.hazards["catastrophe"]["cubes"]))
    duels = HazardDuelService(state)
    started = duels.begin(cube_id)
    out = duels.resolve(started["duel"]["id"], success=False)
    assert out["terminal"] is False
    assert state.clock.get("terminal") in {None, False}


def test_treatment_and_saved_ledger() -> None:
    state = _seed()
    mil = MilitaryService(state)
    director = FormationDirector(state)
    u = mil.spawn(
        "unit.ancient.line",
        home_node_id=state.player["node_id"],
        faction_id="faction:a",
        era="prehistoric",
        factory_id="f",
    )
    form = director.group([u["id"]], faction_id="faction:a", node_id=state.player["node_id"])
    cube = next(c for c in state.hazards["catastrophe"]["cubes"].values() if c["active"])
    out = HazardResponder(state).treat(form["id"], cube["id"])
    assert out["status"] == "treated"
    blob = state.to_dict()
    restored = WorldState.from_dict(blob)
    assert restored.player["visits"]["current"]["success_count"] >= 0


def test_terminal_once_and_pollution_no_duel() -> None:
    state = _seed()
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    pol = CatastropheService(state).add_cube(
        data["pollution_placeholder"]["hex_id"], "pollution"
    )["cube"]
    assert HazardDuelService(state).can_start(pol["id"])["ok"] is False
    cat = state.hazards["catastrophe"]
    cat["era_outbreaks"] = 7
    for hid in ("hex:a", "hex:b", "hex:c"):
        while len(CatastropheService(state).cubes_on_hex(hid)) < 3:
            CatastropheService(state).add_cube(hid, "demon")
    engine = PropagationEngine(state)
    engine.begin_event()
    result = engine.outbreak_from("hex:a", "demon")
    assert result["status"] == "terminal"
    second = TerminalService(state).trigger("again")
    assert second["emitted"] is False
    assert second.get("return_to_menu") is not True or len(state.hazards["terminal_events"]) == 1

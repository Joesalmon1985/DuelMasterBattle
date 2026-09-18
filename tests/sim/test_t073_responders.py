"""T073 faction treatment instead of movement."""

from __future__ import annotations

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.hazards.responders import HazardResponder
from sim.dmb.hazards.service import CatastropheService
from sim.dmb.military.formations import FormationDirector
from sim.dmb.military.units import MilitaryService


def test_responder_removes_one_moves_zero() -> None:
    state = WorldState(world_id=WorldId("world:t073"))
    state.clock["active_faction_id"] = "faction:a"
    state.clock["turn"] = 1
    state.clock["era"] = "prehistoric"
    state.board["node_hexes"] = {"n1": ["h1"]}
    mil = MilitaryService(state)
    director = FormationDirector(state)
    u = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="faction:a", era="prehistoric", factory_id="f")
    form = director.group([u["id"]], faction_id="faction:a", node_id="n1")
    svc = CatastropheService(state)
    cube = svc.add_cube("h1", "demon")["cube"]
    responder = HazardResponder(state)
    out = responder.treat(form["id"], cube["id"])
    assert out["status"] == "treated"
    assert out["edges_moved"] == 0
    assert form["movement_spent_turn"] == 1
    assert form["node_id"] == "n1"
    assert not svc.cubes_on_hex("h1")


def test_inactive_cannot_treat() -> None:
    state = WorldState(world_id=WorldId("world:t073b"))
    state.clock["active_faction_id"] = "faction:b"
    state.board["node_hexes"] = {"n1": ["h1"]}
    mil = MilitaryService(state)
    director = FormationDirector(state)
    u = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="faction:a", era="prehistoric", factory_id="f")
    form = director.group([u["id"]], faction_id="faction:a", node_id="n1")
    cube = CatastropheService(state).add_cube("h1", "demon")["cube"]
    out = HazardResponder(state).treat(form["id"], cube["id"])
    assert out["status"] == "rejected"


def test_already_removed_noop() -> None:
    state = WorldState(world_id=WorldId("world:t073c"))
    state.clock["active_faction_id"] = "faction:a"
    state.clock["turn"] = 1
    state.clock["era"] = "prehistoric"
    state.board["node_hexes"] = {"n1": ["h1"]}
    mil = MilitaryService(state)
    director = FormationDirector(state)
    u = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="faction:a", era="prehistoric", factory_id="f")
    form = director.group([u["id"]], faction_id="faction:a", node_id="n1")
    svc = CatastropheService(state)
    cube = svc.add_cube("h1", "demon")["cube"]
    svc.remove_cube(cube["id"], "other")
    out = HazardResponder(state).treat(form["id"], cube["id"])
    assert out["status"] == "noop"
    assert out["removed"] is False

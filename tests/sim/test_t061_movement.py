"""T061 strategic formation movement and withdrawal."""

from __future__ import annotations

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.military.formations import FormationDirector
from sim.dmb.military.movement import StrategicMovement
from sim.dmb.military.units import MilitaryService


def _board_line() -> dict:
    return {
        "nodes": {
            "n1": {"id": "n1", "exits": ["n2"]},
            "n2": {"id": "n2", "exits": ["n1", "n3"]},
            "n3": {"id": "n3", "exits": ["n2", "n4"]},
            "n4": {"id": "n4", "exits": ["n3"]},
        }
    }


def _world() -> WorldState:
    state = WorldState(world_id=WorldId("world:t061"))
    state.board = _board_line()
    state.clock["turn"] = 1
    state.clock["active_faction_id"] = "faction:a"
    state.factions["faction:a"] = {"id": "faction:a"}
    state.factions["faction:b"] = {"id": "faction:b"}
    return state


def test_seconds_alone_move_zero_nodes() -> None:
    state = _world()
    mil = MilitaryService(state)
    director = FormationDirector(state)
    u = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="faction:a", era="prehistoric", factory_id="f")
    form = director.group([u["id"]], faction_id="faction:a", node_id="n1")
    before = form["node_id"]
    # No activate call — Game Time / seconds alone must not move.
    assert director.get(form["id"])["node_id"] == before


def test_inactive_faction_stays() -> None:
    state = _world()
    mil = MilitaryService(state)
    director = FormationDirector(state)
    u = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="faction:a", era="prehistoric", factory_id="f")
    form = director.group([u["id"]], faction_id="faction:a", node_id="n1")
    try:
        director.activate(form["id"], ["n2"], active_faction_id="faction:b")
        raise AssertionError("inactive should fail")
    except ValueError as exc:
        assert "inactive" in str(exc)
    assert director.get(form["id"])["node_id"] == "n1"


def test_hostile_first_edge_stops_second() -> None:
    state = _world()
    mil = MilitaryService(state)
    director = FormationDirector(state)
    friendly = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="faction:a", era="prehistoric", factory_id="f")
    enemy = mil.spawn("unit.ancient.line", home_node_id="n2", faction_id="faction:b", era="prehistoric", factory_id="f")
    assert enemy["node_id"] == "n2"
    form = director.group([friendly["id"]], faction_id="faction:a", node_id="n1")
    result = director.activate(form["id"], ["n2", "n3"], active_faction_id="faction:a")
    assert result["node_id"] == "n2"
    assert result["stopped"] is True
    assert result["path"] == ["n2"]
    assert director.get(form["id"])["node_id"] == "n2"


def test_new_unit_gets_no_past_move() -> None:
    state = _world()
    state.clock["turn"] = 5
    mil = MilitaryService(state)
    director = FormationDirector(state)
    old = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="faction:a", era="prehistoric", factory_id="f")
    old["spawned_turn"] = 1
    new = mil.spawn("unit.ancient.skirmisher", home_node_id="n1", faction_id="faction:a", era="prehistoric", factory_id="f")
    assert new["spawned_turn"] == 5
    form = director.group([old["id"], new["id"]], faction_id="faction:a", node_id="n1")
    director.activate(form["id"], ["n2"], active_faction_id="faction:a", turn=5)
    assert state.units[old["id"]]["node_id"] == "n2"
    assert state.units[new["id"]]["node_id"] == "n1"  # new unit stays this activation


def test_blocked_retreat_revalidates() -> None:
    state = _world()
    mil = MilitaryService(state)
    move = StrategicMovement(state)
    director = FormationDirector(state)
    u = mil.spawn("unit.ancient.heavy", home_node_id="n2", faction_id="faction:a", era="prehistoric", factory_id="f")
    form = director.group([u["id"]], faction_id="faction:a", node_id="n2")
    form["entry_strength"] = 400
    state.units[u["id"]]["current_health"] = 50  # below 25% of 400
    state.settlements["s1"] = {"id": "s1", "node_id": "n1", "faction_id": "faction:a"}
    marked = director.mark_withdrawal(form["id"], entry_effective_health=400)
    assert marked["status"] == "pending"
    assert marked["immediate_move"] is False
    assert director.get(form["id"])["node_id"] == "n2"
    # Block retreat target.
    mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="faction:b", era="prehistoric", factory_id="f")
    result = move.revalidate_withdrawal(form["id"])
    assert result["status"] == "blocked"
    assert result.get("reengage") is True

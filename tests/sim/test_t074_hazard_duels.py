"""T074 hazard duel lease integration."""

from __future__ import annotations

from sim.dmb.adventure.duels import HazardDuelService
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.hazards.service import CatastropheService
from sim.dmb.player.visits import VisitService


def _ready() -> tuple[WorldState, str]:
    state = WorldState(world_id=WorldId("world:t074"))
    state.board["node_hexes"] = {"n1": ["h1"]}
    state.player["node_id"] = "n1"
    VisitService(state).arrive("n1", "travel", 1)
    cube = CatastropheService(state).add_cube("h1", "demon")["cube"]
    return state, cube["id"]


def test_duel_freezes_and_removes_only_cube() -> None:
    state, cube_id = _ready()
    duels = HazardDuelService(state)
    started = duels.begin(cube_id)
    assert started["status"] == "started"
    assert state.clock["pause_tokens"].get("hazard_duel") is True
    other = CatastropheService(state).add_cube("h2", "demon")["cube"]
    resolved = duels.resolve(started["duel"]["id"], success=True, command_id="cmd:1")
    assert resolved["status"] == "success"
    assert resolved["allowance_spent"] is True
    cubes = state.hazards["catastrophe"]["cubes"]
    assert cubes[cube_id]["active"] is False
    assert cubes[other["id"]]["active"] is True


def test_duplicate_stale_cannot_remove_another() -> None:
    state, cube_id = _ready()
    duels = HazardDuelService(state)
    started = duels.begin(cube_id)
    duels.resolve(started["duel"]["id"], success=True, command_id="cmd:1")
    again = duels.resolve(started["duel"]["id"], success=True, command_id="cmd:1")
    assert again["status"] == "idempotent"


def test_pollution_rejected() -> None:
    state = WorldState(world_id=WorldId("world:t074p"))
    state.board["node_hexes"] = {"n1": ["h1"]}
    VisitService(state).arrive("n1", "travel", 1)
    cube = CatastropheService(state).add_cube("h1", "pollution")["cube"]
    assert HazardDuelService(state).can_start(cube["id"])["reason"] == "pollution_no_duel"

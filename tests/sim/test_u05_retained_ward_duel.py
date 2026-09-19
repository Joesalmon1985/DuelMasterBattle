"""G04 retained ward-duel lease + observation identity."""

from __future__ import annotations

from sim.dmb.adventure.duels import HazardDuelService
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.core.world import WorldSim, bootstrap_world
from sim.dmb.hazards.service import CatastropheService
from sim.dmb.player.visits import VisitService
from sim.dmb.testing.fixtures import load_fixture


def _hazard_ready() -> tuple[WorldState, str]:
    state = WorldState(world_id=WorldId("world:u05"))
    state.board["node_hexes"] = {"n1": ["h1"]}
    state.player["node_id"] = "n1"
    VisitService(state).arrive("n1", "travel", 1)
    cube = CatastropheService(state).add_cube("h1", "demon")["cube"]
    return state, cube["id"]


def test_start_hazard_duel_uses_ward_lease_not_mastermind() -> None:
    state, cube_id = _hazard_ready()
    started = HazardDuelService(state).begin(cube_id)
    assert started["status"] == "started"
    duel = started["duel"]
    public = started["public"]
    assert duel["kind"] == "hazard_ward_duel"
    assert duel["engine"] == "DmbBattleSim"
    assert "mastermind" not in duel
    assert public["scene"].endswith("game_board.tscn")
    enc = public["encounter"]
    assert enc["slot_count"] == 4
    assert enc["max_casts"] == 10
    assert len(enc["attack_pool"]) == 6


def test_duplicate_resolve_is_idempotent_with_receipt() -> None:
    state, cube_id = _hazard_ready()
    duels = HazardDuelService(state)
    started = duels.begin(cube_id)
    first = duels.resolve(started["duel"]["id"], success=True, command_id="cmd:1")
    assert first["status"] == "success"
    again = duels.resolve(started["duel"]["id"], success=True, command_id="cmd:1")
    assert again["status"] == "idempotent"
    assert again.get("outcome") == "success"
    # Only one cube removed.
    cubes = state.hazards["catastrophe"]["cubes"]
    assert cubes[cube_id]["active"] is False


def test_observe_learns_soldier_name_once() -> None:
    sim = load_fixture("FX-BATTLE", seed=404)
    unit_id = next(iter(sim.state.units))
    before = sim.state.knowledge.get(unit_id)
    assert before is None or before.get("name") in (None, "")
    from sim.dmb.core.commands import CommandEnvelope

    env = CommandEnvelope(
        protocol_version=1,
        session_id="s",
        world_id=str(sim.state.world_id),
        command_id="obs:1",
        expected_world_version=sim.state.world_version,
        kind="Observe",
        payload={"entity_id": unit_id},
    )
    result = sim._handle_observe(env)
    assert result.status == "ACCEPTED"
    name = sim.state.knowledge[unit_id]["name"]
    assert name
    person = sim.state.units[unit_id]["person_name"]
    assert person == name
    # Second observe keeps the same name.
    env2 = CommandEnvelope(
        protocol_version=1,
        session_id="s",
        world_id=str(sim.state.world_id),
        command_id="obs:2",
        expected_world_version=sim.state.world_version,
        kind="Observe",
        payload={"entity_id": unit_id},
    )
    sim._handle_observe(env2)
    assert sim.state.units[unit_id]["person_name"] == name
    label = sim.state.board["fx_battle"]["labels"][unit_id]
    assert " — " in label and name in label

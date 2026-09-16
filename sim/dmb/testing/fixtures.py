"""Production-path fixture loader for scenario tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.core.world import WorldSim, bootstrap_world


@dataclass
class FixtureResult:
    name: str
    status: str
    details: dict[str, Any]


def load_fixture(name: str, seed: int = 7) -> WorldSim:
    if name != "FX-CLOCK":
        raise ValueError(f"unsupported fixture {name}")
    return bootstrap_world(world_id=f"world:{name.lower()}", seed=seed)


def run_fx_clock(sim: WorldSim | None = None) -> FixtureResult:
    sim = sim or load_fixture("FX-CLOCK")
    start_turn = int(sim.state.clock["turn"])
    start_node = sim.state.player["node_id"]
    travel = sim.dispatch(
        CommandEnvelope(
            protocol_version=1,
            session_id="fx",
            world_id=sim.state.world_id,
            command_id="fx-travel-1",
            expected_world_version=sim.state.world_version,
            kind="Travel",
            payload={"from_node": "node:1", "to_node": "node:2"},
        )
    )
    assert travel.status == "ACCEPTED"
    dup = sim.dispatch(
        CommandEnvelope(
            protocol_version=1,
            session_id="fx",
            world_id=sim.state.world_id,
            command_id="fx-travel-1",
            expected_world_version=start_turn,  # ignored for duplicate id path
            kind="Travel",
            payload={"from_node": "node:1", "to_node": "node:2"},
        )
    )
    assert dup.status == "DUPLICATE"
    assert int(sim.state.clock["turn"]) == start_turn + 1
    wait = sim.dispatch(
        CommandEnvelope(
            protocol_version=1,
            session_id="fx",
            world_id=sim.state.world_id,
            command_id="fx-wait-1",
            expected_world_version=sim.state.world_version,
            kind="Wait",
            payload={"current_node": "node:2", "press_id": "press-1"},
        )
    )
    assert wait.status == "ACCEPTED"
    held = sim.dispatch(
        CommandEnvelope(
            protocol_version=1,
            session_id="fx",
            world_id=sim.state.world_id,
            command_id="fx-wait-held",
            expected_world_version=sim.state.world_version,
            kind="Wait",
            payload={"current_node": "node:2", "press_id": "press-1"},
        )
    )
    assert held.status == "REJECTED"
    invalid = sim.dispatch(
        CommandEnvelope(
            protocol_version=1,
            session_id="fx",
            world_id=sim.state.world_id,
            command_id="fx-travel-bad",
            expected_world_version=sim.state.world_version,
            kind="Travel",
            payload={"from_node": "node:2", "to_node": "node:99"},
        )
    )
    assert invalid.status == "REJECTED"
    assert int(sim.state.clock["turn"]) == start_turn + 2
    assert sim.state.player["node_id"] == "node:2"
    assert sim.state.legacy_godot_world_tick_enabled is False
    assert sim.state.legacy_godot_world_save_enabled is False
    return FixtureResult(
        name="FX-CLOCK",
        status="PASS",
        details={
            "start_node": start_node,
            "end_node": sim.state.player["node_id"],
            "turns": int(sim.state.clock["turn"]),
            "duplicate_status": dup.status,
            "held_wait_status": held.status,
            "invalid_travel_status": invalid.status,
        },
    )

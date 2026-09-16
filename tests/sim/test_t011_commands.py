"""T011 command dispatch, receipts and abort semantics."""

from __future__ import annotations

from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.core.types import TypeValidationError
from sim.dmb.core.world import bootstrap_world


def _env(sim, command_id: str, kind: str, payload: dict, version: int | None = None) -> CommandEnvelope:
    return CommandEnvelope(
        protocol_version=1,
        session_id="t011",
        world_id=sim.state.world_id,
        command_id=command_id,
        expected_world_version=sim.state.world_version if version is None else version,
        kind=kind,
        payload=payload,
    )


def test_rejected_command_preserves_state_rng_next_id() -> None:
    sim = bootstrap_world()
    before = sim.state.to_dict()
    next_id = sim.state.ids.peek("person")
    result = sim.dispatch(_env(sim, "bad", "Travel", {"from_node": "node:1", "to_node": "node:99"}))
    assert result.status == "REJECTED"
    assert sim.state.to_dict()["player"] == before["player"]
    assert sim.state.to_dict()["rng"] == before["rng"]
    assert sim.state.ids.peek("person") == next_id


def test_duplicated_successful_command_returns_original_without_mutation() -> None:
    sim = bootstrap_world()
    first = sim.dispatch(_env(sim, "t1", "Travel", {"from_node": "node:1", "to_node": "node:2"}))
    version = sim.state.world_version
    turn = sim.state.clock["turn"]
    dup = sim.dispatch(_env(sim, "t1", "Travel", {"from_node": "node:1", "to_node": "node:2"}, version=0))
    assert first.status == "ACCEPTED"
    assert dup.status == "DUPLICATE"
    assert sim.state.world_version == version
    assert sim.state.clock["turn"] == turn


def test_injected_handler_error_aborts_provisional_writes() -> None:
    sim = bootstrap_world()

    def boom(_envelope):
        sim.tx.begin("boom")
        sim.state.player["node_id"] = "node:2"
        raise RuntimeError("injected")

    sim.router.register("Boom", boom)
    before = sim.state.player["node_id"]
    result = sim.dispatch(_env(sim, "x", "Boom", {}))
    assert result.status == "REJECTED"
    assert result.code == "INTERNAL"
    assert sim.state.player["node_id"] == before

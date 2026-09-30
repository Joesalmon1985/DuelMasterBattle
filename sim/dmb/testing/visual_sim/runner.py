"""Cheap simulation-mode smoke and journey helpers for Visual Sim QA."""

from __future__ import annotations

from typing import Any

from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.testing.visual_sim.authority import observe_authority


def dispatch(sim, kind: str, payload: dict[str, Any], *, cmd_id: str) -> Any:
    env = CommandEnvelope(
        1,
        "local",
        sim.state.world_id,
        cmd_id,
        sim.state.world_version,
        kind,
        payload,
    )
    result = sim.dispatch(env)
    if result.status != "ACCEPTED":
        raise RuntimeError(f"{kind} rejected: {result}")
    return result


def wait_once(sim, *, press_id: str, node: str | None = None) -> Any:
    node = node or str(sim.state.player.get("node_id") or "node:35")
    return dispatch(
        sim,
        "Wait",
        {"current_node": node, "press_id": press_id},
        cmd_id=f"cmd:{press_id}",
    )


def advance_once(sim, *, seq: int, delta_ms: int = 1000) -> Any:
    return dispatch(
        sim,
        "AdvanceGame",
        {"delta_ms": delta_ms, "clock_sequence": seq},
        cmd_id=f"cmd:adv:{seq}",
    )


def run_sim_smoke(contract: dict[str, Any]) -> dict[str, Any]:
    """ARRANGED_STATE/production setup via fixture; observe Layer1 only."""
    sim = load_fixture(str(contract["fixture"]), seed=int(contract["seed"]))
    setup = contract.get("setup") or {}
    for i in range(int(setup.get("advance_seconds", 0))):
        advance_once(sim, seq=i + 1, delta_ms=1000)
    for i in range(int(setup.get("waits", 0))):
        wait_once(sim, press_id=f"smoke-w{i}")
    authority = observe_authority(sim)
    return {"sim": sim, "authority": authority}

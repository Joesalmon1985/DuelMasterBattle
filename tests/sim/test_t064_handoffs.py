"""T064 arrival/departure/reinforcement handoffs."""

from __future__ import annotations

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.encounters.registry import EncounterRegistry
from sim.dmb.military.units import MilitaryService


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t064"))


def test_leave_after_casualties_never_restores() -> None:
    state = _world()
    mil = MilitaryService(state)
    a = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="red", era="prehistoric", factory_id="f")
    b = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="blue", era="prehistoric", factory_id="f")
    reg = EncounterRegistry()
    snap = {"units": {a["id"]: dict(a), b["id"]: dict(b)}, "node_id": "n1"}
    lease = reg.grant("battle", [a["id"], b["id"]], snap, "lease:leave")
    # Half army dies on checkpoint.
    a["current_health"] = 0
    a["alive"] = False
    mil.receive_checkpoint(
        lease.lease_id,
        {"version": 1, "units": {a["id"]: {"current_health": 0, "alive": False, "status": "dead"}}},
    )
    closed = reg.close_for_travel(
        lease.lease_id,
        world_state=state,
        acknowledged_checkpoint={
            "units": {
                a["id"]: {"current_health": 0, "alive": False, "status": "dead"},
                b["id"]: {"current_health": b["current_health"], "alive": True},
            }
        },
    )
    assert closed["result"]["reason"] == "travel"
    assert state.units[a["id"]]["alive"] is False
    assert state.units[a["id"]]["current_health"] == 0


def test_duplicate_reinforcement_adds_once() -> None:
    reg = EncounterRegistry()
    lease = reg.grant("battle", ["u1"], {"units": {"u1": {"id": "u1"}}}, "lease:r")
    unit = {"id": "u2", "faction_id": "red", "alive": True, "current_health": 10}
    first = reg.queue_reinforcement(lease.lease_id, unit)
    second = reg.queue_reinforcement(lease.lease_id, unit)
    assert first["added"] is True
    assert second["added"] is False
    assert sum(1 for u in lease.pending_reinforcements if u["id"] == "u2") == 1


def test_stale_checkpoint_cannot_overwrite_result() -> None:
    reg = EncounterRegistry()
    lease = reg.grant("battle", ["u1"], {"units": {"u1": {"id": "u1", "alive": True}}}, "lease:stale")
    base = lease.checkpoint_hash
    reg.close(lease.lease_id, {"outcome": "done"})
    try:
        reg.reject_stale_checkpoint(lease.lease_id, version=1, base_hash=base)
        raise AssertionError("expected stale reject")
    except TypeValidationError as exc:
        assert "overwrite" in str(exc) or "stale" in str(exc)


def test_wait_does_not_close_battle() -> None:
    reg = EncounterRegistry()
    lease = reg.grant("battle", ["u1"], {"units": {"u1": {"id": "u1"}}}, "lease:wait")
    retained = reg.retain_on_wait(lease.lease_id)
    assert retained.state == "ACTIVE"
    assert lease.lease_id in reg.leases
    assert retained.checkpoint.get("retained_on_wait") is True

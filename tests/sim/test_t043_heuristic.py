"""T043 deterministic heuristic leadership."""

from __future__ import annotations

from sim.dmb.ai.heuristic import HeuristicBrain
from sim.dmb.ai.legal import LegalActionGenerator
from sim.dmb.ai.observation import ObservationBuilder
from sim.dmb.ai.policy import PolicyService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.logistics.stock import StockLedger


def _state() -> WorldState:
    state = WorldState(world_id=WorldId("world:t043"), ids=IdAllocator(WorldId("world:t043")))
    state.world_version = 1
    state.factions = {
        "faction:1": {"id": "faction:1"},
        "faction:2": {"id": "faction:2"},
    }
    state.settlements["settlement:1"] = {
        "id": "settlement:1",
        "faction_id": "faction:1",
        "node_id": "node:1",
        "store_id": "store:1",
        "tier": "settlement",
        "operational": True,
    }
    state.roads["road:1"] = {"id": "road:1", "faction_id": "faction:1", "a": "node:1", "b": "node:2"}
    # Board nodes used by placement (HexBoard.radius2 uses hex ids; keep simple exits graph too).
    state.board = {
        "nodes": {
            "node:1": {"id": "node:1", "exits": ["node:2"]},
            "node:2": {"id": "node:2", "exits": ["node:1", "node:3"]},
            "node:3": {"id": "node:3", "exits": ["node:2"]},
        }
    }
    return state


def test_tie_sorted_by_action_id() -> None:
    brain = HeuristicBrain()
    obs = {"own": {"vp": 0}, "public": {}, "faction_id": "faction:1"}
    cands = [
        {"id": "construct:b", "action_kind": "construct", "params": {"action": "road"}, "benefit": {}},
        {"id": "construct:a", "action_kind": "construct", "params": {"action": "road"}, "benefit": {}},
    ]
    assert brain.choose(obs, cands) == "construct:a"


def test_no_repeated_free_action_loop() -> None:
    state = _state()
    policy = PolicyService(state)
    policy.assign_brain("faction:1")
    first = policy.activate("faction:1")
    second = policy.activate("faction:1")
    # Activations record distinct selections; noop/construct does not grant free stock.
    assert first["selected_ids"]
    assert second["selected_ids"]
    ledger = StockLedger(state)
    assert ledger.available("store:1", "timber") == 0
    # Commitments grow but do not invent resources.
    assert len(policy._policy_bucket("faction:1")["selections"]) == 2


def test_unaffordable_road_schedules_cargo() -> None:
    state = _state()
    # Ensure a road candidate exists via legal generator with empty stock.
    StockLedger(state).credit("store:1", "timber", 0)
    obs = ObservationBuilder(state).build("faction:1", "seat")
    gen = LegalActionGenerator(state)
    cands = gen.enumerate(obs, "seat")
    road = next((c for c in cands if c.get("params", {}).get("action") == "road"), None)
    assert road is not None
    policy = PolicyService(state)
    # Force apply unaffordable road.
    result = policy._apply_construct(road, road["params"])
    assert result["status"] == "cargo_scheduled"
    assert result["schedule"]["missing"]
    assert any(o.get("status") == "awaiting_cargo" for o in state.orders.values())
    schedules = policy._policy_bucket("faction:1")["cargo_schedules"]
    assert schedules and schedules[-1]["action"] == "road"


def test_replay_uses_recorded_selection() -> None:
    state = _state()
    policy = PolicyService(state)
    cands = [
        {"id": "noop:reason=wait", "action_kind": "noop", "params": {"reason": "wait"}},
        {
            "id": "construct:z",
            "action_kind": "construct",
            "params": {"action": "settlement"},
            "benefit": {"vp_gain": 1},
        },
    ]
    # Live heuristic would prefer construct over noop.
    live = HeuristicBrain().choose({"own": {"vp": 0}, "public": {}}, cands)
    assert live == "construct:z"
    # Replay forces recorded noop.
    replayed = policy.choose_recorded_or_live(
        "faction:1", cands, recorded_primary_id="noop:reason=wait"
    )
    assert replayed == "noop:reason=wait"

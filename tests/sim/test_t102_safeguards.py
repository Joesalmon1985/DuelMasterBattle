"""T102 — sole-faction and zero-faction recovery safeguards."""

from __future__ import annotations

from fractions import Fraction

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.eras.collapse import select_collapse_factions
from sim.dmb.eras.safeguards import (
    RecoveryService,
    mark_mandatory_fission,
    plan_undersized_mandatory_split,
    sole_era_starter_ids,
)
from sim.dmb.time.runner import TurnRunner
from sim.dmb.time.turns import TurnScheduler
from sim.dmb.world.board import HexBoard


def test_sole_survives_then_marked_for_fission() -> None:
    wid = WorldId("world:t102")
    state = WorldState(world_id=wid, ids=IdAllocator(wid))
    state.clock["started_faction_ids"] = ["faction:solo"]
    state.clock["sole_era_starter"] = True
    state.factions["faction:solo"] = {"id": "faction:solo", "status": "active"}
    state.settlements["settlement:1"] = {
        "id": "settlement:1",
        "faction_id": "faction:solo",
        "node_id": "node:1",
        "tier": "settlement",
        "operational": True,
    }
    scores = {"faction:solo": 10}
    caps = {"faction:solo": Fraction(1)}
    collapsed, _ = select_collapse_factions(
        scores,
        caps,
        winner_faction_id="faction:solo",
        sole_era_starter=True,
        entered_faction_ids=["faction:solo"],
    )
    assert collapsed == []
    assert sole_era_starter_ids(state) == ["faction:solo"]
    mark_mandatory_fission(state, "faction:solo")
    assert "faction:solo" in state.clock["mandatory_split_ids"]


def test_one_site_split_never_duplicates_four_centres() -> None:
    wid = WorldId("world:t102b")
    state = WorldState(world_id=wid, ids=IdAllocator(wid))
    board = HexBoard.radius2()
    state.board["topology"] = board.to_dict()
    node = board.nodes[0]
    state.factions["faction:solo"] = {"id": "faction:solo", "status": "active"}
    state.settlements["settlement:only"] = {
        "id": "settlement:only",
        "faction_id": "faction:solo",
        "node_id": node,
        "tier": "settlement",
        "operational": True,
    }
    plan = plan_undersized_mandatory_split(
        state,
        parent_faction_id="faction:solo",
        successor_faction_ids=["faction:a", "faction:b"],
    )
    assert plan["site_count"] == 1
    assert plan["undersized"] is True
    existing_cores = [
        sid
        for pair in plan["core_pairs"]
        for sid in pair.get("core_settlement_ids") or []
    ]
    assert existing_cores == ["settlement:only"]
    assert len(plan["seed_operations"]) == 1
    assert plan["seed_operations"][0]["node_id"] != node


def test_zero_faction_world_turn_seeds_two_not_game_over() -> None:
    wid = WorldId("world:t102c")
    state = WorldState(world_id=wid, ids=IdAllocator(wid))
    board = HexBoard.radius2()
    state.board["topology"] = board.to_dict()
    state.board["nodes"] = {nid: {"id": nid, "exits": []} for nid in board.nodes}
    state.player["node_id"] = board.nodes[0]
    state.people["person:displaced"] = {
        "id": "person:displaced",
        "alive": True,
        "status": "displaced",
        "faction_id": None,
    }
    state.quests["quest.blocked_exit_boulder"] = {"id": "quest.blocked_exit_boulder", "status": "active"}
    state.carts["cart:1"] = {"id": "cart:1", "owner_faction": None, "cargo_lots": [], "status": "idle"}
    # No active factions.
    result = RecoveryService(state).ensure_factions_for_world_turn()
    assert len(result["seeded"]) == 2
    assert state.people["person:displaced"]["alive"] is True
    assert state.quests["quest.blocked_exit_boulder"]["status"] == "active"
    assert "game_over" not in state.clock


def test_only_remaining_mid_era_winner_not_self_collapsed() -> None:
    scores = {"faction:w": 10, "faction:l": 2}
    caps = {fid: Fraction(1) for fid in scores}
    collapsed, _ = select_collapse_factions(
        scores, caps, winner_faction_id="faction:w", entered_faction_ids=sorted(scores)
    )
    assert collapsed == ["faction:l"]
    assert "faction:w" not in collapsed


def test_runner_invokes_recovery_on_world_turn() -> None:
    wid = WorldId("world:t102d")
    state = WorldState(world_id=wid, ids=IdAllocator(wid))
    board = HexBoard.radius2()
    state.board["topology"] = board.to_dict()
    start = board.nodes[0]
    state.board["nodes"] = {start: {"id": start, "exits": {}}}
    state.player["node_id"] = start
    state.clock["scheduled_faction_ids"] = []
    scheduler = TurnScheduler(state.clock)
    runner = TurnRunner(state, scheduler)
    out = runner.execute_wait(start, "press:1")
    assert "last_faction_recovery" in state.clock
    assert len(state.clock["last_faction_recovery"].get("seeded") or []) == 2
    assert out["turn"] >= 0

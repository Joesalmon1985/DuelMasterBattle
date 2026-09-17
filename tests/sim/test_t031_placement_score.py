"""T031 placement rules and derived VP."""

from __future__ import annotations

from sim.dmb.construction.placement import PlacementRules
from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.world.board import HexBoard


def _world() -> tuple[WorldState, HexBoard]:
    board = HexBoard.radius2()
    state = WorldState(world_id=WorldId("world:t031"), ids=IdAllocator(WorldId("world:t031")))
    state.board["topology"] = board.to_dict()
    return state, board


def test_adjacent_active_blocks_ruins_do_not() -> None:
    state, board = _world()
    a = board.nodes[0]
    b = board.adjacent_nodes(a)[0]
    state.settlements["s1"] = {
        "id": "s1",
        "node_id": a,
        "faction_id": "f:enemy",
        "tier": "settlement",
        "operational": True,
    }
    state.roads["r1"] = {"id": "r1", "a": b, "b": board.adjacent_nodes(b)[0], "faction_id": "f:1"}
    # Ensure road endpoint includes b — add road from b to a neighbour owned path
    # For settle we need own road endpoint at target
    state.roads["r2"] = {"id": "r2", "a": b, "b": a, "faction_id": "f:1"}
    rules = PlacementRules(state, board)
    ok, reason = rules.can_settle("f:1", b)
    assert ok is False
    assert reason == "adjacent_settlement"

    # Inert ruins do not block
    state.settlements["s1"]["status"] = "inert"
    state.settlements["s1"]["ruin_only"] = True
    ok2, reason2 = rules.can_settle("f:1", b)
    assert ok2 is True
    assert reason2 == "ok"


def test_hostile_blocks_road_through() -> None:
    state, board = _world()
    a = board.nodes[0]
    b = board.adjacent_nodes(a)[0]
    state.settlements["enemy"] = {
        "id": "enemy",
        "node_id": b,
        "faction_id": "f:hostile",
        "tier": "settlement",
        "operational": True,
    }
    state.roads["seed"] = {"id": "seed", "a": a, "b": board.adjacent_nodes(a)[1] if len(board.adjacent_nodes(a)) > 1 else a, "faction_id": "f:1"}
    # Fix seed to be a real adjacent pair from a
    neighbours = board.adjacent_nodes(a)
    other = neighbours[1] if neighbours[1] != b else neighbours[0]
    state.roads["seed"] = {"id": "seed", "a": a, "b": other, "faction_id": "f:1"}
    rules = PlacementRules(state, board)
    ok, reason = rules.can_road("f:1", a, b)
    assert ok is False
    assert reason == "hostile_node"


def test_scores_settlement_city_legacy_no_caps() -> None:
    state, _board = _world()
    state.settlements["s1"] = {
        "id": "s1",
        "node_id": "node:1",
        "faction_id": "f:1",
        "tier": "settlement",
        "operational": True,
    }
    state.settlements["s2"] = {
        "id": "s2",
        "node_id": "node:2",
        "faction_id": "f:1",
        "tier": "city",
        "operational": True,
    }
    state.settlements["legacy"] = {
        "id": "legacy",
        "node_id": "node:3",
        "faction_id": "f:1",
        "tier": "settlement",
        "legacy": True,
        "upgraded": False,
        "operational": True,
    }
    state.settlements["staging"] = {
        "id": "staging",
        "node_id": "node:4",
        "faction_id": None,
        "tier": "staging",
        "staging": True,
        "operational": True,
    }
    scores = ScoreService(state)
    assert scores.score("f:1") == 1 + 2 + 0
    assert scores.settlement_vp(state.settlements["s2"]) == 2
    # No piece-cap fields invented
    assert "piece_cap" not in state.settlements["s1"]
    assert "piece_cap" not in state.factions

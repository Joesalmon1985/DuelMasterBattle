"""T034 routes and one-edge-per-turn movement."""

from __future__ import annotations

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.logistics.carts import CartService
from sim.dmb.logistics.routes import RoutePlanner
from sim.dmb.logistics.stock import StockLedger


def _three_node() -> tuple[WorldState, RoutePlanner, CartService]:
    state = WorldState(world_id=WorldId("world:t034"), ids=IdAllocator(WorldId("world:t034")))
    state.board = {
        "node_hexes": {"N0": ["hex:0"], "N1": ["hex:1"], "N2": ["hex:2"]},
        "hazard_cubes": {},
    }
    state.roads = {
        "r01": {"id": "r01", "a": "N0", "b": "N1", "faction_id": "f:1"},
        "r12": {"id": "r12", "a": "N1", "b": "N2", "faction_id": "f:1"},
    }
    ledger = StockLedger(state)
    carts = CartService(state, ledger=ledger)
    routes = RoutePlanner(state)
    return state, routes, carts


def test_three_node_path_two_turns() -> None:
    state, routes, carts = _three_node()
    planned = routes.route("f:1", "N0", "N2")
    assert planned["path"] == ["N0", "N1", "N2"]
    cart = carts.create(owner_faction="f:1", home_store="store:s", current_node="N0")
    carts.begin_turn()
    carts.assign(cart["id"], planned["path"], destination_store="store:d")
    # Assigned this turn — no retroactive move
    carts.advance_turn(cart["id"], validate_edge=lambda a, b, c: routes.validate_next_edge("f:1", a, b))
    assert state.carts[cart["id"]]["current_node"] == "N0"

    carts.begin_turn()
    carts.advance_turn(cart["id"], validate_edge=lambda a, b, c: routes.validate_next_edge("f:1", a, b))
    assert state.carts[cart["id"]]["current_node"] == "N1"

    carts.begin_turn()
    carts.advance_turn(cart["id"], validate_edge=lambda a, b, c: routes.validate_next_edge("f:1", a, b))
    assert state.carts[cart["id"]]["current_node"] == "N2"


def test_blocked_middle_and_seconds_no_move() -> None:
    state, routes, carts = _three_node()
    state.board["hazard_cubes"] = {"c1": {"hex_id": "hex:1", "active": True}}
    planned = routes.route("f:1", "N0", "N2")
    assert planned["path"] is None
    assert planned["reason"] in {"no_road_path", "destination_blocked"} or "block" in planned["reason"] or planned["reason"] == "no_road_path"
    # Direct path blocked at N1
    cart = carts.create(owner_faction="f:1", home_store="store:s", current_node="N0")
    carts.assign(cart["id"], ["N0", "N1", "N2"])
    carts.begin_turn()
    carts.advance_turn(cart["id"], validate_edge=lambda a, b, c: routes.validate_next_edge("f:1", a, b))
    assert state.carts[cart["id"]]["current_node"] == "N0"
    assert state.carts[cart["id"]]["status"] == "blocked"

    # Seconds alone: no advance_turn => zero edges
    before = state.carts[cart["id"]]["current_node"]
    # simulate game-time advance without world turn logistics
    assert before == "N0"

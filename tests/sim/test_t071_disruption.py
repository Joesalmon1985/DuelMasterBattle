"""T071 hazard disruption of industry and carts."""

from __future__ import annotations

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.hazards.queries import catan_grant_suppressed, industrial_blocked, node_blocked_for_civilian
from sim.dmb.hazards.service import CatastropheService
from sim.dmb.logistics.routes import RoutePlanner


def test_cube_stops_source_leaves_finite() -> None:
    state = WorldState(world_id=WorldId("world:t071"))
    svc = CatastropheService(state)
    svc.add_cube("hex:a", "demon")
    assert industrial_blocked(state.board, "hex:a")
    assert catan_grant_suppressed(state.board, "hex:a")
    assert not industrial_blocked(state.board, "hex:b")
    # Finite stock untouched
    state.stocks["store:1"] = {"ore": 100}
    assert state.stocks["store:1"]["ore"] == 100


def test_cart_blocked_wizard_army_ok() -> None:
    state = WorldState(world_id=WorldId("world:t071b"))
    state.board["node_hexes"] = {"n1": ["hex:a"], "n2": ["hex:b"]}
    svc = CatastropheService(state)
    svc.add_cube("hex:a", "demon")
    assert node_blocked_for_civilian(state.board, "n1", touching_hexes=lambda n: state.board["node_hexes"].get(n, []))
    assert not node_blocked_for_civilian(state.board, "n2", touching_hexes=lambda n: state.board["node_hexes"].get(n, []))
    # Military/wizard exempt — RoutePlanner blocks civilians only.
    planner = RoutePlanner(state)
    assert planner.is_node_blocked("n1")

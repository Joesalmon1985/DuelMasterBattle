"""T035 transport director assign/reroute/park."""

from __future__ import annotations

from sim.dmb.construction.buildings import BuildingService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.logistics.carts import CartService
from sim.dmb.logistics.director import LogisticsService
from sim.dmb.logistics.routes import RoutePlanner
from sim.dmb.logistics.stock import StockLedger


def _world() -> tuple[WorldState, LogisticsService]:
    state = WorldState(world_id=WorldId("world:t035"), ids=IdAllocator(WorldId("world:t035")))
    state.board = {
        "node_hexes": {"N0": ["h0"], "N1": ["h1"], "N2": ["h2"], "N3": ["h3"]},
        "hazard_cubes": {},
    }
    state.roads = {
        "r01": {"id": "r01", "a": "N0", "b": "N1", "faction_id": "f:1"},
        "r12": {"id": "r12", "a": "N1", "b": "N2", "faction_id": "f:1"},
    }
    buildings = BuildingService(state)
    wh0 = buildings.create("building.warehouse", node_id="N0", faction_id="f:1")
    wh2 = buildings.create("building.warehouse", node_id="N2", faction_id="f:1")
    ledger = StockLedger(state)
    ledger.credit(f"store:{wh0['id']}", "timber", 5)
    carts = CartService(state, ledger=ledger)
    c1 = carts.create(owner_faction="f:1", home_store=f"store:{wh0['id']}", current_node="N0")
    c2 = carts.create(owner_faction="f:1", home_store=f"store:{wh0['id']}", current_node="N0")
    director = LogisticsService(state, carts=carts, routes=RoutePlanner(state), ledger=ledger)
    return state, director


def test_split_loads_no_duplicate() -> None:
    state, director = _world()
    ledger = StockLedger(state)
    store = [k for k in state.stocks if k.startswith("store:")][0]
    dest = "store:dest"
    idle = director.idle_carts("f:1")
    assert len(idle) == 2
    r1 = ledger.reserve("o1", {"timber": 2}, store_id=store)
    r2 = ledger.reserve("o2", {"timber": 2}, store_id=store)
    a1 = director.assign(idle[0], source="N0", target="N2", destination_store=dest, reservation_id=r1["id"])
    a2 = director.assign(idle[1], source="N0", target="N2", destination_store=dest, reservation_id=r2["id"])
    assert a1["status"] == "assigned" and a2["status"] == "assigned"
    assert ledger.available(store, "timber") == 1
    assert ledger.totals("timber")["cargo"] == 4


def test_destroyed_destination_reroutes_or_parks_keeps_cargo() -> None:
    state, director = _world()
    ledger = StockLedger(state)
    store = [k for k in state.stocks if k.startswith("store:")][0]
    idle = director.idle_carts("f:1")[0]
    res = ledger.reserve("ox", {"timber": 2}, store_id=store)
    director.assign(idle, source="N0", target="N2", destination_store="store:gone", reservation_id=res["id"])
    # Break middle road network so destination unreachable; park with cargo
    state.roads.clear()
    out = director.reroute(idle)
    assert out["cargo_retained"] is True
    assert out["status"] in {"parked", "rerouted"}
    cart = state.carts[idle]
    aboard = sum(1 for lot in cart.get("cargo_lots") or [] if lot.get("status") == "aboard")
    assert aboard >= 1 or out["status"] == "rerouted"
    # Never silently deleted
    assert ledger.totals("timber")["accounted"] == 5

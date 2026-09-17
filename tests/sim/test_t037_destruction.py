"""T037 destruction consequences."""

from __future__ import annotations

from sim.dmb.construction.buildings import BuildingService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.logistics.carts import CartService
from sim.dmb.logistics.stock import StockLedger
from sim.dmb.people.registry import PeopleService


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t037"), ids=IdAllocator(WorldId("world:t037")))


def test_centre_loss_no_capture_strands_industry() -> None:
    state = _world()
    buildings = BuildingService(state)
    sid = "settlement:1"
    state.settlements[sid] = {
        "id": sid,
        "node_id": "N0",
        "faction_id": "f:1",
        "tier": "settlement",
        "operational": True,
    }
    centre = buildings.create("building.centre", node_id="N0", faction_id="f:1", settlement_id=sid)
    wh = buildings.create("building.warehouse", node_id="N0", faction_id="f:1", settlement_id=sid)
    state.settlements[sid]["centre_id"] = centre["id"]
    state.settlements[sid]["warehouse_id"] = wh["id"]
    out = buildings.destroy(centre["id"], cause_id="attack")
    assert out["effects"]["centre_loss"]["captured"] is False
    assert state.settlements[sid]["captured_by"] is None
    assert state.settlements[sid]["faction_id"] is None
    assert state.buildings[wh["id"]]["owned"] is False
    assert state.buildings[wh["id"]]["active"] is False
    assert state.buildings[wh["id"]]["status"] != "destroyed"


def test_warehouse_loss_spares_cart_cargo_no_double_loss() -> None:
    state = _world()
    buildings = BuildingService(state)
    ledger = StockLedger(state)
    carts = CartService(state, ledger=ledger)
    people = PeopleService(state)
    wh = buildings.create("building.warehouse", node_id="N0", faction_id="f:1")
    store = f"store:{wh['id']}"
    ledger.credit(store, "timber", 4)
    cart = carts.create(owner_faction="f:1", home_store=store, current_node="N1")
    res = ledger.reserve("o1", {"timber": 2}, store_id=store)
    carts.load_from_reservation(cart["id"], res["id"])
    worker = people.create_person(name="W", node_id="N0")
    people.assign_job(worker["id"], "job.warehouse_keeper", wh["id"])

    first = buildings.destroy(wh["id"], cause_id="boom")
    assert first["effects"]["stock_loss"]["goods"]["timber"] == 2  # only local remaining
    assert ledger.totals("timber")["cargo"] == 2
    assert state.people[worker["id"]]["alive"] is True
    assert state.people[worker["id"]]["status"] == "displaced"

    second = buildings.destroy(wh["id"], cause_id="boom")
    assert second["idempotent"] is True
    assert ledger.totals("timber")["lost"] == 2
    assert ledger.totals("timber")["accounted"] == 4

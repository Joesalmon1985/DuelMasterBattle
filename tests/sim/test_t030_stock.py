"""T030 StockLedger conservation and FX-CARGO oracle."""

from __future__ import annotations

import pytest

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.logistics.stock import INDUSTRIAL_NS, StockLedger


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t030"), ids=IdAllocator(WorldId("world:t030")))


def test_fx_cargo_oracle_reserve_load_deliver_destroy() -> None:
    state = _world()
    ledger = StockLedger(state)
    src = "store:src"
    dest = "store:dest"
    ledger.credit(src, "timber", 5)
    assert ledger.available(src, "timber") == 5

    res = ledger.reserve("order:1", {"timber": 3}, store_id=src)
    assert ledger.available(src, "timber") == 2
    assert ledger.reserved(src, "timber") == 3

    with pytest.raises(TypeValidationError, match="insufficient"):
        ledger.reserve("order:2", {"timber": 3}, store_id=src)

    cart_id = state.ids.new("cart")
    state.carts[cart_id] = {
        "id": cart_id,
        "owner_faction": "f:1",
        "capacity": 4,
        "cargo_lots": [],
        "status": "idle",
    }
    ledger.load(res["id"], cart_id)
    assert ledger.available(src, "timber") == 2
    assert ledger.reserved(src, "timber") == 0
    assert ledger.totals("timber")["cargo"] == 3

    delivery = ledger.credit_delivery(cart_id, dest, delivery_id="del:1")
    assert ledger.available(dest, "timber") == 3
    assert ledger.totals("timber")["cargo"] == 0
    assert ledger.totals("timber")["accounted"] == 5

    # Duplicate delivery ack conserves
    again = ledger.credit_delivery(cart_id, dest, delivery_id="del:1")
    assert again["delivery_id"] == delivery["delivery_id"]
    assert ledger.available(dest, "timber") == 3
    assert ledger.totals("timber")["accounted"] == 5

    # Destroy path: reload scenario for loss
    state2 = _world()
    ledger2 = StockLedger(state2)
    ledger2.credit(src, "timber", 5)
    res2 = ledger2.reserve("order:9", {"timber": 3}, store_id=src)
    cart2 = state2.ids.new("cart")
    state2.carts[cart2] = {
        "id": cart2,
        "owner_faction": "f:1",
        "capacity": 4,
        "cargo_lots": [],
        "status": "idle",
    }
    ledger2.load(res2["id"], cart2)
    loss = ledger2.record_loss({"timber": 3}, cart_id=cart2, cause_id="cause:cart")
    assert loss["goods"]["timber"] == 3
    totals = ledger2.totals("timber")
    assert totals["available"] == 2
    assert totals["cargo"] == 0
    assert totals["lost"] == 3
    assert totals["accounted"] == 5


def test_cancellation_restores_same_node_stock() -> None:
    state = _world()
    ledger = StockLedger(state)
    store = "store:home"
    ledger.credit(store, "brick", 4)
    res = ledger.reserve("order:c", {"brick": 2}, store_id=store)
    ledger.release_reservation(res["id"])
    assert ledger.available(store, "brick") == 4
    assert ledger.reserved(store, "brick") == 0


def test_industrial_namespace_separate() -> None:
    state = _world()
    ledger = StockLedger(state)
    store = "store:mixed"
    ledger.credit(store, "ore", 5, namespace="catan")
    ledger.credit(store, "ore", 7, namespace=INDUSTRIAL_NS)
    assert ledger.available(store, "ore") == 5
    assert ledger.available(store, "ore", namespace=INDUSTRIAL_NS) == 7
    ledger.reserve("order:ind", {"ore": 3}, store_id=store, namespace=INDUSTRIAL_NS)
    assert ledger.available(store, "ore") == 5
    assert ledger.available(store, "ore", namespace=INDUSTRIAL_NS) == 4

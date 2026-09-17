"""T033 cart load/deliver/destroy conservation."""

from __future__ import annotations

import pytest

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.logistics.carts import CartService
from sim.dmb.logistics.stock import StockLedger


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t033"), ids=IdAllocator(WorldId("world:t033")))


def test_load_deliver_duplicate_and_capacity() -> None:
    state = _world()
    ledger = StockLedger(state)
    carts = CartService(state, ledger=ledger)
    src, dest = "store:src", "store:dest"
    ledger.credit(src, "timber", 5)
    cart = carts.create(owner_faction="f:1", home_store=src, current_node="N0")
    res = ledger.reserve("o1", {"timber": 3}, store_id=src)
    carts.load_from_reservation(cart["id"], res["id"])
    assert ledger.totals("timber")["accounted"] == 5
    d1 = carts.deliver(cart["id"], dest, delivery_id="d1")
    d2 = carts.deliver(cart["id"], dest, delivery_id="d1")
    assert d1["delivery_id"] == d2["delivery_id"]
    assert ledger.available(dest, "timber") == 3
    assert ledger.available(src, "timber") == 2
    assert ledger.totals("timber")["accounted"] == 5

    cart2 = carts.create(owner_faction="f:1", home_store=src, current_node="N0")
    ledger.credit(src, "brick", 5)
    res2 = ledger.reserve("o2", {"brick": 5}, store_id=src)
    with pytest.raises(TypeValidationError, match="capacity"):
        carts.load_from_reservation(cart2["id"], res2["id"])


def test_destroy_records_exact_cargo_loss() -> None:
    state = _world()
    ledger = StockLedger(state)
    carts = CartService(state, ledger=ledger)
    src = "store:src"
    ledger.credit(src, "wool", 4)
    cart = carts.create(owner_faction="f:1", home_store=src, current_node="N0")
    res = ledger.reserve("o3", {"wool": 4}, store_id=src)
    carts.load_from_reservation(cart["id"], res["id"])
    out = carts.destroy(cart["id"], cause_id="boom")
    assert out["loss"]["goods"]["wool"] == 4
    assert ledger.totals("wool")["lost"] == 4
    assert ledger.totals("wool")["accounted"] == 4

"""Persistent carts, cargo lots and deliveries (C05 / T033–T034)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.logistics.stock import StockLedger

DEFAULT_CAPACITY = 4


@dataclass
class CartService:
    state: WorldState
    ledger: StockLedger | None = None
    moved_this_turn: set[str] = field(default_factory=set)
    assigned_this_turn: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.ledger is None:
            self.ledger = StockLedger(self.state)

    def create(
        self,
        *,
        owner_faction: str,
        home_store: str,
        current_node: str,
        capacity: int = DEFAULT_CAPACITY,
    ) -> dict[str, Any]:
        cart_id = self.state.ids.new("cart")
        record = {
            "id": cart_id,
            "owner_faction": owner_faction,
            "home_store": home_store,
            "current_node": current_node,
            "next_edge": None,
            "status": "idle",
            "capacity": int(capacity),
            "cargo_lots": [],
            "route": [],
            "route_index": 0,
            "source_store": home_store,
            "destination_store": None,
            "shipment_id": None,
            "delivery_id": None,
            "assigned_turn": None,
        }
        self.state.carts[cart_id] = record
        return dict(record)

    def cargo_quantity(self, cart_id: str) -> int:
        cart = self.state.carts[cart_id]
        return sum(int(lot.get("quantity", 0)) for lot in cart.get("cargo_lots") or [] if lot.get("status") == "aboard")

    def assign(self, cart_id: str, route: list[str], *, destination_store: str | None = None) -> dict[str, Any]:
        cart = self.state.carts.get(cart_id)
        if cart is None:
            raise TypeValidationError(f"unknown cart {cart_id}")
        if not route or route[0] != cart.get("current_node"):
            if route and cart.get("current_node") not in route:
                raise TypeValidationError("route must include current node")
        cart["route"] = list(route)
        cart["route_index"] = list(route).index(cart["current_node"]) if cart["current_node"] in route else 0
        cart["destination_store"] = destination_store
        cart["status"] = "en_route"
        cart["assigned_turn"] = int(self.state.clock.get("turn", 0))
        self.assigned_this_turn.add(cart_id)
        return dict(cart)

    def load_from_reservation(self, cart_id: str, reservation_id: str) -> dict[str, Any]:
        cart = self.state.carts.get(cart_id)
        if cart is None:
            raise TypeValidationError(f"unknown cart {cart_id}")
        existing = self.state.stocks.get("_reservations", {}).get(reservation_id)
        if existing is None:
            raise TypeValidationError("unknown reservation")
        qty = sum(int(v) for v in existing.get("goods", {}).values())
        if self.cargo_quantity(cart_id) + qty > int(cart.get("capacity", DEFAULT_CAPACITY)):
            raise TypeValidationError("capacity exceeded")
        assert self.ledger is not None
        self.ledger.load(reservation_id, cart_id)
        cart["status"] = "loaded"
        return dict(cart)

    def deliver(self, cart_id: str, dest_store_id: str | None = None, *, delivery_id: str | None = None) -> dict[str, Any]:
        cart = self.state.carts.get(cart_id)
        if cart is None:
            raise TypeValidationError(f"unknown cart {cart_id}")
        dest = dest_store_id or cart.get("destination_store")
        if not dest:
            raise TypeValidationError("no destination store")
        assert self.ledger is not None
        return self.ledger.credit_delivery(cart_id, str(dest), delivery_id=delivery_id)

    def destroy(self, cart_id: str, *, cause_id: str | None = None) -> dict[str, Any]:
        cart = self.state.carts.get(cart_id)
        if cart is None:
            raise TypeValidationError(f"unknown cart {cart_id}")
        goods: dict[str, int] = {}
        for lot in cart.get("cargo_lots") or []:
            if lot.get("status") != "aboard":
                continue
            good = str(lot["good_id"])
            goods[good] = goods.get(good, 0) + int(lot["quantity"])
        assert self.ledger is not None
        loss = self.ledger.record_loss(goods, cart_id=cart_id, cause_id=cause_id or f"cart-loss:{cart_id}")
        cart["status"] = "destroyed"
        self.state.tombstones[cart_id] = {
            "kind": "cart",
            "display_name": cart_id,
            "cause_id": cause_id,
        }
        return {"cart": dict(cart), "loss": loss}

    def begin_turn(self) -> None:
        self.moved_this_turn.clear()
        self.assigned_this_turn.clear()

    def advance_turn(self, cart_id: str, *, validate_edge=None) -> dict[str, Any]:
        """Move at most one constructed road edge. No retroactive move if assigned this turn."""
        cart = self.state.carts.get(cart_id)
        if cart is None:
            raise TypeValidationError(f"unknown cart {cart_id}")
        if cart.get("status") in {"destroyed", "idle", "parked"}:
            return dict(cart)
        if cart_id in self.assigned_this_turn:
            return dict(cart)
        if cart_id in self.moved_this_turn:
            return dict(cart)
        route = list(cart.get("route") or [])
        idx = int(cart.get("route_index", 0))
        if idx >= len(route) - 1:
            # Arrived — deliver if destination set
            if cart.get("destination_store") and self.cargo_quantity(cart_id) > 0:
                self.deliver(cart_id)
            cart["status"] = "arrived"
            return dict(cart)
        nxt = route[idx + 1]
        if validate_edge is not None:
            ok, reason = validate_edge(cart["current_node"], nxt, cart)
            if not ok:
                cart["status"] = "blocked"
                cart["block_reason"] = reason
                return dict(cart)
        cart["current_node"] = nxt
        cart["route_index"] = idx + 1
        cart["status"] = "en_route"
        self.moved_this_turn.add(cart_id)
        if cart["route_index"] >= len(route) - 1:
            if cart.get("destination_store") and self.cargo_quantity(cart_id) > 0:
                self.deliver(cart_id)
            cart["status"] = "arrived"
        return dict(cart)

    def advance_all(self, *, validate_edge=None) -> list[dict[str, Any]]:
        results = []
        for cart_id in sorted(self.state.carts.keys()):
            cart = self.state.carts[cart_id]
            if cart.get("status") in {"destroyed", "idle", "parked", "delivered"}:
                continue
            results.append(self.advance_turn(cart_id, validate_edge=validate_edge))
        return results

"""Deterministic transport director (C05 / T035)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.logistics.carts import CartService
from sim.dmb.logistics.routes import RoutePlanner
from sim.dmb.logistics.stock import StockLedger


@dataclass
class LogisticsService:
    state: WorldState
    carts: CartService | None = None
    routes: RoutePlanner | None = None
    ledger: StockLedger | None = None

    def __post_init__(self) -> None:
        if self.ledger is None:
            self.ledger = StockLedger(self.state)
        if self.carts is None:
            self.carts = CartService(self.state, ledger=self.ledger)
        if self.routes is None:
            self.routes = RoutePlanner(self.state)

    def idle_carts(self, faction_id: str) -> list[str]:
        out = []
        for cid, cart in sorted(self.state.carts.items()):
            if cart.get("owner_faction") != faction_id:
                continue
            if cart.get("status") in {"idle", "arrived", "delivered"} and cart.get("status") != "destroyed":
                if not any(lot.get("status") == "aboard" for lot in cart.get("cargo_lots") or []):
                    out.append(cid)
        return out

    def assign(
        self,
        cart_id: str,
        *,
        source: str,
        target: str,
        destination_store: str,
        reservation_id: str | None = None,
    ) -> dict[str, Any]:
        assert self.carts is not None and self.routes is not None
        cart = self.state.carts.get(cart_id)
        if cart is None:
            raise TypeValidationError(f"unknown cart {cart_id}")
        planned = self.routes.route(str(cart["owner_faction"]), source, target)
        if planned["path"] is None:
            return {"status": "blocked", "reason": planned["reason"], "cart_id": cart_id}
        if reservation_id:
            self.carts.load_from_reservation(cart_id, reservation_id)
        self.carts.assign(cart_id, planned["path"], destination_store=destination_store)
        return {"status": "assigned", "cart_id": cart_id, "path": planned["path"]}

    def reroute(self, cart_id: str) -> dict[str, Any]:
        """Fallback: destination → source → nearest own warehouse → park. Never delete cargo."""
        assert self.carts is not None and self.routes is not None
        cart = self.state.carts.get(cart_id)
        if cart is None:
            raise TypeValidationError(f"unknown cart {cart_id}")
        owner = str(cart["owner_faction"])
        current = str(cart["current_node"])
        cargo_ok = any(lot.get("status") == "aboard" for lot in cart.get("cargo_lots") or [])

        # 1) original destination node (from destination store / route end)
        dest_node = None
        if cart.get("route"):
            dest_node = cart["route"][-1]
        attempts = []
        if dest_node:
            attempts.append(("destination", dest_node, cart.get("destination_store")))
        src_node = None
        # infer source from home
        home = cart.get("home_store")
        for bid, b in self.state.buildings.items():
            if f"store:{bid}" == home or home == f"store:{bid}":
                src_node = b.get("node_id")
                break
        if cart.get("source_node"):
            src_node = cart["source_node"]
        if src_node:
            attempts.append(("source", src_node, cart.get("source_store") or home))

        # nearest own warehouse
        warehouses = []
        for bid, b in self.state.buildings.items():
            if b.get("slot_kind") != "warehouse" or b.get("status") == "destroyed":
                continue
            if b.get("faction_id") != owner:
                continue
            warehouses.append((str(b["node_id"]), f"store:{bid}"))
        warehouses.sort()
        for node_id, store_id in warehouses:
            attempts.append(("nearest_warehouse", node_id, store_id))

        for label, node_id, store_id in attempts:
            planned = self.routes.route(owner, current, str(node_id))
            if planned["path"] is not None:
                self.carts.assign(cart_id, planned["path"], destination_store=store_id)
                cart["reroute_reason"] = label
                return {"status": "rerouted", "target": label, "path": planned["path"], "cargo_retained": cargo_ok}

        # Park — cargo stays aboard at current node
        cart["status"] = "parked"
        cart["reroute_reason"] = "parked_blocked"
        return {"status": "parked", "node_id": current, "cargo_retained": cargo_ok, "cargo_lots": list(cart.get("cargo_lots") or [])}

    def return_home(self, cart_id: str) -> dict[str, Any]:
        cart = self.state.carts.get(cart_id)
        if cart is None:
            raise TypeValidationError(f"unknown cart {cart_id}")
        cart["destination_store"] = cart.get("home_store")
        return self.reroute(cart_id)

    def park(self, cart_id: str) -> dict[str, Any]:
        cart = self.state.carts.get(cart_id)
        if cart is None:
            raise TypeValidationError(f"unknown cart {cart_id}")
        cart["status"] = "parked"
        return {"status": "parked", "cart_id": cart_id, "cargo_lots": list(cart.get("cargo_lots") or [])}

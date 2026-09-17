"""Conserved Catan/industrial stock ledger (C05 / T030)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError

CATAN_NS = "catan"
INDUSTRIAL_NS = "industrial"


@dataclass
class StockLedger:
    state: WorldState
    losses: dict[str, Any] = field(default_factory=dict)

    def _bucket(self, store_id: str, namespace: str, good: str) -> dict[str, int]:
        store = self.state.stocks.setdefault(store_id, {})
        ns = store.setdefault(namespace, {})
        entry = ns.setdefault(good, {"available": 0, "reserved": 0, "escrow": 0})
        for key in ("available", "reserved", "escrow"):
            entry[key] = int(entry.get(key, 0))
        return entry

    def available(self, store_id: str, good: str, *, namespace: str = CATAN_NS) -> int:
        return int(self._bucket(store_id, namespace, good)["available"])

    def reserved(self, store_id: str, good: str, *, namespace: str = CATAN_NS) -> int:
        return int(self._bucket(store_id, namespace, good)["reserved"])

    def escrow(self, store_id: str, good: str, *, namespace: str = CATAN_NS) -> int:
        return int(self._bucket(store_id, namespace, good)["escrow"])

    def credit(
        self,
        store_id: str,
        good: str,
        qty: int,
        *,
        namespace: str = CATAN_NS,
        classification: str = "available",
    ) -> None:
        if qty < 0:
            raise TypeValidationError("negative credit forbidden")
        entry = self._bucket(store_id, namespace, good)
        if classification not in {"available", "reserved", "escrow"}:
            raise TypeValidationError(f"bad classification {classification}")
        entry[classification] = int(entry[classification]) + int(qty)

    def reserve(
        self,
        order_id: str,
        goods: dict[str, int],
        *,
        store_id: str,
        namespace: str = CATAN_NS,
    ) -> dict[str, Any]:
        """Atomically move available → reserved for an order. Returns reservation record."""
        for good, qty in goods.items():
            if qty < 0:
                raise TypeValidationError("negative reserve")
            if self.available(store_id, good, namespace=namespace) < qty:
                raise TypeValidationError(f"insufficient {namespace}:{good} at {store_id}")
        reservation_id = f"reservation:{order_id}"
        existing = self.state.stocks.setdefault("_reservations", {})
        if reservation_id in existing:
            raise TypeValidationError(f"duplicate reservation {reservation_id}")
        reserved_goods: dict[str, int] = {}
        for good, qty in goods.items():
            entry = self._bucket(store_id, namespace, good)
            entry["available"] -= int(qty)
            entry["reserved"] += int(qty)
            reserved_goods[good] = int(qty)
        record = {
            "id": reservation_id,
            "order_id": order_id,
            "store_id": store_id,
            "namespace": namespace,
            "goods": reserved_goods,
            "status": "reserved",
            "location": "warehouse",
        }
        existing[reservation_id] = record
        return dict(record)

    def release_reservation(self, reservation_id: str) -> dict[str, Any]:
        existing = self.state.stocks.setdefault("_reservations", {})
        record = existing.get(reservation_id)
        if record is None:
            raise TypeValidationError(f"unknown reservation {reservation_id}")
        if record.get("status") != "reserved":
            raise TypeValidationError("reservation not releasable")
        store_id = str(record["store_id"])
        namespace = str(record.get("namespace", CATAN_NS))
        for good, qty in dict(record["goods"]).items():
            entry = self._bucket(store_id, namespace, good)
            entry["reserved"] -= int(qty)
            entry["available"] += int(qty)
        record["status"] = "released"
        return dict(record)

    def load(self, reservation_id: str, cart_id: str) -> dict[str, Any]:
        """Move reserved warehouse goods into cart cargo (atomic)."""
        existing = self.state.stocks.setdefault("_reservations", {})
        record = existing.get(reservation_id)
        if record is None:
            raise TypeValidationError(f"unknown reservation {reservation_id}")
        if record.get("status") != "reserved":
            raise TypeValidationError("reservation not loadable")
        cart = self.state.carts.get(cart_id)
        if cart is None:
            raise TypeValidationError(f"unknown cart {cart_id}")
        store_id = str(record["store_id"])
        namespace = str(record.get("namespace", CATAN_NS))
        lots = cart.setdefault("cargo_lots", [])
        for good, qty in dict(record["goods"]).items():
            entry = self._bucket(store_id, namespace, good)
            if entry["reserved"] < int(qty):
                raise TypeValidationError("reserved underflow")
            entry["reserved"] -= int(qty)
            lot_id = self.state.ids.new("item")
            lots.append(
                {
                    "id": lot_id,
                    "good_id": good,
                    "quantity": int(qty),
                    "namespace": namespace,
                    "reservation_id": reservation_id,
                    "beneficial_owner": cart.get("owner_faction"),
                    "status": "aboard",
                    "physical_container": cart_id,
                }
            )
            # Track cargo totals for conservation queries
            cargo = self.state.stocks.setdefault("_cargo", {})
            key = f"{namespace}:{good}"
            cargo[key] = int(cargo.get(key, 0)) + int(qty)
        record["status"] = "loaded"
        record["cart_id"] = cart_id
        record["location"] = "cart"
        return dict(record)

    def credit_delivery(
        self,
        cart_id: str,
        dest_store_id: str,
        *,
        delivery_id: str | None = None,
        as_escrow: bool = False,
    ) -> dict[str, Any]:
        cart = self.state.carts.get(cart_id)
        if cart is None:
            raise TypeValidationError(f"unknown cart {cart_id}")
        # Idempotent duplicate delivery ack
        deliveries = self.state.stocks.setdefault("_deliveries", {})
        did = delivery_id or cart.get("delivery_id") or f"delivery:{cart_id}:{dest_store_id}"
        if did in deliveries:
            return dict(deliveries[did])
        lots = list(cart.get("cargo_lots") or [])
        credited: list[dict[str, Any]] = []
        cargo = self.state.stocks.setdefault("_cargo", {})
        classification = "escrow" if as_escrow else "available"
        for lot in lots:
            if lot.get("status") != "aboard":
                continue
            good = str(lot["good_id"])
            qty = int(lot["quantity"])
            namespace = str(lot.get("namespace", CATAN_NS))
            self.credit(dest_store_id, good, qty, namespace=namespace, classification=classification)
            key = f"{namespace}:{good}"
            cargo[key] = int(cargo.get(key, 0)) - qty
            lot["status"] = "delivered"
            lot["physical_container"] = dest_store_id
            credited.append({"good": good, "quantity": qty, "namespace": namespace})
        cart["cargo_lots"] = [lot for lot in lots if lot.get("status") == "aboard"]
        result = {
            "delivery_id": did,
            "cart_id": cart_id,
            "dest_store_id": dest_store_id,
            "credited": credited,
            "status": "delivered",
        }
        deliveries[did] = result
        cart["delivery_id"] = did
        cart["status"] = "delivered"
        return dict(result)

    def consume(
        self,
        store_id: str,
        goods: dict[str, int],
        *,
        namespace: str = CATAN_NS,
        from_classification: str = "available",
        cause_id: str | None = None,
    ) -> dict[str, Any]:
        for good, qty in goods.items():
            entry = self._bucket(store_id, namespace, good)
            if int(entry.get(from_classification, 0)) < int(qty):
                raise TypeValidationError(f"insufficient {from_classification} {good}")
        for good, qty in goods.items():
            entry = self._bucket(store_id, namespace, good)
            entry[from_classification] = int(entry[from_classification]) - int(qty)
        consumed = self.state.stocks.setdefault("_consumed", [])
        record = {
            "store_id": store_id,
            "namespace": namespace,
            "goods": dict(goods),
            "from": from_classification,
            "cause_id": cause_id,
        }
        consumed.append(record)
        return dict(record)

    def record_loss(
        self,
        goods: dict[str, int],
        *,
        namespace: str = CATAN_NS,
        cause_id: str | None = None,
        source: str | None = None,
        cart_id: str | None = None,
    ) -> dict[str, Any]:
        loss_id = self.state.ids.new("cause") if cause_id is None else cause_id
        cargo = self.state.stocks.setdefault("_cargo", {})
        if cart_id:
            cart = self.state.carts.get(cart_id)
            if cart:
                for lot in list(cart.get("cargo_lots") or []):
                    if lot.get("status") != "aboard":
                        continue
                    good = str(lot["good_id"])
                    qty = int(lot["quantity"])
                    ns = str(lot.get("namespace", CATAN_NS))
                    key = f"{ns}:{good}"
                    cargo[key] = int(cargo.get(key, 0)) - qty
                    lot["status"] = "lost"
                cart["cargo_lots"] = []
                cart["status"] = "destroyed"
        else:
            for good, qty in goods.items():
                key = f"{namespace}:{good}"
                # If source is a store classification, debit it
                if source and source.startswith("store:"):
                    # Caller already removed from store; just record
                    pass
                cargo[key] = int(cargo.get(key, 0))  # no-op adjust
        losses = self.state.stocks.setdefault("_losses", {})
        if loss_id in losses:
            return dict(losses[loss_id])  # no double loss
        record = {
            "id": loss_id,
            "namespace": namespace,
            "goods": dict(goods),
            "cause_id": cause_id or loss_id,
            "source": source,
            "cart_id": cart_id,
        }
        losses[loss_id] = record
        return dict(record)

    def totals(self, good: str, *, namespace: str = CATAN_NS) -> dict[str, int]:
        available = reserved = escrow = 0
        for store_id, store in self.state.stocks.items():
            if store_id.startswith("_"):
                continue
            entry = store.get(namespace, {}).get(good, {})
            available += int(entry.get("available", 0))
            reserved += int(entry.get("reserved", 0))
            escrow += int(entry.get("escrow", 0))
        cargo = int(self.state.stocks.get("_cargo", {}).get(f"{namespace}:{good}", 0))
        consumed = 0
        for rec in self.state.stocks.get("_consumed", []):
            if rec.get("namespace") == namespace:
                consumed += int(rec.get("goods", {}).get(good, 0))
        lost = 0
        for rec in self.state.stocks.get("_losses", {}).values():
            if rec.get("namespace") == namespace:
                lost += int(rec.get("goods", {}).get(good, 0))
        return {
            "available": available,
            "reserved": reserved,
            "escrow": escrow,
            "cargo": cargo,
            "consumed": consumed,
            "lost": lost,
            "accounted": available + reserved + escrow + cargo + consumed + lost,
        }

"""Bilateral trade contracts and escrow settlement (C05 / T045)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from sim.dmb.ai.diplomacy import DiplomacyService
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.logistics.carts import CartService
from sim.dmb.logistics.routes import RoutePlanner
from sim.dmb.logistics.stock import CATAN_NS, StockLedger


@dataclass
class TradeService:
    state: WorldState
    ledger: StockLedger | None = None
    carts: CartService | None = None
    routes: RoutePlanner | None = None
    diplomacy: DiplomacyService | None = None

    def __post_init__(self) -> None:
        if self.ledger is None:
            self.ledger = StockLedger(self.state)
        if self.carts is None:
            self.carts = CartService(self.state, ledger=self.ledger)
        if self.routes is None:
            self.routes = RoutePlanner(self.state)
        if self.diplomacy is None:
            self.diplomacy = DiplomacyService(self.state)
        self.state.stocks.setdefault("_trades", {})

    def _trades(self) -> dict[str, Any]:
        return self.state.stocks.setdefault("_trades", {})

    def propose(
        self,
        proposer: str,
        counterparty: str,
        *,
        give: dict[str, int],
        receive: dict[str, int],
        proposer_store: str,
        counterparty_store: str,
        proposer_cart: str | None = None,
        counterparty_cart: str | None = None,
    ) -> dict[str, Any]:
        assert self.diplomacy is not None and self.ledger is not None
        if not self.diplomacy.trade_permitted(proposer, counterparty):
            raise TypeValidationError("trade not permitted by diplomacy")
        for good, qty in {**give, **receive}.items():
            if int(qty) <= 0:
                raise TypeValidationError("trade quantities must be positive")
        # Verify proposer can cover give from available (not yet reserved).
        for good, qty in give.items():
            if self.ledger.available(proposer_store, good) < int(qty):
                raise TypeValidationError(f"proposer lacks {good}")
        for good, qty in receive.items():
            if self.ledger.available(counterparty_store, good) < int(qty):
                raise TypeValidationError(f"counterparty lacks {good}")
        trade_id = self.state.ids.new("effect")  # contract id under effect namespace
        # Prefer readable trade:N — use command kind if available; effect is allowed.
        trade_id = f"trade:{trade_id.split(':')[-1]}"
        contract = {
            "id": trade_id,
            "parties": [proposer, counterparty],
            "legs": {
                "a": {
                    "from_faction": proposer,
                    "to_faction": counterparty,
                    "goods": {k: int(v) for k, v in give.items()},
                    "source_store": proposer_store,
                    "dest_store": counterparty_store,
                    "cart_id": proposer_cart,
                    "reservation_id": None,
                    "status": "proposed",
                    "escrowed": False,
                },
                "b": {
                    "from_faction": counterparty,
                    "to_faction": proposer,
                    "goods": {k: int(v) for k, v in receive.items()},
                    "source_store": counterparty_store,
                    "dest_store": proposer_store,
                    "cart_id": counterparty_cart,
                    "reservation_id": None,
                    "status": "proposed",
                    "escrowed": False,
                },
            },
            "status": "proposed",
            "accepted_turn": None,
            "deadline_turn": None,
            "settlement": None,
        }
        self._trades()[trade_id] = contract
        return deepcopy(contract)

    def accept(self, trade_id: str) -> dict[str, Any]:
        """Atomically reserve both legs; set fixed deadline."""
        assert self.ledger is not None and self.routes is not None
        contract = self._trades().get(trade_id)
        if contract is None:
            raise TypeValidationError(f"unknown trade {trade_id}")
        if contract["status"] != "proposed":
            return deepcopy(contract)
        # Dual-leg reserve in one pass — rollback on failure.
        reserved: list[str] = []
        try:
            for leg_key, leg in contract["legs"].items():
                reservation = self.ledger.reserve(
                    f"{trade_id}:{leg_key}",
                    dict(leg["goods"]),
                    store_id=str(leg["source_store"]),
                )
                leg["reservation_id"] = reservation["id"]
                leg["status"] = "reserved"
                reserved.append(reservation["id"])
            turn = int(self.state.clock.get("turn", 0))
            # Deadline: acceptance + 2×longest planned leg distance + 2×faction count.
            distances = []
            for leg in contract["legs"].values():
                # Approximate distance from route if cart path known; else 1.
                distances.append(1)
            faction_count = max(1, len(self.state.factions) or 2)
            longest = max(distances) if distances else 1
            contract["accepted_turn"] = turn
            contract["deadline_turn"] = turn + 2 * longest + 2 * faction_count
            contract["status"] = "accepted"
        except Exception:
            for rid in reserved:
                try:
                    self.ledger.release_reservation(rid)
                except TypeValidationError:
                    pass
            raise
        return deepcopy(contract)

    def dispatch_legs(self, trade_id: str) -> dict[str, Any]:
        """Create physical shipments from reservations onto assigned carts."""
        assert self.ledger is not None and self.carts is not None
        contract = self._trades().get(trade_id)
        if contract is None:
            raise TypeValidationError(f"unknown trade {trade_id}")
        if contract["status"] not in {"accepted", "in_transit"}:
            raise TypeValidationError("trade not dispatchable")
        dispatched = []
        for leg_key, leg in contract["legs"].items():
            if leg.get("status") not in {"reserved", "in_transit"}:
                continue
            cart_id = leg.get("cart_id")
            if not cart_id:
                created = self.carts.create(
                    owner_faction=str(leg["from_faction"]),
                    home_store=str(leg["source_store"]),
                    current_node=self._store_node(str(leg["source_store"])),
                )
                cart_id = created["id"]
                leg["cart_id"] = cart_id
            self.ledger.load(str(leg["reservation_id"]), str(cart_id))
            cart = self.state.carts[str(cart_id)]
            cart["destination_store"] = leg["dest_store"]
            cart["trade_id"] = trade_id
            cart["trade_leg"] = leg_key
            cart["status"] = "in_transit"
            leg["status"] = "in_transit"
            dispatched.append(cart_id)
        contract["status"] = "in_transit"
        return {"trade_id": trade_id, "carts": dispatched}

    def _store_node(self, store_id: str) -> str:
        for settlement in self.state.settlements.values():
            if settlement.get("store_id") == store_id or settlement.get("id") == store_id:
                return str(settlement.get("node_id") or "node:1")
        for building in self.state.buildings.values():
            if f"store:{building.get('id')}" == store_id or building.get("store_id") == store_id:
                return str(building.get("node_id") or "node:1")
        return "node:1"

    def deliver_leg_to_escrow(self, trade_id: str, leg_key: str) -> dict[str, Any]:
        """Credit destination as escrow (not spendable) when a leg arrives."""
        assert self.ledger is not None
        contract = self._trades()[trade_id]
        leg = contract["legs"][leg_key]
        cart_id = str(leg["cart_id"])
        result = self.ledger.credit_delivery(
            cart_id, str(leg["dest_store"]), delivery_id=f"{trade_id}:{leg_key}", as_escrow=True
        )
        leg["status"] = "escrowed"
        leg["escrowed"] = True
        # Escrow is not spendable — leave in escrow classification.
        if all(l.get("escrowed") for l in contract["legs"].values()):
            return self.settle(trade_id)
        return {"status": "leg_escrowed", "leg": leg_key, "delivery": result}

    def settle(self, trade_id: str) -> dict[str, Any]:
        """When both legs escrowed, release escrow → available once (ownership transfer)."""
        assert self.ledger is not None
        contract = self._trades()[trade_id]
        if contract.get("settlement"):
            return deepcopy(contract["settlement"])  # settle once
        if not all(l.get("escrowed") for l in contract["legs"].values()):
            raise TypeValidationError("both legs must be escrowed before settle")
        released = []
        for leg_key, leg in contract["legs"].items():
            dest = str(leg["dest_store"])
            for good, qty in dict(leg["goods"]).items():
                entry = self.ledger._bucket(dest, CATAN_NS, good)
                if entry["escrow"] < int(qty):
                    raise TypeValidationError("escrow underflow on settle")
                entry["escrow"] -= int(qty)
                entry["available"] += int(qty)
                released.append({"store": dest, "good": good, "qty": int(qty), "leg": leg_key})
            leg["status"] = "settled"
        settlement = {
            "trade_id": trade_id,
            "status": "settled",
            "released": released,
            "turn": int(self.state.clock.get("turn", 0)),
        }
        contract["status"] = "settled"
        contract["settlement"] = settlement
        return deepcopy(settlement)

    def cancel_or_default(self, trade_id: str, *, reason: str = "default") -> dict[str, Any]:
        """
        Destroyed/expired leg: release undelivered reservations; keep surviving escrow/cargo
        at real locations under beneficial owner. Never invent repayment.
        """
        assert self.ledger is not None
        contract = self._trades().get(trade_id)
        if contract is None:
            raise TypeValidationError(f"unknown trade {trade_id}")
        if contract["status"] == "settled":
            return {"status": "already_settled", "trade_id": trade_id}
        actions = []
        for leg_key, leg in contract["legs"].items():
            if leg.get("status") == "reserved" and leg.get("reservation_id"):
                try:
                    self.ledger.release_reservation(str(leg["reservation_id"]))
                    actions.append({"leg": leg_key, "action": "released_reservation"})
                    leg["status"] = "released"
                except TypeValidationError:
                    actions.append({"leg": leg_key, "action": "reservation_unavailable"})
            elif leg.get("status") == "in_transit":
                # Cargo stays aboard at real cart location — dispute claim, no conjured goods.
                cart = self.state.carts.get(str(leg.get("cart_id")))
                actions.append(
                    {
                        "leg": leg_key,
                        "action": "cargo_retained",
                        "node": (cart or {}).get("current_node"),
                        "lots": list((cart or {}).get("cargo_lots") or []),
                    }
                )
                leg["status"] = "disputed"
            elif leg.get("escrowed"):
                # Surviving escrow remains at dest under beneficial owner — not spendable gift.
                actions.append({"leg": leg_key, "action": "escrow_held_for_owner", "store": leg["dest_store"]})
                leg["status"] = "disputed"
            elif leg.get("status") == "destroyed":
                actions.append({"leg": leg_key, "action": "loss_recorded_no_repayment"})
        contract["status"] = "defaulted" if reason == "default" else "cancelled"
        contract["default"] = {"reason": reason, "actions": actions, "turn": int(self.state.clock.get("turn", 0))}
        return deepcopy(contract["default"])

    def destroy_leg(self, trade_id: str, leg_key: str) -> dict[str, Any]:
        """Record physical destruction of a leg's cargo without inventing repayment."""
        assert self.ledger is not None
        contract = self._trades()[trade_id]
        leg = contract["legs"][leg_key]
        cart_id = leg.get("cart_id")
        if cart_id and cart_id in self.state.carts:
            goods: dict[str, int] = {}
            for lot in list(self.state.carts[cart_id].get("cargo_lots") or []):
                if lot.get("status") != "aboard":
                    continue
                goods[str(lot["good_id"])] = goods.get(str(lot["good_id"]), 0) + int(lot["quantity"])
            if goods:
                self.ledger.record_loss(
                    goods,
                    cause_id=f"trade-loss:{trade_id}:{leg_key}",
                    cart_id=str(cart_id),
                    source=f"trade:{trade_id}:{leg_key}",
                )
        leg["status"] = "destroyed"
        return self.cancel_or_default(trade_id, reason="destroyed_leg")

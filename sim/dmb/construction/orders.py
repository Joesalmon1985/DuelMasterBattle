"""Delivered construction orders (C04 / T032)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sim.dmb.construction.buildings import BuildingService
from sim.dmb.construction.placement import PlacementRules
from sim.dmb.construction.scoring import ScoreService, VP_THRESHOLD
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.logistics.stock import StockLedger
from sim.dmb.world.board import HexBoard

COSTS: dict[str, dict[str, int]] = {
    "road": {"timber": 1, "brick": 1},
    "settlement": {"timber": 1, "brick": 1, "wool": 1, "grain": 1},
    "legacy_upgrade": {"timber": 1, "brick": 1, "wool": 1, "grain": 1},
    "city": {"grain": 2, "ore": 3},
    "processor": {"timber": 1, "brick": 1, "ore": 1},
    "repair": {"brick": 1, "ore": 1},
    "replacement_cart": {"timber": 1, "brick": 1, "ore": 1},
}


@dataclass
class ConstructionService:
    state: WorldState
    ledger: StockLedger | None = None
    buildings: BuildingService | None = None
    placement: PlacementRules | None = None
    scores: ScoreService | None = None
    board: HexBoard | None = None

    def __post_init__(self) -> None:
        if self.ledger is None:
            self.ledger = StockLedger(self.state)
        if self.buildings is None:
            self.buildings = BuildingService(self.state)
        if self.placement is None:
            self.placement = PlacementRules(self.state, self.board)
        if self.scores is None:
            self.scores = ScoreService(self.state)

    def quote(
        self,
        action: str,
        *,
        faction_id: str,
        store_id: str,
        target_node: str | None = None,
        target_edge: tuple[str, str] | None = None,
        target_building: str | None = None,
    ) -> dict[str, Any]:
        if action not in COSTS:
            raise TypeValidationError(f"unknown action {action}")
        required = dict(COSTS[action])
        missing = {
            good: qty - self.ledger.available(store_id, good)
            for good, qty in required.items()
            if self.ledger.available(store_id, good) < qty
        }
        legal = True
        reason = "ok"
        if action == "settlement" and target_node:
            legal, reason = self.placement.can_settle(faction_id, target_node)
        elif action == "city" and target_node:
            legal, reason = self.placement.can_city(faction_id, target_node)
        elif action == "road" and target_edge:
            legal, reason = self.placement.can_road(faction_id, target_edge[0], target_edge[1])
        elif action == "legacy_upgrade" and target_node:
            legal, reason = self.placement.can_upgrade_legacy(faction_id, target_node)
        elif action == "repair":
            target = self.state.buildings.get(str(target_building))
            if target is None:
                legal, reason = False, "unknown_target_building"
            elif target.get("status") == "destroyed":
                legal, reason = False, "destroyed_building_requires_replacement"
            elif target.get("faction_id") not in (None, faction_id):
                legal, reason = False, "not_owned"
            elif int(target.get("health", 0)) >= int(target.get("max_health", 0)):
                legal, reason = False, "building_not_damaged"
        elif action == "processor":
            settlement = next(
                (
                    item
                    for item in self.state.settlements.values()
                    if item.get("node_id") == target_node
                    and item.get("faction_id") == faction_id
                    and item.get("operational", True)
                ),
                None,
            )
            if settlement is None:
                legal, reason = False, "processor_requires_owned_operational_settlement"
        if missing:
            return {
                "action": action,
                "status": "blocked",
                "reason": "insufficient_local_goods",
                "missing": missing,
                "required": required,
                "store_id": store_id,
                # Remote unshipped cannot pay — only this store's available counts.
            }
        if not legal:
            return {
                "action": action,
                "status": "blocked",
                "reason": reason,
                "required": required,
                "store_id": store_id,
            }
        return {
            "action": action,
            "status": "ok",
            "required": required,
            "store_id": store_id,
            "reason": "ok",
        }

    def reserve_order(
        self,
        action: str,
        *,
        faction_id: str,
        store_id: str,
        target_node: str | None = None,
        target_edge: tuple[str, str] | None = None,
        target_building: str | None = None,
        staging_store: str | None = None,
    ) -> dict[str, Any]:
        q = self.quote(
            action,
            faction_id=faction_id,
            store_id=store_id,
            target_node=target_node,
            target_edge=target_edge,
            target_building=target_building,
        )
        order_id = self.state.ids.new("command")
        if q["status"] == "blocked":
            order = {
                "id": order_id,
                "faction_id": faction_id,
                "action": action,
                "target_node": target_node,
                "target_edge": list(target_edge) if target_edge else None,
                "target_building": target_building,
                "staging_store": staging_store or store_id,
                "required_goods": q["required"],
                "reservation_ids": [],
                "delivered": {},
                "status": "blocked",
                "reason": q.get("reason"),
                "created_turn": int(self.state.clock.get("turn", 0)),
                "completion_receipt": None,
            }
            self.state.orders[order_id] = order
            return dict(order)
        reservation = self.ledger.reserve(order_id, q["required"], store_id=store_id)
        order = {
            "id": order_id,
            "faction_id": faction_id,
            "action": action,
            "target_node": target_node,
            "target_edge": list(target_edge) if target_edge else None,
            "target_building": target_building,
            "staging_store": staging_store or store_id,
            "required_goods": q["required"],
            "reservation_ids": [reservation["id"]],
            "delivered": dict(q["required"]),
            "status": "ready",
            "reason": None,
            "created_turn": int(self.state.clock.get("turn", 0)),
            "completion_receipt": None,
            "store_id": store_id,
            "expected_ownership_version": int(self.state.world_version),
        }
        self.state.orders[order_id] = order
        return dict(order)

    def commit_delivered(self, order_id: str) -> dict[str, Any]:
        order = self.state.orders.get(order_id)
        if order is None:
            raise TypeValidationError(f"unknown order {order_id}")
        if order.get("status") == "committed":
            # Same completion cannot debit twice.
            return dict(order)
        if order.get("status") == "cancelled":
            raise TypeValidationError("cancelled order")
        if order.get("status") == "blocked":
            return dict(order)

        action = str(order["action"])
        faction_id = str(order["faction_id"])
        store_id = str(order.get("store_id") or order.get("staging_store"))
        target_node = order.get("target_node")
        target_edge = tuple(order["target_edge"]) if order.get("target_edge") else None

        # Revalidate legality
        q = self.quote(
            action,
            faction_id=faction_id,
            store_id=store_id,
            target_node=target_node,
            target_edge=target_edge,
            target_building=order.get("target_building"),
        )
        # Quote checks available — goods are reserved, so temporarily treat reserved as present
        # by using legality-only recheck:
        legal = True
        reason = "ok"
        if action == "settlement" and target_node:
            legal, reason = self.placement.can_settle(faction_id, target_node)
        elif action == "city" and target_node:
            legal, reason = self.placement.can_city(faction_id, target_node)
        elif action == "road" and target_edge:
            legal, reason = self.placement.can_road(faction_id, target_edge[0], target_edge[1])
        elif action == "legacy_upgrade" and target_node:
            legal, reason = self.placement.can_upgrade_legacy(faction_id, target_node)
        elif action == "repair":
            target = self.state.buildings.get(str(order.get("target_building")))
            if target is None:
                legal, reason = False, "unknown_target_building"
            elif target.get("status") == "destroyed":
                legal, reason = False, "destroyed_building_requires_replacement"
            elif target.get("faction_id") not in (None, faction_id):
                legal, reason = False, "not_owned"
            elif int(target.get("health", 0)) >= int(target.get("max_health", 0)):
                legal, reason = False, "building_not_damaged"
        elif action == "processor":
            legal = any(
                item.get("node_id") == target_node
                and item.get("faction_id") == faction_id
                and item.get("operational", True)
                for item in self.state.settlements.values()
            )
            reason = "ok" if legal else "processor_requires_owned_operational_settlement"

        if not legal:
            # Illegal target: reclaim reserved goods to accessible store.
            for rid in order.get("reservation_ids") or []:
                try:
                    self.ledger.release_reservation(rid)
                except TypeValidationError:
                    pass
            order["status"] = "blocked"
            order["reason"] = reason
            order["reclaimed"] = True
            return dict(order)

        # Consume reserved goods once
        for rid in order.get("reservation_ids") or []:
            existing = self.state.stocks.get("_reservations", {}).get(rid)
            if existing and existing.get("status") == "reserved":
                self.ledger.consume(
                    store_id,
                    dict(existing["goods"]),
                    from_classification="reserved",
                    cause_id=order_id,
                )
                existing["status"] = "consumed"

        result_payload: dict[str, Any] = {}
        if action == "settlement" and target_node:
            settlement_id = self.state.ids.new("settlement")
            centre = self.buildings.create(
                "building.centre",
                node_id=target_node,
                faction_id=faction_id,
                settlement_id=settlement_id,
            )
            wh = self.buildings.create(
                "building.warehouse",
                node_id=target_node,
                faction_id=faction_id,
                settlement_id=settlement_id,
            )
            for i in range(3):
                self.buildings.create(
                    "building.primary",
                    node_id=target_node,
                    faction_id=faction_id,
                    slot_index=i,
                    settlement_id=settlement_id,
                )
            self.buildings.create(
                "building.processor",
                node_id=target_node,
                faction_id=faction_id,
                settlement_id=settlement_id,
            )
            for i in range(3):
                self.buildings.create(
                    "building.factory",
                    node_id=target_node,
                    faction_id=faction_id,
                    slot_index=i,
                    settlement_id=settlement_id,
                )
            self.state.settlements[settlement_id] = {
                "id": settlement_id,
                "node_id": target_node,
                "faction_id": faction_id,
                "tier": "settlement",
                "operational": True,
                "warehouse_id": wh["id"],
                "centre_id": centre["id"],
            }
            result_payload["settlement_id"] = settlement_id
        elif action == "city" and target_node:
            settlement = None
            for s in self.state.settlements.values():
                if s.get("node_id") == target_node and s.get("faction_id") == faction_id:
                    settlement = s
                    break
            if settlement and settlement.get("centre_id"):
                self.buildings.upgrade_in_place(str(settlement["centre_id"]))
            elif settlement:
                settlement["tier"] = "city"
                settlement["primary_flow_multiplier"] = 2.0
                settlement["primary_slot_multiplier"] = 1.0
            result_payload["settlement_id"] = settlement.get("id") if settlement else None
        elif action == "road" and target_edge:
            road_id = self.state.ids.new("command")
            self.state.roads[road_id] = {
                "id": road_id,
                "a": target_edge[0],
                "b": target_edge[1],
                "faction_id": faction_id,
                "status": "built",
            }
            result_payload["road_id"] = road_id
        elif action == "repair" and order.get("target_building"):
            repaired = self.buildings.repair(str(order["target_building"]))
            result_payload["building_id"] = repaired["id"]
            result_payload["health"] = repaired["health"]
        elif action == "processor" and target_node:
            settlement = next(
                item
                for item in self.state.settlements.values()
                if item.get("node_id") == target_node and item.get("faction_id") == faction_id
            )
            processor = self.buildings.create(
                "building.processor",
                node_id=target_node,
                faction_id=faction_id,
                settlement_id=settlement.get("id"),
            )
            result_payload["building_id"] = processor["id"]
        elif action == "replacement_cart":
            cart_id = self.state.ids.new("cart")
            self.state.carts[cart_id] = {
                "id": cart_id,
                "owner_faction": faction_id,
                "home_store": store_id,
                "current_node": order.get("target_node"),
                "capacity": 4,
                "cargo_lots": [],
                "status": "idle",
            }
            result_payload["cart_id"] = cart_id

        order["status"] = "committed"
        order["completion_receipt"] = {
            "order_id": order_id,
            "action": action,
            "result": result_payload,
            "turn": int(self.state.clock.get("turn", 0)),
        }
        # 10 VP interrupt signal
        winners = self.scores.check_threshold(VP_THRESHOLD)
        interrupt = None
        if winners:
            interrupt = {"kind": "vp_threshold", "factions": winners, "threshold": VP_THRESHOLD}
            self.state.clock["interrupt_reason"] = "vp_threshold"
            self.state.clock["interrupt_factions"] = winners
        order["interrupt"] = interrupt
        return dict(order)

    def cancel(self, order_id: str) -> dict[str, Any]:
        order = self.state.orders.get(order_id)
        if order is None:
            raise TypeValidationError(f"unknown order {order_id}")
        if order.get("status") == "committed":
            raise TypeValidationError("cannot cancel committed")
        for rid in order.get("reservation_ids") or []:
            try:
                self.ledger.release_reservation(rid)
            except TypeValidationError:
                pass
        order["status"] = "cancelled"
        return dict(order)

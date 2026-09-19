"""Persistent inventory and unique ground objects (C10 / T087)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError

INVENTORY_SCHEMA_VERSION = 1
PLAYER_BAG = "container:player"


@dataclass
class InventoryService:
    state: WorldState

    def _ensure_item(self, item_id: str) -> dict[str, Any]:
        item = self.state.items.get(item_id)
        if item is None:
            raise TypeValidationError(f"unknown item {item_id}")
        item.setdefault("schema_version", INVENTORY_SCHEMA_VERSION)
        item.setdefault("quantity", 1)
        item.setdefault("stackable", False)
        item.setdefault("unique", not bool(item.get("stackable")))
        item.setdefault("quest_bound", False)
        return item

    def spawn_ground(
        self,
        *,
        definition_id: str,
        area_id: str,
        position: list[float],
        quantity: int = 1,
        stackable: bool = False,
        quest_bound: bool = False,
        label: str | None = None,
        item_id: str | None = None,
    ) -> dict[str, Any]:
        iid = item_id or self.state.ids.new("item")
        if iid in self.state.items:
            raise TypeValidationError(f"item already exists {iid}")
        record = {
            "id": iid,
            "definition_id": definition_id,
            "label": label or definition_id,
            "quantity": int(quantity),
            "stackable": bool(stackable),
            "unique": not bool(stackable),
            "quest_bound": bool(quest_bound),
            "container_id": None,
            "holder_id": None,
            "ground": {"area_id": area_id, "position": list(position)},
            "alive": True,
            "schema_version": INVENTORY_SCHEMA_VERSION,
        }
        self.state.items[iid] = record
        return dict(record)

    def pickup(
        self,
        item_id: str,
        *,
        holder_id: str = "player",
        container_id: str = PLAYER_BAG,
        in_range: bool = True,
    ) -> dict[str, Any]:
        if not in_range:
            raise TypeValidationError("out of range")
        item = self._ensure_item(item_id)
        if item.get("holder_id") and item.get("holder_id") != holder_id:
            raise TypeValidationError("wrong owner")
        if item.get("container_id") and item.get("ground") is None:
            raise TypeValidationError("item already contained")
        item["container_id"] = container_id
        item["holder_id"] = holder_id
        item["ground"] = None
        return dict(item)

    def drop(
        self,
        item_id: str,
        *,
        area_id: str,
        position: list[float],
        holder_id: str = "player",
    ) -> dict[str, Any]:
        item = self._ensure_item(item_id)
        if item.get("holder_id") not in {None, holder_id}:
            raise TypeValidationError("wrong owner")
        item["container_id"] = None
        item["holder_id"] = None
        item["equipped_slot"] = None
        item["ground"] = {"area_id": area_id, "position": list(position)}
        return dict(item)

    def give(
        self,
        item_id: str,
        *,
        to_holder: str,
        from_holder: str = "player",
        quantity: int | None = None,
    ) -> dict[str, Any]:
        item = self._ensure_item(item_id)
        if item.get("holder_id") != from_holder:
            raise TypeValidationError("wrong owner")
        qty = int(quantity) if quantity is not None else int(item.get("quantity") or 1)
        have = int(item.get("quantity") or 1)
        if qty <= 0 or qty > have:
            raise TypeValidationError("invalid transfer quantity")
        if item.get("stackable") and qty < have:
            # Split stack without duplicating total quantity.
            new_id = self.state.ids.new("item")
            child = deepcopy(item)
            child["id"] = new_id
            child["quantity"] = qty
            child["holder_id"] = to_holder
            child["container_id"] = f"container:{to_holder}"
            child["ground"] = None
            item["quantity"] = have - qty
            self.state.items[new_id] = child
            return {"status": "split", "kept": dict(item), "given": dict(child)}
        item["holder_id"] = to_holder
        item["container_id"] = f"container:{to_holder}"
        item["ground"] = None
        return {"status": "moved", "item": dict(item)}

    def equip(self, item_id: str, *, slot: str, holder_id: str = "player") -> dict[str, Any]:
        if slot not in {"focus", "artifact"}:
            raise TypeValidationError("only focus/artifact slots")
        item = self._ensure_item(item_id)
        if item.get("holder_id") != holder_id:
            raise TypeValidationError("wrong owner")
        # One item per slot.
        for other in self.state.items.values():
            if other.get("holder_id") == holder_id and other.get("equipped_slot") == slot:
                other["equipped_slot"] = None
        item["equipped_slot"] = slot
        return dict(item)

    def use(self, item_id: str, *, holder_id: str = "player") -> dict[str, Any]:
        item = self._ensure_item(item_id)
        if item.get("holder_id") != holder_id:
            raise TypeValidationError("wrong owner")
        return {"status": "used", "item_id": item_id, "definition_id": item.get("definition_id")}

    def combine(
        self,
        inputs: list[tuple[str, int]],
        *,
        result_definition_id: str,
        holder_id: str = "player",
    ) -> dict[str, Any]:
        """Explicit combine definition only — consumes listed quantities once."""
        for item_id, need in inputs:
            item = self._ensure_item(item_id)
            if item.get("holder_id") != holder_id:
                raise TypeValidationError("wrong owner")
            if int(item.get("quantity") or 0) < int(need):
                raise TypeValidationError("insufficient quantity")
        for item_id, need in inputs:
            item = self.state.items[item_id]
            left = int(item["quantity"]) - int(need)
            if left <= 0:
                item["alive"] = False
                item["quantity"] = 0
                item["holder_id"] = None
                item["container_id"] = None
            else:
                item["quantity"] = left
        created = self.spawn_ground(
            definition_id=result_definition_id,
            area_id="bag",
            position=[0.0, 0.0],
            quantity=1,
            stackable=False,
        )
        # Move result into holder bag (not ground).
        return self.pickup(created["id"], holder_id=holder_id)

    def player_items(self, holder_id: str = "player") -> list[dict[str, Any]]:
        return [
            dict(item)
            for item in self.state.items.values()
            if item.get("holder_id") == holder_id and item.get("alive", True)
        ]

    def ground_items(self, area_id: str) -> list[dict[str, Any]]:
        out = []
        for item in self.state.items.values():
            ground = item.get("ground") or {}
            if ground.get("area_id") == area_id and item.get("alive", True):
                out.append(dict(item))
        return out

    def as_construction_payment(self, item_id: str) -> dict[str, Any]:
        """Personal inventory never silently pays faction construction."""
        item = self._ensure_item(item_id)
        if item.get("holder_id") == "player" or item.get("container_id") == PLAYER_BAG:
            raise TypeValidationError("personal inventory cannot pay faction construction")
        return {"ok": False, "reason": "not_construction_stock"}

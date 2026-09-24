"""Persistent inventory and unique ground objects (C10 / T087 / T088)."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sim.dmb.core.effects import apply_effects
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError

INVENTORY_SCHEMA_VERSION = 1
PLAYER_BAG = "container:player"

_CONTENT_ROOT = (
    Path(__file__).resolve().parents[3]
    / "godot_project"
    / "content"
    / "source"
    / "items"
)


def load_item_catalog(root: Path | None = None) -> dict[str, Any]:
    path = (root or _CONTENT_ROOT) / "catalog.json"
    if not path.is_file():
        return {"items": [], "combinations": [], "recovery": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _index_catalog(catalog: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    items = {str(i["id"]): dict(i) for i in catalog.get("items") or [] if i.get("id")}
    combos = {str(c["id"]): dict(c) for c in catalog.get("combinations") or [] if c.get("id")}
    return items, combos


@dataclass
class InventoryService:
    state: WorldState
    catalog: dict[str, Any] | None = None

    def _catalog(self) -> dict[str, Any]:
        if self.catalog is not None:
            return self.catalog
        return load_item_catalog()

    def _defs(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return _index_catalog(self._catalog())

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
        item_defs, _ = self._defs()
        authored = item_defs.get(definition_id) or {}
        if authored:
            stackable = bool(authored.get("stackable", stackable))
            quest_bound = bool(authored.get("quest_bound", quest_bound))
            label = label or authored.get("label")
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

    def _find_use(self, definition_id: str, use_id: str | None) -> dict[str, Any]:
        item_defs, _ = self._defs()
        authored = item_defs.get(definition_id)
        if authored is None:
            raise TypeValidationError(f"unknown item definition {definition_id}")
        uses = list(authored.get("uses") or [])
        if not uses:
            raise TypeValidationError(f"no allowlisted uses for {definition_id}")
        if use_id is None:
            if len(uses) != 1:
                raise TypeValidationError("use_id required when multiple uses exist")
            return dict(uses[0])
        for use in uses:
            if str(use.get("id")) == use_id:
                return dict(use)
        raise TypeValidationError(f"use {use_id!r} not allowlisted for {definition_id}")

    def use(
        self,
        item_id: str,
        *,
        holder_id: str = "player",
        use_id: str | None = None,
        target: str | None = None,
        command_id: str | None = None,
    ) -> dict[str, Any]:
        """Apply an allowlisted use. Invalid uses reject without consuming the item."""
        item = self._ensure_item(item_id)
        if item.get("holder_id") != holder_id:
            raise TypeValidationError("wrong owner")
        snapshot = deepcopy(item)
        definition_id = str(item.get("definition_id") or "")
        try:
            use_def = self._find_use(definition_id, use_id)
        except TypeValidationError:
            # Leave inventory untouched on invalid use.
            raise
        required_target = use_def.get("requires_target")
        if required_target and target != required_target:
            raise TypeValidationError("invalid use target")

        effects = list(use_def.get("effects") or [])
        # Stamp unique effect ids per command so retries stay idempotent without
        # blocking a legitimate second use of a different instance.
        stamped: list[dict[str, Any]] = []
        base = command_id or f"use:{item_id}:{use_def.get('id')}:{self.state.world_version}"
        for idx, effect in enumerate(effects):
            stamped_effect = dict(effect)
            stamped_effect["effect_id"] = f"{base}:{stamped_effect.get('effect_id') or idx}"
            stamped.append(stamped_effect)

        applied = apply_effects(self.state, stamped) if stamped else []

        if use_def.get("consumes"):
            qty = int(item.get("quantity") or 1)
            if qty <= 1:
                item["alive"] = False
                item["quantity"] = 0
                item["holder_id"] = None
                item["container_id"] = None
            else:
                item["quantity"] = qty - 1

        return {
            "status": "used",
            "item_id": item_id,
            "definition_id": definition_id,
            "use_id": use_def.get("id"),
            "consumed": bool(use_def.get("consumes")),
            "effects": applied,
            "prior": snapshot,
            "item": dict(item) if item.get("alive", True) else None,
        }

    def combine(
        self,
        inputs: list[tuple[str, int]] | None = None,
        *,
        combination_id: str | None = None,
        result_definition_id: str | None = None,
        holder_id: str = "player",
        command_id: str | None = None,
    ) -> dict[str, Any]:
        """Explicit allowlisted combine — consumes listed quantities once."""
        _, combos = self._defs()
        combo: dict[str, Any] | None = None
        if combination_id is not None:
            combo = combos.get(combination_id)
            if combo is None:
                raise TypeValidationError(f"combination {combination_id!r} not allowlisted")
        elif result_definition_id is not None:
            matches = [
                c
                for c in combos.values()
                if str(c.get("result_definition_id")) == result_definition_id
            ]
            if len(matches) != 1:
                raise TypeValidationError(
                    f"combination for result {result_definition_id!r} not uniquely allowlisted"
                )
            combo = matches[0]
        else:
            raise TypeValidationError("combination_id or result_definition_id required")

        authored_inputs = list(combo.get("inputs") or [])
        if not authored_inputs:
            raise TypeValidationError("combination has no inputs")

        # Resolve held stacks matching each authored definition/quantity.
        resolved: list[tuple[str, int]] = []
        if inputs is not None:
            # Caller supplies exact instance ids; validate against allowlist defs.
            if len(inputs) != len(authored_inputs):
                raise TypeValidationError("combine inputs must match allowlist exactly")
            for (item_id, need), authored in zip(inputs, authored_inputs, strict=True):
                item = self._ensure_item(item_id)
                if item.get("holder_id") != holder_id:
                    raise TypeValidationError("wrong owner")
                if str(item.get("definition_id")) != str(authored["definition_id"]):
                    raise TypeValidationError("input definition mismatch")
                if int(need) != int(authored["quantity"]):
                    raise TypeValidationError("input quantity mismatch")
                if int(item.get("quantity") or 0) < int(need):
                    raise TypeValidationError("insufficient quantity")
                resolved.append((item_id, int(need)))
        else:
            # Auto-pick held stacks by definition.
            held = [
                i
                for i in self.state.items.values()
                if i.get("holder_id") == holder_id and i.get("alive", True)
            ]
            used_ids: set[str] = set()
            for authored in authored_inputs:
                need = int(authored["quantity"])
                def_id = str(authored["definition_id"])
                match = next(
                    (
                        i
                        for i in held
                        if i["id"] not in used_ids
                        and str(i.get("definition_id")) == def_id
                        and int(i.get("quantity") or 0) >= need
                    ),
                    None,
                )
                if match is None:
                    raise TypeValidationError("insufficient quantity")
                used_ids.add(str(match["id"]))
                resolved.append((str(match["id"]), need))

        # Snapshot for rollback if effects fail after consume (effects validated first).
        effects = list(combo.get("effects") or [])
        base = command_id or f"combine:{combo.get('id')}:{self.state.world_version}"
        stamped = []
        for idx, effect in enumerate(effects):
            stamped_effect = dict(effect)
            stamped_effect["effect_id"] = f"{base}:{stamped_effect.get('effect_id') or idx}"
            stamped.append(stamped_effect)
        # Validate effects before consuming (apply_effects also validates, but
        # we consume first only after a dry validate via apply that is empty-safe).
        if stamped:
            from sim.dmb.core.effects import validate_effects

            validate_effects(stamped)

        for item_id, need in resolved:
            item = self.state.items[item_id]
            left = int(item["quantity"]) - int(need)
            if left <= 0:
                item["alive"] = False
                item["quantity"] = 0
                item["holder_id"] = None
                item["container_id"] = None
            else:
                item["quantity"] = left

        result_def = str(combo.get("result_definition_id") or result_definition_id or "")
        created = self.spawn_ground(
            definition_id=result_def,
            area_id="bag",
            position=[0.0, 0.0],
            quantity=1,
            stackable=False,
        )
        result_item = self.pickup(created["id"], holder_id=holder_id)
        applied = apply_effects(self.state, stamped) if stamped else []
        return {
            "status": "combined",
            "combination_id": combo.get("id"),
            "consumed": [{"item_id": iid, "quantity": q} for iid, q in resolved],
            "result": result_item,
            "effects": applied,
        }

    def player_items(self, holder_id: str = "player") -> list[dict[str, Any]]:
        return [
            dict(item)
            for item in self.state.items.values()
            if item.get("holder_id") == holder_id and item.get("alive", True)
        ]

    def player_view(self, holder_id: str = "player") -> dict[str, Any]:
        """Lean inventory slice for UI/bridge."""
        items = self.player_items(holder_id=holder_id)
        area = str((self.state.player or {}).get("area_id") or (self.state.player or {}).get("node_id") or "")
        return {
            "schema_version": INVENTORY_SCHEMA_VERSION,
            "holder_id": holder_id,
            "items": items,
            "ground": self.ground_items(area) if area else [],
            "can_manage_remotely": False,
        }

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

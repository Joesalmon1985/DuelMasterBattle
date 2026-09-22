"""Mandatory quest/puzzle item recovery routes (C10 / T088).

Relocate stranded required items after layout changes, or open an explicit
alternate recovery interaction when a home location is destroyed. Every
recovery writes one durable receipt — never silently delete required items.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError

_CONTENT_ROOT = (
    Path(__file__).resolve().parents[3]
    / "godot_project"
    / "content"
    / "source"
    / "items"
)

RECOVERY_RECEIPT_BUCKET = "item_recovery"


def load_item_recovery_catalog(root: Path | None = None) -> dict[str, Any]:
    path = (root or _CONTENT_ROOT) / "catalog.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload.get("recovery") or {})


def _distance(a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]) -> float:
    ax, ay = float(a[0]), float(a[1]) if len(a) > 1 else 0.0
    bx, by = float(b[0]), float(b[1]) if len(b) > 1 else 0.0
    return abs(ax - bx) + abs(ay - by)


@dataclass
class ItemRecoveryService:
    state: WorldState
    catalog: dict[str, Any] | None = None

    def _catalog(self) -> dict[str, Any]:
        if self.catalog is not None:
            return self.catalog
        return load_item_recovery_catalog()

    def _receipts(self) -> dict[str, Any]:
        bucket = self.state.definitions.setdefault(RECOVERY_RECEIPT_BUCKET, {})
        return bucket

    def required_definition_ids(self) -> set[str]:
        return {
            def_id
            for def_id, rule in self._catalog().items()
            if rule.get("required")
        }

    def find_instances(self, definition_id: str) -> list[dict[str, Any]]:
        return [
            dict(item)
            for item in self.state.items.values()
            if item.get("definition_id") == definition_id and item.get("alive", True)
        ]

    def relocate_stranded(
        self,
        item_id: str,
        *,
        accessible_area_ids: set[str] | frozenset[str] | list[str],
        command_id: str | None = None,
    ) -> dict[str, Any]:
        """Move a stranded ground item to the nearest accessible recovery point.

        Records exactly one relocation receipt. Items held by the player are
        already accessible and are left untouched.
        """
        item = self.state.items.get(item_id)
        if item is None or not item.get("alive", True):
            raise TypeValidationError(f"unknown item {item_id}")
        definition_id = str(item.get("definition_id") or "")
        rule = self._catalog().get(definition_id)
        if not rule or not rule.get("required"):
            raise TypeValidationError(f"no required recovery rule for {definition_id}")

        receipt_id = command_id or f"recovery.relocate:{item_id}:{self.state.world_version}"
        existing = self._receipts().get(receipt_id)
        if existing is not None:
            return {"status": "idempotent", "receipt": dict(existing)}

        # Already held — not stranded.
        if item.get("holder_id") and item.get("ground") is None:
            receipt = {
                "receipt_id": receipt_id,
                "kind": "not_stranded",
                "item_id": item_id,
                "definition_id": definition_id,
            }
            self._receipts()[receipt_id] = receipt
            return {"status": "not_stranded", "receipt": receipt}

        ground = item.get("ground") or {}
        current_area = str(ground.get("area_id") or "")
        accessible = {str(a) for a in accessible_area_ids}
        if current_area in accessible:
            receipt = {
                "receipt_id": receipt_id,
                "kind": "already_accessible",
                "item_id": item_id,
                "definition_id": definition_id,
                "area_id": current_area,
            }
            self._receipts()[receipt_id] = receipt
            return {"status": "already_accessible", "receipt": receipt}

        points = list(rule.get("accessible_points") or [])
        if not points:
            raise TypeValidationError(f"no accessible recovery points for {definition_id}")

        candidates = [p for p in points if str(p.get("area_id")) in accessible]
        if not candidates:
            # Fall back to authored home / first point even if not listed accessible —
            # still records relocation rather than deleting.
            candidates = points

        current_pos = list(ground.get("position") or rule.get("home_position") or [0.0, 0.0])
        best = min(
            candidates,
            key=lambda p: _distance(current_pos, list(p.get("position") or [0.0, 0.0])),
        )
        new_area = str(best["area_id"])
        new_pos = list(best.get("position") or [0.0, 0.0])
        prior = {"area_id": current_area, "position": list(current_pos)}
        item["ground"] = {"area_id": new_area, "position": new_pos}
        item["container_id"] = None
        item["holder_id"] = None
        receipt = {
            "receipt_id": receipt_id,
            "kind": "relocation",
            "item_id": item_id,
            "definition_id": definition_id,
            "from": prior,
            "to": {"area_id": new_area, "position": new_pos},
        }
        self._receipts()[receipt_id] = receipt
        return {"status": "relocated", "item": dict(item), "receipt": receipt}

    def open_destroyed_location_route(
        self,
        definition_id: str,
        *,
        destroyed_area_id: str,
        command_id: str | None = None,
    ) -> dict[str, Any]:
        """When a home location is destroyed, open the alternate recovery interaction."""
        rule = self._catalog().get(definition_id)
        if not rule or not rule.get("required"):
            raise TypeValidationError(f"no required recovery rule for {definition_id}")
        route = dict(rule.get("destroyed_location_route") or {})
        if not route:
            raise TypeValidationError(f"no destroyed-location route for {definition_id}")

        receipt_id = command_id or (
            f"recovery.destroyed:{definition_id}:{destroyed_area_id}:{self.state.world_version}"
        )
        existing = self._receipts().get(receipt_id)
        if existing is not None:
            return {"status": "idempotent", "receipt": dict(existing)}

        # Rehome any ground instances that lived in the destroyed area.
        moved: list[str] = []
        for item in self.state.items.values():
            if item.get("definition_id") != definition_id or not item.get("alive", True):
                continue
            ground = item.get("ground") or {}
            if str(ground.get("area_id") or "") != destroyed_area_id:
                continue
            item["ground"] = {
                "area_id": str(route["area_id"]),
                "position": list(route.get("position") or [0.0, 0.0]),
            }
            item["container_id"] = None
            item["holder_id"] = None
            moved.append(str(item["id"]))

        # If no instance existed in the destroyed area, spawn recovery at the route
        # only when zero living instances remain (soft-lock prevention).
        living = self.find_instances(definition_id)
        spawned: str | None = None
        if not living and not moved:
            from sim.dmb.player.inventory import InventoryService

            created = InventoryService(self.state).spawn_ground(
                definition_id=definition_id,
                area_id=str(route["area_id"]),
                position=list(route.get("position") or [0.0, 0.0]),
                quest_bound=True,
            )
            spawned = str(created["id"])
            living = self.find_instances(definition_id)

        interaction = {
            "interaction_id": str(route.get("interaction_id") or f"recovery.{definition_id}"),
            "area_id": str(route["area_id"]),
            "position": list(route.get("position") or [0.0, 0.0]),
            "witness_id": route.get("witness_id"),
            "definition_id": definition_id,
            "active": True,
        }
        interactions = self.state.definitions.setdefault("recovery_interactions", {})
        interactions[interaction["interaction_id"]] = interaction

        receipt = {
            "receipt_id": receipt_id,
            "kind": "destroyed_location_route",
            "definition_id": definition_id,
            "destroyed_area_id": destroyed_area_id,
            "interaction": interaction,
            "moved_item_ids": moved,
            "spawned_item_id": spawned,
            "recoverable_item_ids": [str(i["id"]) for i in living],
        }
        self._receipts()[receipt_id] = receipt
        return {"status": "route_opened", "receipt": receipt, "interaction": interaction}

    def is_recoverable(self, definition_id: str) -> bool:
        """True when a required item still has a living instance or active alternate route."""
        if self.find_instances(definition_id):
            return True
        for interaction in (self.state.definitions.get("recovery_interactions") or {}).values():
            if interaction.get("definition_id") == definition_id and interaction.get("active"):
                return True
        return False

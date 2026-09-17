"""Building identity, health, slots and capacity (C04 / T027)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError

CONTENT_ROOT = Path(__file__).resolve().parents[3] / "godot_project" / "content" / "source"
BUILDINGS_DIR = CONTENT_ROOT / "buildings"
UNITS_DIR = CONTENT_ROOT / "units"

BASELINE_MAX_HEALTH = {
    "centre": 500,
    "warehouse": 300,
    "primary": 200,
    "processor": 200,
    "factory": 200,
}


def load_building_definitions(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    root = directory or BUILDINGS_DIR
    by_id: dict[str, dict[str, Any]] = {}
    if not root.exists():
        return by_id
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload if isinstance(payload, list) else [payload]
        for raw in items:
            def_id = str(raw["id"])
            if def_id in by_id:
                raise TypeValidationError(f"duplicate definition id: {def_id}")
            by_id[def_id] = dict(raw)
    return by_id


def load_unit_definitions(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    root = directory or UNITS_DIR
    by_id: dict[str, dict[str, Any]] = {}
    if not root.exists():
        return by_id
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload if isinstance(payload, list) else [payload]
        for raw in items:
            def_id = str(raw["id"])
            if def_id in by_id:
                raise TypeValidationError(f"duplicate definition id: {def_id}")
            by_id[def_id] = dict(raw)
    return by_id


def usable_capacity(health: int, max_health: int, capacity_base: float = 1.0) -> float:
    if max_health <= 0 or health <= 0:
        return 0.0
    return float(capacity_base) * (float(health) / float(max_health))


@dataclass
class BuildingService:
    state: WorldState
    definitions: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.definitions:
            self.definitions = {
                k: v
                for k, v in load_building_definitions().items()
                if v.get("kind") == "building"
            }

    def _require_def(self, definition_id: str) -> dict[str, Any]:
        defn = self.definitions.get(definition_id)
        if defn is None:
            raise TypeValidationError(f"missing building definition: {definition_id}")
        return defn

    def _slot_key(self, node_id: str, slot_kind: str, slot_index: int) -> str:
        return f"{node_id}:{slot_kind}:{slot_index}"

    def _occupied_slots(self, node_id: str, slot_kind: str) -> set[int]:
        occupied: set[int] = set()
        for record in self.state.buildings.values():
            if record.get("status") == "destroyed":
                continue
            if record.get("node_id") != node_id:
                continue
            if record.get("slot_kind") != slot_kind:
                continue
            occupied.add(int(record.get("slot_index", 0)))
        return occupied

    def primary_slot_count(self, node_id: str) -> int:
        """Cities double primary flow, never primary slot count."""
        return len(self._occupied_slots(node_id, "primary"))

    def create(
        self,
        definition_id: str,
        *,
        node_id: str,
        faction_id: str,
        slot_index: int = 0,
        settlement_id: str | None = None,
        era_multiplier: float = 1.0,
    ) -> dict[str, Any]:
        defn = self._require_def(definition_id)
        fields = dict(defn.get("fields", {}))
        slot_kind = str(fields.get("slot_kind", "industry"))
        occupied = self._occupied_slots(node_id, slot_kind)
        if slot_index in occupied:
            raise TypeValidationError(
                f"duplicate slot {slot_kind}:{slot_index} at {node_id}"
            )
        # City upgrades must not invent extra primary slots.
        if slot_kind == "primary":
            settlement = self.state.settlements.get(settlement_id or "")
            if settlement and settlement.get("tier") == "city":
                # Still one slot index occupancy; count stays slot-based.
                pass
        base_health = int(fields.get("max_health", BASELINE_MAX_HEALTH.get(slot_kind, 200)))
        max_health = max(1, int(round(base_health * float(era_multiplier))))
        building_id = self.state.ids.new("building")
        record = {
            "id": building_id,
            "definition_id": definition_id,
            "node_id": node_id,
            "faction_id": faction_id,
            "settlement_id": settlement_id,
            "slot_kind": slot_kind,
            "slot_index": int(slot_index),
            "slot_key": self._slot_key(node_id, slot_kind, slot_index),
            "job_id": fields.get("job_ref"),
            "footprint": int(fields.get("footprint", 1)),
            "max_health": max_health,
            "health": max_health,
            "capacity_base": float(fields.get("capacity_base", 1.0)),
            "status": "operational",
            "active": True,
            "owned": True,
        }
        record["usable_capacity"] = usable_capacity(
            record["health"], record["max_health"], record["capacity_base"]
        )
        self.state.buildings[building_id] = record
        return dict(record)

    def damage(self, building_id: str, amount: int) -> dict[str, Any]:
        record = self.state.buildings.get(building_id)
        if record is None:
            raise TypeValidationError(f"unknown building {building_id}")
        if record.get("status") == "destroyed":
            return dict(record)
        health = max(0, int(record["health"]) - max(0, int(amount)))
        record["health"] = health
        record["usable_capacity"] = usable_capacity(
            health, int(record["max_health"]), float(record.get("capacity_base", 1.0))
        )
        if health <= 0:
            record["status"] = "destroyed"
            record["active"] = False
            record["usable_capacity"] = 0.0
        return dict(record)

    def repair(self, building_id: str) -> dict[str, Any]:
        record = self.state.buildings.get(building_id)
        if record is None:
            raise TypeValidationError(f"unknown building {building_id}")
        if record.get("status") == "destroyed":
            raise TypeValidationError("cannot repair destroyed building without rebuild")
        record["health"] = int(record["max_health"])
        record["status"] = "operational"
        record["active"] = True
        record["usable_capacity"] = usable_capacity(
            record["health"], record["max_health"], float(record.get("capacity_base", 1.0))
        )
        return dict(record)

    def upgrade_in_place(self, building_id: str, upgrade_definition_id: str | None = None) -> dict[str, Any]:
        record = self.state.buildings.get(building_id)
        if record is None:
            raise TypeValidationError(f"unknown building {building_id}")
        if record.get("status") == "destroyed":
            raise TypeValidationError("cannot upgrade destroyed building")
        current = self._require_def(str(record["definition_id"]))
        mapped = upgrade_definition_id or current.get("fields", {}).get("upgrade_ref")
        if not mapped:
            raise TypeValidationError(f"missing upgrade mapping for {record['definition_id']}")
        new_def = self._require_def(str(mapped))
        fields = dict(new_def.get("fields", {}))
        # In-place: same id/slot/node; refresh definition and health ceiling proportionally.
        old_max = int(record["max_health"])
        old_health = int(record["health"])
        base_health = int(fields.get("max_health", old_max))
        record["definition_id"] = str(mapped)
        record["max_health"] = base_health
        if old_max > 0:
            record["health"] = max(1, int(round(base_health * (old_health / old_max))))
        else:
            record["health"] = base_health
        record["capacity_base"] = float(fields.get("capacity_base", record.get("capacity_base", 1.0)))
        record["job_id"] = fields.get("job_ref", record.get("job_id"))
        record["usable_capacity"] = usable_capacity(
            record["health"], record["max_health"], record["capacity_base"]
        )
        if fields.get("settlement_tier") == "city" and record.get("settlement_id"):
            settlement = self.state.settlements.get(str(record["settlement_id"]))
            if settlement is not None:
                settlement["tier"] = "city"
                settlement["primary_flow_multiplier"] = float(
                    fields.get("primary_flow_multiplier", 2.0)
                )
                # Explicit: city does not double primary slot count.
                settlement["primary_slot_multiplier"] = float(
                    fields.get("primary_slot_multiplier", 1.0)
                )
        return dict(record)

    def destroy(self, building_id: str, *, cause_id: str | None = None) -> dict[str, Any]:
        record = self.state.buildings.get(building_id)
        if record is None:
            raise TypeValidationError(f"unknown building {building_id}")
        if record.get("status") == "destroyed":
            # Idempotent — no second loss.
            return {"building": dict(record), "idempotent": True, "effects": record.get("destroy_effects", {})}
        record["health"] = 0
        record["usable_capacity"] = 0.0
        record["status"] = "destroyed"
        record["active"] = False
        record["owned"] = False
        record["destroy_cause_id"] = cause_id
        self.state.tombstones[building_id] = {
            "kind": "building",
            "display_name": str(record.get("definition_id")),
            "node_id": record.get("node_id"),
            "cause_id": cause_id,
        }
        effects: dict[str, Any] = {"displaced_people": [], "stock_loss": None, "centre_loss": None}

        # Displace workers (do not kill).
        try:
            from sim.dmb.people.registry import PeopleService

            displaced = PeopleService(self.state).displace_workplace(
                building_id, reason="building_destroyed"
            )
            effects["displaced_people"] = [p["id"] for p in displaced]
        except Exception:
            pass

        slot_kind = record.get("slot_kind")
        settlement_id = record.get("settlement_id")

        if slot_kind == "warehouse":
            from sim.dmb.logistics.stock import StockLedger

            store_id = f"store:{building_id}"
            ledger = StockLedger(self.state)
            loss_goods: dict[str, int] = {}
            store = self.state.stocks.get(store_id, {})
            for ns_name, ns in list(store.items()):
                if not isinstance(ns, dict):
                    continue
                for good, entry in ns.items():
                    if not isinstance(entry, dict):
                        continue
                    qty = int(entry.get("available", 0)) + int(entry.get("reserved", 0)) + int(entry.get("escrow", 0))
                    if qty > 0:
                        loss_goods[good] = loss_goods.get(good, 0) + qty
                        entry["available"] = 0
                        entry["reserved"] = 0
                        entry["escrow"] = 0
            if loss_goods:
                effects["stock_loss"] = ledger.record_loss(
                    loss_goods, cause_id=cause_id or f"wh-loss:{building_id}", source=store_id
                )
            # Cart cargo elsewhere is unaffected.

        if slot_kind == "centre" and settlement_id:
            settlement = self.state.settlements.get(str(settlement_id))
            if settlement is not None:
                settlement["operational"] = False
                settlement["status"] = "centre_lost"
                settlement["faction_id_before_loss"] = settlement.get("faction_id")
                # Centre loss does not capture the node for the attacker.
                settlement["captured_by"] = None
                # Strand surviving industry: inactive/unowned
                for bid, b in self.state.buildings.items():
                    if b.get("settlement_id") == settlement_id and bid != building_id:
                        if b.get("status") != "destroyed":
                            b["active"] = False
                            b["owned"] = False
                            b["faction_id"] = None
                settlement["faction_id"] = None
                effects["centre_loss"] = {
                    "settlement_id": settlement_id,
                    "node_id": settlement.get("node_id"),
                    "captured": False,
                }
                # Last-centre dissolution signal for later era safeguards
                fid = settlement.get("faction_id_before_loss")
                if fid:
                    remaining = [
                        s
                        for s in self.state.settlements.values()
                        if s.get("faction_id") == fid and s.get("operational", True)
                    ]
                    if not remaining:
                        effects["faction_dissolved"] = fid
                        self.state.clock.setdefault("dissolved_factions", []).append(fid)

        record["destroy_effects"] = effects
        return {"building": dict(record), "idempotent": False, "effects": effects}

    def capacity_state(self, building_id: str) -> dict[str, Any]:
        record = self.state.buildings.get(building_id)
        if record is None:
            raise TypeValidationError(f"unknown building {building_id}")
        return {
            "building_id": building_id,
            "health": int(record["health"]),
            "max_health": int(record["max_health"]),
            "usable_capacity": float(record.get("usable_capacity", 0.0)),
            "status": record.get("status"),
            "active": bool(record.get("active")),
        }

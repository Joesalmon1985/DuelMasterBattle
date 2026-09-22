"""Historic core upgrades and one-time transition starter grants (C11 / T100)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.types import TypeValidationError
from sim.dmb.industry import fraction_wire
from sim.dmb.logistics.stock import StockLedger
from sim.dmb.world.setup import STARTER_GOODS

ROOT = Path(__file__).resolve().parents[3]
HISTORIC_CORE_PATH = (
    ROOT / "godot_project" / "content" / "source" / "eras" / "historic" / "core_upgrade.json"
)
RECIPES_PATH = ROOT / "godot_project" / "content" / "source" / "recipes" / "mvp.json"

SLOT_UPGRADE = {
    "centre": "building.centre.historic",
    "warehouse": "building.warehouse.historic",
    "primary": "building.primary.historic",
    "processor": "building.processor.historic",
    "factory": "building.factory.historic",
}

HISTORIC_UNITS = (
    "unit.historic.skirmisher",
    "unit.historic.line",
    "unit.historic.heavy",
)


def load_historic_core_config(path: Path | None = None) -> dict[str, Any]:
    target = path or HISTORIC_CORE_PATH
    if not target.exists():
        return {
            "core_upgrade": {
                "centre_def": SLOT_UPGRADE["centre"],
                "warehouse_def": SLOT_UPGRADE["warehouse"],
                "primary_def": SLOT_UPGRADE["primary"],
                "processor_def": SLOT_UPGRADE["processor"],
                "factory_def": SLOT_UPGRADE["factory"],
                "unit_defs": list(HISTORIC_UNITS),
                "starter_grant": dict(STARTER_GOODS),
            },
            "terrain_industrial": {},
        }
    return json.loads(target.read_text(encoding="utf-8"))


def _slot_kind(building: Mapping[str, Any]) -> str:
    kind = str(building.get("slot_kind") or "")
    if kind:
        return kind
    def_id = str(building.get("def_id") or building.get("definition_id") or "")
    for candidate in ("centre", "warehouse", "primary", "processor", "factory"):
        if candidate in def_id:
            return candidate
    return ""


def _rebind_building(building: dict[str, Any], new_def: str, *, era: str = "historic") -> None:
    building["definition_id"] = new_def
    building["def_id"] = new_def
    building["era"] = era
    building["era_id"] = era
    building["presentation_era"] = era


def mark_legacy_sites(
    state: Any,
    settlement_ids: Sequence[str],
    *,
    source_era: str = "prehistoric",
) -> list[dict[str, Any]]:
    """Mark surviving non-core settlements as operational legacy (0 current VP)."""
    marked: list[dict[str, Any]] = []
    for sid in settlement_ids:
        settlement = state.settlements.get(sid)
        if settlement is None or settlement.get("ruin_only"):
            continue
        settlement["legacy"] = True
        settlement["upgraded"] = False
        settlement["historic_core"] = False
        settlement["operational"] = True
        settlement["era"] = source_era
        settlement["source_era"] = source_era
        settlement["status"] = settlement.get("status") or "active"
        # Industry/units/stocks/people unchanged — still score 0 via ScoreService.
        marked.append({"settlement_id": sid, "legacy": True, "vp": 0})
    return marked


@dataclass
class CoreUpgradeService:
    state: Any
    config: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.config is None:
            self.config = load_historic_core_config()

    def upgrade_core(
        self,
        settlement_id: str,
        *,
        transition_id: str,
        next_era: str = "historic",
        grant_starter: bool = True,
    ) -> dict[str, Any]:
        """Upgrade centre/warehouse/primary/factory slots in place; optional starter grant."""
        settlement = self.state.settlements.get(settlement_id)
        if settlement is None:
            raise TypeValidationError(f"unknown settlement {settlement_id}")
        receipts = self.state.command_receipts.setdefault("era_core_upgrade", {})
        receipt_key = f"{transition_id}:{settlement_id}"
        if receipt_key in receipts:
            return {"idempotent": True, "receipt": receipts[receipt_key]}

        cfg = (self.config or {}).get("core_upgrade") or {}
        people_before = set(self.state.people)
        building_ids_before = set(self.state.buildings)
        primary_before = sum(
            1
            for b in self.state.buildings.values()
            if b.get("settlement_id") == settlement_id and _slot_kind(b) == "primary"
        )
        factory_before = sum(
            1
            for b in self.state.buildings.values()
            if b.get("settlement_id") == settlement_id and _slot_kind(b) == "factory"
        )

        upgraded: list[str] = []
        for bid, building in list(self.state.buildings.items()):
            if building.get("settlement_id") != settlement_id:
                continue
            kind = _slot_kind(building)
            target = cfg.get(f"{kind}_def") or SLOT_UPGRADE.get(kind)
            if not target:
                continue
            _rebind_building(building, str(target), era=next_era)
            upgraded.append(bid)

        # Reset new factory meters only.
        industry = self.state.industry.setdefault("factories", {})
        meter_resets: list[str] = []
        for bid in upgraded:
            building = self.state.buildings.get(bid) or {}
            if _slot_kind(building) != "factory":
                continue
            record = industry.setdefault(
                bid,
                {
                    "id": bid,
                    "node_id": building.get("node_id"),
                    "faction_id": settlement.get("faction_id"),
                    "settlement_id": settlement_id,
                    "era": next_era,
                    "unit_def_id": HISTORIC_UNITS[0],
                    "meter": fraction_wire(Fraction()),
                    "active": True,
                },
            )
            record["era"] = next_era
            record["meter"] = fraction_wire(Fraction())
            slot = int(building.get("slot_index") or 0)
            units = list(cfg.get("unit_defs") or HISTORIC_UNITS)
            record["unit_def_id"] = units[min(slot, len(units) - 1)]
            meter_resets.append(bid)
            routes = self.state.industry.setdefault("routes", {})
            if bid in routes:
                routes[bid]["unit_def_id"] = record["unit_def_id"]
            else:
                for _rid, route in list(routes.items()):
                    if route.get("factory_id") == bid:
                        route["unit_def_id"] = record["unit_def_id"]
                        route["era"] = next_era

        processor_route = self._install_minimal_historic_processor(settlement_id, next_era=next_era)

        settlement["tier"] = "settlement"
        settlement["era"] = next_era
        settlement["legacy"] = False
        settlement["upgraded"] = True
        settlement["historic_core"] = True
        settlement["operational"] = True
        settlement["ruin_only"] = False
        settlement["status"] = "active"

        grant: dict[str, Any] | None = None
        if grant_starter:
            grant = self._grant_starter_once(settlement, transition_id=transition_id, cfg=cfg)

        if set(self.state.people) != people_before:
            raise TypeValidationError("core upgrade must not create or delete people")
        if not set(self.state.buildings).issuperset(building_ids_before):
            raise TypeValidationError("core upgrade must not remove buildings")
        primaries = [
            b
            for b in self.state.buildings.values()
            if b.get("settlement_id") == settlement_id and _slot_kind(b) == "primary"
        ]
        factories = [
            b
            for b in self.state.buildings.values()
            if b.get("settlement_id") == settlement_id and _slot_kind(b) == "factory"
        ]
        if len(primaries) != primary_before or len(factories) != factory_before:
            raise TypeValidationError("core upgrade must not add primary/factory slots")
        receipt = {
            "settlement_id": settlement_id,
            "transition_id": transition_id,
            "upgraded_buildings": upgraded,
            "meter_resets": meter_resets,
            "starter_grant": grant,
            "processor_route": processor_route,
            "vp": ScoreService(self.state).settlement_vp(settlement),
            "primary_count": len(primaries),
            "factory_count": len(factories),
            "grant_starter": grant_starter,
        }
        receipts[receipt_key] = receipt
        return {"idempotent": False, "receipt": receipt}

    def upgrade_legacy(
        self,
        settlement_id: str,
        *,
        order_id: str,
        next_era: str = "historic",
    ) -> dict[str, Any]:
        """Paid legacy upgrade: same in-place rebind, no free starter grant."""
        settlement = self.state.settlements.get(settlement_id)
        if settlement is None:
            raise TypeValidationError(f"unknown settlement {settlement_id}")
        if not settlement.get("legacy"):
            raise TypeValidationError("not_legacy")
        # Do not refill depleted source layers.
        layers = (self.state.industry or {}).get("layers") or {}
        layer_balances = {
            lid: dict(rec) if isinstance(rec, dict) else rec for lid, rec in layers.items()
        }
        result = self.upgrade_core(
            settlement_id,
            transition_id=f"legacy:{order_id}",
            next_era=next_era,
            grant_starter=False,
        )
        settlement["legacy"] = False
        settlement["upgraded"] = True
        settlement["historic_core"] = False  # paid upgrade site, not transition core
        settlement["paid_legacy_upgrade"] = True
        # Layer balances must be unchanged (no silent refill).
        for lid, before in layer_balances.items():
            after = layers.get(lid)
            if isinstance(before, dict) and isinstance(after, dict):
                if before.get("finite_balance") != after.get("finite_balance"):
                    raise TypeValidationError(f"legacy upgrade refilled layer {lid}")
        return result

    def _grant_starter_once(
        self, settlement: dict[str, Any], *, transition_id: str, cfg: Mapping[str, Any]
    ) -> dict[str, Any]:
        warehouse_id = settlement.get("warehouse_id")
        if not warehouse_id:
            for bid, building in self.state.buildings.items():
                if building.get("settlement_id") == settlement["id"] and _slot_kind(building) == "warehouse":
                    warehouse_id = bid
                    settlement["warehouse_id"] = bid
                    break
        if not warehouse_id:
            raise TypeValidationError(f"core {settlement['id']} missing warehouse")
        store_id = f"store:{warehouse_id}"
        grant_receipts = self.state.command_receipts.setdefault("era_core_starter", {})
        key = f"{transition_id}:{settlement['id']}"
        if key in grant_receipts:
            return {"idempotent": True, **grant_receipts[key]}

        goods = dict(cfg.get("starter_grant") or STARTER_GOODS)
        # Capture prior Catan stock so we verify retention + grant.
        ledger = StockLedger(self.state)
        before = {good: ledger.available(store_id, good) for good in goods}
        for good, qty in goods.items():
            ledger.credit(store_id, good, int(qty))
        after = {good: ledger.available(store_id, good) for good in goods}
        record = {
            "store_id": store_id,
            "goods": goods,
            "before": before,
            "after": after,
        }
        grant_receipts[key] = record
        return record

    def _install_minimal_historic_processor(
        self, settlement_id: str, *, next_era: str
    ) -> dict[str, Any] | None:
        """Rebind existing processor to a feasible Historic recipe when possible.

        Extra legacy processors remain; we do not add duplicate primary/factory slots.
        """
        processors = [
            bid
            for bid, building in self.state.buildings.items()
            if building.get("settlement_id") == settlement_id and _slot_kind(building) == "processor"
        ]
        if not processors:
            return None
        processor_id = sorted(processors)[0]
        recipe = self._pick_historic_recipe()
        if recipe is None:
            # Still mark processor era for presentation; routes may stay until layers exist.
            binding = self.state.industry.setdefault("processors", {}).get(processor_id)
            if isinstance(binding, dict):
                binding["era"] = next_era
            return {"processor_id": processor_id, "recipe_id": None, "status": "era_marked_only"}

        existing = self.state.industry.setdefault("processors", {}).get(processor_id) or {}
        channels = self.state.industry.get("channels") or {}
        # Prefer keeping existing channel ids when present; otherwise leave binding era-marked.
        input_a = existing.get("input_a_channel_id")
        input_b = existing.get("input_b_channel_id")
        if input_a and input_b and input_a in channels and input_b in channels:
            self.state.industry["processors"][processor_id] = {
                **existing,
                "building_id": processor_id,
                "recipe_id": recipe["id"],
                "era": next_era,
                "input_a_channel_id": input_a,
                "input_b_channel_id": input_b,
                "output_capacity": existing.get("output_capacity")
                or fraction_wire(Fraction(1, 10)),
                "active": True,
            }
            # Channel resource ids stay on installed layers for T101 legacy distinction;
            # minimal historic route records the intended recipe for later layer install.
            return {
                "processor_id": processor_id,
                "recipe_id": recipe["id"],
                "status": "rebound",
                "note": "channel resource layer rebinding deferred to industry service when layers exist",
            }
        return {"processor_id": processor_id, "recipe_id": recipe["id"], "status": "pending_channels"}

    def _pick_historic_recipe(self) -> dict[str, Any] | None:
        if not RECIPES_PATH.exists():
            return None
        data = json.loads(RECIPES_PATH.read_text(encoding="utf-8"))
        recipes = [
            r
            for r in data.get("recipes") or []
            if r.get("era") == "historic" and r.get("mvp_subset")
        ]
        return recipes[0] if recipes else None


def upgrade_cores(
    state: Any,
    settlement_ids: Sequence[str],
    *,
    transition_id: str,
    next_era: str = "historic",
) -> list[dict[str, Any]]:
    svc = CoreUpgradeService(state)
    return [
        svc.upgrade_core(sid, transition_id=transition_id, next_era=next_era)
        for sid in settlement_ids
    ]

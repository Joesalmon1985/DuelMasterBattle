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
ERAS_ROOT = ROOT / "godot_project" / "content" / "source" / "eras"
HISTORIC_CORE_PATH = ERAS_ROOT / "historic" / "core_upgrade.json"
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

DEFAULT_UNITS = {
    "historic": HISTORIC_UNITS,
    "modern": (
        "unit.modern.skirmisher",
        "unit.modern.line",
        "unit.modern.heavy",
    ),
    "future": (
        "unit.future.skirmisher",
        "unit.future.line",
        "unit.future.heavy",
    ),
}


def load_core_config(era: str = "historic", path: Path | None = None) -> dict[str, Any]:
    """Load era core-upgrade JSON (historic/modern/future)."""
    era_key = str(era or "historic").lower()
    if era_key in {"ancient", "prehistoric"}:
        era_key = "historic"
    target = path or (ERAS_ROOT / era_key / "core_upgrade.json")
    if not target.exists():
        units = list(DEFAULT_UNITS.get(era_key, HISTORIC_UNITS))
        return {
            "core_upgrade": {
                "centre_def": f"building.centre.{era_key}",
                "warehouse_def": f"building.warehouse.{era_key}",
                "primary_def": f"building.primary.{era_key}",
                "processor_def": f"building.processor.{era_key}",
                "factory_def": f"building.factory.{era_key}",
                "unit_defs": units,
                "starter_grant": dict(STARTER_GOODS),
            },
            "terrain_industrial": {},
        }
    return json.loads(target.read_text(encoding="utf-8"))


def load_historic_core_config(path: Path | None = None) -> dict[str, Any]:
    """Backward-compatible Historic loader."""
    return load_core_config("historic", path=path)


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
            self.config = load_core_config("historic")

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

        self.config = load_core_config(next_era)
        cfg = (self.config or {}).get("core_upgrade") or {}
        default_units = list(DEFAULT_UNITS.get(str(next_era).lower(), HISTORIC_UNITS))
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
            target = cfg.get(f"{kind}_def") or f"building.{kind}.{next_era}"
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
                    "unit_def_id": default_units[0],
                    "meter": fraction_wire(Fraction()),
                    "active": True,
                },
            )
            record["era"] = next_era
            record["meter"] = fraction_wire(Fraction())
            slot = int(building.get("slot_index") or 0)
            units = list(cfg.get("unit_defs") or default_units)
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

        processor_route = self._install_minimal_era_processor(settlement_id, next_era=next_era)

        settlement["tier"] = "settlement"
        settlement["era"] = next_era
        settlement["legacy"] = False
        settlement["upgraded"] = True
        settlement["era_core"] = True
        settlement["historic_core"] = str(next_era).lower() == "historic"
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

    def _install_minimal_era_processor(
        self, settlement_id: str, *, next_era: str
    ) -> dict[str, Any] | None:
        """Rebind existing processor to a feasible era recipe when possible.

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
        recipe = self._pick_era_recipe(next_era)
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
            return {
                "processor_id": processor_id,
                "recipe_id": recipe["id"],
                "status": "rebound",
                "note": "channel resource layer rebinding deferred to industry service when layers exist",
            }
        return {"processor_id": processor_id, "recipe_id": recipe["id"], "status": "pending_channels"}

    def _install_minimal_historic_processor(
        self, settlement_id: str, *, next_era: str
    ) -> dict[str, Any] | None:
        return self._install_minimal_era_processor(settlement_id, next_era=next_era)

    def _pick_era_recipe(self, era: str) -> dict[str, Any] | None:
        from sim.dmb.content.catalogue import recipes_for_era

        era_key = str(era or "historic").lower()
        # Prefer MVP-marked recipes when present (G06 Pre/Hist); else full catalogue.
        mvp = recipes_for_era(era_key, mvp_only=True)
        if mvp:
            return dict(mvp[0])
        full = recipes_for_era(era_key)
        return dict(full[0]) if full else None

    def _pick_historic_recipe(self) -> dict[str, Any] | None:
        return self._pick_era_recipe("historic")


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

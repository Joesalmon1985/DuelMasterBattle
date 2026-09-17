"""Faction research archive, activation and scoped modifiers (C12 / T040)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.technology.definitions import TechnologyCatalog, TechDef


def _empty_research() -> dict[str, Any]:
    return {
        "owned": {},  # tech_instance_id -> card record
        "active_stacks": {},  # definition_id -> list of active instance ids (capped)
        "inactive_archive": {},  # tech_instance_id -> card record (owned but inactive)
        "activated_definition_ids": [],  # ordered history of activated defs (prereq source)
        "acquisition_receipts": [],
        "activation_receipts": [],
    }


@dataclass
class TechnologyService:
    state: WorldState
    catalog: TechnologyCatalog = field(default_factory=TechnologyCatalog)

    def __post_init__(self) -> None:
        if not self.catalog.ids:
            self.catalog.load()

    def research_of(self, faction_id: str) -> dict[str, Any]:
        bucket = self.state.research.setdefault(faction_id, _empty_research())
        for key, default in _empty_research().items():
            bucket.setdefault(key, deepcopy(default) if not isinstance(default, list) else [])
        return bucket

    def make_card_instance(self, definition_id: str, *, playable: bool = True) -> dict[str, Any]:
        defn = self.catalog.get(definition_id)
        instance_id = self.state.ids.new("tech")
        return {
            "id": instance_id,
            "definition_id": defn.id,
            "era": defn.era,
            "effect_kind": defn.effect_kind,
            "playable": bool(playable),
            "status": "pending",
        }

    def acquire(self, faction_id: str, card_instance: dict[str, Any]) -> dict[str, Any]:
        """Own a drafted/picked card instance. Does not activate."""
        if not faction_id:
            raise TypeValidationError("faction_id required")
        card = dict(card_instance)
        instance_id = str(card.get("id") or "")
        definition_id = str(card.get("definition_id") or "")
        if not instance_id or not definition_id:
            raise TypeValidationError("card_instance requires id and definition_id")
        self.catalog.get(definition_id)  # validate
        research = self.research_of(faction_id)
        if instance_id in research["owned"]:
            raise TypeValidationError(f"duplicate acquire {instance_id}")
        card["status"] = "owned_inactive"
        card["faction_id"] = faction_id
        research["owned"][instance_id] = card
        research["inactive_archive"][instance_id] = card
        receipt = {
            "kind": "acquire",
            "faction_id": faction_id,
            "instance_id": instance_id,
            "definition_id": definition_id,
            "turn": int(self.state.clock.get("turn", 0)),
        }
        research["acquisition_receipts"].append(receipt)
        return receipt

    def _predecessors_satisfied(self, faction_id: str, defn: TechDef) -> bool:
        if not defn.allowed_predecessor_ids:
            return True
        research = self.research_of(faction_id)
        activated = set(research["activated_definition_ids"])
        # any_previously_activated: at least one listed predecessor activated in history
        return any(pred in activated for pred in defn.allowed_predecessor_ids)

    def _activation_order(self, definition_ids: list[str]) -> list[str]:
        """Topological order by predecessor edges among the given definitions."""
        pending = set(definition_ids)
        ordered: list[str] = []
        while pending:
            ready = []
            for did in sorted(pending):
                defn = self.catalog.get(did)
                preds = [p for p in defn.allowed_predecessor_ids if p in pending]
                if not preds:
                    ready.append(did)
            if not ready:
                # Cycle among pending — fall back to stable id order (should not happen
                # for validated catalogs; still drain to avoid hang).
                ready = [sorted(pending)[0]]
            for did in ready:
                pending.remove(did)
                ordered.append(did)
        return ordered

    def activate_eligible(self, faction_id: str) -> list[dict[str, Any]]:
        """Activate newly eligible inactive cards until stable; respect stack caps."""
        research = self.research_of(faction_id)
        receipts: list[dict[str, Any]] = []
        progressed = True
        while progressed:
            progressed = False
            candidates: list[str] = []
            for instance_id, card in list(research["inactive_archive"].items()):
                if not card.get("playable", True):
                    continue  # unplayable stays owned/inactive
                status = str(card.get("status", ""))
                if status in {"active", "owned_inert_cap"}:
                    continue
                defn = self.catalog.get(str(card["definition_id"]))
                if not self._predecessors_satisfied(faction_id, defn):
                    continue
                candidates.append(str(card["definition_id"]))
            # Unique defs to activate this wave, topo-ordered.
            unique_defs = self._activation_order(sorted(set(candidates)))
            for definition_id in unique_defs:
                # Activate one eligible instance of this definition per wave pass
                # (drain loop continues until stable for multi-copy / unlock chains).
                instance = None
                for instance_id, card in list(research["inactive_archive"].items()):
                    if str(card["definition_id"]) != definition_id:
                        continue
                    if not card.get("playable", True):
                        continue
                    status = str(card.get("status", ""))
                    if status in {"active", "owned_inert_cap"}:
                        continue
                    defn = self.catalog.get(definition_id)
                    if not self._predecessors_satisfied(faction_id, defn):
                        continue
                    instance = card
                    break
                if instance is None:
                    continue
                receipt = self._activate_one(faction_id, instance)
                if receipt is not None:
                    receipts.append(receipt)
                    progressed = True
        return receipts

    def _activate_one(self, faction_id: str, card: dict[str, Any]) -> dict[str, Any] | None:
        research = self.research_of(faction_id)
        instance_id = str(card["id"])
        definition_id = str(card["definition_id"])
        defn = self.catalog.get(definition_id)
        stacks = research["active_stacks"].setdefault(definition_id, [])
        if len(stacks) >= int(defn.max_stacks):
            # Fourth capped copy stays owned but inert (inactive archive).
            card["status"] = "owned_inert_cap"
            research["owned"][instance_id] = card
            research["inactive_archive"][instance_id] = card
            receipt = {
                "kind": "cap_inert",
                "faction_id": faction_id,
                "instance_id": instance_id,
                "definition_id": definition_id,
                "turn": int(self.state.clock.get("turn", 0)),
            }
            research["activation_receipts"].append(receipt)
            return receipt
        card["status"] = "active"
        stacks.append(instance_id)
        research["owned"][instance_id] = card
        research["inactive_archive"].pop(instance_id, None)
        if definition_id not in research["activated_definition_ids"]:
            research["activated_definition_ids"].append(definition_id)
        receipt = {
            "kind": "activate",
            "faction_id": faction_id,
            "instance_id": instance_id,
            "definition_id": definition_id,
            "stack_index": len(stacks),
            "turn": int(self.state.clock.get("turn", 0)),
        }
        research["activation_receipts"].append(receipt)
        return receipt

    def effective_modifiers(
        self,
        faction_id: str,
        *,
        asset_era: str | None = None,
        scope: str | None = None,
    ) -> dict[str, float]:
        """Project stacked active modifiers; duplicate refresh does not double-count."""
        research = self.research_of(faction_id)
        totals: dict[str, float] = {kind: 0.0 for kind in (
            "primary_flow",
            "processor_cap",
            "factory_ceiling",
            "cart_capacity",
            "unit_health",
            "unit_attack",
        )}
        # Count each active stack once from active_stacks (source of truth).
        for definition_id, instance_ids in research["active_stacks"].items():
            defn = self.catalog.get(definition_id)
            if scope is not None and defn.compatibility_scope != scope:
                continue
            if defn.compatibility_scope == "unit_era" and asset_era is not None:
                if defn.era != asset_era:
                    continue
            # Cap already enforced at activation; still clamp for safety.
            count = min(len(instance_ids), int(defn.max_stacks))
            totals[defn.effect_kind] = float(totals.get(defn.effect_kind, 0.0)) + (
                float(defn.effect_value) * float(count)
            )
        return totals

    def inherit_to_successor(self, source_faction_id: str, successor_faction_id: str) -> dict[str, Any]:
        """Fission copy of research history into a new faction bucket."""
        source = deepcopy(self.research_of(source_faction_id))
        self.state.research[successor_faction_id] = source
        return self.research_of(successor_faction_id)

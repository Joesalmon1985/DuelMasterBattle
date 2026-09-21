"""Individual persistent military unit creation and combat state (C07)."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

# C07 archetype baseline — era factor applied exactly once at spawn.
ARCHETYPES: dict[str, dict[str, Any]] = {
    "skirmisher": {
        "base_hp": 60,
        "base_attack": 10,
        "period_ms": 1200,
        "range_tiles": 4,
        "speed_tiles_per_s": 2.5,
        "factory_cost": 2,
    },
    "line": {
        "base_hp": 100,
        "base_attack": 15,
        "period_ms": 1000,
        "range_tiles": 1,
        "speed_tiles_per_s": 2.0,
        "factory_cost": 3,
    },
    "heavy": {
        "base_hp": 180,
        "base_attack": 25,
        "period_ms": 1500,
        "range_tiles": 1,
        "speed_tiles_per_s": 1.4,
        "factory_cost": 5,
    },
}

ERA_FACTORS: dict[str, int] = {
    "prehistoric": 1,
    "ancient": 1,  # content alias used by existing unit defs
    "historic": 10,
    "modern": 100,
    "future": 1000,
}


def era_factor(era: str) -> int:
    key = str(era or "prehistoric").lower()
    if key not in ERA_FACTORS:
        raise ValueError(f"unknown era {era!r}")
    return ERA_FACTORS[key]


def archetype_from_definition(unit_def_id: str) -> str:
    lowered = str(unit_def_id).lower()
    for name in ("skirmisher", "line", "heavy"):
        if name in lowered:
            return name
    raise ValueError(f"cannot derive archetype from {unit_def_id!r}")


def round_half_up(value: float | Decimal) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class MilitaryService:
    def __init__(self, world_state: Any):
        self.state = world_state
        self._ensure_formations()

    def _ensure_formations(self) -> dict[str, Any]:
        formations = getattr(self.state, "formations", None)
        if not isinstance(formations, dict):
            formations = {}
            self.state.formations = formations
        return formations

    def spawn(
        self,
        unit_def_id: str,
        *,
        home_node_id: str,
        faction_id: str,
        era: str,
        factory_id: str,
        position: list[float] | None = None,
        person_id: str | None = None,
    ) -> dict[str, Any]:
        from sim.dmb.people.registry import PeopleService
        from sim.dmb.persistence.migrate import stable_soldier_name

        unit_id = self.state.ids.new("unit")
        archetype = archetype_from_definition(unit_def_id)
        base = ARCHETYPES[archetype]
        factor = era_factor(era)
        max_hp = base["base_hp"] * factor
        derived_attack = base["base_attack"] * factor

        people = PeopleService(self.state)
        linked_person_id = person_id
        if linked_person_id and linked_person_id in self.state.people:
            person = self.state.people[linked_person_id]
            name = str(person.get("name") or person.get("display_name") or linked_person_id)
        else:
            name = stable_soldier_name(unit_id)
            person = people.create_person(
                name=name,
                affiliation=faction_id,
                role="soldier",
                node_id=home_node_id,
                position=list(position or [0.0, 0.0]),
                dialogue_profile="dialogue.soldier",
                cultural_appearance={
                    "culture_id": "culture.common",
                    "appearance_id": "appearance.soldier",
                },
                history_refs=[f"unit:{unit_id}"],
                profile_flags=[],
            )
            linked_person_id = person["id"]
            self.state.people[linked_person_id]["occupation"] = "soldier"
        self.state.people[linked_person_id]["unit_id"] = unit_id
        self.state.people[linked_person_id]["node_id"] = home_node_id
        self.state.people[linked_person_id]["affiliation"] = faction_id

        record = {
            "id": unit_id,
            "person_id": linked_person_id,
            "person_name": name,
            "definition_id": unit_def_id,
            "archetype": archetype,
            "home_node_id": home_node_id,
            "home_settlement": home_node_id,
            "node_id": home_node_id,
            "faction_id": faction_id,
            "era": era,
            "era_factor": factor,
            "factory_id": factory_id,
            "spawned_turn": int(getattr(self.state, "clock", {}).get("turn", 0) or 0),
            "status": "available",
            "alive": True,
            "formation_id": None,
            "engagement_id": None,
            "lease_id": None,
            "lease_version": None,
            "base_hp": base["base_hp"],
            "base_attack": base["base_attack"],
            "max_health": max_hp,
            "current_health": max_hp,
            "health_rounding_remainder": 0,
            "derived_attack": derived_attack,
            "armour": 0,
            "period_ms": base["period_ms"],
            "range_tiles": base["range_tiles"],
            "speed_tiles_per_s": base["speed_tiles_per_s"],
            "position": list(position or [0.0, 0.0]),
            "facing": 0.0,
            "target_id": None,
            "remaining_attack_cooldown_ms": 0,
            "entry_strength": max_hp,
            "shield_remaining": 0,
            "buffs": [],
            "material_change_version": 0,
        }
        self.state.units[unit_id] = record
        return record

    def group(self, unit_ids: list[str], *, faction_id: str, node_id: str) -> dict[str, Any]:
        formations = self._ensure_formations()
        ordered: list[str] = []
        for unit_id in unit_ids:
            unit = self.state.units.get(unit_id)
            if unit is None or not unit.get("alive", True):
                raise ValueError(f"missing or dead unit {unit_id}")
            if unit.get("faction_id") != faction_id:
                raise ValueError(f"unit {unit_id} faction mismatch")
            if unit.get("formation_id"):
                raise ValueError(f"unit {unit_id} already in formation {unit['formation_id']}")
            ordered.append(unit_id)
        formation_id = self.state.ids.new("formation")
        strength = sum(int(self.state.units[uid]["current_health"]) for uid in ordered)
        record = {
            "id": formation_id,
            "faction_id": faction_id,
            "unit_ids": list(ordered),
            "objective": None,
            "node_id": node_id,
            "path": [],
            "engagement_id": None,
            "movement_spent_turn": None,
            "withdrawal_target": None,
            "withdrawal_status": None,
            "derived_strength": strength,
        }
        formations[formation_id] = record
        for unit_id in ordered:
            self.state.units[unit_id]["formation_id"] = formation_id
            self.state.units[unit_id]["node_id"] = node_id
        return record

    def apply_casualties(
        self,
        damages: dict[str, int],
        *,
        lease_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Apply simultaneous damage; shields consume earliest-expiry first via BuffService."""
        from sim.dmb.military.buffs import BuffService

        buffs = BuffService(self.state)
        events: list[dict[str, Any]] = []
        for unit_id, raw in sorted(damages.items()):
            unit = self.state.units.get(unit_id)
            if unit is None or not unit.get("alive", True):
                continue
            if lease_id is not None and unit.get("lease_id") not in {None, lease_id}:
                continue
            amount = max(0, int(raw))
            remaining = buffs.absorb_damage(unit_id, amount)
            before = int(unit["current_health"])
            after = max(0, before - remaining)
            unit["current_health"] = after
            unit["material_change_version"] = int(unit.get("material_change_version", 0)) + 1
            event = {
                "unit_id": unit_id,
                "damage": amount,
                "health_before": before,
                "health_after": after,
                "killed": after <= 0,
            }
            if after <= 0:
                unit["alive"] = False
                unit["status"] = "dead"
                unit["target_id"] = None
                self._tombstone(unit)
                self._kill_linked_person(unit)
                formation_id = unit.get("formation_id")
                if formation_id:
                    self._detach_from_formation(unit_id, formation_id)
            events.append(event)
        return events

    def receive_checkpoint(self, lease_id: str, checkpoint: dict[str, Any]) -> dict[str, Any]:
        """Apply leased battle checkpoint fields once onto persistent units."""
        applied: list[str] = []
        for unit_id, patch in sorted((checkpoint.get("units") or {}).items()):
            unit = self.state.units.get(unit_id)
            if unit is None:
                continue
            if unit.get("lease_id") not in {None, lease_id}:
                continue
            for key in (
                "position",
                "facing",
                "target_id",
                "remaining_attack_cooldown_ms",
                "current_health",
                "shield_remaining",
                "buffs",
                "alive",
                "status",
            ):
                if key in patch:
                    unit[key] = deepcopy(patch[key])
            unit["lease_id"] = lease_id
            unit["lease_version"] = int(checkpoint.get("version", unit.get("lease_version") or 0))
            unit["material_change_version"] = int(unit.get("material_change_version", 0)) + 1
            if not unit.get("alive", True) or int(unit.get("current_health", 0)) <= 0:
                unit["alive"] = False
                unit["status"] = "dead"
                unit["current_health"] = 0
                self._tombstone(unit)
                self._kill_linked_person(unit)
            applied.append(unit_id)
        return {"lease_id": lease_id, "applied": applied}

    def formation_strength(self, formation_id: str) -> int:
        formations = self._ensure_formations()
        formation = formations[formation_id]
        living = [
            int(self.state.units[uid]["current_health"])
            for uid in formation["unit_ids"]
            if self.state.units.get(uid, {}).get("alive", True)
        ]
        strength = sum(living)
        formation["derived_strength"] = strength
        formation["unit_ids"] = [
            uid for uid in formation["unit_ids"] if self.state.units.get(uid, {}).get("alive", True)
        ]
        return strength

    def _detach_from_formation(self, unit_id: str, formation_id: str) -> None:
        formations = self._ensure_formations()
        formation = formations.get(formation_id)
        if formation is None:
            return
        formation["unit_ids"] = [uid for uid in formation["unit_ids"] if uid != unit_id]
        self.state.units[unit_id]["formation_id"] = None
        self.formation_strength(formation_id)

    def _tombstone(self, unit: dict[str, Any]) -> None:
        unit_id = unit["id"]
        self.state.tombstones[unit_id] = {
            "kind": "unit",
            "display_name": unit.get("person_name") or unit.get("definition_id", unit_id),
            "faction_id": unit.get("faction_id"),
            "node_id": unit.get("node_id"),
            "definition_id": unit.get("definition_id"),
            "person_id": unit.get("person_id"),
            "alive": False,
        }

    def _kill_linked_person(self, unit: dict[str, Any]) -> None:
        person_id = unit.get("person_id")
        if not person_id or person_id not in self.state.people:
            return
        person = self.state.people[person_id]
        if not person.get("alive", True):
            return
        from sim.dmb.people.registry import PeopleService

        PeopleService(self.state).record_death(str(person_id), cause_id="combat")

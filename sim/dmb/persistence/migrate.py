"""Versioned WorldState / save migrations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.types import WorldId
from sim.dmb.people.registry import PeopleService

# Current on-disk snapshot schema.
SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1

_SOLDIER_NAMES = (
    "Bren", "Cal", "Dorin", "Ellis", "Fenna", "Garr", "Hale", "Ivo",
    "Jora", "Kest", "Lira", "Marn", "Ness", "Orin", "Piet", "Quinn",
    "Rusk", "Sera", "Tovin", "Una", "Vell", "Wren", "Yara", "Zell",
)


def stable_soldier_name(unit_id: str, existing: str | None = None) -> str:
    if existing:
        return str(existing)
    import zlib

    digest = zlib.crc32(str(unit_id).encode("utf-8")) & 0xFFFFFFFF
    return _SOLDIER_NAMES[digest % len(_SOLDIER_NAMES)]


def migrate_world_dict(world: dict[str, Any], *, from_schema: int | None = None) -> dict[str, Any]:
    """Return a deep-copied world dict upgraded to SCHEMA_VERSION (idempotent)."""
    payload = deepcopy(world)
    current = int(
        from_schema
        if from_schema is not None
        else payload.get("_schema_version", LEGACY_SCHEMA_VERSION)
    )
    if current < 2:
        payload = _migrate_v1_to_v2(payload)
    payload["_schema_version"] = SCHEMA_VERSION
    return payload


def _allocator_for(world: dict[str, Any]) -> IdAllocator:
    world_id = str(world.get("world_id") or "world:migrate")
    ids_blob = world.get("ids")
    if isinstance(ids_blob, dict) and ids_blob.get("world_id"):
        try:
            return IdAllocator.from_dict(ids_blob)
        except Exception:
            pass
    return IdAllocator(WorldId(world_id))


def _migrate_v1_to_v2(world: dict[str, Any]) -> dict[str, Any]:
    """Ensure every unit has a linked Person via person_id (dead units get dead Persons)."""
    people = world.setdefault("people", {})
    units = world.setdefault("units", {})
    tombstones = world.setdefault("tombstones", {})
    allocator = _allocator_for(world)

    for unit_id, unit in sorted(units.items()):
        if not isinstance(unit, dict):
            continue
        existing_pid = unit.get("person_id")
        if existing_pid and existing_pid in people:
            person = people[existing_pid]
            person["unit_id"] = unit_id
            name = person.get("name") or unit.get("person_name")
            if name:
                person["name"] = name
                person["display_name"] = name
                unit["person_name"] = name
            person.setdefault("occupation", "soldier" if person.get("role") == "soldier" else person.get("occupation"))
            continue

        name = stable_soldier_name(
            unit_id,
            existing=unit.get("person_name") or unit.get("given_name") or unit.get("display_name"),
        )
        alive = bool(unit.get("alive", True)) and str(unit.get("status") or "") != "dead"
        person_id = allocator.new("person")
        while person_id in people:
            person_id = allocator.new("person")

        person = {
            "id": person_id,
            "name": name,
            "display_name": name,
            "alive": alive,
            "status": "active" if alive else "dead",
            "affiliation": unit.get("faction_id"),
            "role": "soldier",
            "occupation": "soldier",
            "job_id": None,
            "workplace_id": None,
            "node_id": unit.get("node_id") or unit.get("home_node_id"),
            "home_node_id": unit.get("home_node_id") or unit.get("node_id"),
            "area_id": None,
            "position": list(unit.get("position") or [0.0, 0.0]),
            "profile_schema_version": 1,
            "cultural_appearance": {
                "culture_id": "culture.common",
                "appearance_id": "appearance.soldier",
            },
            "preferences": [
                {"trait_id": "pref.loyal", "kind": "social", "strength": 1},
                {"trait_id": "pref.diligent", "kind": "work", "strength": 1},
                {"trait_id": "pref.curious", "kind": "curiosity", "strength": 1},
            ],
            "goal_ids": [],
            "relationship_map": {},
            "known_facts": [],
            "dialogue_profile": {
                "profile_id": "dialogue.soldier",
                "voice_id": "voice.common",
                "tone_tags": ["military"],
                "schema_version": 1,
            },
            "history_refs": [f"unit:{unit_id}"],
            "anchor": False,
            "profile_flags": [],
            "unit_id": unit_id,
        }
        people[person_id] = person
        unit["person_id"] = person_id
        unit["person_name"] = name
        if not alive:
            tombstones.setdefault(
                person_id,
                {
                    "kind": "person",
                    "display_name": name,
                    "cause_id": "combat",
                    "linked_unit_id": unit_id,
                },
            )
            if unit_id in tombstones:
                tombstones[unit_id]["person_id"] = person_id
                tombstones[unit_id]["display_name"] = name

    world["ids"] = allocator.to_dict()
    return world


def ensure_unit_person_links(state: Any) -> list[str]:
    """Mutate a live WorldState so every unit has person_id. Idempotent."""
    created: list[str] = []
    people_svc = PeopleService(state)
    for unit_id, unit in sorted((state.units or {}).items()):
        pid = unit.get("person_id")
        if pid and pid in state.people:
            state.people[pid]["unit_id"] = unit_id
            if not state.people[pid].get("occupation") and state.people[pid].get("role") == "soldier":
                state.people[pid]["occupation"] = "soldier"
            continue
        name = stable_soldier_name(
            unit_id,
            existing=unit.get("person_name") or unit.get("given_name"),
        )
        person = people_svc.create_person(
            name=name,
            affiliation=str(unit.get("faction_id")) if unit.get("faction_id") else None,
            role="soldier",
            node_id=str(unit.get("node_id") or unit.get("home_node_id") or "") or None,
            position=list(unit.get("position") or [0.0, 0.0]),
            dialogue_profile="dialogue.soldier",
            cultural_appearance={
                "culture_id": "culture.common",
                "appearance_id": "appearance.soldier",
            },
            history_refs=[f"unit:{unit_id}"],
            profile_flags=[],
        )
        person_id = person["id"]
        state.people[person_id]["occupation"] = "soldier"
        state.people[person_id]["unit_id"] = unit_id
        unit["person_id"] = person_id
        unit["person_name"] = name
        if not unit.get("alive", True) or str(unit.get("status") or "") == "dead":
            people_svc.record_death(person_id, cause_id="combat")
        created.append(person_id)
    if hasattr(state, "_schema_version"):
        state._schema_version = SCHEMA_VERSION
    return created

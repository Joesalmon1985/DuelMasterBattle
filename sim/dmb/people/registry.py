"""Persistent people identity and deep profiles (C09 / T028 / T077)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError

PROFILE_SCHEMA_VERSION = 1

# Profile states are flags/status overlays on the same person record — never a replacement ID.
PROFILE_STATES = frozenset({"leader", "anchor", "worker", "displaced"})
STATUS_VALUES = frozenset(
    {"active", "employed", "idle", "displaced", "dead", "leader", "worker"}
)

DEFAULT_TYPED_PREFERENCES: list[dict[str, Any]] = [
    {"trait_id": "pref.diligent", "kind": "work", "strength": 1},
    {"trait_id": "pref.curious", "kind": "curiosity", "strength": 1},
    {"trait_id": "pref.loyal", "kind": "social", "strength": 1},
]

_CONTENT_ROOT = (
    Path(__file__).resolve().parents[3] / "godot_project" / "content" / "source" / "people"
)


def _clamp_relationship(score: int) -> int:
    return max(-100, min(100, int(score)))


def relationship_band(score: int) -> int:
    """Map −100..100 relationship storage to Aspect modifier −1/0/+1 (C09)."""
    if score <= -25:
        return -1
    if score >= 25:
        return 1
    return 0


def _normalize_preference(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        return {
            "trait_id": raw if raw.startswith("pref.") else f"pref.{raw}",
            "kind": "work",
            "strength": 1,
        }
    if not isinstance(raw, dict):
        raise TypeValidationError("preference must be string or typed object")
    trait_id = str(raw.get("trait_id") or raw.get("id") or "")
    if not trait_id:
        raise TypeValidationError("preference requires trait_id")
    kind = str(raw.get("kind") or "work")
    strength = int(raw.get("strength", 1))
    return {"trait_id": trait_id, "kind": kind, "strength": strength}


def _normalize_preferences(prefs: list[Any] | None) -> list[dict[str, Any]]:
    source = list(prefs) if prefs is not None else list(DEFAULT_TYPED_PREFERENCES)
    normalized = [_normalize_preference(item) for item in source[:3]]
    while len(normalized) < 3:
        normalized.append(deepcopy(DEFAULT_TYPED_PREFERENCES[len(normalized)]))
    return normalized[:3]


def _normalize_dialogue_profile(
    profile: dict[str, Any] | str | None, *, role: str
) -> dict[str, Any]:
    if isinstance(profile, str):
        return {
            "profile_id": profile,
            "voice_id": "voice.common",
            "tone_tags": [],
            "schema_version": PROFILE_SCHEMA_VERSION,
        }
    if profile is None:
        return {
            "profile_id": f"dialogue.{role}",
            "voice_id": "voice.common",
            "tone_tags": [],
            "schema_version": PROFILE_SCHEMA_VERSION,
        }
    return {
        "profile_id": str(profile.get("profile_id") or f"dialogue.{role}"),
        "voice_id": str(profile.get("voice_id") or "voice.common"),
        "tone_tags": list(profile.get("tone_tags") or []),
        "schema_version": int(profile.get("schema_version") or PROFILE_SCHEMA_VERSION),
    }


def _normalize_known_fact(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        return {
            "id": raw,
            "subject": raw,
            "predicate": "known",
            "value": True,
            "kind": "verified",
        }
    if not isinstance(raw, dict):
        raise TypeValidationError("known_fact must be string or object")
    fact_id = str(raw.get("id") or "")
    if not fact_id:
        raise TypeValidationError("known_fact requires id")
    return {
        "id": fact_id,
        "subject": str(raw.get("subject") or fact_id),
        "predicate": str(raw.get("predicate") or "known"),
        "value": raw.get("value", True),
        "kind": str(raw.get("kind") or "verified"),
        "source": raw.get("source"),
        "learned_time": raw.get("learned_time"),
    }


def load_people_content(root: Path | None = None) -> dict[str, Any]:
    """Load authored preference / dialogue / goal catalogues (content/source/people)."""
    base = root or _CONTENT_ROOT
    out: dict[str, Any] = {"preferences": [], "dialogue_profiles": [], "goals": []}
    mapping = {
        "preferences": "preferences.json",
        "dialogue_profiles": "dialogue_profiles.json",
        "goals": "goals.json",
    }
    for key, filename in mapping.items():
        path = base / filename
        if not path.is_file():
            continue
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            out[key] = payload
        elif isinstance(payload, dict):
            out[key] = list(payload.get(key) or payload.get("items") or [])
    return out


@dataclass
class PeopleService:
    state: WorldState

    def ensure_profile_fields(self, person_id: str) -> dict[str, Any]:
        """Fill missing T077 profile fields without replacing identity or history."""
        person = self.state.people.get(person_id)
        if person is None:
            raise TypeValidationError(f"unknown person {person_id}")
        role = str(person.get("role") or "worker")
        if "profile_schema_version" not in person:
            person["profile_schema_version"] = PROFILE_SCHEMA_VERSION
        if "cultural_appearance" not in person:
            person["cultural_appearance"] = {
                "culture_id": "culture.common",
                "appearance_id": "appearance.default",
            }
        prefs = person.get("preferences")
        person["preferences"] = _normalize_preferences(prefs if isinstance(prefs, list) else None)
        if "goal_ids" not in person or person["goal_ids"] is None:
            person["goal_ids"] = []
        else:
            person["goal_ids"] = list(person["goal_ids"])
        if "relationship_map" not in person or person["relationship_map"] is None:
            person["relationship_map"] = {}
        else:
            person["relationship_map"] = {
                str(k): _clamp_relationship(int(v)) for k, v in dict(person["relationship_map"]).items()
            }
        facts = person.get("known_facts")
        if not isinstance(facts, list):
            person["known_facts"] = []
        else:
            person["known_facts"] = [_normalize_known_fact(f) for f in facts]
        if "history_refs" not in person or person["history_refs"] is None:
            person["history_refs"] = []
        else:
            person["history_refs"] = list(person["history_refs"])
        person["dialogue_profile"] = _normalize_dialogue_profile(
            person.get("dialogue_profile"), role=role
        )
        if "profile_flags" not in person or person["profile_flags"] is None:
            flags = set()
            if person.get("anchor"):
                flags.add("anchor")
            if role == "leader":
                flags.add("leader")
            if role == "worker" or person.get("job_id"):
                flags.add("worker")
            if person.get("status") == "displaced":
                flags.add("displaced")
            person["profile_flags"] = sorted(flags)
        else:
            person["profile_flags"] = sorted(
                {str(f) for f in person["profile_flags"] if str(f) in PROFILE_STATES}
            )
        if "anchor" not in person:
            person["anchor"] = "anchor" in person["profile_flags"]
        return dict(person)

    def create_person(
        self,
        *,
        name: str,
        affiliation: str | None = None,
        role: str = "worker",
        node_id: str | None = None,
        preferences: list[Any] | None = None,
        workplace_id: str | None = None,
        job_id: str | None = None,
        goal_ids: list[str] | None = None,
        dialogue_profile: dict[str, Any] | str | None = None,
        cultural_appearance: dict[str, Any] | None = None,
        relationship_map: dict[str, int] | None = None,
        known_facts: list[Any] | None = None,
        history_refs: list[str] | None = None,
        area_id: str | None = None,
        position: list[float] | None = None,
        anchor: bool = False,
        profile_flags: list[str] | None = None,
    ) -> dict[str, Any]:
        person_id = self.state.ids.new("person")
        flags = {str(f) for f in (profile_flags or []) if str(f) in PROFILE_STATES}
        if anchor:
            flags.add("anchor")
        if role == "leader":
            flags.add("leader")
        if role == "worker" or job_id:
            flags.add("worker")
        record = {
            "id": person_id,
            "name": name,
            "display_name": name,
            "alive": True,
            "status": "employed" if job_id else "active",
            "affiliation": affiliation,
            "role": role,
            "job_id": job_id,
            "workplace_id": workplace_id,
            "node_id": node_id,
            "home_node_id": node_id,
            "area_id": area_id,
            "position": list(position) if position is not None else None,
            "profile_schema_version": PROFILE_SCHEMA_VERSION,
            "cultural_appearance": dict(
                cultural_appearance
                or {"culture_id": "culture.common", "appearance_id": "appearance.default"}
            ),
            "preferences": _normalize_preferences(preferences),
            "goal_ids": list(goal_ids or []),
            "relationship_map": {
                str(k): _clamp_relationship(int(v)) for k, v in dict(relationship_map or {}).items()
            },
            "known_facts": [_normalize_known_fact(f) for f in (known_facts or [])],
            "dialogue_profile": _normalize_dialogue_profile(dialogue_profile, role=role),
            "history_refs": list(history_refs or []),
            "anchor": "anchor" in flags,
            "profile_flags": sorted(flags),
        }
        self.state.people[person_id] = record
        return dict(record)

    def assign_job(self, person_id: str, job_id: str, workplace_id: str) -> dict[str, Any]:
        person = self.state.people.get(person_id)
        if person is None or not person.get("alive"):
            raise TypeValidationError(f"unknown or dead person {person_id}")
        self.ensure_profile_fields(person_id)
        # One active workplace/job at a time; changing workplace keeps ID.
        for other_id, other in self.state.people.items():
            if other_id == person_id or not other.get("alive"):
                continue
            if other.get("workplace_id") == workplace_id and other.get("job_id") == job_id:
                raise TypeValidationError("job already occupied")
            if other.get("id") == person_id:
                raise TypeValidationError("conflicting person identity")
        person["job_id"] = job_id
        person["workplace_id"] = workplace_id
        person["status"] = "employed"
        flags = set(person.get("profile_flags") or [])
        flags.add("worker")
        flags.discard("displaced")
        person["profile_flags"] = sorted(flags)
        return dict(person)

    def relocate(self, person_id: str, node_id: str) -> dict[str, Any]:
        person = self.state.people.get(person_id)
        if person is None:
            raise TypeValidationError(f"unknown person {person_id}")
        person["node_id"] = node_id
        return dict(person)

    def displace(self, person_id: str, *, reason: str = "building_destroyed") -> dict[str, Any]:
        person = self.state.people.get(person_id)
        if person is None:
            raise TypeValidationError(f"unknown person {person_id}")
        self.ensure_profile_fields(person_id)
        person["workplace_id"] = None
        person["job_id"] = None
        person["status"] = "displaced"
        person["displace_reason"] = reason
        # Alive: destruction displaces, does not kill.
        person["alive"] = True
        flags = set(person.get("profile_flags") or [])
        flags.add("displaced")
        person["profile_flags"] = sorted(flags)
        return dict(person)

    def record_death(self, person_id: str, *, cause_id: str | None = None) -> dict[str, Any]:
        person = self.state.people.get(person_id)
        if person is None:
            raise TypeValidationError(f"unknown person {person_id}")
        self.ensure_profile_fields(person_id)
        person["alive"] = False
        person["status"] = "dead"
        person["job_id"] = None
        person["workplace_id"] = None
        person["death_cause_id"] = cause_id
        # Preserve profile refs on the dead record; tombstone is the public remnant.
        self.state.tombstones[person_id] = {
            "kind": "person",
            "display_name": person.get("display_name") or person.get("name"),
            "cause_id": cause_id,
            "profile_refs": {
                "dialogue_profile_id": (person.get("dialogue_profile") or {}).get("profile_id"),
                "goal_ids": list(person.get("goal_ids") or []),
                "history_refs": list(person.get("history_refs") or []),
            },
        }
        return dict(person)

    def set_relationship(self, person_id: str, other_id: str, score: int) -> dict[str, Any]:
        person = self.state.people.get(person_id)
        if person is None:
            raise TypeValidationError(f"unknown person {person_id}")
        self.ensure_profile_fields(person_id)
        person["relationship_map"][str(other_id)] = _clamp_relationship(score)
        return dict(person)

    def add_known_fact(self, person_id: str, fact: Any) -> dict[str, Any]:
        person = self.state.people.get(person_id)
        if person is None:
            raise TypeValidationError(f"unknown person {person_id}")
        self.ensure_profile_fields(person_id)
        normalized = _normalize_known_fact(fact)
        facts = list(person.get("known_facts") or [])
        facts = [f for f in facts if f.get("id") != normalized["id"]]
        facts.append(normalized)
        person["known_facts"] = facts
        return dict(person)

    def set_goals(self, person_id: str, goal_ids: list[str]) -> dict[str, Any]:
        person = self.state.people.get(person_id)
        if person is None:
            raise TypeValidationError(f"unknown person {person_id}")
        self.ensure_profile_fields(person_id)
        person["goal_ids"] = list(goal_ids)
        return dict(person)

    def append_history(self, person_id: str, history_ref: str) -> dict[str, Any]:
        person = self.state.people.get(person_id)
        if person is None:
            raise TypeValidationError(f"unknown person {person_id}")
        self.ensure_profile_fields(person_id)
        refs = list(person.get("history_refs") or [])
        if history_ref not in refs:
            refs.append(history_ref)
        person["history_refs"] = refs
        return dict(person)

    def apply_profile_state(self, person_id: str, state_name: str, *, enabled: bool = True) -> dict[str, Any]:
        """Add/remove leader|anchor|worker|displaced without replacing the person record."""
        if state_name not in PROFILE_STATES:
            raise TypeValidationError(f"unknown profile state {state_name}")
        person = self.state.people.get(person_id)
        if person is None:
            raise TypeValidationError(f"unknown person {person_id}")
        self.ensure_profile_fields(person_id)
        flags = set(person.get("profile_flags") or [])
        if enabled:
            flags.add(state_name)
        else:
            flags.discard(state_name)
        person["profile_flags"] = sorted(flags)
        person["anchor"] = "anchor" in flags
        if state_name == "displaced" and enabled:
            person["status"] = "displaced"
        if state_name == "leader" and enabled:
            person["role"] = "leader"
        return dict(person)

    def promote_profile(
        self,
        person_id: str,
        *,
        anchor: bool = True,
        role: str | None = None,
        to_leader: bool = False,
    ) -> dict[str, Any]:
        """Promote role/anchor flags while preserving relationships, goals, facts and history."""
        person = self.state.people.get(person_id)
        if person is None:
            raise TypeValidationError(f"unknown person {person_id}")
        self.ensure_profile_fields(person_id)
        preserved = {
            "relationship_map": deepcopy(person.get("relationship_map") or {}),
            "known_facts": deepcopy(person.get("known_facts") or []),
            "goal_ids": list(person.get("goal_ids") or []),
            "history_refs": list(person.get("history_refs") or []),
            "preferences": deepcopy(person.get("preferences") or []),
            "dialogue_profile": deepcopy(person.get("dialogue_profile") or {}),
            "cultural_appearance": deepcopy(person.get("cultural_appearance") or {}),
            "id": person["id"],
        }
        person["anchor"] = bool(anchor)
        flags = set(person.get("profile_flags") or [])
        if anchor:
            flags.add("anchor")
        else:
            flags.discard("anchor")
        if to_leader:
            person["role"] = "leader"
            flags.add("leader")
        elif role:
            person["role"] = role
            if role == "leader":
                flags.add("leader")
            if role == "worker":
                flags.add("worker")
        person["profile_flags"] = sorted(flags)
        # Restore preserved profile refs explicitly (promotion must not wipe them).
        person["relationship_map"] = preserved["relationship_map"]
        person["known_facts"] = preserved["known_facts"]
        person["goal_ids"] = preserved["goal_ids"]
        person["history_refs"] = preserved["history_refs"]
        person["preferences"] = preserved["preferences"]
        person["dialogue_profile"] = preserved["dialogue_profile"]
        person["cultural_appearance"] = preserved["cultural_appearance"]
        return dict(person)

    def production_job_occupancy(self, workplace_id: str, job_id: str) -> dict[str, Any]:
        """Return living occupant or explicit vacancy for a production job slot."""
        living: list[str] = []
        for person_id, person in self.state.people.items():
            if (
                person.get("alive")
                and person.get("workplace_id") == workplace_id
                and person.get("job_id") == job_id
            ):
                living.append(person_id)
        if len(living) > 1:
            raise TypeValidationError(
                f"production job {workplace_id}/{job_id} has multiple living occupants"
            )
        if living:
            occupant = self.ensure_profile_fields(living[0])
            return {
                "workplace_id": workplace_id,
                "job_id": job_id,
                "vacant": False,
                "person_id": living[0],
                "anchor": bool(occupant.get("anchor")),
            }
        return {
            "workplace_id": workplace_id,
            "job_id": job_id,
            "vacant": True,
            "person_id": None,
            "anchor": False,
        }

    def ensure_production_job_anchor(
        self,
        workplace_id: str,
        job_id: str,
        *,
        node_id: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Guarantee one living anchor worker or leave an explicit vacancy record."""
        occupancy = self.production_job_occupancy(workplace_id, job_id)
        if not occupancy["vacant"]:
            person_id = occupancy["person_id"]
            assert person_id is not None
            return self.promote_profile(person_id, anchor=True, role="worker")
        # Explicit vacancy: do not invent a person unless caller registers via JobService.
        vacancies = self.state.definitions.setdefault("job_vacancies", {})
        key = f"{workplace_id}:{job_id}"
        vacancies[key] = {
            "workplace_id": workplace_id,
            "job_id": job_id,
            "node_id": node_id,
            "vacant": True,
            "person_id": None,
            "requested_name": name,
        }
        return dict(vacancies[key])

    def displace_workplace(self, workplace_id: str, *, reason: str = "building_destroyed") -> list[dict[str, Any]]:
        displaced = []
        for person_id, person in list(self.state.people.items()):
            if person.get("workplace_id") == workplace_id and person.get("alive"):
                displaced.append(self.displace(person_id, reason=reason))
        return displaced

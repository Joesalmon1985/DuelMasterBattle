"""Persistent people identity (C09 / T028)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError


@dataclass
class PeopleService:
    state: WorldState

    def create_person(
        self,
        *,
        name: str,
        affiliation: str | None = None,
        role: str = "worker",
        node_id: str | None = None,
        preferences: list[str] | None = None,
        workplace_id: str | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        person_id = self.state.ids.new("person")
        record = {
            "id": person_id,
            "name": name,
            "display_name": name,
            "alive": True,
            "status": "active",
            "affiliation": affiliation,
            "role": role,
            "job_id": job_id,
            "workplace_id": workplace_id,
            "node_id": node_id,
            "home_node_id": node_id,
            "preferences": list(preferences or ["diligent", "curious", "loyal"])[:3],
            "relationship_map": {},
            "known_facts": [],
            "goal_ids": [],
            "history_refs": [],
            "anchor": False,
        }
        self.state.people[person_id] = record
        return dict(record)

    def assign_job(self, person_id: str, job_id: str, workplace_id: str) -> dict[str, Any]:
        person = self.state.people.get(person_id)
        if person is None or not person.get("alive"):
            raise TypeValidationError(f"unknown or dead person {person_id}")
        # One active workplace/job at a time; changing workplace keeps ID.
        for other_id, other in self.state.people.items():
            if other_id == person_id or not other.get("alive"):
                continue
            if other.get("workplace_id") == workplace_id and other.get("job_id") == job_id:
                raise TypeValidationError("job already occupied")
            if other.get("id") == person_id:
                raise TypeValidationError("conflicting person identity")
        if person.get("job_id") and person.get("job_id") != job_id and person.get("workplace_id"):
            # Changing job: vacate old then assign — still same person ID.
            pass
        person["job_id"] = job_id
        person["workplace_id"] = workplace_id
        person["status"] = "employed"
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
        person["workplace_id"] = None
        person["job_id"] = None
        person["status"] = "displaced"
        person["displace_reason"] = reason
        # Alive: destruction displaces, does not kill.
        person["alive"] = True
        return dict(person)

    def record_death(self, person_id: str, *, cause_id: str | None = None) -> dict[str, Any]:
        person = self.state.people.get(person_id)
        if person is None:
            raise TypeValidationError(f"unknown person {person_id}")
        person["alive"] = False
        person["status"] = "dead"
        person["job_id"] = None
        person["workplace_id"] = None
        person["death_cause_id"] = cause_id
        self.state.tombstones[person_id] = {
            "kind": "person",
            "display_name": person.get("display_name") or person.get("name"),
            "cause_id": cause_id,
        }
        return dict(person)

    def promote_profile(self, person_id: str, *, anchor: bool = True, role: str | None = None) -> dict[str, Any]:
        person = self.state.people.get(person_id)
        if person is None:
            raise TypeValidationError(f"unknown person {person_id}")
        person["anchor"] = bool(anchor)
        if role:
            person["role"] = role
        return dict(person)

    def displace_workplace(self, workplace_id: str, *, reason: str = "building_destroyed") -> list[dict[str, Any]]:
        displaced = []
        for person_id, person in list(self.state.people.items()):
            if person.get("workplace_id") == workplace_id and person.get("alive"):
                displaced.append(self.displace(person_id, reason=reason))
        return displaced

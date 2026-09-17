"""Job vacancy and backfill (C09 / T028)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.people.registry import PeopleService


@dataclass
class JobService:
    state: WorldState
    people: PeopleService | None = None

    def __post_init__(self) -> None:
        if self.people is None:
            self.people = PeopleService(self.state)

    def _jobs(self) -> dict[str, Any]:
        return self.state.definitions.setdefault("jobs", {})

    def register_job(
        self,
        job_key: str,
        *,
        workplace_id: str,
        job_id: str,
        node_id: str | None = None,
        person_id: str | None = None,
    ) -> dict[str, Any]:
        jobs = self._jobs()
        if job_key in jobs and jobs[job_key].get("person_id") and jobs[job_key].get("person_id") != person_id:
            raise TypeValidationError(f"job key occupied: {job_key}")
        record = {
            "job_key": job_key,
            "workplace_id": workplace_id,
            "job_id": job_id,
            "node_id": node_id,
            "person_id": person_id,
            "modifier": 1.0,
            "vacant": person_id is None,
        }
        jobs[job_key] = record
        return dict(record)

    def vacate(self, job_key: str) -> dict[str, Any]:
        jobs = self._jobs()
        record = jobs.get(job_key)
        if record is None:
            raise TypeValidationError(f"unknown job {job_key}")
        person_id = record.get("person_id")
        if person_id and person_id in self.state.people:
            person = self.state.people[person_id]
            if person.get("workplace_id") == record.get("workplace_id"):
                person["job_id"] = None
                person["workplace_id"] = None
                if person.get("alive") and person.get("status") == "employed":
                    person["status"] = "idle"
        record["person_id"] = None
        record["vacant"] = True
        return dict(record)

    def set_modifier(self, job_key: str, modifier: float) -> dict[str, Any]:
        jobs = self._jobs()
        record = jobs.get(job_key)
        if record is None:
            raise TypeValidationError(f"unknown job {job_key}")
        record["modifier"] = float(modifier)
        return dict(record)

    def person_active_jobs(self, person_id: str) -> list[str]:
        jobs = self._jobs()
        return [key for key, rec in jobs.items() if rec.get("person_id") == person_id and not rec.get("vacant")]

    def assign_person(self, job_key: str, person_id: str) -> dict[str, Any]:
        jobs = self._jobs()
        record = jobs.get(job_key)
        if record is None:
            raise TypeValidationError(f"unknown job {job_key}")
        if not record.get("vacant") and record.get("person_id") not in (None, person_id):
            raise TypeValidationError("job not vacant")
        # Reject conflicting active jobs for the same person.
        for other_key, other in jobs.items():
            if other_key == job_key:
                continue
            if other.get("person_id") == person_id and not other.get("vacant"):
                raise TypeValidationError("person already holds conflicting active job")
        assert self.people is not None
        self.people.assign_job(person_id, str(record["job_id"]), str(record["workplace_id"]))
        record["person_id"] = person_id
        record["vacant"] = False
        return dict(record)

    def backfill_tick(self, *, name_prefix: str = "Worker") -> list[dict[str, Any]]:
        """Fill vacant jobs with new person IDs (ordinary vacant jobs)."""
        assert self.people is not None
        created: list[dict[str, Any]] = []
        jobs = self._jobs()
        for job_key, record in sorted(jobs.items()):
            if not record.get("vacant"):
                continue
            person = self.people.create_person(
                name=f"{name_prefix}-{job_key}",
                affiliation=None,
                role="worker",
                node_id=record.get("node_id"),
                workplace_id=str(record["workplace_id"]),
                job_id=str(record["job_id"]),
            )
            record["person_id"] = person["id"]
            record["vacant"] = False
            created.append(person)
        return created

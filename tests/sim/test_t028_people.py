"""T028 people identity, jobs, backfill and displacement."""

from __future__ import annotations

import pytest

from sim.dmb.construction.buildings import BuildingService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.people.jobs import JobService
from sim.dmb.people.registry import PeopleService


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t028"), ids=IdAllocator(WorldId("world:t028")))


def test_workplace_change_keeps_person_id() -> None:
    state = _world()
    people = PeopleService(state)
    buildings = BuildingService(state)
    a = buildings.create("building.primary", node_id="node:1", faction_id="f:1", slot_index=0)
    b = buildings.create("building.primary", node_id="node:1", faction_id="f:1", slot_index=1)
    person = people.create_person(name="Ada", node_id="node:1")
    people.assign_job(person["id"], "job.primary_worker", a["id"])
    original = person["id"]
    people.assign_job(original, "job.primary_worker", b["id"])
    assert state.people[original]["workplace_id"] == b["id"]
    assert state.people[original]["id"] == original


def test_backfill_creates_different_id() -> None:
    state = _world()
    people = PeopleService(state)
    jobs = JobService(state, people)
    buildings = BuildingService(state)
    plant = buildings.create("building.factory", node_id="node:1", faction_id="f:1", slot_index=0)
    first = people.create_person(name="Old", node_id="node:1")
    jobs.register_job("factory:0", workplace_id=plant["id"], job_id="job.factory_worker", node_id="node:1")
    jobs.assign_person("factory:0", first["id"])
    jobs.vacate("factory:0")
    created = jobs.backfill_tick()
    assert len(created) == 1
    assert created[0]["id"] != first["id"]
    assert state.definitions["jobs"]["factory:0"]["person_id"] == created[0]["id"]


def test_conflicting_jobs_rejected() -> None:
    state = _world()
    people = PeopleService(state)
    jobs = JobService(state, people)
    buildings = BuildingService(state)
    a = buildings.create("building.primary", node_id="node:1", faction_id="f:1", slot_index=0)
    b = buildings.create("building.processor", node_id="node:1", faction_id="f:1")
    person = people.create_person(name="Bob", node_id="node:1")
    jobs.register_job("p0", workplace_id=a["id"], job_id="job.primary_worker", node_id="node:1")
    jobs.register_job("pr0", workplace_id=b["id"], job_id="job.processor_worker", node_id="node:1")
    jobs.assign_person("p0", person["id"])
    with pytest.raises(TypeValidationError, match="conflicting"):
        jobs.assign_person("pr0", person["id"])


def test_building_destroy_displaces_not_kills() -> None:
    state = _world()
    people = PeopleService(state)
    buildings = BuildingService(state)
    plant = buildings.create("building.warehouse", node_id="node:1", faction_id="f:1")
    person = people.create_person(name="Cara", node_id="node:1")
    people.assign_job(person["id"], "job.warehouse_keeper", plant["id"])
    buildings.destroy(plant["id"], cause_id="cause:1")
    people.displace_workplace(plant["id"], reason="building_destroyed")
    surviving = state.people[person["id"]]
    assert surviving["alive"] is True
    assert surviving["status"] == "displaced"
    assert surviving["workplace_id"] is None

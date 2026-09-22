"""T078 stable village projection: preserve IDs, expand area, reachable exits."""

from __future__ import annotations

from sim.dmb.construction.buildings import BuildingService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.people.registry import PeopleService
from sim.dmb.world.projection import BASE_SIZE, GROW_STEP, LocalProjectionService


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t078"), ids=IdAllocator(WorldId("world:t078")))


def test_two_visits_preserve_ids_and_positions() -> None:
    state = _world()
    buildings = BuildingService(state)
    people = PeopleService(state)
    proj = LocalProjectionService(state)
    plant = buildings.create("building.factory", node_id="node:v", faction_id="f:1", slot_index=0)
    worker = people.create_person(name="Ada", node_id="node:v", workplace_id=plant["id"], job_id="job.factory_worker")
    people.assign_job(worker["id"], "job.factory_worker", plant["id"])

    first = proj.project("node:v")
    second = proj.project("node:v")
    assert first["seed"] == second["seed"]
    assert first["buildings"][0]["id"] == plant["id"]
    assert first["buildings"][0]["grid"] == second["buildings"][0]["grid"]
    assert first["people"][0]["id"] == worker["id"]
    assert first["people"][0]["grid"] == second["people"][0]["grid"]
    # Re-entry must not mint a new person.
    assert list(state.people.keys()) == [worker["id"]]


def test_destroyed_entities_stay_absent() -> None:
    state = _world()
    buildings = BuildingService(state)
    people = PeopleService(state)
    proj = LocalProjectionService(state)
    plant = buildings.create("building.factory", node_id="node:v", faction_id="f:1", slot_index=0)
    worker = people.create_person(name="Ben", node_id="node:v")
    view1 = proj.project("node:v")
    assert any(b["id"] == plant["id"] for b in view1["buildings"])
    buildings.destroy(plant["id"], cause_id="cause:1")
    proj.mark_destroyed("node:v", plant["id"])
    people.record_death(worker["id"], cause_id="cause:1")
    proj.mark_destroyed("node:v", worker["id"])
    view2 = proj.project("node:v")
    assert all(b["id"] != plant["id"] for b in view2["buildings"])
    assert all(p["id"] != worker["id"] for p in view2["people"])
    assert plant["id"] in view2["destroyed_ids"]
    assert worker["id"] in view2["destroyed_ids"]


def test_required_exits_reachable() -> None:
    state = _world()
    buildings = BuildingService(state)
    proj = LocalProjectionService(state)
    buildings.create("building.factory", node_id="node:v", faction_id="f:1", slot_index=0)
    view = proj.project("node:v")
    assert set(view["exits_reachable"]) >= {"exit.north", "exit.south", "exit.east", "exit.west"}
    layout = proj.layout_record("node:v")
    assert layout is not None
    assert len(proj.exits_reachable(layout)) == 4


def test_adding_processor_expands_area_not_drop() -> None:
    state = _world()
    buildings = BuildingService(state)
    proj = LocalProjectionService(state)
    ids = []
    # Force expansion beyond base packing capacity.
    for i in range(40):
        defn = "building.processor" if i % 2 else "building.factory"
        b = buildings.create(
            defn,
            node_id="node:v",
            faction_id="f:1",
            slot_index=i,
        )
        ids.append(b["id"])
    view = proj.project("node:v", manifest={"building_ids": ids})
    assert view["width"] >= BASE_SIZE
    assert view["height"] >= BASE_SIZE
    assert view["width"] == view["height"]
    assert (view["width"] - BASE_SIZE) % GROW_STEP == 0
    present = {b["id"] for b in view["buildings"]}
    assert present == set(ids)
    assert len(present) == 40
    # Area must have grown once packing exceeded the 48×48 baseline.
    assert view["width"] > BASE_SIZE or view["height"] > BASE_SIZE


def test_override_persists_across_project() -> None:
    state = _world()
    buildings = BuildingService(state)
    proj = LocalProjectionService(state)
    plant = buildings.create("building.warehouse", node_id="node:v", faction_id="f:1")
    proj.project("node:v")
    proj.save_override("node:v", {"entity_id": plant["id"], "label": "West Shed"})
    again = proj.project("node:v")
    assert again["overrides"][plant["id"]]["label"] == "West Shed"


def test_save_roundtrip_preserves_layout() -> None:
    state = _world()
    buildings = BuildingService(state)
    proj = LocalProjectionService(state)
    plant = buildings.create("building.factory", node_id="node:v", faction_id="f:1", slot_index=0)
    before = proj.project("node:v")
    payload = state.to_dict()
    loaded = WorldState.from_dict(payload)
    again = LocalProjectionService(loaded).project("node:v")
    assert again["buildings"][0]["id"] == plant["id"]
    assert again["buildings"][0]["grid"] == before["buildings"][0]["grid"]
    assert again["width"] == before["width"]

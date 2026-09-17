"""T027 building definitions, slots, health capacity and units."""

from __future__ import annotations

import pytest

from sim.dmb.construction.buildings import (
    BuildingService,
    load_building_definitions,
    load_unit_definitions,
    usable_capacity,
)
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.content.catalog import DefinitionCatalog


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:t027"), ids=IdAllocator(WorldId("world:t027")))


def test_content_loads_and_catalog_validates() -> None:
    buildings = load_building_definitions()
    units = load_unit_definitions()
    assert "building.centre" in buildings
    assert "building.warehouse" in buildings
    assert "building.primary" in buildings
    assert "building.processor" in buildings
    assert "building.factory" in buildings
    assert len([u for u in units if u.startswith("unit.")]) == 6
    catalog = DefinitionCatalog()
    catalog.load(list(buildings.values()) + list(units.values()))
    assert catalog.catalog_hash


def test_duplicate_slots_fail() -> None:
    state = _world()
    svc = BuildingService(state)
    svc.create("building.factory", node_id="node:1", faction_id="faction:1", slot_index=0)
    with pytest.raises(TypeValidationError, match="duplicate slot"):
        svc.create("building.factory", node_id="node:1", faction_id="faction:1", slot_index=0)


def test_city_does_not_double_primary_slot_count() -> None:
    state = _world()
    state.settlements["settlement:1"] = {
        "id": "settlement:1",
        "node_id": "node:1",
        "faction_id": "faction:1",
        "tier": "settlement",
    }
    svc = BuildingService(state)
    centre = svc.create(
        "building.centre",
        node_id="node:1",
        faction_id="faction:1",
        settlement_id="settlement:1",
    )
    svc.create(
        "building.primary",
        node_id="node:1",
        faction_id="faction:1",
        slot_index=0,
        settlement_id="settlement:1",
    )
    svc.create(
        "building.primary",
        node_id="node:1",
        faction_id="faction:1",
        slot_index=1,
        settlement_id="settlement:1",
    )
    before = svc.primary_slot_count("node:1")
    assert before == 2
    svc.upgrade_in_place(centre["id"])
    assert state.settlements["settlement:1"]["tier"] == "city"
    assert state.settlements["settlement:1"]["primary_flow_multiplier"] == 2.0
    assert state.settlements["settlement:1"]["primary_slot_multiplier"] == 1.0
    assert svc.primary_slot_count("node:1") == before


def test_missing_definition_and_upgrade_mapping_fail() -> None:
    state = _world()
    svc = BuildingService(state)
    with pytest.raises(TypeValidationError, match="missing building definition"):
        svc.create("building.missing", node_id="node:1", faction_id="faction:1")
    # centre.city has no upgrade_ref
    city = svc.create("building.centre.city", node_id="node:1", faction_id="faction:1")
    with pytest.raises(TypeValidationError, match="missing upgrade mapping"):
        svc.upgrade_in_place(city["id"])


def test_damage_scales_capacity_destroy_explicit() -> None:
    state = _world()
    svc = BuildingService(state)
    b = svc.create("building.processor", node_id="node:1", faction_id="faction:1")
    assert b["usable_capacity"] == pytest.approx(1.0)
    half = svc.damage(b["id"], 100)
    assert half["health"] == 100
    assert half["usable_capacity"] == pytest.approx(0.5)
    assert usable_capacity(100, 200) == pytest.approx(0.5)
    destroyed = svc.damage(b["id"], 1000)
    assert destroyed["status"] == "destroyed"
    assert destroyed["usable_capacity"] == 0.0
    cap = svc.capacity_state(b["id"])
    assert cap["status"] == "destroyed"
    assert cap["usable_capacity"] == 0.0


def test_repair_restores_full_health() -> None:
    state = _world()
    svc = BuildingService(state)
    b = svc.create("building.warehouse", node_id="node:1", faction_id="faction:1")
    svc.damage(b["id"], 150)
    repaired = svc.repair(b["id"])
    assert repaired["health"] == repaired["max_health"] == 300
    assert repaired["usable_capacity"] == pytest.approx(1.0)


def test_baseline_facility_set_and_six_units() -> None:
    state = _world()
    svc = BuildingService(state)
    sid = "settlement:1"
    state.settlements[sid] = {"id": sid, "node_id": "node:1", "faction_id": "f:1", "tier": "settlement"}
    svc.create("building.centre", node_id="node:1", faction_id="f:1", settlement_id=sid)
    svc.create("building.warehouse", node_id="node:1", faction_id="f:1", settlement_id=sid)
    for i in range(3):
        svc.create(
            "building.primary",
            node_id="node:1",
            faction_id="f:1",
            slot_index=i,
            settlement_id=sid,
        )
    svc.create("building.processor", node_id="node:1", faction_id="f:1", settlement_id=sid)
    for i in range(3):
        svc.create(
            "building.factory",
            node_id="node:1",
            faction_id="f:1",
            slot_index=i,
            settlement_id=sid,
        )
    kinds = {r["slot_kind"] for r in state.buildings.values()}
    assert kinds == {"centre", "warehouse", "primary", "processor", "factory"}
    assert sum(1 for r in state.buildings.values() if r["slot_kind"] == "factory") == 3
    units = load_unit_definitions()
    assert len(units) == 6

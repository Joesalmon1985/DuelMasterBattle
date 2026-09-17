"""T029 Catan grants and hazard suppression queries."""

from __future__ import annotations

from sim.dmb.construction.buildings import BuildingService
from sim.dmb.construction.production import CatanProductionService, terrain_good
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.hazards.queries import catan_grant_suppressed, industrial_blocked
from sim.dmb.world.generation import TERRAIN_TO_GOOD


def _world() -> WorldState:
    state = WorldState(world_id=WorldId("world:t029"), ids=IdAllocator(WorldId("world:t029")))
    state.board = {
        "hex_terrain": {
            "hex:0,0": "woodland",
            "hex:1,0": "clay_mountains",
            "hex:0,1": "ore_mountains",
            "hex:-1,0": "fields",
            "hex:0,-1": "grazing_land",
            "hex:1,-1": "desert",
        },
        "hex_token": {
            "hex:0,0": 6,
            "hex:1,0": 6,
            "hex:0,1": 8,
            "hex:-1,0": 5,
            "hex:0,-1": 9,
            "hex:1,-1": 6,
        },
        "hex_nodes": {
            "hex:0,0": ["node:A"],
            "hex:1,0": ["node:A"],
            "hex:0,1": ["node:A"],
            "hex:-1,0": ["node:B"],
            "hex:0,-1": ["node:B"],
            "hex:1,-1": ["node:C"],
        },
        "node_hexes": {
            "node:A": ["hex:0,0", "hex:1,0", "hex:0,1"],
            "node:B": ["hex:-1,0", "hex:0,-1"],
            "node:C": ["hex:1,-1"],
        },
        "hazard_cubes": {},
        "industrial_balance": {"hex:0,1": 0},  # depleted ore must not stop Catan
    }
    return state


def test_terrain_token_map_complete() -> None:
    assert TERRAIN_TO_GOOD == {
        "woodland": "timber",
        "clay_mountains": "brick",
        "ore_mountains": "ore",
        "fields": "grain",
        "grazing_land": "wool",
        "desert": None,
    }
    for terrain, good in TERRAIN_TO_GOOD.items():
        assert terrain_good(terrain) == good


def test_settlement_one_city_two_desert_none() -> None:
    state = _world()
    buildings = BuildingService(state)
    wh = buildings.create("building.warehouse", node_id="node:A", faction_id="f:1")
    state.settlements["s:1"] = {
        "id": "s:1",
        "node_id": "node:A",
        "faction_id": "f:1",
        "tier": "settlement",
        "warehouse_id": wh["id"],
        "operational": True,
    }
    prod = CatanProductionService(state)
    out = prod.grant_for_roll(6)
    goods = {(g["good"], g["amount"]) for g in out["grants"]}
    assert ("timber", 1) in goods
    assert ("brick", 1) in goods
    assert all(g["good"] != "desert" for g in out["grants"])
    # Desert hex token 6 suppressed
    assert any(s["reason"] == "desert_or_no_catan_good" for s in out["suppressed"])

    state.settlements["s:1"]["tier"] = "city"
    out2 = prod.grant_for_roll(6)
    assert any(g["good"] == "timber" and g["amount"] == 2 for g in out2["grants"])


def test_cube_suppresses_industrial_depletion_does_not() -> None:
    state = _world()
    buildings = BuildingService(state)
    wh = buildings.create("building.warehouse", node_id="node:A", faction_id="f:1")
    state.settlements["s:1"] = {
        "id": "s:1",
        "node_id": "node:A",
        "faction_id": "f:1",
        "tier": "settlement",
        "warehouse_id": wh["id"],
        "operational": True,
    }
    prod = CatanProductionService(state)
    # Depleted industrial ore hex still grants Catan ore on 8
    out = prod.grant_for_roll(8)
    assert any(g["good"] == "ore" and g["amount"] == 1 for g in out["grants"])
    assert industrial_blocked(state.board, "hex:0,1") is False

    state.board["hazard_cubes"] = {"cube:1": {"hex_id": "hex:0,1", "active": True}}
    assert catan_grant_suppressed(state.board, "hex:0,1")
    assert industrial_blocked(state.board, "hex:0,1")
    out2 = prod.grant_for_roll(8)
    assert out2["grants"] == []
    assert any(s["reason"] == "catastrophe_cube" for s in out2["suppressed"])


def test_missing_warehouse_does_not_invent_stock() -> None:
    state = _world()
    state.settlements["s:1"] = {
        "id": "s:1",
        "node_id": "node:A",
        "faction_id": "f:1",
        "tier": "settlement",
        "operational": True,
    }
    prod = CatanProductionService(state)
    out = prod.grant_for_roll(6)
    assert out["grants"] == []
    assert state.stocks == {}
    assert any(s["reason"] == "missing_warehouse" for s in out["suppressed"])


def test_roll_seven_grants_nothing() -> None:
    state = _world()
    prod = CatanProductionService(state)
    assert prod.grant_for_roll(7)["grants"] == []

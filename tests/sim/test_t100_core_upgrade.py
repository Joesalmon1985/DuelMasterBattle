"""T100 — Historic core upgrades and one-time bootstrap grant."""

from __future__ import annotations

from fractions import Fraction

from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.eras.upgrades import CoreUpgradeService
from sim.dmb.industry import fraction, fraction_wire
from sim.dmb.logistics.stock import StockLedger


def _core_world() -> WorldState:
    wid = WorldId("world:t100")
    state = WorldState(world_id=wid, ids=IdAllocator(wid))
    state.factions["faction:1"] = {"id": "faction:1"}
    state.settlements["settlement:1"] = {
        "id": "settlement:1",
        "faction_id": "faction:1",
        "node_id": "node:1",
        "tier": "city",
        "operational": True,
        "warehouse_id": "building:wh",
        "centre_id": "building:centre",
    }
    state.buildings["building:centre"] = {
        "id": "building:centre",
        "def_id": "building.centre.city",
        "definition_id": "building.centre.city",
        "slot_kind": "centre",
        "settlement_id": "settlement:1",
        "faction_id": "faction:1",
        "node_id": "node:1",
        "status": "active",
        "active": True,
    }
    state.buildings["building:wh"] = {
        "id": "building:wh",
        "def_id": "building.warehouse",
        "definition_id": "building.warehouse",
        "slot_kind": "warehouse",
        "settlement_id": "settlement:1",
        "faction_id": "faction:1",
        "node_id": "node:1",
        "status": "active",
        "active": True,
    }
    for i in range(3):
        pid = f"building:primary:{i}"
        state.buildings[pid] = {
            "id": pid,
            "def_id": "building.primary",
            "slot_kind": "primary",
            "slot_index": i,
            "settlement_id": "settlement:1",
            "faction_id": "faction:1",
            "node_id": "node:1",
            "status": "active",
            "active": True,
        }
    state.buildings["building:processor"] = {
        "id": "building:processor",
        "def_id": "building.processor",
        "slot_kind": "processor",
        "settlement_id": "settlement:1",
        "faction_id": "faction:1",
        "node_id": "node:1",
        "status": "active",
        "active": True,
    }
    for i in range(3):
        fid = f"building:factory:{i}"
        state.buildings[fid] = {
            "id": fid,
            "def_id": "building.factory",
            "slot_kind": "factory",
            "slot_index": i,
            "settlement_id": "settlement:1",
            "faction_id": "faction:1",
            "node_id": "node:1",
            "status": "active",
            "active": True,
        }
        state.industry.setdefault("factories", {})[fid] = {
            "id": fid,
            "settlement_id": "settlement:1",
            "era": "prehistoric",
            "unit_def_id": "unit.ancient.skirmisher",
            "meter": fraction_wire(Fraction(1, 2)),
            "active": True,
        }
        state.industry.setdefault("routes", {})[fid] = {
            "factory_id": fid,
            "processor_id": "building:processor",
            "unit_def_id": "unit.ancient.skirmisher",
            "processed_units_per_unit": 2,
            "requested_weight": fraction_wire(Fraction(1)),
        }
    state.industry.setdefault("processors", {})["building:processor"] = {
        "building_id": "building:processor",
        "recipe_id": "recipe.prehistoric.pre_04",
        "era": "prehistoric",
        "input_a_channel_id": "channel:a",
        "input_b_channel_id": "channel:b",
        "output_capacity": fraction_wire(Fraction(1, 10)),
        "active": True,
    }
    state.industry.setdefault("channels", {})["channel:a"] = {"channel_id": "channel:a"}
    state.industry.setdefault("channels", {})["channel:b"] = {"channel_id": "channel:b"}
    # Compatible prior Catan stock.
    StockLedger(state).credit("store:building:wh", "timber", 1)
    StockLedger(state).credit("store:building:wh", "ore", 4)
    state.people["person:worker"] = {
        "id": "person:worker",
        "alive": True,
        "workplace_id": "building:factory:0",
        "settlement_id": "settlement:1",
        "node_id": "node:1",
    }
    return state


def test_city_becomes_one_vp_core_no_duplicate_slots_or_people() -> None:
    state = _core_world()
    before_buildings = len(state.buildings)
    before_people = set(state.people)
    primary_before = sum(1 for b in state.buildings.values() if b.get("slot_kind") == "primary")
    factory_before = sum(1 for b in state.buildings.values() if b.get("slot_kind") == "factory")

    result = CoreUpgradeService(state).upgrade_core("settlement:1", transition_id="tr:1")
    assert result["idempotent"] is False
    settlement = state.settlements["settlement:1"]
    assert settlement["tier"] == "settlement"
    assert ScoreService(state).settlement_vp(settlement) == 1
    assert len(state.buildings) == before_buildings
    assert set(state.people) == before_people
    assert sum(1 for b in state.buildings.values() if b.get("slot_kind") == "primary") == primary_before
    assert sum(1 for b in state.buildings.values() if b.get("slot_kind") == "factory") == factory_before
    assert state.buildings["building:centre"]["def_id"] == "building.centre.historic"
    assert state.buildings["building:factory:0"]["def_id"] == "building.factory.historic"
    assert state.people["person:worker"]["workplace_id"] == "building:factory:0"


def test_reload_grants_no_second_package_and_meters_reset() -> None:
    state = _core_world()
    ledger = StockLedger(state)
    CoreUpgradeService(state).upgrade_core("settlement:1", transition_id="tr:1")
    timber_after_first = ledger.available("store:building:wh", "timber")
    # 1 prior + 2 grant
    assert timber_after_first == 3
    assert ledger.available("store:building:wh", "ore") == 4  # retained compatible stock

    meters = [
        state.industry["factories"][fid]["meter"]
        for fid in ("building:factory:0", "building:factory:1", "building:factory:2")
    ]
    assert all(fraction(m) == 0 for m in meters)
    assert state.industry["factories"]["building:factory:0"]["unit_def_id"] == "unit.historic.skirmisher"

    again = CoreUpgradeService(state).upgrade_core("settlement:1", transition_id="tr:1")
    assert again["idempotent"] is True
    assert ledger.available("store:building:wh", "timber") == timber_after_first

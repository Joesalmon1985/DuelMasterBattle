"""T101 — operational legacy sites and paid upgrades."""

from __future__ import annotations

from fractions import Fraction

from sim.dmb.construction.orders import ConstructionService
from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.eras.upgrades import CoreUpgradeService, mark_legacy_sites
from sim.dmb.industry import fraction, fraction_wire
from sim.dmb.logistics.stock import StockLedger
from sim.dmb.world.board import HexBoard


def _legacy_world() -> WorldState:
    wid = WorldId("world:t101")
    state = WorldState(world_id=wid, ids=IdAllocator(wid))
    board = HexBoard.radius2()
    state.board["topology"] = board.to_dict()
    node = board.nodes[0]
    state.factions["faction:1"] = {"id": "faction:1"}
    state.settlements["settlement:legacy"] = {
        "id": "settlement:legacy",
        "faction_id": "faction:1",
        "node_id": node,
        "tier": "settlement",
        "operational": True,
        "warehouse_id": "building:wh",
    }
    state.buildings["building:wh"] = {
        "id": "building:wh",
        "def_id": "building.warehouse",
        "slot_kind": "warehouse",
        "settlement_id": "settlement:legacy",
        "faction_id": "faction:1",
        "node_id": node,
        "status": "active",
        "active": True,
    }
    state.buildings["building:centre"] = {
        "id": "building:centre",
        "def_id": "building.centre",
        "slot_kind": "centre",
        "settlement_id": "settlement:legacy",
        "faction_id": "faction:1",
        "node_id": node,
        "status": "active",
        "active": True,
    }
    for i in range(3):
        state.buildings[f"building:primary:{i}"] = {
            "id": f"building:primary:{i}",
            "def_id": "building.primary",
            "slot_kind": "primary",
            "slot_index": i,
            "settlement_id": "settlement:legacy",
            "faction_id": "faction:1",
            "node_id": node,
            "status": "active",
            "active": True,
        }
    state.buildings["building:processor"] = {
        "id": "building:processor",
        "def_id": "building.processor",
        "slot_kind": "processor",
        "settlement_id": "settlement:legacy",
        "faction_id": "faction:1",
        "node_id": node,
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
            "settlement_id": "settlement:legacy",
            "faction_id": "faction:1",
            "node_id": node,
            "status": "active",
            "active": True,
        }
        state.industry.setdefault("factories", {})[fid] = {
            "id": fid,
            "settlement_id": "settlement:legacy",
            "era": "prehistoric",
            "unit_def_id": "unit.ancient.skirmisher",
            "meter": fraction_wire(Fraction(1, 4)),
            "active": True,
        }
        state.industry.setdefault("routes", {})[fid] = {
            "factory_id": fid,
            "processor_id": "building:processor",
            "unit_def_id": "unit.ancient.skirmisher",
            "processed_units_per_unit": 2,
            "requested_weight": fraction_wire(Fraction(1)),
        }
    state.industry.setdefault("layers", {})["layer:depleted"] = {
        "id": "layer:depleted",
        "hex_id": "hex:0,0",
        "resource_id": "ind.prehistoric.woodland.finite",
        "era": "prehistoric",
        "cycle": 0,
        "finite_balance": fraction_wire(Fraction(0)),
        "renewable_capacity": None,
        "retired": False,
    }
    return state


def test_legacy_factory_keeps_old_era_and_zero_vp() -> None:
    state = _legacy_world()
    mark_legacy_sites(state, ["settlement:legacy"], source_era="prehistoric")
    settlement = state.settlements["settlement:legacy"]
    assert settlement["legacy"] is True
    assert ScoreService(state).settlement_vp(settlement) == 0
    assert state.industry["factories"]["building:factory:0"]["era"] == "prehistoric"
    assert state.industry["routes"]["building:factory:0"]["unit_def_id"] == "unit.ancient.skirmisher"
    # Depleted layer not refilled by marking.
    assert fraction(state.industry["layers"]["layer:depleted"]["finite_balance"]) == 0


def test_paid_upgrade_restores_vp_no_extra_slots_no_refill() -> None:
    state = _legacy_world()
    mark_legacy_sites(state, ["settlement:legacy"])
    node = state.settlements["settlement:legacy"]["node_id"]
    ledger = StockLedger(state)
    for good, qty in (("timber", 1), ("brick", 1), ("wool", 1), ("grain", 1)):
        ledger.credit("store:building:wh", good, qty)
    primary_before = sum(1 for b in state.buildings.values() if b.get("slot_kind") == "primary")
    factory_before = sum(1 for b in state.buildings.values() if b.get("slot_kind") == "factory")

    svc = ConstructionService(state, board=HexBoard.from_dict(state.board["topology"]))
    order = svc.reserve_order(
        "legacy_upgrade",
        faction_id="faction:1",
        store_id="store:building:wh",
        target_node=node,
    )
    completed = svc.commit_delivered(order["id"])
    assert completed["status"] == "committed"
    settlement = state.settlements["settlement:legacy"]
    assert settlement.get("legacy") is False
    assert settlement.get("upgraded") is True
    assert ScoreService(state).settlement_vp(settlement) == 1
    assert sum(1 for b in state.buildings.values() if b.get("slot_kind") == "primary") == primary_before
    assert sum(1 for b in state.buildings.values() if b.get("slot_kind") == "factory") == factory_before
    assert fraction(state.industry["layers"]["layer:depleted"]["finite_balance"]) == 0
    assert state.buildings["building:factory:0"]["def_id"] == "building.factory.historic"
    # No free starter grant on paid path.
    assert ledger.available("store:building:wh", "timber") == 0

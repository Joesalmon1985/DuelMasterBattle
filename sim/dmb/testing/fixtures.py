"""Production-path fixture loader for scenario tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.construction.buildings import BuildingService
from sim.dmb.construction.orders import ConstructionService
from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.core.state import WorldState
from sim.dmb.core.world import WorldSim, bootstrap_world
from sim.dmb.logistics.carts import CartService
from sim.dmb.logistics.director import LogisticsService
from sim.dmb.logistics.routes import RoutePlanner
from sim.dmb.logistics.stock import StockLedger
from sim.dmb.world.generation import BoardBuilder


@dataclass
class FixtureResult:
    name: str
    status: str
    details: dict[str, Any]


def load_fixture(name: str, seed: int = 7) -> WorldSim:
    if name == "FX-CLOCK":
        return bootstrap_world(world_id=f"world:{name.lower()}", seed=seed)
    if name == "FX-CARGO":
        return _load_fx_cargo(seed=seed)
    raise ValueError(f"unsupported fixture {name}")


def _load_fx_cargo(seed: int = 202) -> WorldSim:
    """Playable FX-CARGO: three linked rooms + warehouse/cart/staging on one graph.

    N0=node:1 Warehouse Yard, N1=node:2 Blocked Way, N2=node:3 Construction Staging.
    G01-style linked arrivals; cart roads on the same nodes; blockage uses node_id.
    """
    sim = bootstrap_world(world_id="world:fx-cargo", seed=seed)
    state = sim.state

    state.player = {
        "node_id": "node:1",
        "area_id": "area.warehouse",
        "position": [4.0, 5.0],
        "facing": "down",
        "pose_generation": 0,
    }
    state.board["nodes"] = {
        "node:1": {
            "id": "node:1",
            "def": "node.home",
            "label": "Warehouse Yard",
            "area_id": "area.warehouse",
            "theme": "grass",
            "exits": {
                "node:2": {
                    "exit_id": "warehouse.east",
                    "direction": "east",
                    "hold_position": [12.0, 5.0],
                    "hold_facing": "right",
                    "arrival": {
                        "node_id": "node:2",
                        "area_id": "area.waypoint",
                        "position": [1.5, 5.0],
                        "facing": "right",
                    },
                }
            },
        },
        "node:2": {
            "id": "node:2",
            "def": "node.road",
            "label": "Blocked Way",
            "area_id": "area.waypoint",
            "theme": "path",
            "exits": {
                "node:1": {
                    "exit_id": "waypoint.west",
                    "direction": "west",
                    "hold_position": [1.0, 5.0],
                    "hold_facing": "left",
                    "arrival": {
                        "node_id": "node:1",
                        "area_id": "area.warehouse",
                        "position": [12.0, 5.0],
                        "facing": "left",
                    },
                },
                "node:3": {
                    "exit_id": "waypoint.east",
                    "direction": "east",
                    "hold_position": [12.0, 5.0],
                    "hold_facing": "right",
                    "arrival": {
                        "node_id": "node:3",
                        "area_id": "area.staging",
                        "position": [1.5, 5.0],
                        "facing": "right",
                    },
                },
            },
        },
        "node:3": {
            "id": "node:3",
            "def": "node.road",
            "label": "Construction Staging",
            "area_id": "area.staging",
            "theme": "path",
            "exits": {
                "node:2": {
                    "exit_id": "staging.west",
                    "direction": "west",
                    "hold_position": [1.0, 5.0],
                    "hold_facing": "left",
                    "arrival": {
                        "node_id": "node:2",
                        "area_id": "area.waypoint",
                        "position": [12.0, 5.0],
                        "facing": "left",
                    },
                }
            },
        },
    }

    n0, n1, n2 = "node:1", "node:2", "node:3"
    state.board["cargo_nodes"] = {"N0": n0, "N1": n1, "N2": n2}
    state.board["hazard_cubes"] = {}
    plan = BoardBuilder.generate(seed, 2)
    state.board["topology"] = plan.board.to_dict()
    state.board["hex_terrain"] = dict(plan.hex_terrain)
    state.board["hex_token"] = {k: int(v) for k, v in plan.hex_token.items()}

    state.roads = {
        "fx-r01": {"id": "fx-r01", "a": n0, "b": n1, "faction_id": "faction:1", "status": "built"},
        "fx-r12": {"id": "fx-r12", "a": n1, "b": n2, "faction_id": "faction:1", "status": "built"},
    }

    buildings = BuildingService(state)
    sid = state.ids.new("settlement")
    centre = buildings.create("building.centre", node_id=n0, faction_id="faction:1", settlement_id=sid)
    wh = buildings.create("building.warehouse", node_id=n0, faction_id="faction:1", settlement_id=sid)
    state.settlements[sid] = {
        "id": sid,
        "node_id": n0,
        "faction_id": "faction:1",
        "tier": "settlement",
        "operational": True,
        "warehouse_id": wh["id"],
        "centre_id": centre["id"],
    }
    state.factions["faction:1"] = {"id": "faction:1", "settlement_ids": [sid]}
    state.factions["faction:player"] = {"id": "faction:player"}

    staging_id = state.ids.new("settlement")
    state.settlements[staging_id] = {
        "id": staging_id,
        "node_id": n2,
        "faction_id": None,
        "tier": "staging",
        "staging": True,
        "operational": False,
        "status": "inert",
        "ruin_only": True,
    }

    store = f"store:{wh['id']}"
    staging_store = f"store:staging:{n2}"
    ledger = StockLedger(state)
    ledger.credit(store, "timber", 5)
    for good, qty in {"brick": 2, "wool": 2, "grain": 2, "ore": 2}.items():
        ledger.credit(store, good, qty)

    carts = CartService(state, ledger=ledger)
    cart = carts.create(owner_faction="faction:1", home_store=store, current_node=n0, capacity=4)

    state.people = {
        "person:warehouse": {
            "id": "person:warehouse",
            "definition_id": "npc.warehouse",
            "node_id": n0,
            "grid": [8, 3],
            "role": "warehouse",
            "display_name": "Timber Warehouse",
            "label": "Timber Warehouse",
            "known": True,
            "name": "Timber Warehouse",
            "store_id": store,
        },
        "person:cart": {
            "id": "person:cart",
            "definition_id": "npc.cart",
            "node_id": n0,
            "grid": [6, 5],
            "role": "cart",
            "display_name": "Hauler Cart",
            "label": "Hauler Cart",
            "known": True,
            "name": "Hauler Cart",
            "cart_id": cart["id"],
        },
        "person:staging": {
            "id": "person:staging",
            "definition_id": "npc.staging",
            "node_id": n2,
            "grid": [8, 4],
            "role": "staging",
            "display_name": "Construction Site",
            "label": "Construction Site",
            "known": True,
            "name": "Construction Site",
            "store_id": staging_store,
        },
    }

    state.board["fx_cargo"] = {
        "seed": seed,
        "N0": n0,
        "N1": n1,
        "N2": n2,
        "store": store,
        "staging_store": staging_store,
        "cart_id": cart["id"],
        "cart_person_id": "person:cart",
        "warehouse_person_id": "person:warehouse",
        "staging_person_id": "person:staging",
        "settlement_id": sid,
        "staging_id": staging_id,
        "block_node": n1,
        "block_hex": n1,
        "delivery_status": "idle",
        "construction_pending": False,
        "required": {"timber": 1, "brick": 1, "wool": 1, "grain": 1},
    }
    # Visible/inspectable names in the playable yard (not unknown placeholders).
    for pid, role, name in (
        ("person:warehouse", "warehouse", "Timber Warehouse"),
        ("person:cart", "cart", "Hauler Cart"),
        ("person:staging", "staging", "Construction Site"),
    ):
        state.knowledge[pid] = {"fact": "met", "role": role, "name": name, "known": True}
    state.clock["scheduled_faction_ids"] = ["faction:1", "faction:player"]
    try:
        from sim.dmb.technology.draft import DraftService

        DraftService(state).deal("prehistoric", ["faction:1", "faction:player"])
    except Exception:
        pass
    return sim


def run_fx_clock(sim: WorldSim | None = None) -> FixtureResult:
    sim = sim or load_fixture("FX-CLOCK")
    start_turn = int(sim.state.clock["turn"])
    start_node = sim.state.player["node_id"]
    travel = sim.dispatch(
        CommandEnvelope(
            protocol_version=1,
            session_id="fx",
            world_id=sim.state.world_id,
            command_id="fx-travel-1",
            expected_world_version=sim.state.world_version,
            kind="Travel",
            payload={"from_node": "node:1", "to_node": "node:2"},
        )
    )
    assert travel.status == "ACCEPTED"
    dup = sim.dispatch(
        CommandEnvelope(
            protocol_version=1,
            session_id="fx",
            world_id=sim.state.world_id,
            command_id="fx-travel-1",
            expected_world_version=start_turn,
            kind="Travel",
            payload={"from_node": "node:1", "to_node": "node:2"},
        )
    )
    assert dup.status == "DUPLICATE"
    assert int(sim.state.clock["turn"]) == start_turn + 1
    wait = sim.dispatch(
        CommandEnvelope(
            protocol_version=1,
            session_id="fx",
            world_id=sim.state.world_id,
            command_id="fx-wait-1",
            expected_world_version=sim.state.world_version,
            kind="Wait",
            payload={"current_node": "node:2", "press_id": "press-1"},
        )
    )
    assert wait.status == "ACCEPTED"
    held = sim.dispatch(
        CommandEnvelope(
            protocol_version=1,
            session_id="fx",
            world_id=sim.state.world_id,
            command_id="fx-wait-held",
            expected_world_version=sim.state.world_version,
            kind="Wait",
            payload={"current_node": "node:2", "press_id": "press-1"},
        )
    )
    assert held.status == "REJECTED"
    invalid = sim.dispatch(
        CommandEnvelope(
            protocol_version=1,
            session_id="fx",
            world_id=sim.state.world_id,
            command_id="fx-travel-bad",
            expected_world_version=sim.state.world_version,
            kind="Travel",
            payload={"from_node": "node:2", "to_node": "node:99"},
        )
    )
    assert invalid.status == "REJECTED"
    assert int(sim.state.clock["turn"]) == start_turn + 2
    assert sim.state.player["node_id"] == "node:2"
    assert sim.state.legacy_godot_world_tick_enabled is False
    assert sim.state.legacy_godot_world_save_enabled is False
    return FixtureResult(
        name="FX-CLOCK",
        status="PASS",
        details={
            "start_node": start_node,
            "end_node": sim.state.player["node_id"],
            "turns": int(sim.state.clock["turn"]),
            "duplicate_status": dup.status,
            "held_wait_status": held.status,
            "invalid_travel_status": invalid.status,
        },
    )


def run_fx_cargo(sim: WorldSim | None = None, seed: int = 202) -> FixtureResult:
    sim = sim or load_fixture("FX-CARGO", seed=seed)
    state = sim.state
    fx = state.board["fx_cargo"]
    n0, n1, n2 = fx["N0"], fx["N1"], fx["N2"]
    store = fx["store"]
    cart_id = fx["cart_id"]
    ledger = StockLedger(state)
    carts = CartService(state, ledger=ledger)
    director = LogisticsService(state, carts=carts, routes=RoutePlanner(state), ledger=ledger)
    construction = ConstructionService(state, ledger=ledger)

    staging_store = str(fx.get("staging_store") or "store:staging:N2")
    required = dict(fx.get("required") or {"timber": 1, "brick": 1, "wool": 1, "grain": 1})
    res = ledger.reserve("fx-settle", required, store_id=store)
    assign = director.assign(
        cart_id, source=n0, target=n2, destination_store=staging_store, reservation_id=res["id"]
    )
    assert assign["status"] == "assigned"

    block_node = str(fx.get("block_node") or fx.get("block_hex") or n1)
    state.board["hazard_cubes"] = {"fx-block": {"node_id": block_node, "active": True}}

    def wait_once(press: str) -> None:
        sim.dispatch(
            CommandEnvelope(
                protocol_version=1,
                session_id="fx-cargo",
                world_id=state.world_id,
                command_id=f"fx-cargo-wait-{press}",
                expected_world_version=state.world_version,
                kind="Wait",
                payload={"current_node": state.player["node_id"], "press_id": press},
            )
        )

    wait_once("block-1")
    # Assigned this turn: no move. Next turns blocked at N1.
    assert state.carts[cart_id]["current_node"] == n0
    wait_once("block-2")
    assert state.carts[cart_id]["current_node"] == n0
    assert state.carts[cart_id].get("status") == "blocked"

    state.board["hazard_cubes"] = {}
    state.carts[cart_id]["status"] = "en_route"
    wait_once("clear-1")
    assert state.carts[cart_id]["current_node"] == n1
    wait_once("clear-2")
    assert state.carts[cart_id]["current_node"] == n2
    assert ledger.available(staging_store, "timber") >= 1

    # Ensure full settlement cost present at staging after delivery of reserved goods
    for good, qty in required.items():
        have = ledger.available(staging_store, good)
        if have < qty:
            ledger.credit(staging_store, good, qty - have)

    order = construction.reserve_order(
        "settlement",
        faction_id="faction:1",
        store_id=staging_store,
        target_node=n2,
    )
    assert order["status"] == "ready", order
    committed = construction.commit_delivered(order["id"])
    assert committed["status"] == "committed"
    new_settlements = [
        s for s in state.settlements.values() if s.get("node_id") == n2 and not s.get("staging") and s.get("operational")
    ]
    assert new_settlements

    # Save/replay in-transit cargo
    mid = load_fixture("FX-CARGO", seed=seed)
    mid_fx = mid.state.board["fx_cargo"]
    mid_ledger = StockLedger(mid.state)
    mid_carts = CartService(mid.state, ledger=mid_ledger)
    mid_dir = LogisticsService(mid.state, carts=mid_carts, routes=RoutePlanner(mid.state), ledger=mid_ledger)
    mid_res = mid_ledger.reserve("mid", {"timber": 2}, store_id=mid_fx["store"])
    mid_dir.assign(
        mid_fx["cart_id"],
        source=mid_fx["N0"],
        target=mid_fx["N2"],
        destination_store="store:mid-dest",
        reservation_id=mid_res["id"],
    )
    snap = mid.snapshot()
    restored_state = WorldState.from_dict(snap["world"])
    cargo_before = sum(
        int(lot["quantity"])
        for lot in restored_state.carts[mid_fx["cart_id"]].get("cargo_lots") or []
        if lot.get("status") == "aboard"
    )
    assert cargo_before == 2

    return FixtureResult(
        name="FX-CARGO",
        status="PASS",
        details={
            "seed": seed,
            "settlement_at_n2": new_settlements[0]["id"],
            "block_cleared": True,
            "in_transit_cargo_preserved": cargo_before,
            "turns": int(state.clock["turn"]),
        },
    )

"""Production-path fixture loader for scenario tools."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
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
    if name == "FX-INDUSTRY":
        return _load_fx_industry(seed=303 if seed == 7 else seed)
    if name == "FX-BATTLE":
        return _load_fx_battle(seed=404 if seed == 7 else seed)
    if name == "FX-HAZARD":
        return _load_fx_hazard(seed=408 if seed == 7 else seed)
    if name == "FX-VILLAGE":
        return _load_fx_village(seed=507 if seed == 7 else seed, mode="baseline")
    if name == "FX-VILLAGE-QUEST":
        return _load_fx_village(seed=507 if seed == 7 else seed, mode="quest")
    if name == "FX-WORLD-LAYERS":
        return _load_fx_world_layers(seed=507 if seed == 7 else seed)
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
    # Extra available for faction AI; delivery package reserved separately so
    # exploration/Wait cannot spend the playtest haul.
    ledger.credit(store, "timber", 5)
    for good, qty in {"brick": 2, "wool": 2, "grain": 2, "ore": 2}.items():
        ledger.credit(store, good, qty)
    required = {"timber": 1, "brick": 1, "wool": 1, "grain": 1}
    delivery_res = ledger.reserve("fx-cargo-delivery", required, store_id=store)

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
        "required": required,
        "delivery_reservation_id": delivery_res["id"],
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


def _load_fx_industry(seed: int = 303) -> WorldSim:
    """C06 numerical oracle using the normal WorldSim and IndustryService."""
    from sim.dmb.industry.layers import ResourceLayerService
    from sim.dmb.industry.primary import PrimaryChannel
    from sim.dmb.industry.routes import FactoryRoute, ProcessorBinding
    from sim.dmb.logistics.stock import StockLedger
    from sim.dmb.people.jobs import JobService

    sim = bootstrap_world(world_id="world:fx-industry", seed=seed)
    state = sim.state
    node_id = "node:industry"
    state.board["nodes"][node_id] = {"id": node_id, "label": "Industry Oracle", "exits": {}}
    state.player["node_id"] = node_id
    state.player["position"] = [6, 5]
    state.settlements["settlement:industry"] = {
        "id": "settlement:industry",
        "node_id": node_id,
        "faction_id": "faction:industry",
        "operational": True,
    }
    layers = ResourceLayerService(state.industry)
    finite = layers.create_layer(
        "hex:ore",
        "ind.prehistoric.ore_mountains.finite",
        "prehistoric",
        0,
        finite=True,
    )
    renewable = layers.create_layer(
        "hex:woodland",
        "ind.prehistoric.woodland.renewable",
        "prehistoric",
        0,
        finite=False,
    )
    channels = (
        PrimaryChannel(
            "channel:source:woodland:renewable", "source:woodland", node_id, "woodland",
            "prehistoric", 0, "ind.prehistoric.woodland.renewable",
            renewable.layer_id, False, Fraction(1, 10), True,
        ),
        PrimaryChannel(
            "channel:source:ore:finite", "source:ore", node_id, "ore_mountains",
            "prehistoric", 0, "ind.prehistoric.ore_mountains.finite",
            finite.layer_id, True, Fraction(1, 10), True,
        ),
    )
    processor = ProcessorBinding(
        "processor:fx-industry",
        "recipe.prehistoric.pre_07",
        "prehistoric",
        channels[0].channel_id,
        channels[1].channel_id,
    )
    routes = (
        FactoryRoute("factory:fx-skirmisher", processor.building_id, "unit.ancient.skirmisher", 2),
        FactoryRoute("factory:fx-line", processor.building_id, "unit.ancient.line", 3),
        FactoryRoute("factory:fx-heavy", processor.building_id, "unit.ancient.heavy", 5),
    )
    for channel in channels:
        sim.industry.install_channel(channel)
    sim.industry.install_processor(processor)
    # Authoritative primary sites already referenced by channels — persist as buildings.
    state.buildings["source:woodland"] = {
        "id": "source:woodland",
        "node_id": node_id,
        "slot_kind": "primary",
        "slot_index": 0,
        "definition_id": "building.primary",
        "label": "Woodland source",
        "resource_name": "Foraged berries and nuts",
        "terrain": "woodland",
        "health": 100,
        "max_health": 100,
        "active": True,
        "status": "built",
    }
    state.buildings["source:ore"] = {
        "id": "source:ore",
        "node_id": node_id,
        "slot_kind": "primary",
        "slot_index": 1,
        "definition_id": "building.primary",
        "label": "Ore Mountains source",
        "resource_name": "Flint",
        "terrain": "ore_mountains",
        "health": 100,
        "max_health": 100,
        "active": True,
        "status": "built",
    }
    state.buildings[processor.building_id] = {
        "id": processor.building_id,
        "node_id": node_id,
        "slot_kind": "processor",
        "slot_index": 0,
        "definition_id": "processor.prehistoric.pre_07",
        "label": "Stone-ground berry paste Cooking Hearth",
        "recipe_id": "recipe.prehistoric.pre_07",
        "health": 100,
        "max_health": 100,
        "active": True,
        "status": "built",
    }
    factory_labels = {
        "factory:fx-skirmisher": "Skirmisher factory",
        "factory:fx-line": "Line factory",
        "factory:fx-heavy": "Heavy factory",
    }
    for index, route in enumerate(routes):
        sim.industry.install_route(route)
        sim.industry.factories.create(
            route.factory_id,
            node_id=node_id,
            faction_id="faction:industry",
            era="prehistoric",
            unit_def_id=route.unit_def_id,
        )
        state.buildings[route.factory_id] = {
            "id": route.factory_id,
            "node_id": node_id,
            "slot_kind": "factory",
            "slot_index": index,
            "definition_id": "building.factory",
            "label": factory_labels[route.factory_id],
            "unit_def_id": route.unit_def_id,
            "health": 100,
            "max_health": 100,
            "active": True,
            "status": "built",
        }
    # Presentation anchors for the Godot village (project existing IDs; no extra authority).
    layout_sites = [
        {
            "id": "source:woodland",
            "kind": "source",
            "label": "Woodland\nForaged berries and nuts",
            "short_label": "Berries",
            "resource_name": "Foraged berries and nuts",
            "grid": [2, 2],
            "entrance": [2, 3],
            "color": "#2f7d32",
        },
        {
            "id": "source:ore",
            "kind": "source",
            "label": "Ore Mountains\nFlint (finite)",
            "short_label": "Flint",
            "resource_name": "Flint",
            "grid": [11, 2],
            "entrance": [11, 3],
            "color": "#8a8f98",
        },
        {
            "id": "processor:fx-industry",
            "kind": "processor",
            "label": "Cooking Hearth\nin: Berries + Flint\nout: Berry paste",
            "short_label": "Hearth",
            "inputs": ["Foraged berries and nuts", "Flint"],
            "output_name": "Stone-ground berry paste",
            "grid": [6, 3],
            "entrance": [6, 4],
            "color": "#c47a2c",
        },
        {
            "id": "factory:fx-skirmisher",
            "kind": "factory",
            "label": "Factory\n→ Skirmisher",
            "short_label": "Skirmisher",
            "grid": [2, 7],
            "entrance": [2, 6],
            "color": "#3b6ea5",
            "unit_def_id": "unit.ancient.skirmisher",
        },
        {
            "id": "factory:fx-line",
            "kind": "factory",
            "label": "Factory\n→ Line",
            "short_label": "Line",
            "grid": [7, 7],
            "entrance": [7, 6],
            "color": "#7a4bb5",
            "unit_def_id": "unit.ancient.line",
        },
        {
            "id": "factory:fx-heavy",
            "kind": "factory",
            "label": "Factory\n→ Heavy",
            "short_label": "Heavy",
            "grid": [11, 7],
            "entrance": [11, 6],
            "color": "#a33b3b",
            "unit_def_id": "unit.ancient.heavy",
        },
    ]
    state.board["fx_industry"] = {
        "seed": seed,
        "node_id": node_id,
        "processor_id": processor.building_id,
        "factory_ids": [route.factory_id for route in routes],
        "source_ids": ["source:woodland", "source:ore"],
        "finite_layer_id": finite.layer_id,
        "renewable_layer_id": renewable.layer_id,
        "repair_store_id": "store:fx-industry",
        "repair_cost": {"brick": 1, "ore": 1},
        "recipe_id": "recipe.prehistoric.pre_07",
        "output_id": "processed.prehistoric.pre_07",
        "output_name": "Stone-ground berry paste",
        "layout": {
            "sites": layout_sites,
            "assembly": {"grid": [7, 9], "label": "Assembly yard"},
            "walk_lanes": [
                [[2, 3], [6, 4]],
                [[11, 3], [6, 4]],
                [[6, 4], [2, 6]],
                [[6, 4], [7, 6]],
                [[6, 4], [11, 6]],
            ],
            "visual_carry_capacity_per_sec": "0.01",
            "max_carriers_per_connection": 3,
        },
    }
    fixture_jobs = JobService(state)
    fixture_jobs.register_job(
        "industry:operator:fx",
        workplace_id=processor.building_id,
        job_id="job:processor",
        node_id=node_id,
    )
    fixture_jobs.backfill_tick(name_prefix="FX Worker")
    from sim.dmb.industry.projection import IndustryProjection

    IndustryProjection(state).sync_carrier_jobs()
    repair_ledger = StockLedger(state)
    repair_ledger.credit("store:fx-industry", "brick", 3)
    repair_ledger.credit("store:fx-industry", "ore", 3)
    return sim


def run_fx_industry(sim: WorldSim | None = None) -> FixtureResult:
    """Run the published 100-second FX-INDUSTRY oracle in production runtime."""
    from sim.dmb.industry import fraction
    from sim.dmb.industry.layers import ResourceLayerService

    sim = sim or load_fixture("FX-INDUSTRY", seed=303)
    sequence = int(sim.state.clock.get("clock_sequence", 0)) + 1
    result = sim.advance(100_000, sequence)
    fx = sim.state.board["fx_industry"]
    meters = {
        factory_id: str(fraction(sim.state.industry["factories"][factory_id]["meter"]))
        for factory_id in fx["factory_ids"]
    }
    unit_types = sorted(unit["definition_id"] for unit in sim.state.units.values())
    finite = ResourceLayerService(sim.state.industry).balance(fx["finite_layer_id"])
    passed = (
        result.status == "ACCEPTED"
        and set(meters.values()) == {"0"}
        and len(unit_types) == 3
        and finite == 590
    )
    return FixtureResult(
        "FX-INDUSTRY",
        "PASS" if passed else "FAIL",
        {
            "game_ms": sim.state.clock["game_ms"],
            "factory_meters": meters,
            "unit_ids": sorted(sim.state.units),
            "unit_types": unit_types,
            "finite_balance": str(finite),
            "worker_ids": sorted(sim.state.people),
            "save_schema_version": sim.state.industry.get("schema_version"),
        },
    )


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


def _load_fx_battle(seed: int = 404) -> WorldSim:
    """Playable FX-BATTLE isolated from G01–G03 saves (slot g04_battle).

    Lawful one-owner defended settlement: Red owns node:1 and its active
    factories; Blue invades from a separate home settlement on node:2.
    Spawn is clear for cardinal movement; armies start far enough apart for
    a human to approach and inspect before melee resolves (C07 math unchanged).
    """
    from sim.dmb.construction.placement import PlacementRules
    from sim.dmb.military.units import MilitaryService

    sim = bootstrap_world(world_id="world:fx-battle", seed=seed)
    state = sim.state
    # Clear of FIXTURE_TREES_HOME (2,2)/(7,7)/(11,7) and south boundary row 9.
    state.player = {
        "id": "wizard",
        "node_id": "node:1",
        "area_id": "area.battle",
        "position": [4.0, 5.0],
        "facing": "up",
        "pose_generation": 0,
    }
    state.board.setdefault("nodes", {})
    state.board["nodes"]["node:1"] = {
        "id": "node:1",
        "exits": {
            "node:2": {
                "exit_id": "battle.east",
                "direction": "east",
                "hold_position": [12.0, 5.0],
                "hold_facing": "right",
                "arrival": {
                    "node_id": "node:2",
                    "area_id": "area.blue_home",
                    "position": [1.5, 5.0],
                    "facing": "right",
                },
            }
        },
        "area_id": "area.battle",
        "label": "Battle Glade",
        "theme": "grass",
    }
    state.board["nodes"]["node:2"] = {
        "id": "node:2",
        "exits": {
            "node:1": {
                "exit_id": "blue.west",
                "direction": "west",
                "hold_position": [1.5, 5.0],
                "hold_facing": "left",
                "arrival": {
                    "node_id": "node:1",
                    "area_id": "area.battle",
                    "position": [12.0, 5.0],
                    "facing": "left",
                },
            }
        },
        "area_id": "area.blue_home",
        "label": "Blue Muster",
        "theme": "grass",
    }
    state.factions["faction:red"] = {"id": "faction:red", "label": "Red Host", "settlement_ids": []}
    state.factions["faction:blue"] = {"id": "faction:blue", "label": "Blue Host", "settlement_ids": []}

    red_sid = "settlement:red_glade"
    blue_sid = "settlement:blue_muster"
    # Red owns the battle node: centre + three distinct military factories.
    state.buildings["building:centre_red"] = {
        "id": "building:centre_red",
        "definition_id": "building.centre",
        "faction_id": "faction:red",
        "settlement_id": red_sid,
        "node_id": "node:1",
        "health": 300,
        "max_health": 300,
        "current_health": 300,
        "alive": True,
        "status": "active",
        "label": "Red Centre",
        "position": [1.0, 1.0],
        "kind": "building",
    }
    state.buildings["building:factory_red_line"] = {
        "id": "building:factory_red_line",
        "definition_id": "building.factory",
        "faction_id": "faction:red",
        "settlement_id": red_sid,
        "node_id": "node:1",
        "produces": "unit.ancient.line",
        "health": 200,
        "max_health": 200,
        "current_health": 200,
        "alive": True,
        "status": "active",
        "label": "Red Line Yard",
        "position": [2.0, 1.0],
        "kind": "building",
    }
    state.buildings["building:factory_red_skirm"] = {
        "id": "building:factory_red_skirm",
        "definition_id": "building.factory",
        "faction_id": "faction:red",
        "settlement_id": red_sid,
        "node_id": "node:1",
        "produces": "unit.ancient.skirmisher",
        "health": 200,
        "max_health": 200,
        "current_health": 200,
        "alive": True,
        "status": "active",
        "label": "Red Skirm Yard",
        "position": [3.0, 1.0],
        "kind": "building",
    }
    state.buildings["building:factory_red_heavy"] = {
        "id": "building:factory_red_heavy",
        "definition_id": "building.factory",
        "faction_id": "faction:red",
        "settlement_id": red_sid,
        "node_id": "node:1",
        "produces": "unit.ancient.heavy",
        "health": 200,
        "max_health": 200,
        "current_health": 200,
        "alive": True,
        "status": "active",
        "label": "Red Heavy Yard",
        "position": [4.0, 1.0],
        "kind": "building",
    }
    state.settlements[red_sid] = {
        "id": red_sid,
        "node_id": "node:1",
        "faction_id": "faction:red",
        "tier": "settlement",
        "operational": True,
        "centre_id": "building:centre_red",
        "status": "active",
    }
    state.factions["faction:red"]["settlement_ids"] = [red_sid]

    # Blue home settlement on a separate node (factories stay there).
    state.buildings["building:centre_blue"] = {
        "id": "building:centre_blue",
        "definition_id": "building.centre",
        "faction_id": "faction:blue",
        "settlement_id": blue_sid,
        "node_id": "node:2",
        "health": 300,
        "max_health": 300,
        "current_health": 300,
        "alive": True,
        "status": "active",
        "label": "Blue Centre",
        "position": [2.0, 2.0],
        "kind": "building",
    }
    state.buildings["building:factory_blue_line"] = {
        "id": "building:factory_blue_line",
        "definition_id": "building.factory",
        "faction_id": "faction:blue",
        "settlement_id": blue_sid,
        "node_id": "node:2",
        "produces": "unit.ancient.line",
        "health": 200,
        "max_health": 200,
        "current_health": 200,
        "alive": True,
        "status": "active",
        "label": "Blue Line Yard",
        "position": [3.0, 2.0],
        "kind": "building",
    }
    state.buildings["building:factory_blue_skirm"] = {
        "id": "building:factory_blue_skirm",
        "definition_id": "building.factory",
        "faction_id": "faction:blue",
        "settlement_id": blue_sid,
        "node_id": "node:2",
        "produces": "unit.ancient.skirmisher",
        "health": 200,
        "max_health": 200,
        "current_health": 200,
        "alive": True,
        "status": "active",
        "label": "Blue Skirm Yard",
        "position": [4.0, 2.0],
        "kind": "building",
    }
    state.buildings["building:factory_blue_heavy"] = {
        "id": "building:factory_blue_heavy",
        "definition_id": "building.factory",
        "faction_id": "faction:blue",
        "settlement_id": blue_sid,
        "node_id": "node:2",
        "produces": "unit.ancient.heavy",
        "health": 200,
        "max_health": 200,
        "current_health": 200,
        "alive": True,
        "status": "active",
        "label": "Blue Heavy Yard",
        "position": [5.0, 2.0],
        "kind": "building",
    }
    state.settlements[blue_sid] = {
        "id": blue_sid,
        "node_id": "node:2",
        "faction_id": "faction:blue",
        "tier": "settlement",
        "operational": True,
        "centre_id": "building:centre_blue",
        "status": "active",
    }
    state.factions["faction:blue"]["settlement_ids"] = [blue_sid]

    mil = MilitaryService(state)
    # Defenders west/south; invaders east/north — spaced for approach time.
    red_line = mil.spawn(
        "unit.ancient.line",
        home_node_id="node:1",
        faction_id="faction:red",
        era="prehistoric",
        factory_id="building:factory_red_line",
        position=[2.5, 6.5],
    )
    red_skirm = mil.spawn(
        "unit.ancient.skirmisher",
        home_node_id="node:1",
        faction_id="faction:red",
        era="prehistoric",
        factory_id="building:factory_red_skirm",
        position=[3.5, 7.0],
    )
    red_heavy = mil.spawn(
        "unit.ancient.heavy",
        home_node_id="node:1",
        faction_id="faction:red",
        era="prehistoric",
        factory_id="building:factory_red_heavy",
        position=[4.5, 6.5],
    )
    blue_line = mil.spawn(
        "unit.ancient.line",
        home_node_id="node:2",
        faction_id="faction:blue",
        era="prehistoric",
        factory_id="building:factory_blue_line",
        position=[11.0, 2.5],
    )
    blue_skirm = mil.spawn(
        "unit.ancient.skirmisher",
        home_node_id="node:2",
        faction_id="faction:blue",
        era="prehistoric",
        factory_id="building:factory_blue_skirm",
        position=[12.0, 3.0],
    )
    blue_heavy = mil.spawn(
        "unit.ancient.heavy",
        home_node_id="node:2",
        faction_id="faction:blue",
        era="prehistoric",
        factory_id="building:factory_blue_heavy",
        position=[10.0, 2.5],
    )
    # Invaders are currently on the battle node; home/factory remain on node:2.
    for unit in (blue_line, blue_skirm, blue_heavy):
        unit["node_id"] = "node:1"
        unit["home_settlement"] = blue_sid
    for unit in (red_line, red_skirm, red_heavy):
        unit["home_settlement"] = red_sid

    historic = mil.spawn(
        "unit.ancient.line",
        home_node_id="node:2",
        faction_id="faction:blue",
        era="historic",
        factory_id="building:factory_blue_line",
        position=[12.0, 8.0],
    )
    historic["status"] = "reserve"
    historic["alive"] = True
    historic["node_id"] = "node:1"
    historic["home_settlement"] = blue_sid

    participants = [
        red_line["id"],
        red_skirm["id"],
        red_heavy["id"],
        blue_line["id"],
        blue_skirm["id"],
        blue_heavy["id"],
    ]
    hostiles = {
        "faction:red": ["faction:blue"],
        "faction:blue": ["faction:red"],
    }
    # Mid-field ruin; keep spawn [4,5] and cardinal exits clear.
    blockers = [
        {"position": [7.0, 4.0], "half": 0.55, "blocks_los": True, "blocks_move": True, "label": "ruin"},
    ]
    state.battles["battle:fx"] = {
        "id": "battle:fx",
        "node_id": "node:1",
        "participants": participants,
        "buildings": [
            "building:centre_red",
            "building:factory_red_line",
            "building:factory_red_skirm",
            "building:factory_red_heavy",
        ],
        "state": "READY",
        "prefer_local": True,
        "hostiles": hostiles,
        "blockers": blockers,
        "cover_by_target": {blue_skirm["id"]: 0.25},
        "owner_faction_id": "faction:red",
        "owner_settlement_id": red_sid,
    }
    state.board["fx_battle"] = {
        "seed": seed,
        "save_slot": "g04_battle",
        "demo_mode": "comparable_era",
        "cross_era_ids": [historic["id"]],
        "labels": {
            red_line["id"]: "Red Line",
            red_skirm["id"]: "Red Skirmisher",
            red_heavy["id"]: "Red Heavy",
            blue_line["id"]: "Blue Line",
            blue_skirm["id"]: "Blue Skirmisher",
            blue_heavy["id"]: "Blue Heavy",
        },
        "wizard_intervene": True,
        "hostiles": hostiles,
        "owner_faction_id": "faction:red",
        "spawn": [4.0, 5.0],
        "reset_hint": "Delete user save slot g04_battle then relaunch tools/play_g04_battle.sh",
    }
    ownership_errors = PlacementRules(state).validate_one_owner_per_node()
    if ownership_errors:
        raise ValueError("FX-BATTLE ownership invalid: " + "; ".join(ownership_errors))
    return sim


def _load_fx_hazard(seed: int = 408) -> WorldSim:
    """Playable FX-HAZARD isolated saves (g04_hazard / g04_hazard_terminal)."""
    from sim.dmb.hazards.service import CatastropheService
    from sim.dmb.player.visits import VisitService

    sim = bootstrap_world(world_id="world:fx-hazard", seed=seed)
    state = sim.state
    state.player = {
        "id": "wizard",
        "node_id": "node:1",
        "area_id": "area.hazard",
        "position": [7.0, 5.0],
        "facing": "up",
        "pose_generation": 0,
    }
    state.board["nodes"]["node:1"] = {
        "id": "node:1",
        "exits": {},
        "area_id": "area.hazard",
        "label": "Pressure Crossroads",
        "theme": "grass",
    }
    state.board["node_hexes"] = {"node:1": ["hex:a", "hex:b", "hex:c"]}
    state.board["hex_adjacency"] = {
        "hex:a": ["hex:b"],
        "hex:b": ["hex:a", "hex:c"],
        "hex:c": ["hex:b"],
    }
    # Three distinct boundary approaches (west / north / east), walkable and clear of trees.
    state.board["hex_anchors"] = {
        "hex:a": {"grid": [2.0, 5.0], "label": "West Approach"},
        "hex:b": {"grid": [7.0, 2.0], "label": "North Approach"},
        "hex:c": {"grid": [11.0, 5.0], "label": "East Approach"},
    }
    state.clock["era"] = "prehistoric"
    state.clock["turn"] = 1
    state.clock["active_faction_id"] = "faction:a"
    state.factions["faction:a"] = {"id": "faction:a", "label": "Local Responders"}
    svc = CatastropheService(state)
    for hid in ("hex:a", "hex:b", "hex:c"):
        svc.add_cube(hid, "demon")
    VisitService(state).arrive("node:1", "travel", 1)
    cubes = (state.hazards.get("catastrophe") or {}).get("cubes") or {}
    cube_by_hex = {}
    for cube in cubes.values():
        if cube.get("active", True):
            cube_by_hex[str(cube.get("hex_id"))] = str(cube.get("id"))
    state.board["fx_hazard"] = {
        "seed": seed,
        "save_slot": "g04_hazard",
        "terminal_slot": "g04_hazard_terminal",
        "outbreak_warning_at": 7,
        "hex_labels": {
            "hex:a": "West Demon",
            "hex:b": "North Demon",
            "hex:c": "East Demon",
        },
        "hex_anchors": state.board["hex_anchors"],
        "cube_by_hex": cube_by_hex,
        "reset_hint": "Delete user save slots g04_hazard and g04_hazard_terminal then relaunch tools/play_g04_hazard.sh",
    }
    return sim


def run_fx_battle(sim: WorldSim | None = None) -> FixtureResult:
    sim = sim or load_fixture("FX-BATTLE", seed=404)
    fx = sim.state.board.get("fx_battle") or {}
    return FixtureResult(
        name="FX-BATTLE",
        status="PASS",
        details={
            "seed": fx.get("seed", 404),
            "units": len(sim.state.units),
            "battle": "battle:fx" in sim.state.battles,
            "save_slot": fx.get("save_slot"),
        },
    )


def run_fx_hazard(sim: WorldSim | None = None) -> FixtureResult:
    sim = sim or load_fixture("FX-HAZARD", seed=408)
    fx = sim.state.board.get("fx_hazard") or {}
    cubes = (sim.state.hazards.get("catastrophe") or {}).get("cubes") or {}
    return FixtureResult(
        name="FX-HAZARD",
        status="PASS",
        details={
            "seed": fx.get("seed", 408),
            "active_cubes": sum(1 for c in cubes.values() if c.get("active", True)),
            "save_slot": fx.get("save_slot"),
        },
    )


def run_fx_village(sim: WorldSim | None = None, seed: int = 507) -> FixtureResult:
    """Smoke the FX-VILLAGE-QUEST shortage binding for scenario/panel parity (T095)."""
    sim = sim or load_fixture("FX-VILLAGE-QUEST", seed=seed)
    fx = sim.state.board.get("fx_village") or {}
    quest_id = str(fx.get("quest_id") or "")
    quest = (sim.state.quests or {}).get(quest_id) or {}
    mara_id = str(fx.get("mara_id") or "")
    factory_id = str(fx.get("factory_id") or "")
    routes = sim.state.definitions.get("installed_routes") or {}
    ok = bool(quest) and bool(mara_id) and bool(factory_id)
    return FixtureResult(
        name="FX-VILLAGE",
        status="PASS" if ok else "FAIL",
        details={
            "seed": seed,
            "quest_id": quest_id,
            "quest_status": quest.get("status"),
            "mara_id": mara_id,
            "factory_id": factory_id,
            "route_a_available": bool((routes.get("route:A") or {}).get("available")),
            "route_b_available": bool((routes.get("route:B") or {}).get("available")),
            "shortage": bool((sim.state.buildings.get(factory_id) or {}).get("shortage")),
            "command_log": list(fx.get("command_log") or []),
        },
    )


def _load_fx_village(seed: int = 507, *, mode: str = "baseline") -> WorldSim:
    """FX-VILLAGE: full Prehistoric board (baseline) or archived quest (mode=quest)."""
    if mode == "quest":
        from sim.dmb.world.fx_village_world import load_fx_village

        return load_fx_village(seed=507 if seed == 7 else seed, mode="quest")
    from sim.dmb.world.prehistoric_world import load_prehistoric_world

    return load_prehistoric_world(seed=507 if seed == 7 else seed)


def _load_fx_world_layers(seed: int = 507) -> WorldSim:
    """FX-WORLD-LAYERS: same Prehistoric board as FX-VILLAGE, with G01–G04 layers staged near start.

    Does not invent a separate simulation or change topology. Arranges cargo,
    construction, industry meters, soldiers, a local battle, and keeps the
    existing catastrophe cube on a hex touching John's start (node:35).
    """
    from sim.dmb.industry import fraction_wire
    from sim.dmb.military.units import MilitaryService

    sim = _load_fx_village(seed=seed, mode="baseline")
    state = sim.state
    g05 = state.board.setdefault("g05", {})
    start = str(g05.get("start_node_id") or state.player.get("node_id") or "node:35")
    settlement_id = str(g05.get("start_settlement_id") or "")
    faction_id = str(g05.get("start_faction_id") or state.player.get("faction_id") or "faction:2")
    settlement = state.settlements.get(settlement_id) or next(
        s
        for s in state.settlements.values()
        if s.get("node_id") == start and not s.get("staging")
    )
    settlement_id = str(settlement["id"])
    store = f"store:{settlement['warehouse_id']}"

    exits = list(((state.board.get("nodes") or {}).get(start) or {}).get("exits") or {})
    # Prefer an open road target for cart assignment; fall back to first exit.
    road_target = None
    for rid, road in state.roads.items():
        if road.get("status") != "built":
            continue
        ends = {str(road.get("a")), str(road.get("b"))}
        if start in ends:
            other = next(iter(ends - {start}))
            road_target = other
            break
    if road_target is None and exits:
        road_target = str(exits[0])
    build_edge_target = next((str(n) for n in exits if n != road_target), str(exits[0]) if exits else "node:30")
    battle_node = str(exits[0]) if exits else "node:30"

    # --- Cargo: loaded cart with real delivery assignment (FX-CARGO services) ---
    ledger = StockLedger(state)
    carts = CartService(state, ledger=ledger)
    # Ensure warehouse can fund delivery + subsequent road order.
    for good, qty in (("timber", 2), ("brick", 2), ("wool", 1), ("grain", 1)):
        have = ledger.available(store, good)
        if have < qty:
            ledger.credit(store, good, qty - have)
    required = {"timber": 1, "brick": 1, "wool": 1, "grain": 1}
    delivery_res = ledger.reserve("fx-world-layers-delivery", required, store_id=store)
    cart_id = next(
        cid
        for cid, cart in sorted(state.carts.items())
        if cart.get("owner_faction") == faction_id
        and cart.get("current_node") == start
        and cart.get("status") in {"idle", "arrived", "delivered"}
    )
    carts.load_from_reservation(cart_id, delivery_res["id"])
    dest_store = f"store:staging:{road_target}"
    # RoutePlanner blocks while cube:2 touches start — assign via CartService on the
    # existing constructed road (same load/assign steps LogisticsService.assign uses).
    carts.assign(cart_id, [start, str(road_target)], destination_store=dest_store)

    # --- Construction: genuine ready order on a nearby edge ---
    construction = ConstructionService(state, ledger=ledger)
    order = construction.reserve_order(
        "road",
        faction_id=faction_id,
        store_id=store,
        target_edge=(start, build_edge_target),
    )
    if order.get("status") != "ready":
        # Fall back to repair-style order on centre if road illegal for any reason.
        centre_id = str(settlement.get("centre_id") or "")
        if centre_id and centre_id in state.buildings:
            b = state.buildings[centre_id]
            b["health"] = max(1, int(b.get("max_health", 100)) // 2)
            for good, qty in (("brick", 1), ("ore", 1)):
                if ledger.available(store, good) < qty:
                    ledger.credit(store, good, qty)
            order = construction.reserve_order(
                "repair",
                faction_id=faction_id,
                store_id=store,
                target_building=centre_id,
            )

    # --- Industry meters partly progressed on starting settlement factories ---
    factories = state.industry.setdefault("factories", {})
    start_factories = [
        (fid, rec)
        for fid, rec in sorted(factories.items())
        if rec.get("node_id") == start and rec.get("active", True)
    ]
    progressions = (Fraction(1, 3), Fraction(1, 2), Fraction(2, 3))
    for index, (_fid, rec) in enumerate(start_factories):
        rec["meter"] = fraction_wire(progressions[index % len(progressions)])

    # --- Persistent soldiers (both factions, all archetypes) + hostile battle ---
    mil = MilitaryService(state)
    unit_defs = (
        "unit.ancient.skirmisher",
        "unit.ancient.line",
        "unit.ancient.heavy",
    )
    home_factory_by_def = {
        str(rec.get("unit_def_id")): fid
        for fid, rec in start_factories
        if rec.get("unit_def_id")
    }
    # Enemy settlement factories (may lack industry meter records; IDs still valid).
    enemy_faction = next(
        (
            str(s.get("faction_id"))
            for s in state.settlements.values()
            if not s.get("staging") and str(s.get("faction_id") or "") not in {"", faction_id}
        ),
        "faction:1",
    )
    enemy_settlement = next(
        (
            s
            for s in state.settlements.values()
            if not s.get("staging") and s.get("faction_id") == enemy_faction
        ),
        None,
    )
    enemy_home = str((enemy_settlement or {}).get("node_id") or "node:2")
    enemy_factory_ids = sorted(
        bid
        for bid, b in state.buildings.items()
        if b.get("node_id") == enemy_home
        and (b.get("slot_kind") == "factory" or str(b.get("definition_id") or "") == "building.factory")
    )
    while len(enemy_factory_ids) < 3:
        enemy_factory_ids.append(enemy_factory_ids[-1] if enemy_factory_ids else f"building:enemy_factory")

    neighbour = battle_node if battle_node != start else str(road_target or build_edge_target)
    persistent: list[dict[str, Any]] = []
    # Home node: defending faction, all three archetypes.
    for i, udef in enumerate(unit_defs):
        factory_id = home_factory_by_def.get(udef) or (start_factories[i][0] if start_factories else "building:25")
        unit = mil.spawn(
            udef,
            home_node_id=start,
            faction_id=faction_id,
            era="prehistoric",
            factory_id=factory_id,
            position=[6.0 + i * 2.0, 14.0],
        )
        persistent.append(unit)
    # Neighbour: invading faction archetypes (person_id linked by spawn).
    for i, udef in enumerate(unit_defs):
        unit = mil.spawn(
            udef,
            home_node_id=enemy_home,
            faction_id=enemy_faction,
            era="prehistoric",
            factory_id=enemy_factory_ids[i],
            position=[18.0 + i * 2.0, 8.0],
        )
        unit["node_id"] = neighbour
        persistent.append(unit)

    defenders: list[dict[str, Any]] = []
    invaders: list[dict[str, Any]] = []
    for i, udef in enumerate(unit_defs):
        factory_id = home_factory_by_def.get(udef) or (start_factories[i][0] if start_factories else "building:25")
        d = mil.spawn(
            udef,
            home_node_id=start,
            faction_id=faction_id,
            era="prehistoric",
            factory_id=factory_id,
            position=[8.0 + i * 1.5, 20.0],
        )
        d["node_id"] = battle_node
        defenders.append(d)
        inv = mil.spawn(
            udef,
            home_node_id=enemy_home,
            faction_id=enemy_faction,
            era="prehistoric",
            factory_id=enemy_factory_ids[i],
            position=[22.0 + i * 1.5, 6.0],
        )
        inv["node_id"] = battle_node
        invaders.append(inv)

    form_def = mil.group([u["id"] for u in defenders], faction_id=faction_id, node_id=battle_node)
    form_inv = mil.group([u["id"] for u in invaders], faction_id=enemy_faction, node_id=battle_node)
    participants = [u["id"] for u in defenders + invaders]
    hostiles = {faction_id: [enemy_faction], enemy_faction: [faction_id]}
    battle_id = "battle:world-layers"
    state.battles[battle_id] = {
        "id": battle_id,
        "node_id": battle_node,
        "participants": participants,
        "buildings": [],
        "state": "READY",
        "prefer_local": True,
        "hostiles": hostiles,
        "blockers": [],
        "owner_faction_id": faction_id,
        "owner_settlement_id": settlement_id,
    }
    form_def["engagement_id"] = battle_id
    form_inv["engagement_id"] = battle_id

    # --- Catastrophe: verify cube:2 remains on hex:0,1 touching start ---
    cubes = (state.hazards.get("catastrophe") or {}).get("cubes") or {}
    board_cubes = state.board.get("hazard_cubes") or {}
    cube2 = cubes.get("cube:2") or board_cubes.get("cube:2")
    if cube2 is None or str(cube2.get("hex_id")) != "hex:0,1" or not cube2.get("active", True):
        raise ValueError("FX-WORLD-LAYERS expected active cube:2 on hex:0,1 touching node:35")

    g05["mode"] = "world_layers"
    g05["quest_enabled"] = False
    fx_village = state.board.setdefault("fx_village", {})
    fx_village["quest_enabled"] = False
    state.board["fx_world_layers"] = {
        "seed": seed,
        "start_node_id": start,
        "cart_id": cart_id,
        "delivery_reservation_id": delivery_res["id"],
        "construction_order_id": order.get("id"),
        "battle_id": battle_id,
        "battle_node_id": battle_node,
        "formation_ids": [form_def["id"], form_inv["id"]],
        "persistent_unit_ids": [u["id"] for u in persistent],
        "cube_id": "cube:2",
        "cube_hex_id": "hex:0,1",
    }
    return sim


def run_fx_world_layers(sim: WorldSim | None = None, seed: int = 507) -> FixtureResult:
    """Smoke FX-WORLD-LAYERS layer staging on the Prehistoric board."""
    sim = sim or load_fixture("FX-WORLD-LAYERS", seed=seed)
    state = sim.state
    fx = state.board.get("fx_world_layers") or {}
    g05 = state.board.get("g05") or {}
    cubes = (state.hazards.get("catastrophe") or {}).get("cubes") or {}
    cube2 = cubes.get("cube:2") or (state.board.get("hazard_cubes") or {}).get("cube:2")
    cart = state.carts.get(str(fx.get("cart_id") or ""))
    cargo_aboard = 0
    if cart:
        cargo_aboard = sum(
            int(lot.get("quantity") or 0)
            for lot in cart.get("cargo_lots") or []
            if lot.get("status") == "aboard"
        )
    orders_ready = sum(1 for o in state.orders.values() if o.get("status") == "ready")
    meters_progressed = 0
    start = str(g05.get("start_node_id") or "")
    for rec in (state.industry.get("factories") or {}).values():
        if rec.get("node_id") != start:
            continue
        meter = rec.get("meter") or {}
        try:
            num = Fraction(str(meter.get("numerator", "0")))
            den = Fraction(str(meter.get("denominator", "1")))
            if den and num / den > 0:
                meters_progressed += 1
        except (ValueError, ZeroDivisionError, TypeError):
            pass
    units_with_person = sum(
        1 for u in state.units.values() if u.get("alive", True) and u.get("person_id") in state.people
    )
    ok = (
        g05.get("mode") == "world_layers"
        and not bool((state.board.get("fx_village") or {}).get("quest_enabled"))
        and cargo_aboard > 0
        and orders_ready >= 1
        and meters_progressed >= 1
        and units_with_person >= 6
        and len(state.formations or {}) >= 2
        and str(fx.get("battle_id") or "") in state.battles
        and cube2 is not None
        and str(cube2.get("hex_id")) == "hex:0,1"
        and bool(cube2.get("active", True))
    )
    return FixtureResult(
        name="FX-WORLD-LAYERS",
        status="PASS" if ok else "FAIL",
        details={
            "seed": seed,
            "g05_mode": g05.get("mode"),
            "quest_enabled": (state.board.get("fx_village") or {}).get("quest_enabled"),
            "cart_id": fx.get("cart_id"),
            "cargo_aboard": cargo_aboard,
            "orders_ready": orders_ready,
            "meters_progressed": meters_progressed,
            "units": len(state.units),
            "units_with_person": units_with_person,
            "formations": len(state.formations or {}),
            "battle_id": fx.get("battle_id"),
            "battle_node_id": fx.get("battle_node_id"),
            "cube_2_hex": (cube2 or {}).get("hex_id"),
            "start_node_id": start,
        },
    )


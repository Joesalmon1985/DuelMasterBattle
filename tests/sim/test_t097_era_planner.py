"""T097 — pure EraTransitionPlanner and theoretical capacity ranking."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction

import pytest

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.eras.planner import (
    EraTransitionPlanner,
    TransitionTrigger,
    compute_plan_hash,
    theoretical_site_capacity,
    validate_plan_freshness,
)
from sim.dmb.industry import fraction_wire
from sim.dmb.industry.allocation import build_theoretical_constraints, solve_theoretical
from sim.dmb.industry.layers import LayerState
from sim.dmb.industry.primary import PrimaryChannel
from sim.dmb.industry.routes import FactoryRoute, ProcessorBinding


def _base_world() -> WorldState:
    wid = WorldId("world:t097")
    state = WorldState(world_id=wid, ids=IdAllocator(wid))
    state.world_version = 3
    state.clock["era"] = "prehistoric"
    state.clock["cycle"] = 0
    state.factions = {
        "faction:1": {"id": "faction:1"},
        "faction:2": {"id": "faction:2"},
    }
    return state


def _install_factory_site(
    state: WorldState,
    *,
    settlement_id: str,
    faction_id: str,
    node_id: str,
    factory_id: str,
    processor_id: str,
    tier: str = "settlement",
    health: int = 100,
    finite_balance: Fraction | None = Fraction(600),
    catastrophe_block: bool = False,
) -> None:
    state.settlements[settlement_id] = {
        "id": settlement_id,
        "faction_id": faction_id,
        "node_id": node_id,
        "tier": tier,
        "operational": True,
    }
    state.buildings[factory_id] = {
        "id": factory_id,
        "def_id": "building.factory",
        "settlement_id": settlement_id,
        "faction_id": faction_id,
        "node_id": node_id,
        "status": "active",
        "active": True,
        "health": health,
        "max_health": 100,
    }
    state.buildings[processor_id] = {
        "id": processor_id,
        "def_id": "building.processor",
        "settlement_id": settlement_id,
        "faction_id": faction_id,
        "node_id": node_id,
        "status": "active",
        "active": True,
        "health": health,
        "max_health": 100,
    }
    channel_a = f"channel:{settlement_id}:a"
    channel_b = f"channel:{settlement_id}:b"
    layer_id = f"layer:{settlement_id}:finite"
    industry = state.industry
    industry.setdefault("factories", {})[factory_id] = {
        "id": factory_id,
        "node_id": node_id,
        "faction_id": faction_id,
        "settlement_id": settlement_id,
        "era": "prehistoric",
        "unit_def_id": "unit.skirmisher",
        "meter": fraction_wire(Fraction()),
        "active": True,
    }
    industry.setdefault("channels", {})[channel_a] = {
        "channel_id": channel_a,
        "building_id": f"building.primary.{settlement_id}.a",
        "node_id": node_id,
        "terrain": "woodland",
        "era": "prehistoric",
        "cycle": 0,
        "resource_id": "res.a",
        "layer_id": layer_id,
        "finite": True,
        "capacity": fraction_wire(Fraction(1, 10)),
        "storable": True,
    }
    industry.setdefault("channels", {})[channel_b] = {
        "channel_id": channel_b,
        "building_id": f"building.primary.{settlement_id}.b",
        "node_id": node_id,
        "terrain": "fields",
        "era": "prehistoric",
        "cycle": 0,
        "resource_id": "res.b",
        "layer_id": f"layer:{settlement_id}:renew",
        "finite": False,
        "capacity": fraction_wire(Fraction(1, 10)),
        "storable": False,
    }
    industry.setdefault("layers", {})[layer_id] = {
        "id": layer_id,
        "hex_id": "hex:1",
        "resource_id": "res.a",
        "era": "prehistoric",
        "cycle": 0,
        "finite_balance": None if finite_balance is None else fraction_wire(finite_balance),
        "renewable_capacity": None,
        "retired": False,
    }
    industry.setdefault("layers", {})[f"layer:{settlement_id}:renew"] = {
        "id": f"layer:{settlement_id}:renew",
        "hex_id": "hex:2",
        "resource_id": "res.b",
        "era": "prehistoric",
        "cycle": 0,
        "finite_balance": None,
        "renewable_capacity": fraction_wire(Fraction(1, 10)),
        "retired": False,
    }
    industry.setdefault("processors", {})[processor_id] = {
        "building_id": processor_id,
        "recipe_id": "recipe.test",
        "era": "prehistoric",
        "input_a_channel_id": channel_a,
        "input_b_channel_id": channel_b,
        "output_capacity": fraction_wire(Fraction(1, 10)),
        "health": health,
        "max_health": 100,
        "active": True,
        "strike": False,
        "modifier": fraction_wire(Fraction(1)),
    }
    industry.setdefault("routes", {})[factory_id] = {
        "factory_id": factory_id,
        "processor_id": processor_id,
        "unit_def_id": "unit.skirmisher",
        "processed_units_per_unit": 1,
        "requested_weight": fraction_wire(Fraction(1)),
    }
    if catastrophe_block:
        state.board.setdefault("hazard_cubes", {})["cube:tmp"] = {
            "id": "cube:tmp",
            "hex_id": "hex:1",
            "blocks_industry": True,
        }


def test_temporary_disruption_does_not_alter_rank() -> None:
    healthy = _base_world()
    _install_factory_site(
        healthy,
        settlement_id="settlement:a",
        faction_id="faction:1",
        node_id="node:1",
        factory_id="factory:a",
        processor_id="processor:a",
    )
    _install_factory_site(
        healthy,
        settlement_id="settlement:b",
        faction_id="faction:1",
        node_id="node:2",
        factory_id="factory:b",
        processor_id="processor:b",
    )
    # Give A a permanent city multiplier advantage.
    healthy.settlements["settlement:a"]["tier"] = "city"

    disrupted = deepcopy(healthy)
    # Temporary damage + depleted finite layer + processor strike.
    disrupted.industry["processors"]["processor:a"]["health"] = 10
    disrupted.industry["processors"]["processor:a"]["strike"] = True
    disrupted.industry["layers"]["layer:settlement:a:finite"]["finite_balance"] = fraction_wire(Fraction(0))
    disrupted.buildings["factory:a"]["health"] = 10

    cap_h_a = theoretical_site_capacity(healthy, "settlement:a")
    cap_d_a = theoretical_site_capacity(disrupted, "settlement:a")
    assert cap_h_a == cap_d_a
    assert cap_h_a > theoretical_site_capacity(healthy, "settlement:b")

    for i in range(10):
        healthy.settlements[f"pad:{i}"] = {
            "id": f"pad:{i}",
            "faction_id": "faction:1",
            "node_id": f"node:pad:{i}",
            "tier": "settlement",
            "operational": True,
        }
        disrupted.settlements[f"pad:{i}"] = dict(healthy.settlements[f"pad:{i}"])

    plan_h = EraTransitionPlanner().plan(
        healthy, TransitionTrigger("evt:1", "faction:1", scores_at_trigger={"faction:1": 10})
    )
    plan_d = EraTransitionPlanner().plan(
        disrupted, TransitionTrigger("evt:1", "faction:1", scores_at_trigger={"faction:1": 10})
    )
    assert [r["settlement_id"] for r in plan_h.theoretical_site_ranking[:2]] == [
        r["settlement_id"] for r in plan_d.theoretical_site_ranking[:2]
    ]


def test_installed_capacity_change_does_alter_rank() -> None:
    state = _base_world()
    _install_factory_site(
        state,
        settlement_id="settlement:a",
        faction_id="faction:1",
        node_id="node:1",
        factory_id="factory:a",
        processor_id="processor:a",
    )
    _install_factory_site(
        state,
        settlement_id="settlement:b",
        faction_id="faction:1",
        node_id="node:2",
        factory_id="factory:b",
        processor_id="processor:b",
    )
    before = theoretical_site_capacity(state, "settlement:a")
    # Permanently remove factory A installation.
    state.buildings["factory:a"]["status"] = "destroyed"
    after = theoretical_site_capacity(state, "settlement:a")
    assert after < before
    assert after == Fraction()


def test_equal_rank_uses_settlement_id() -> None:
    state = _base_world()
    _install_factory_site(
        state,
        settlement_id="settlement:z",
        faction_id="faction:1",
        node_id="node:1",
        factory_id="factory:z",
        processor_id="processor:z",
    )
    _install_factory_site(
        state,
        settlement_id="settlement:a",
        faction_id="faction:1",
        node_id="node:2",
        factory_id="factory:a",
        processor_id="processor:a",
    )
    for i in range(10):
        state.settlements[f"pad:{i}"] = {
            "id": f"pad:{i}",
            "faction_id": "faction:1",
            "node_id": f"node:pad:{i}",
            "tier": "settlement",
            "operational": True,
        }
    plan = EraTransitionPlanner().plan(
        state, TransitionTrigger("evt:tie", "faction:1", scores_at_trigger={"faction:1": 12})
    )
    top_two = [r["settlement_id"] for r in plan.theoretical_site_ranking if r["settlement_id"].startswith("settlement:")]
    assert top_two[:2] == ["settlement:a", "settlement:z"]


def test_planner_does_not_mutate_snapshot() -> None:
    state = _base_world()
    for i in range(1, 11):
        state.settlements[f"settlement:{i}"] = {
            "id": f"settlement:{i}",
            "faction_id": "faction:1",
            "node_id": f"node:{i}",
            "tier": "settlement",
            "operational": True,
        }
    before = deepcopy(state.settlements)
    before_industry = deepcopy(state.industry)
    EraTransitionPlanner().plan(
        state, TransitionTrigger("evt:m", "faction:1", scores_at_trigger={"faction:1": 10})
    )
    assert state.settlements == before
    assert state.industry == before_industry


def test_stale_plan_hash_cannot_commit() -> None:
    state = _base_world()
    for i in range(1, 11):
        state.settlements[f"settlement:{i}"] = {
            "id": f"settlement:{i}",
            "faction_id": "faction:1",
            "node_id": f"node:{i}",
            "tier": "settlement",
            "operational": True,
        }
    plan = EraTransitionPlanner().plan(
        state, TransitionTrigger("evt:s", "faction:1", scores_at_trigger={"faction:1": 10})
    )
    fresh = validate_plan_freshness(plan, state)
    assert fresh["ok"] is True
    assert fresh["can_commit"] is True

    # Tamper hash.
    tampered = plan.to_dict()
    tampered["plan_hash"] = "sha256:deadbeef"
    assert validate_plan_freshness(tampered, state)["can_commit"] is False

    # World advances.
    state.world_version += 1
    assert validate_plan_freshness(plan, state)["can_commit"] is False

    # Recomputed hash for untampered body still matches algorithm.
    body = plan.to_dict()
    assert compute_plan_hash(body) == plan.plan_hash


def test_theoretical_allocation_marker() -> None:
    routes = [FactoryRoute("factory:1", "processor:1", "unit.a", 1)]
    processors = {
        "processor:1": ProcessorBinding(
            "processor:1",
            "recipe",
            "prehistoric",
            "channel:a",
            "channel:b",
            output_capacity=Fraction(1, 10),
            health=5,
            max_health=100,
            strike=True,
        )
    }
    channels = {
        "channel:a": PrimaryChannel(
            "channel:a", "b1", "node:1", "woodland", "prehistoric", 0, "ra", "layer:a", True, Fraction(1, 10), True
        ),
        "channel:b": PrimaryChannel(
            "channel:b", "b2", "node:1", "fields", "prehistoric", 0, "rb", "layer:b", False, Fraction(1, 10), False
        ),
    }
    layers = {
        "layer:a": LayerState("layer:a", "hex:1", "ra", "prehistoric", 0, Fraction(0), None),
        "layer:b": LayerState("layer:b", "hex:2", "rb", "prehistoric", 0, None, Fraction(1, 10)),
    }
    built = build_theoretical_constraints(routes, processors, channels, layers)
    assert all(c.reason != "finite_layer_balance" for c in built.constraints)
    plan = solve_theoretical(routes, processors, channels, layers)
    assert plan.theoretical is True
    assert plan.rate("factory:1") > 0

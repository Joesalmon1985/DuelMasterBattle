from fractions import Fraction

import pytest

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.industry.layers import ResourceLayerService
from sim.dmb.industry.primary import PrimaryBinding, PrimaryCapacity, node_slots


def test_best_adjacent_pips_caps_slots_and_city_only_doubles_flow() -> None:
    assert node_slots([6, 8]) == 5
    binding = PrimaryBinding(
        "building:1", "node:1", "hex:1", "woodland", "prehistoric", 0,
        "finite", "renewable", "layer:f", "layer:r", city=True,
    )
    channels = PrimaryCapacity.channels(binding)
    assert node_slots([6]) == 5
    assert {channel.capacity for channel in channels} == {Fraction(1, 5)}


def test_two_nodes_share_one_finite_layer_and_cycle_is_distinct() -> None:
    state = WorldState(world_id=WorldId("world:t050"))
    service = ResourceLayerService(state.industry)
    old = service.create_layer("hex:1", "ore", "prehistoric", 0, finite=True)
    assert service.create_layer("hex:1", "ore", "prehistoric", 0, finite=True).layer_id == old.layer_id
    service.consume_plan([(old.layer_id, Fraction(3)), (old.layer_id, Fraction(2))])
    assert service.balance(old.layer_id) == 595
    new = service.create_layer("hex:1", "ore", "prehistoric", 1, finite=True)
    assert new.layer_id != old.layer_id
    assert service.balance(old.layer_id) == 595
    assert service.balance(new.layer_id) == 600


def test_renewable_service_has_capacity_but_no_balance_or_stock() -> None:
    state = WorldState(world_id=WorldId("world:t050-service"))
    service = ResourceLayerService(state.industry)
    layer = service.create_layer("hex:1", "power", "historic", 0, finite=False)
    assert layer.finite_balance is None
    assert layer.renewable_capacity == Fraction(1, 10)
    assert "power" not in state.stocks
    with pytest.raises(TypeValidationError):
        service.restore_explicitly(layer.layer_id, Fraction(1))


def test_damage_tech_and_catastrophe_modify_channels_without_workers() -> None:
    damaged = PrimaryBinding(
        "building:2", "node:1", "hex:1", "ore", "historic", 0,
        "finite", "service", "layer:f", "layer:r",
        health=25, max_health=100, tech_modifier=Fraction(2),
    )
    assert PrimaryCapacity.channels(damaged)[0].capacity == Fraction(1, 20)
    assert PrimaryCapacity.channels(PrimaryBinding(**{**damaged.__dict__, "catastrophe": True}))[0].capacity == 0

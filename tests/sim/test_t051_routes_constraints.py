from fractions import Fraction

import pytest

from sim.dmb.core.types import TypeValidationError
from sim.dmb.industry.constraints import build_constraints
from sim.dmb.industry.layers import LayerState
from sim.dmb.industry.primary import PrimaryChannel
from sim.dmb.industry.routes import FactoryRoute, ProcessorBinding, RouteSelector, validate_processor


def _channel(cid: str, terrain: str, resource: str, layer: str, finite: bool = False, era: str = "prehistoric") -> PrimaryChannel:
    return PrimaryChannel(cid, cid, "N", terrain, era, 0, resource, layer, finite, Fraction(1, 10), True)


def _setup():
    channels = {
        "a": _channel("a", "woodland", "wood", "renew"),
        "b": _channel("b", "ore", "ore", "deposit", True),
    }
    processor = ProcessorBinding("processor:1", "recipe:1", "prehistoric", "a", "b")
    layers = {
        "deposit": LayerState("deposit", "H", "ore", "prehistoric", 0, Fraction(600), None),
    }
    return channels, processor, layers


def test_processor_exact_channels_validate_terrain_and_era() -> None:
    channels, processor, _ = _setup()
    validate_processor(processor, channels, {"input_a_id": "wood", "input_b_id": "ore"})
    same = {**channels, "b": _channel("b", "woodland", "ore", "deposit", True)}
    with pytest.raises(TypeValidationError, match="same-terrain"):
        validate_processor(processor, same, {"input_a_id": "wood", "input_b_id": "ore"})
    cross = {**channels, "b": _channel("b", "ore", "ore", "deposit", True, "historic")}
    with pytest.raises(TypeValidationError, match="cross-era"):
        validate_processor(processor, cross, {"input_a_id": "wood", "input_b_id": "ore"})


def test_missing_processor_and_exhausted_source_disable_only_route() -> None:
    channels, processor, layers = _setup()
    routes = [FactoryRoute("factory:1", "processor:missing", "unit.a", 2)]
    assert build_constraints(routes, {}, channels, layers).bottlenecks["factory:1"] == "missing_processor"
    exhausted = {**layers, "deposit": LayerState("deposit", "H", "ore", "prehistoric", 0, Fraction(), None)}
    routes = [FactoryRoute("factory:1", processor.building_id, "unit.a", 2)]
    built = build_constraints(routes, {processor.building_id: processor}, channels, exhausted)
    assert built.requests == ()
    assert built.bottlenecks["factory:1"].startswith("exhausted_source")


def test_duplicate_factories_share_one_processor_constraint() -> None:
    channels, processor, layers = _setup()
    routes = [
        FactoryRoute("factory:1", processor.building_id, "unit.a", 2),
        FactoryRoute("factory:2", processor.building_id, "unit.b", 3),
    ]
    built = build_constraints(routes, {processor.building_id: processor}, channels, layers)
    shared = next(c for c in built.constraints if c.constraint_id == "processor:processor:1")
    assert shared.coefficients == {"factory:1": Fraction(2), "factory:2": Fraction(3)}


def test_one_installed_route_per_factory() -> None:
    _, processor, _ = _setup()
    routes = [
        FactoryRoute("factory:1", processor.building_id, "unit.a", 2),
        FactoryRoute("factory:1", processor.building_id, "unit.b", 3),
    ]
    with pytest.raises(TypeValidationError, match="multiple"):
        RouteSelector().select_installed_route("factory:1", routes, {processor.building_id: processor})

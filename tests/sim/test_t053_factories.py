from fractions import Fraction

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.industry.allocation import AllocationPlan
from sim.dmb.industry.factories import FactoryService
from sim.dmb.industry.layers import ResourceLayerService
from sim.dmb.industry.primary import PrimaryChannel
from sim.dmb.industry.routes import FactoryRoute, ProcessorBinding


def _world():
    state = WorldState(world_id=WorldId("world:t053"))
    layers = ResourceLayerService(state.industry)
    finite = layers.create_layer("hex:ore", "ore", "prehistoric", 0, finite=True)
    renewable = layers.create_layer("hex:wood", "wood", "prehistoric", 0, finite=False)
    channels = {
        "wood": PrimaryChannel("wood", "source:wood", "node:industry", "woodland", "prehistoric", 0, "wood", renewable.layer_id, False, Fraction(1, 10), True),
        "ore": PrimaryChannel("ore", "source:ore", "node:industry", "ore_mountains", "prehistoric", 0, "ore", finite.layer_id, True, Fraction(1, 10), True),
    }
    processor = ProcessorBinding("processor:fx", "recipe:fx", "prehistoric", "wood", "ore")
    routes = [
        FactoryRoute("factory:skirmisher", processor.building_id, "unit.ancient.skirmisher", 2),
        FactoryRoute("factory:line", processor.building_id, "unit.ancient.line", 3),
        FactoryRoute("factory:heavy", processor.building_id, "unit.ancient.heavy", 5),
    ]
    service = FactoryService(state)
    for route in routes:
        service.create(route.factory_id, node_id="node:industry", faction_id="faction:fx", era="prehistoric", unit_def_id=route.unit_def_id)
    plan = AllocationPlan({route.factory_id: Fraction(1, 100) for route in routes}, ("processor:fx",))
    return state, service, finite.layer_id, channels, processor, routes, plan


def _advance(service, channels, processor, routes, plan, ticks):
    spawned = []
    for _ in range(ticks):
        spawned.extend(service.apply_allocations(plan, routes, {processor.building_id: processor}, channels))
    return spawned


def test_sixty_and_hundred_second_numerical_oracle() -> None:
    state, service, layer_id, channels, processor, routes, plan = _world()
    assert _advance(service, channels, processor, routes, plan, 600) == []
    assert [service.meter(route.factory_id) for route in routes] == [Fraction(3, 5)] * 3
    spawned = _advance(service, channels, processor, routes, plan, 400)
    assert len(spawned) == 3
    assert len({unit["id"] for unit in spawned}) == 3
    assert [service.meter(route.factory_id) for route in routes] == [Fraction()] * 3
    assert service.layers.balance(layer_id) == 590


def test_save_at_599_seconds_resumes_identically() -> None:
    state, service, layer_id, channels, processor, routes, plan = _world()
    _advance(service, channels, processor, routes, plan, 599)
    restored = WorldState.from_dict(state.to_dict())
    resumed = FactoryService(restored)
    spawned = _advance(resumed, channels, processor, routes, plan, 401)
    assert len(spawned) == 3
    assert resumed.layers.balance(layer_id) == 590
    assert {unit["factory_id"] for unit in restored.units.values()} == {route.factory_id for route in routes}

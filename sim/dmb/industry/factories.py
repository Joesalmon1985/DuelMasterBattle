"""Exact factory meters and atomic 100 ms production commits."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from typing import Any, Mapping, Sequence

from sim.dmb.core.types import TypeValidationError
from sim.dmb.industry import fraction, fraction_wire
from sim.dmb.industry.allocation import AllocationPlan
from sim.dmb.industry.layers import ResourceLayerService
from sim.dmb.industry.primary import PrimaryChannel
from sim.dmb.industry.routes import FactoryRoute, ProcessorBinding
from sim.dmb.military.units import MilitaryService


class FactoryService:
    def __init__(self, world_state: Any):
        self.world = world_state
        self.state = world_state.industry
        self.factories = self.state.setdefault("factories", {})
        self.layers = ResourceLayerService(self.state)
        self.military = MilitaryService(world_state)

    def create(
        self,
        factory_id: str,
        *,
        node_id: str,
        faction_id: str,
        era: str,
        unit_def_id: str,
    ) -> dict[str, Any]:
        record = self.factories.setdefault(
            factory_id,
            {
                "id": factory_id,
                "node_id": node_id,
                "faction_id": faction_id,
                "era": era,
                "unit_def_id": unit_def_id,
                "meter": fraction_wire(Fraction()),
                "active": True,
            },
        )
        return record

    def meter(self, factory_id: str) -> Fraction:
        return fraction(self.factories[factory_id]["meter"])

    def apply_allocations(
        self,
        plan: AllocationPlan,
        routes: Sequence[FactoryRoute],
        processors: Mapping[str, ProcessorBinding],
        channels: Mapping[str, PrimaryChannel],
        *,
        dt: Fraction = Fraction(1, 10),
    ) -> list[dict[str, Any]]:
        if plan.theoretical:
            raise TypeValidationError("theoretical plan cannot be committed")
        route_by_factory = {route.factory_id: route for route in routes}
        debits: list[tuple[str, Fraction]] = []
        progress: dict[str, Fraction] = {}
        for factory_id, rate in sorted(plan.rates.items()):
            if rate <= 0:
                continue
            record = self.factories.get(factory_id)
            route = route_by_factory.get(factory_id)
            if record is None or route is None or not record.get("active", True):
                continue
            processor = processors.get(route.processor_id)
            if processor is None or processor.capacity <= 0:
                continue
            amount = fraction(rate) * fraction(dt)
            progress[factory_id] = amount
            raw_amount = amount * route.processed_units_per_unit
            for channel_id in (processor.input_a_channel_id, processor.input_b_channel_id):
                channel = channels[channel_id]
                if channel.finite:
                    debits.append((channel.layer_id, raw_amount))

        layers_before = deepcopy(self.state.get("layers", {}))
        factories_before = deepcopy(self.factories)
        units_before = deepcopy(self.world.units)
        ids_before = deepcopy(self.world.ids)
        try:
            self.layers.consume_plan(debits)
            spawned: list[dict[str, Any]] = []
            for factory_id, amount in sorted(progress.items()):
                record = self.factories[factory_id]
                total = fraction(record["meter"]) + amount
                completed = total.numerator // total.denominator
                record["meter"] = fraction_wire(total - completed)
                route = route_by_factory[factory_id]
                for _ in range(completed):
                    spawned.append(
                        self.military.spawn(
                            route.unit_def_id,
                            home_node_id=str(record["node_id"]),
                            faction_id=str(record["faction_id"]),
                            era=str(record["era"]),
                            factory_id=factory_id,
                        )
                    )
            return spawned
        except Exception:
            self.state["layers"] = layers_before
            self.state["factories"] = factories_before
            self.world.units = units_before
            self.world.ids = ids_before
            self.factories = self.state["factories"]
            self.layers = ResourceLayerService(self.state)
            raise

"""Global fixed-quantum industrial accounting service."""

from __future__ import annotations

from dataclasses import asdict
from fractions import Fraction
from typing import Any

from sim.dmb.industry import fraction, fraction_wire
from sim.dmb.industry.allocation import RateAllocator
from sim.dmb.industry.constraints import build_constraints
from sim.dmb.industry.factories import FactoryService
from sim.dmb.industry.layers import LayerState
from sim.dmb.industry.primary import PrimaryChannel
from sim.dmb.industry.projection import IndustryProjection
from sim.dmb.industry.routes import FactoryRoute, ProcessorBinding
from sim.dmb.people.jobs import JobService


def _channel_to_dict(channel: PrimaryChannel) -> dict[str, Any]:
    record = asdict(channel)
    record["capacity"] = fraction_wire(channel.capacity)
    return record


def _channel_from_dict(record: dict[str, Any]) -> PrimaryChannel:
    return PrimaryChannel(**{**record, "capacity": fraction(record["capacity"])})


def _processor_to_dict(processor: ProcessorBinding) -> dict[str, Any]:
    record = asdict(processor)
    record["output_capacity"] = fraction_wire(processor.output_capacity)
    record["modifier"] = fraction_wire(processor.modifier)
    return record


def _processor_from_dict(record: dict[str, Any]) -> ProcessorBinding:
    return ProcessorBinding(
        **{
            **record,
            "output_capacity": fraction(record["output_capacity"]),
            "modifier": fraction(record["modifier"]),
        }
    )


def _route_to_dict(route: FactoryRoute) -> dict[str, Any]:
    record = asdict(route)
    record["requested_weight"] = fraction_wire(route.requested_weight)
    return record


def _route_from_dict(record: dict[str, Any]) -> FactoryRoute:
    return FactoryRoute(**{**record, "requested_weight": fraction(record["requested_weight"])})


class IndustryService:
    def __init__(self, world_state: Any):
        self.world = world_state
        self.state = world_state.industry
        self.state.setdefault("schema_version", 1)
        self.state.setdefault("channels", {})
        self.state.setdefault("processors", {})
        self.state.setdefault("routes", {})
        self.state.setdefault("events", [])
        self.factories = FactoryService(world_state)
        self.allocator = RateAllocator()

    def install_channel(self, channel: PrimaryChannel) -> None:
        self.state["channels"][channel.channel_id] = _channel_to_dict(channel)

    def install_processor(self, processor: ProcessorBinding) -> None:
        self.state["processors"][processor.building_id] = _processor_to_dict(processor)

    def install_route(self, route: FactoryRoute) -> None:
        self.state["routes"][route.factory_id] = _route_to_dict(route)

    def advance_quanta(self, quanta: int) -> list[dict[str, Any]]:
        emitted: list[dict[str, Any]] = []
        for _ in range(max(0, int(quanta))):
            emitted.extend(self._tick())
        return emitted

    def _tick(self) -> list[dict[str, Any]]:
        # Vacancies are durable people state. Filling them is part of the
        # accounting cadence, but never derives output from loaded sprites.
        JobService(self.world).backfill_tick()
        channels = {
            channel_id: _channel_from_dict(record)
            for channel_id, record in self.state["channels"].items()
        }
        processors = {
            processor_id: _processor_from_dict(record)
            for processor_id, record in self.state["processors"].items()
        }
        routes = [_route_from_dict(record) for _, record in sorted(self.state["routes"].items())]

        active: dict[str, bool] = {}
        for route in routes:
            factory_record = self.factories.factories.get(route.factory_id, {})
            building = self.world.buildings.get(route.factory_id)
            operational = bool(factory_record.get("active", True))
            if building is not None:
                operational = operational and building.get("status") != "destroyed" and bool(building.get("active", True))
            active[route.factory_id] = operational
        for processor_id, processor in list(processors.items()):
            building = self.world.buildings.get(processor_id)
            job_modifiers = [
                fraction(job.get("modifier", 1))
                for job in self.world.definitions.get("jobs", {}).values()
                if job.get("workplace_id") == processor_id and not job.get("vacant")
            ]
            job_modifier = min(job_modifiers, default=Fraction(1))
            if building is not None:
                processors[processor_id] = ProcessorBinding(
                    **{
                        **processor.__dict__,
                        "health": int(building.get("health", processor.health)),
                        "max_health": int(building.get("max_health", processor.max_health)),
                        "active": processor.active and building.get("status") != "destroyed" and bool(building.get("active", True)),
                        "modifier": processor.modifier * job_modifier,
                    }
                )
            elif job_modifiers:
                processors[processor_id] = ProcessorBinding(
                    **{**processor.__dict__, "modifier": processor.modifier * job_modifier}
                )

        layers = {
            layer_id: LayerState.from_dict(record)
            for layer_id, record in self.state.get("layers", {}).items()
        }
        built = build_constraints(routes, processors, channels, layers, factory_active=active)
        plan = self.allocator.solve(built.requests, built.constraints)
        spawned = self.factories.apply_allocations(plan, routes, processors, channels)
        rate_event = {
            "kind": "industry_rates",
            "rates": {key: fraction_wire(value) for key, value in plan.rates.items()},
        }
        emitted = [rate_event]
        if built.bottlenecks:
            emitted.append({"kind": "industry_shortage", "reasons": dict(sorted(built.bottlenecks.items()))})
        if spawned:
            emitted.append({"kind": "industry_spawn", "unit_ids": [unit["id"] for unit in spawned]})
        self.state["events"].extend(emitted)
        # Carrier roster follows committed rates; presentation only.
        IndustryProjection(self.world).sync_carrier_jobs()
        return emitted

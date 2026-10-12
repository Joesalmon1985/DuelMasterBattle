"""Constraint construction for installed industrial routes."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping, Sequence

from sim.dmb.industry.layers import LayerState
from sim.dmb.industry.primary import PrimaryChannel
from sim.dmb.industry.routes import FactoryRoute, ProcessorBinding


@dataclass(frozen=True)
class AllocationRequest:
    request_id: str
    route: FactoryRoute
    weight: Fraction
    ceiling: Fraction


@dataclass(frozen=True)
class CapacityConstraint:
    constraint_id: str
    capacity: Fraction
    coefficients: Mapping[str, Fraction]
    reason: str


@dataclass(frozen=True)
class ConstraintBuild:
    requests: tuple[AllocationRequest, ...]
    constraints: tuple[CapacityConstraint, ...]
    bottlenecks: Mapping[str, str]


def build_constraints(
    routes: Sequence[FactoryRoute],
    processors: Mapping[str, ProcessorBinding],
    channels: Mapping[str, PrimaryChannel],
    layers: Mapping[str, LayerState],
    *,
    factory_active: Mapping[str, bool] | None = None,
    factory_ceiling: Mapping[str, Fraction] | None = None,
    tick_seconds: Fraction = Fraction(1, 10),
) -> ConstraintBuild:
    active_map = factory_active or {}
    requests: list[AllocationRequest] = []
    constraints: list[CapacityConstraint] = []
    bottlenecks: dict[str, str] = {}
    coefficients: dict[str, dict[str, Fraction]] = {}
    capacities: dict[str, Fraction] = {}
    reasons: dict[str, str] = {}

    def add(request_id: str, constraint_id: str, coefficient: Fraction, capacity: Fraction, reason: str) -> None:
        coefficients.setdefault(constraint_id, {})[request_id] = coefficient
        capacities[constraint_id] = capacity
        reasons[constraint_id] = reason

    for route in sorted(routes, key=lambda item: item.factory_id):
        rid = route.factory_id
        processor = processors.get(route.processor_id)
        if processor is None:
            bottlenecks[rid] = "missing_processor"
            continue
        if not active_map.get(route.factory_id, True):
            bottlenecks[rid] = "factory_inactive"
            continue
        source_channels = [
            channels.get(processor.input_a_channel_id),
            channels.get(processor.input_b_channel_id),
        ]
        if any(channel is None for channel in source_channels):
            bottlenecks[rid] = "missing_source_channel"
            continue
        if processor.capacity <= 0:
            bottlenecks[rid] = "processor_disabled"
            continue
        exhausted = next(
            (
                channel
                for channel in source_channels
                if channel.finite and (
                    channel.layer_id not in layers
                    or layers[channel.layer_id].finite_balance is None
                    or layers[channel.layer_id].finite_balance <= 0
                    or layers[channel.layer_id].retired
                )
            ),
            None,
        )
        if exhausted is not None:
            bottlenecks[rid] = f"exhausted_source:{exhausted.layer_id}"
            continue
        cost = Fraction(route.processed_units_per_unit)
        ceiling = (factory_ceiling or {}).get(rid, Fraction(1, 60))
        requests.append(AllocationRequest(rid, route, route.requested_weight, ceiling))
        add(rid, f"factory:{rid}", Fraction(1), ceiling, "factory_ceiling")
        add(rid, f"processor:{processor.building_id}", cost, processor.capacity, "processor_capacity")
        for channel in source_channels:
            assert channel is not None
            add(rid, f"channel:{channel.channel_id}", cost, channel.capacity, "source_channel_capacity")
            if channel.finite:
                layer = layers[channel.layer_id]
                assert layer.finite_balance is not None
                add(
                    rid,
                    f"layer:{channel.layer_id}",
                    cost,
                    layer.finite_balance / tick_seconds,
                    "finite_layer_balance",
                )
    for constraint_id in sorted(coefficients):
        constraints.append(
            CapacityConstraint(
                constraint_id,
                capacities[constraint_id],
                dict(sorted(coefficients[constraint_id].items())),
                reasons[constraint_id],
            )
        )
    return ConstraintBuild(tuple(requests), tuple(constraints), bottlenecks)

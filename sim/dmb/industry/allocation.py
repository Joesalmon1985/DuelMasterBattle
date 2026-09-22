"""Pure deterministic weighted max-min progressive-fill allocation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Mapping, Sequence

from sim.dmb.core.types import TypeValidationError
from sim.dmb.industry.constraints import (
    AllocationRequest,
    CapacityConstraint,
    ConstraintBuild,
    build_constraints,
)
from sim.dmb.industry.layers import LayerState
from sim.dmb.industry.primary import PrimaryChannel
from sim.dmb.industry.routes import FactoryRoute, ProcessorBinding


@dataclass(frozen=True)
class AllocationPlan:
    rates: Mapping[str, Fraction]
    saturated_constraints: tuple[str, ...]
    theoretical: bool = False

    def rate(self, request_id: str) -> Fraction:
        return self.rates.get(request_id, Fraction())


class RateAllocator:
    def solve(
        self,
        requests: Sequence[AllocationRequest],
        constraints: Sequence[CapacityConstraint],
        *,
        theoretical: bool = False,
    ) -> AllocationPlan:
        ordered_requests = sorted(requests, key=lambda item: item.request_id)
        request_by_id = {request.request_id: request for request in ordered_requests}
        if len(request_by_id) != len(ordered_requests):
            raise TypeValidationError("duplicate allocation request id")
        if any(request.weight <= 0 or request.ceiling < 0 for request in ordered_requests):
            raise TypeValidationError("invalid allocation request")
        ordered_constraints = sorted(constraints, key=lambda item: item.constraint_id)
        if any(constraint.capacity < 0 for constraint in ordered_constraints):
            raise TypeValidationError("negative constraint capacity")

        rates = {request.request_id: Fraction() for request in ordered_requests}
        active = set(rates)
        saturated: list[str] = []
        while active:
            candidates: list[tuple[Fraction, str, str]] = []
            for rid in sorted(active):
                request = request_by_id[rid]
                candidates.append(((request.ceiling - rates[rid]) / request.weight, "ceiling", rid))
            for constraint in ordered_constraints:
                active_coefficient = sum(
                    (
                        constraint.coefficients.get(rid, Fraction()) * request_by_id[rid].weight
                        for rid in active
                    ),
                    Fraction(),
                )
                if active_coefficient <= 0:
                    continue
                used = sum(
                    (
                        coefficient * rates.get(rid, Fraction())
                        for rid, coefficient in constraint.coefficients.items()
                    ),
                    Fraction(),
                )
                remaining = constraint.capacity - used
                if remaining < 0:
                    raise TypeValidationError(f"infeasible starting plan for {constraint.constraint_id}")
                candidates.append((remaining / active_coefficient, "constraint", constraint.constraint_id))
            if not candidates:
                break
            delta = min(item[0] for item in candidates)
            if delta < 0:
                raise TypeValidationError("negative progressive-fill increment")
            for rid in active:
                rates[rid] += request_by_id[rid].weight * delta

            frozen: set[str] = set()
            for rid in active:
                if rates[rid] == request_by_id[rid].ceiling:
                    frozen.add(rid)
            for constraint in ordered_constraints:
                used = sum(
                    (
                        coefficient * rates.get(rid, Fraction())
                        for rid, coefficient in constraint.coefficients.items()
                    ),
                    Fraction(),
                )
                if used == constraint.capacity:
                    affected = {
                        rid
                        for rid in active
                        if constraint.coefficients.get(rid, Fraction()) > 0
                    }
                    if affected:
                        frozen.update(affected)
                        if constraint.constraint_id not in saturated:
                            saturated.append(constraint.constraint_id)
            if not frozen:
                raise TypeValidationError("progressive fill made no freezing progress")
            active.difference_update(frozen)
        return AllocationPlan(dict(sorted(rates.items())), tuple(saturated), theoretical)


def build_theoretical_constraints(
    routes: Sequence[FactoryRoute],
    processors: Mapping[str, ProcessorBinding],
    channels: Mapping[str, PrimaryChannel],
    layers: Mapping[str, LayerState],
    *,
    factory_installed: Mapping[str, bool] | None = None,
    tick_seconds: Fraction = Fraction(1, 10),
) -> ConstraintBuild:
    """Constraint set for era ranking: installed/permanent only.

    Temporary catastrophe blocks, damage, strikes, and finite depletion are
    removed. Permanently missing/inactive installations stay excluded.
    Finite layers are treated as available (no depletion bottleneck).
    """
    # Temporary damage/strikes do not affect ranking; permanently missing max_health
    # installations are excluded.
    healed_processors = {
        pid: replace(
            processor,
            health=max(int(processor.max_health), 1),
            max_health=max(int(processor.max_health), 1),
            strike=False,
            active=True,
        )
        for pid, processor in processors.items()
        if int(processor.max_health) > 0
    }
    # Channels keep installed capacity; temporary zeroing is upstream of this helper.
    available_layers = {
        lid: LayerState(
            layer_id=layer.layer_id,
            hex_id=layer.hex_id,
            resource_id=layer.resource_id,
            era=layer.era,
            cycle=layer.cycle,
            # Treat finite supply as available for ranking (C11).
            finite_balance=None if layer.finite_balance is None else Fraction(10**9),
            renewable_capacity=layer.renewable_capacity,
            retired=False if not layer.retired else True,
        )
        for lid, layer in layers.items()
        if not layer.retired
    }
    installed = factory_installed or {route.factory_id: True for route in routes}
    built = build_constraints(
        routes,
        healed_processors,
        channels,
        available_layers,
        factory_active=installed,
        tick_seconds=tick_seconds,
    )
    # Drop finite-layer balance constraints entirely (depletion must not rank).
    filtered = tuple(c for c in built.constraints if c.reason != "finite_layer_balance")
    return ConstraintBuild(built.requests, filtered, built.bottlenecks)


def solve_theoretical(
    routes: Sequence[FactoryRoute],
    processors: Mapping[str, ProcessorBinding],
    channels: Mapping[str, PrimaryChannel],
    layers: Mapping[str, LayerState],
    *,
    factory_installed: Mapping[str, bool] | None = None,
) -> AllocationPlan:
    built = build_theoretical_constraints(
        routes, processors, channels, layers, factory_installed=factory_installed
    )
    return RateAllocator().solve(built.requests, built.constraints, theoretical=True)

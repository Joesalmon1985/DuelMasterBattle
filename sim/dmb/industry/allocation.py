"""Pure deterministic weighted max-min progressive-fill allocation."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping, Sequence

from sim.dmb.core.types import TypeValidationError
from sim.dmb.industry.constraints import AllocationRequest, CapacityConstraint


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

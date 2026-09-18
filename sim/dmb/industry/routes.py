"""Installed processor and factory route bindings."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping, Sequence

from sim.dmb.core.types import TypeValidationError
from sim.dmb.industry.primary import PrimaryChannel


@dataclass(frozen=True)
class ProcessorBinding:
    building_id: str
    recipe_id: str
    era: str
    input_a_channel_id: str
    input_b_channel_id: str
    output_capacity: Fraction = Fraction(1, 10)
    health: int = 100
    max_health: int = 100
    active: bool = True
    strike: bool = False
    modifier: Fraction = Fraction(1)

    @property
    def capacity(self) -> Fraction:
        if not self.active or self.strike or self.health <= 0:
            return Fraction()
        return self.output_capacity * Fraction(self.health, max(1, self.max_health)) * self.modifier


@dataclass(frozen=True)
class FactoryRoute:
    factory_id: str
    processor_id: str
    unit_def_id: str
    processed_units_per_unit: int
    requested_weight: Fraction = Fraction(1)

    def __post_init__(self) -> None:
        if self.processed_units_per_unit <= 0 or self.requested_weight <= 0:
            raise TypeValidationError("route cost and weight must be positive")


def validate_processor(
    binding: ProcessorBinding,
    channels: Mapping[str, PrimaryChannel],
    recipe: Mapping[str, str],
) -> None:
    try:
        a = channels[binding.input_a_channel_id]
        b = channels[binding.input_b_channel_id]
    except KeyError as exc:
        raise TypeValidationError(f"missing exact source channel {exc.args[0]}") from exc
    if a.channel_id == b.channel_id:
        raise TypeValidationError("processor inputs require two exact channels")
    if a.era != b.era or a.era != binding.era:
        raise TypeValidationError("cross-era processor binding")
    if a.terrain == b.terrain:
        raise TypeValidationError("same-terrain processor binding")
    if a.resource_id != recipe["input_a_id"] or b.resource_id != recipe["input_b_id"]:
        raise TypeValidationError("processor channels do not match recipe inputs")


class RouteSelector:
    def candidates(
        self,
        factory_id: str,
        installed_routes: Sequence[FactoryRoute],
        processors: Mapping[str, ProcessorBinding],
    ) -> list[FactoryRoute]:
        return sorted(
            (
                route
                for route in installed_routes
                if route.factory_id == factory_id and route.processor_id in processors
            ),
            key=lambda route: (route.processor_id, route.unit_def_id),
        )

    def select_installed_route(
        self,
        factory_id: str,
        installed_routes: Sequence[FactoryRoute],
        processors: Mapping[str, ProcessorBinding],
    ) -> FactoryRoute | None:
        candidates = self.candidates(factory_id, installed_routes, processors)
        if not candidates:
            return None
        if len({route.processor_id for route in candidates}) != len(candidates):
            raise TypeValidationError(
                f"factory {factory_id} has multiple installed routes for one processor"
            )
        # Prefer a route that can really run. Alternate routes are installed
        # durable options, not implicit access to unsupported imported inputs.
        return sorted(
            candidates,
            key=lambda route: (
                processors[route.processor_id].capacity <= 0,
                -processors[route.processor_id].capacity,
                -route.requested_weight,
                route.processor_id,
                route.unit_def_id,
            ),
        )[0]

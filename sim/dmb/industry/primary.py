"""Primary industrial bindings and capacity channels."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Iterable

from sim.dmb.industry import fraction

PIPS = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}


def node_slots(numbers: Iterable[int]) -> int:
    return max((PIPS.get(int(number), 0) for number in numbers), default=0)


@dataclass(frozen=True)
class PrimaryBinding:
    building_id: str
    node_id: str
    adjacent_hex_id: str
    terrain: str
    era: str
    cycle: int
    finite_resource_id: str
    renewable_resource_id: str
    finite_layer_id: str
    renewable_layer_id: str
    city: bool = False
    health: int = 100
    max_health: int = 100
    tech_modifier: Fraction = Fraction(1)
    catastrophe: bool = False
    active: bool = True

    def channel_id(self, kind: str) -> str:
        return f"channel:{self.building_id}:{kind}"


@dataclass(frozen=True)
class PrimaryChannel:
    channel_id: str
    building_id: str
    node_id: str
    terrain: str
    era: str
    cycle: int
    resource_id: str
    layer_id: str
    finite: bool
    capacity: Fraction
    storable: bool


class PrimaryCapacity:
    @staticmethod
    def node_slots(numbers: Iterable[int]) -> int:
        return node_slots(numbers)

    @staticmethod
    def channels(binding: PrimaryBinding, resource_metadata: dict[str, dict[str, Any]] | None = None) -> tuple[PrimaryChannel, PrimaryChannel]:
        metadata = resource_metadata or {}
        health = Fraction(max(0, binding.health), max(1, binding.max_health))
        factor = (Fraction(2) if binding.city else Fraction(1)) * health * fraction(binding.tech_modifier)
        if binding.catastrophe or not binding.active:
            factor = Fraction()
        capacity = Fraction(1, 10) * factor

        def build(kind: str, resource_id: str, layer_id: str, finite: bool) -> PrimaryChannel:
            record = metadata.get(resource_id, {})
            return PrimaryChannel(
                binding.channel_id(kind),
                binding.building_id,
                binding.node_id,
                binding.terrain,
                binding.era,
                binding.cycle,
                resource_id,
                layer_id,
                finite,
                capacity,
                bool(record.get("storable", True)),
            )

        return (
            build("finite", binding.finite_resource_id, binding.finite_layer_id, True),
            build("renewable", binding.renewable_resource_id, binding.renewable_layer_id, False),
        )

"""Shared finite resource layers, distinct by hex, era, and world cycle."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Iterable

from sim.dmb.core.types import TypeValidationError
from sim.dmb.industry import fraction, fraction_wire


@dataclass(frozen=True)
class LayerState:
    layer_id: str
    hex_id: str
    resource_id: str
    era: str
    cycle: int
    finite_balance: Fraction | None
    renewable_capacity: Fraction | None
    retired: bool = False

    @property
    def finite(self) -> bool:
        return self.finite_balance is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.layer_id,
            "hex_id": self.hex_id,
            "resource_id": self.resource_id,
            "era": self.era,
            "cycle": self.cycle,
            "finite_balance": None if self.finite_balance is None else fraction_wire(self.finite_balance),
            "renewable_capacity": None if self.renewable_capacity is None else fraction_wire(self.renewable_capacity),
            "retired": self.retired,
        }

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> "LayerState":
        return cls(
            layer_id=str(record["id"]),
            hex_id=str(record["hex_id"]),
            resource_id=str(record["resource_id"]),
            era=str(record["era"]),
            cycle=int(record["cycle"]),
            finite_balance=None if record.get("finite_balance") is None else fraction(record["finite_balance"]),
            renewable_capacity=None if record.get("renewable_capacity") is None else fraction(record["renewable_capacity"]),
            retired=bool(record.get("retired", False)),
        )


class ResourceLayerService:
    def __init__(self, industry_state: dict[str, Any]):
        self.state = industry_state
        self.layers = self.state.setdefault("layers", {})

    def create_layer(
        self,
        hex_id: str,
        resource_id: str,
        era: str,
        cycle: int,
        *,
        finite: bool,
        renewable_capacity: Fraction | str = Fraction(1, 10),
    ) -> LayerState:
        layer_id = f"layer:{hex_id}:{era}:{cycle}:{resource_id}"
        existing = self.layers.get(layer_id)
        if existing is not None:
            return LayerState.from_dict(existing)
        layer = LayerState(
            layer_id,
            hex_id,
            resource_id,
            era,
            int(cycle),
            Fraction(600) if finite else None,
            None if finite else fraction(renewable_capacity),
        )
        self.layers[layer_id] = layer.to_dict()
        return layer

    def balance(self, layer_id: str) -> Fraction | None:
        return LayerState.from_dict(self.layers[layer_id]).finite_balance

    def consume_plan(self, debits: Iterable[tuple[str, Fraction]]) -> dict[str, Fraction]:
        totals: dict[str, Fraction] = {}
        for layer_id, amount in debits:
            exact = fraction(amount)
            if exact < 0:
                raise TypeValidationError("negative layer debit")
            totals[layer_id] = totals.get(layer_id, Fraction()) + exact
        for layer_id, amount in totals.items():
            layer = LayerState.from_dict(self.layers[layer_id])
            if layer.retired:
                raise TypeValidationError(f"retired layer {layer_id}")
            if layer.finite_balance is not None and amount > layer.finite_balance:
                raise TypeValidationError(f"insufficient finite layer {layer_id}")
        for layer_id, amount in totals.items():
            record = self.layers[layer_id]
            if record.get("finite_balance") is not None:
                record["finite_balance"] = fraction_wire(fraction(record["finite_balance"]) - amount)
        return totals

    def restore_explicitly(self, layer_id: str, amount: Fraction) -> None:
        record = self.layers[layer_id]
        if record.get("finite_balance") is None:
            raise TypeValidationError("renewable layer has no balance")
        record["finite_balance"] = fraction_wire(fraction(record["finite_balance"]) + fraction(amount))

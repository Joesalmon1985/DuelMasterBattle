"""Common validated value types for the authoritative Python simulation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, NewType

JSON_INT_MAX = (1 << 53) - 1
JSON_INT_MIN = -JSON_INT_MAX
FIXED_POINT_SCALE = 1_000_000

DefinitionId = NewType("DefinitionId", str)
EntityId = NewType("EntityId", str)
CommandId = NewType("CommandId", str)
EffectId = NewType("EffectId", str)
CauseId = NewType("CauseId", str)
LeaseId = NewType("LeaseId", str)
TransitionId = NewType("TransitionId", str)
EventId = NewType("EventId", str)
WorldId = NewType("WorldId", str)

_DEF_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
_INSTANCE_RE = re.compile(r"^[a-z][a-z0-9_]*:\d+$")


class TypeValidationError(ValueError):
    pass


def validate_definition_id(value: str) -> DefinitionId:
    if not isinstance(value, str) or not _DEF_RE.fullmatch(value):
        raise TypeValidationError(f"invalid definition id: {value!r}")
    return DefinitionId(value)


def validate_instance_id(value: str) -> EntityId:
    if not isinstance(value, str) or not _INSTANCE_RE.fullmatch(value):
        raise TypeValidationError(f"invalid instance id: {value!r}")
    return EntityId(value)


def wire_int(value: int) -> int | str:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeValidationError("wire_int requires int")
    if JSON_INT_MIN <= value <= JSON_INT_MAX:
        return value
    return format(value, "d")


def parse_wire_int(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeValidationError("boolean is not a wire int")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value):
        return int(value)
    raise TypeValidationError(f"invalid wire int: {value!r}")


@dataclass(frozen=True, slots=True)
class RationalCarry:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if self.denominator <= 0:
            raise TypeValidationError("denominator must be positive")

    def to_wire(self) -> dict[str, str]:
        return {
            "numerator": format(self.numerator, "d"),
            "denominator": format(self.denominator, "d"),
        }

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> "RationalCarry":
        return cls(parse_wire_int(payload["numerator"]), parse_wire_int(payload["denominator"]))

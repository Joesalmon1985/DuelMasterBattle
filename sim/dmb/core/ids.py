"""Deterministic identity allocation scoped by world_id."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import EntityId, TypeValidationError, WorldId, parse_wire_int, wire_int

INSTANCE_KINDS = (
    "person",
    "building",
    "cart",
    "unit",
    "formation",
    "battle",
    "cube",
    "settlement",
    "faction",
    "item",
    "quest",
    "lease",
    "event",
    "command",
    "effect",
    "cause",
    "node",
    "tech",
    "visit",
    "dialogue",
)


@dataclass
class IdAllocator:
    world_id: WorldId
    counters: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.world_id, str) or not self.world_id:
            raise TypeValidationError("world_id required")
        for kind, value in list(self.counters.items()):
            self.counters[kind] = int(value)

    def new(self, kind: str) -> EntityId:
        if kind not in INSTANCE_KINDS:
            raise TypeValidationError(f"unknown id kind: {kind}")
        nxt = self.counters.get(kind, 0) + 1
        self.counters[kind] = nxt
        return EntityId(f"{kind}:{nxt}")

    def peek(self, kind: str) -> int:
        return int(self.counters.get(kind, 0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "counters": {kind: wire_int(value) for kind, value in sorted(self.counters.items())},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, expected_world_id: str | None = None) -> "IdAllocator":
        world_id = str(payload.get("world_id", ""))
        if expected_world_id is not None and world_id != expected_world_id:
            raise TypeValidationError(
                f"foreign world_id rejected: got {world_id!r}, expected {expected_world_id!r}"
            )
        counters = {
            str(kind): parse_wire_int(value) for kind, value in dict(payload.get("counters", {})).items()
        }
        return cls(WorldId(world_id), counters)

"""Ordered replay input records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReplayLog:
    inputs: list[dict[str, Any]] = field(default_factory=list)

    def append(self, kind: str, payload: dict[str, Any], *, sequence: int) -> None:
        self.inputs.append({"sequence": sequence, "kind": kind, "payload": dict(payload)})

    def ordered(self) -> list[dict[str, Any]]:
        return sorted(self.inputs, key=lambda item: int(item["sequence"]))

    def to_dict(self) -> dict[str, Any]:
        return {"inputs": self.ordered()}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReplayLog":
        log = cls()
        log.inputs = [dict(item) for item in payload.get("inputs", [])]
        return log

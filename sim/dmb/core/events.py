"""Ordered immutable event journal."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EventJournal:
    events: list[dict[str, Any]] = field(default_factory=list)
    next_sequence: int = 1

    def append_batch(self, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        committed: list[dict[str, Any]] = []
        for raw in batch:
            event = dict(raw)
            event["sequence"] = self.next_sequence
            self.next_sequence += 1
            self.events.append(event)
            committed.append(event)
        return committed

    def since(self, sequence: int) -> list[dict[str, Any]]:
        return [event for event in self.events if int(event["sequence"]) > sequence]

    def to_dict(self) -> dict[str, Any]:
        return {"events": list(self.events), "next_sequence": self.next_sequence}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EventJournal":
        return cls(
            events=[dict(event) for event in payload.get("events", [])],
            next_sequence=int(payload.get("next_sequence", 1)),
        )

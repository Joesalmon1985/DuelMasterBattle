"""Immediate terminal/interrupt checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState


@dataclass
class ImmediateOutcomeService:
    state: WorldState

    def check(self) -> dict[str, Any] | None:
        if self.state.clock.get("force_terminal"):
            return {"interrupt": "terminal_loss", "code": "TERMINAL"}
        return None

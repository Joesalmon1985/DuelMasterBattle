"""Game-time clock with pause tokens and accounting quanta."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.types import TypeValidationError

QUANTUM_MS = 100


@dataclass
class ClockService:
    state_clock: dict[str, Any]

    def clock_view(self) -> dict[str, Any]:
        return {
            "game_ms": int(self.state_clock.get("game_ms", 0)),
            "residual_ms": int(self.state_clock.get("residual_ms", 0)),
            "turn": int(self.state_clock.get("turn", 0)),
            "round": int(self.state_clock.get("round", 0)),
            "pause_tokens": dict(self.state_clock.get("pause_tokens", {})),
            "clock_sequence": int(self.state_clock.get("clock_sequence", 0)),
            "paused": bool(self.state_clock.get("pause_tokens")),
        }

    def acquire_pause(self, reason: str, owner: str) -> str:
        token = f"{reason}:{owner}:{len(self.state_clock.setdefault('pause_tokens', {})) + 1}"
        self.state_clock.setdefault("pause_tokens", {})[token] = {
            "reason": reason,
            "owner": owner,
        }
        return token

    def release_pause(self, token: str) -> None:
        tokens = self.state_clock.setdefault("pause_tokens", {})
        if token not in tokens:
            raise TypeValidationError(f"unknown pause token {token}")
        del tokens[token]

    def request_advance(self, ms: int, sequence: int) -> int:
        if ms < 0:
            raise TypeValidationError("negative advance forbidden")
        current_seq = int(self.state_clock.get("clock_sequence", 0))
        if sequence != current_seq + 1:
            # Duplicate or stale advance produces zero quanta.
            return 0
        if self.state_clock.get("pause_tokens"):
            self.state_clock["clock_sequence"] = sequence
            return 0
        total = int(self.state_clock.get("residual_ms", 0)) + int(ms)
        quanta = total // QUANTUM_MS
        self.state_clock["residual_ms"] = total % QUANTUM_MS
        self.state_clock["game_ms"] = int(self.state_clock.get("game_ms", 0)) + quanta * QUANTUM_MS
        self.state_clock["clock_sequence"] = sequence
        return quanta

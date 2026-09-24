"""Local compute budget for bounded training jobs (C12 / T146)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ComputeBudget:
    """Stop on explicit local budget.

    Reaching the decision target successfully is completion, not failure.
    `incomplete_batch` means the job stopped prematurely (time, interrupt,
    environment error) before the intended target was met.
    """

    max_seconds: float
    max_decisions: int
    label: str = "train"
    started_at: float = field(default_factory=time.monotonic)
    decisions: int = 0
    stopped_reason: str | None = None
    premature: bool = False

    def touch(self) -> None:
        if self.exhausted():
            return

    def note_decision(self, n: int = 1) -> None:
        self.decisions += n
        if self.decisions >= self.max_decisions and self.stopped_reason is None:
            self.stopped_reason = "max_decisions"
        if (time.monotonic() - self.started_at) >= self.max_seconds and self.stopped_reason is None:
            self.stopped_reason = "max_seconds"
            self.premature = True

    def mark_premature(self, reason: str) -> None:
        """Record an early stop that did not meet the intended target."""
        if self.stopped_reason is None:
            self.stopped_reason = reason
        self.premature = True

    def exhausted(self) -> bool:
        if self.stopped_reason:
            return True
        if self.decisions >= self.max_decisions:
            self.stopped_reason = "max_decisions"
            return True
        if (time.monotonic() - self.started_at) >= self.max_seconds:
            self.stopped_reason = "max_seconds"
            self.premature = True
            return True
        return False

    def target_met(self) -> bool:
        return self.decisions >= self.max_decisions and not self.premature

    def snapshot(self) -> dict[str, Any]:
        target_met = self.decisions >= self.max_decisions and (
            self.stopped_reason in {None, "max_decisions"} and not self.premature
        )
        # Hitting max_decisions as the intended stop is complete success.
        if self.stopped_reason == "max_decisions" and self.decisions >= self.max_decisions:
            target_met = True
        incomplete = bool(self.premature) or (
            self.stopped_reason not in {None, "max_decisions"} and self.decisions < self.max_decisions
        )
        if self.stopped_reason == "max_seconds" and self.decisions < self.max_decisions:
            incomplete = True
        return {
            "label": self.label,
            "max_seconds": self.max_seconds,
            "max_decisions": self.max_decisions,
            "decisions": self.decisions,
            "elapsed_seconds": round(time.monotonic() - self.started_at, 3),
            "stopped_reason": self.stopped_reason,
            "complete": bool(target_met),
            "incomplete_batch": bool(incomplete) and not bool(target_met),
        }

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.snapshot(), indent=2) + "\n", encoding="utf-8")

"""Local compute budget for bounded training jobs (C12 / T146)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ComputeBudget:
    """Stop on explicit local budget — incomplete batch is not promotion."""

    max_seconds: float
    max_decisions: int
    label: str = "train"
    started_at: float = field(default_factory=time.monotonic)
    decisions: int = 0
    stopped_reason: str | None = None

    def touch(self) -> None:
        if self.exhausted():
            return

    def note_decision(self, n: int = 1) -> None:
        self.decisions += n
        if self.decisions >= self.max_decisions and self.stopped_reason is None:
            self.stopped_reason = "max_decisions"
        if (time.monotonic() - self.started_at) >= self.max_seconds and self.stopped_reason is None:
            self.stopped_reason = "max_seconds"

    def exhausted(self) -> bool:
        if self.stopped_reason:
            return True
        if self.decisions >= self.max_decisions:
            self.stopped_reason = "max_decisions"
            return True
        if (time.monotonic() - self.started_at) >= self.max_seconds:
            self.stopped_reason = "max_seconds"
            return True
        return False

    def snapshot(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "max_seconds": self.max_seconds,
            "max_decisions": self.max_decisions,
            "decisions": self.decisions,
            "elapsed_seconds": round(time.monotonic() - self.started_at, 3),
            "stopped_reason": self.stopped_reason,
            "complete": self.stopped_reason is None
            and self.decisions >= self.max_decisions,  # noqa: intentional — complete only if target met without early stop confusion
            "incomplete_batch": bool(self.stopped_reason),
        }

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.snapshot(), indent=2) + "\n", encoding="utf-8")

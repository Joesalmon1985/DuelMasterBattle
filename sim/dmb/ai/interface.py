"""Faction brain interface — choose without mutating (C12 / T042)."""

from __future__ import annotations

from typing import Any, Protocol


class FactionBrain(Protocol):
    def choose(self, observation: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
        """Return exactly one candidate_id. Must not mutate world state."""
        ...


class NoOpBrain:
    """Always selects the legal no-op when present."""

    def choose(self, observation: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
        for cand in candidates:
            if cand.get("action_kind") == "noop":
                return str(cand["id"])
        if not candidates:
            raise RuntimeError("no candidates")
        return str(candidates[0]["id"])

"""Derived victory points from centres (C04 / T031)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState

VP_THRESHOLD = 10


@dataclass
class ScoreService:
    state: WorldState

    def settlement_vp(self, settlement: dict[str, Any]) -> int:
        if settlement.get("status") in {"ruined", "inert", "destroyed"}:
            return 0
        if settlement.get("ruin_only"):
            return 0
        if not settlement.get("operational", True):
            return 0
        if settlement.get("legacy") and not settlement.get("upgraded"):
            return 0  # Legacy unupgraded site 0 VP
        if settlement.get("staging"):
            return 0  # Neutral staging stores are not settlements
        tier = settlement.get("tier", "settlement")
        if tier == "city":
            return 2
        if tier in {"settlement", "core"}:
            return 1
        return 0

    def score(self, faction_id: str) -> int:
        total = 0
        for settlement in self.state.settlements.values():
            if settlement.get("faction_id") != faction_id:
                continue
            total += self.settlement_vp(settlement)
        return total

    def scores(self) -> dict[str, int]:
        factions = set()
        for settlement in self.state.settlements.values():
            fid = settlement.get("faction_id")
            if fid:
                factions.add(str(fid))
        for fid in self.state.factions:
            factions.add(str(fid))
        return {fid: self.score(fid) for fid in sorted(factions)}

    def check_threshold(self, threshold: int = VP_THRESHOLD) -> list[str]:
        """Return faction IDs at/above threshold in stable ID order."""
        return [fid for fid, pts in sorted(self.scores().items()) if pts >= threshold]

"""Relic, scar and contamination dispositions for full cycles (C11 / T126)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class LegacyDispositionService:
    state: Any

    def _bucket(self) -> dict[str, Any]:
        legacy = self.state.board.setdefault("legacy", {})
        legacy.setdefault("scars", {})
        legacy.setdefault("relics", {})
        legacy.setdefault("contamination", {})
        legacy.setdefault("inert_ruins", {})
        return legacy

    def record_inert_ruin(self, settlement_id: str, *, cause: str = "collapse") -> dict[str, Any]:
        legacy = self._bucket()
        record = {
            "id": settlement_id,
            "kind": "inert_ruin",
            "loot": False,
            "collision": False,
            "vp": 0,
            "cause": cause,
        }
        legacy["inert_ruins"][settlement_id] = record
        settlement = self.state.settlements.get(settlement_id) or {}
        settlement["ruin_only"] = True
        settlement["blocks_placement"] = False
        settlement["operational"] = False
        return record

    def record_scar(self, place_id: str, *, scar_type: str, active: bool = True) -> dict[str, Any]:
        legacy = self._bucket()
        record = {
            "id": f"scar:{place_id}:{scar_type}",
            "place_id": place_id,
            "scar_type": scar_type,
            "active": active,
            "faction_id": None,
        }
        legacy["scars"][record["id"]] = record
        return record

    def register_relic(self, relic_id: str, *, kind: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        legacy = self._bucket()
        record = {
            "id": relic_id,
            "kind": kind,
            "active": True,
            "faction_id": None,
            "joins_army": False,
            "payload": dict(payload or {}),
        }
        if kind == "future_soldier":
            # Unsupported silent army join — remain inert history.
            record["active"] = False
            record["joins_army"] = False
            record["status"] = "unsupported_army_relic"
        legacy["relics"][relic_id] = record
        return record

    def preserve_bunker(self, bunker_id: str, *, puzzle_state: Mapping[str, Any]) -> dict[str, Any]:
        return self.register_relic(
            bunker_id,
            kind="bunker",
            payload={"puzzle_state": dict(puzzle_state), "retains_puzzle": True},
        )

"""Turn roster and seat scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TurnScheduler:
    clock: dict[str, Any]

    def begin_turn(self, trigger: str) -> None:
        self.clock["turn"] = int(self.clock.get("turn", 0)) + 1
        roster = [
            faction
            for faction in list(self.clock.get("scheduled_faction_ids") or ["faction:player"])
            if faction and faction not in set(self.clock.get("removed_faction_ids", []))
        ]
        self.clock["scheduled_faction_ids"] = roster
        self.clock["completed_seats"] = []
        self.clock["active_faction_id"] = roster[0] if roster else None
        self.clock["last_trigger"] = trigger
        self.clock["draft"] = None
        self.clock["round_complete"] = False

    def remove_faction(self, faction_id: str) -> None:
        removed = set(self.clock.setdefault("removed_faction_ids", []))
        removed.add(faction_id)
        self.clock["removed_faction_ids"] = sorted(removed)
        roster = [faction for faction in self.clock.get("scheduled_faction_ids", []) if faction != faction_id]
        self.clock["scheduled_faction_ids"] = roster
        if self.clock.get("active_faction_id") == faction_id:
            remaining = [faction for faction in roster if faction not in self.clock.get("completed_seats", [])]
            self.clock["active_faction_id"] = remaining[0] if remaining else None

    def active_seat(self) -> str | None:
        return self.clock.get("active_faction_id")

    def finish_seat(self) -> dict[str, Any]:
        active = self.clock.get("active_faction_id")
        completed = list(self.clock.get("completed_seats", []))
        if active and active not in completed:
            completed.append(active)
        self.clock["completed_seats"] = completed
        roster = [
            faction
            for faction in self.clock.get("scheduled_faction_ids", [])
            if faction and faction not in set(self.clock.get("removed_faction_ids", []))
        ]
        remaining = [faction for faction in roster if faction not in completed]
        if remaining:
            self.clock["active_faction_id"] = remaining[0]
            self.clock["round_complete"] = False
            self.clock["draft"] = None
            return {"round_complete": False, "active_faction_id": remaining[0], "draft": None}
        self.clock["round"] = int(self.clock.get("round", 0)) + 1
        self.clock["active_faction_id"] = None
        self.clock["round_complete"] = True
        draft = {"round": self.clock["round"], "seats": list(completed)}
        self.clock["draft"] = draft
        return {"round_complete": True, "round": self.clock["round"], "draft": draft}

    def reset_for_era(self, faction_ids: list[str]) -> None:
        self.clock["scheduled_faction_ids"] = list(faction_ids)
        self.clock["completed_seats"] = []
        self.clock["removed_faction_ids"] = []
        self.clock["active_faction_id"] = faction_ids[0] if faction_ids else None
        self.clock["draft"] = None
        self.clock["round_complete"] = False

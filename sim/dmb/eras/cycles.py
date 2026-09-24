"""Full-cycle political reseeding (C11 / T125).

Future→Prehistoric is political reseeding, not ordinary legacy continuation.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass
class CycleReseedService:
    state: Any

    def reseed_cycle(self, *, plan_id: str | None = None, faction_count: int = 6) -> dict[str, Any]:
        """Retire strategic memberships and seed a new Prehistoric contest."""
        receipts = self.state.command_receipts.setdefault("cycle_reseed", {})
        key = plan_id or f"reseed:{int(self.state.clock.get('cycle') or 0)}"
        if key in receipts:
            return {"idempotent": True, "receipt": receipts[key]}

        before_cycle = int(self.state.clock.get("cycle") or 0)
        people_before = set(self.state.people)
        board_hexes = deepcopy((self.state.board.get("topology") or {}).get("hexes"))
        board_numbers = deepcopy(self.state.board.get("hex_numbers") or self.state.board.get("numbers"))

        # Retire military organisations and research competition.
        retired_units = []
        for uid, unit in list((self.state.units or {}).items()):
            if unit.get("alive", True):
                unit["alive"] = False
                unit["status"] = "retired_cycle"
                unit["faction_id"] = None
                retired_units.append(uid)
        for fid, formation in list((getattr(self.state, "formations", {}) or {}).items()):
            formation["unit_ids"] = []
            formation["status"] = "retired_cycle"

        # Archive old factions; keep IDs for chronicle lineage.
        old_factions = list(self.state.factions)
        for fid, faction in self.state.factions.items():
            faction["status"] = "retired_cycle"
            faction["operational"] = False
            faction["research"] = {}

        # Preserve industrial layer historical balances under prior cycle key.
        industry = self.state.industry.setdefault("layers", {})
        archived_layers = 0
        for lid, layer in industry.items():
            if isinstance(layer, dict) and "cycle" in layer:
                layer["historical_cycle"] = layer.get("cycle")
                layer["archived"] = True
                archived_layers += 1

        # New cycle number increments once.
        new_cycle = before_cycle + 1
        self.state.clock["cycle"] = new_cycle
        self.state.clock["era"] = "prehistoric"
        self.state.clock["era_id"] = "prehistoric"
        self.state.board["era_id"] = "prehistoric"
        self.state.clock["next_future_path"] = "dystopia"
        self.state.clock.pop("interrupt_reason", None)
        self.state.clock.pop("era_transition_handled_interrupt", None)
        self.state.clock.pop("last_era_transition_id", None)

        # Seed new factions (bounded by request; setup may later remap seats).
        new_faction_ids: list[str] = []
        for i in range(max(1, min(int(faction_count), 6))):
            fid = self.state.ids.new("faction")
            self.state.factions[fid] = {
                "id": fid,
                "status": "active",
                "operational": True,
                "cycle": new_cycle,
                "era": "prehistoric",
            }
            new_faction_ids.append(fid)
        self.state.clock["started_faction_ids"] = list(new_faction_ids)
        self.state.clock["sole_era_starter"] = len(new_faction_ids) == 1

        # Living people preserved; clear military affiliation only.
        for person in self.state.people.values():
            if not person.get("alive", True):
                continue
            if person.get("role") == "soldier" or person.get("unit_id"):
                person["affiliation"] = None
                person["unit_id"] = None
                person["occupation"] = person.get("occupation") or "displaced"
            # Civilian affiliations cleared for political reseeding.
            elif person.get("affiliation") in old_factions:
                person["affiliation"] = None

        assert set(self.state.people) == people_before
        if board_hexes is not None:
            assert (self.state.board.get("topology") or {}).get("hexes") == board_hexes

        receipt = {
            "plan_id": key,
            "previous_cycle": before_cycle,
            "cycle": new_cycle,
            "era": "prehistoric",
            "retired_factions": old_factions,
            "new_faction_ids": new_faction_ids,
            "retired_units": retired_units,
            "archived_layers": archived_layers,
            "next_future_path": "dystopia",
            "board_numbers_preserved": board_numbers is not None,
        }
        receipts[key] = receipt
        from sim.dmb.history.chronicle import HistoryService

        HistoryService(self.state).record(
            kind="cycle_reseed",
            summary=f"Cycle {before_cycle} → {new_cycle} Prehistoric reseed",
            subject_ids=new_faction_ids,
            facts=receipt,
            transition_id=key,
        )
        return {"idempotent": False, "receipt": receipt}

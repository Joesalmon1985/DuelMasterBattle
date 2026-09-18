"""Player catastrophe visits and treatment allowances (C08 / T072)."""

from __future__ import annotations

from typing import Any


class VisitService:
    def __init__(self, world_state: Any):
        self.state = world_state
        player = self.state.player.setdefault("visits", {})
        player.setdefault("current", None)
        player.setdefault("ledgers", {})

    def arrive(self, node_id: str, arrival_kind: str, turn: int) -> dict[str, Any]:
        """New strategic arrival creates a visit; Wait/interior/load reuse ledgers."""
        visits = self.state.player["visits"]
        key = f"{node_id}:{int(turn)}"
        if arrival_kind in {"wait", "interior", "load", "recovery", "menu"}:
            # Do not refresh allowances.
            current = visits.get("current")
            if current and current.get("node_id") == node_id:
                return {"status": "retained", "visit": current}
            ledger = visits["ledgers"].get(key)
            if ledger:
                visits["current"] = ledger
                return {"status": "restored_ledger", "visit": ledger}
            # Same-turn recovery without prior ledger still no new allowance refresh
            return {"status": "no_refresh", "visit": visits.get("current")}

        visit_id = self.state.ids.new("visit")
        visit = {
            "id": visit_id,
            "node_id": node_id,
            "arrival_turn": int(turn),
            "arrival_kind": arrival_kind,
            "treated_hexes": [],
            "success_count": 0,
        }
        visits["current"] = visit
        visits["ledgers"][key] = visit
        return {"status": "new", "visit": visit}

    def can_treat(self, hex_id: str) -> dict[str, Any]:
        visit = (self.state.player.get("visits") or {}).get("current")
        if not visit:
            return {"ok": False, "reason": "no_visit"}
        treated = set(visit.get("treated_hexes") or [])
        if hex_id in treated:
            return {"ok": False, "reason": "hex_already_treated"}
        if int(visit.get("success_count") or 0) >= 3:
            return {"ok": False, "reason": "visit_cap"}
        # Must be adjacent to player node.
        node_id = str(visit.get("node_id"))
        touching = (self.state.board.get("node_hexes") or {}).get(node_id) or []
        if hex_id not in touching and hex_id != node_id:
            # Also allow hexes listed as adjacent via board helper.
            adj = (self.state.board.get("node_adjacent_hexes") or {}).get(node_id) or touching
            if hex_id not in adj:
                return {"ok": False, "reason": "not_adjacent"}
        return {"ok": True, "visit_id": visit["id"]}

    def record_success(self, hex_id: str, effect_id: str) -> dict[str, Any]:
        check = self.can_treat(hex_id)
        if not check.get("ok"):
            return {"status": "rejected", **check}
        visit = self.state.player["visits"]["current"]
        visit.setdefault("treated_hexes", []).append(hex_id)
        visit["success_count"] = int(visit.get("success_count") or 0) + 1
        visit.setdefault("effects", []).append(effect_id)
        # Persist ledger
        key = f"{visit['node_id']}:{visit['arrival_turn']}"
        self.state.player["visits"]["ledgers"][key] = visit
        return {"status": "recorded", "visit": visit, "hex_id": hex_id}

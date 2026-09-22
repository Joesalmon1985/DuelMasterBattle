"""Faction hazard responders treat instead of moving (C08 / T073)."""

from __future__ import annotations

from typing import Any

from sim.dmb.hazards.service import CatastropheService

# Baseline responder capability by hazard type.
RESPONDER_CAPABILITY = {
    "demon": {"eras": {"prehistoric", "historic", "ancient", "modern", "future"}, "units": {"line", "heavy", "skirmisher"}},
    "alien": {"eras": {"modern", "future"}, "units": {"skirmisher", "line"}},
    "machine": {"eras": {"future"}, "units": {"heavy", "line"}},
    "nuclear": {"eras": {"future"}, "units": {"heavy"}},
    "pollution": {"eras": {"modern", "future"}, "facilities": {"cleanup"}, "units": set()},
}


class HazardResponder:
    def __init__(self, world_state: Any):
        self.state = world_state
        self.service = CatastropheService(world_state)

    def eligible_treatments(self, faction_id: str) -> list[dict[str, Any]]:
        active = self.state.clock.get("active_faction_id")
        if active is not None and str(active) != faction_id:
            return []
        out = []
        formations = getattr(self.state, "formations", {}) or {}
        for fid, formation in formations.items():
            if str(formation.get("faction_id")) != faction_id:
                continue
            if formation.get("movement_spent_turn") == self.state.clock.get("turn"):
                continue
            node_id = str(formation.get("node_id"))
            touching = (self.state.board.get("node_hexes") or {}).get(node_id) or []
            for hex_id in touching:
                for cube in self.service.cubes_on_hex(hex_id):
                    if self._formation_can_treat(formation, cube):
                        out.append(
                            {
                                "formation_id": fid,
                                "cube_id": cube["id"],
                                "hex_id": hex_id,
                                "type": cube["type"],
                            }
                        )
        return out

    def _formation_can_treat(self, formation: dict[str, Any], cube: dict[str, Any]) -> bool:
        htype = cube.get("type")
        caps = RESPONDER_CAPABILITY.get(str(htype))
        if caps is None:
            return False
        era = str(self.state.clock.get("era") or "prehistoric").lower()
        if era not in caps["eras"]:
            return False
        if htype == "pollution":
            # Cleanup facility at the formation node, or a cleanup-capable modern unit.
            node_id = formation.get("node_id")
            for b in (self.state.buildings or {}).values():
                if b.get("node_id") == node_id and (
                    b.get("cleanup_capable") or "cleanup" in str(b.get("definition_id") or "")
                ):
                    return True
            for uid in formation.get("unit_ids") or []:
                unit = self.state.units.get(uid)
                if unit is None or not unit.get("alive", True):
                    continue
                def_id = str(unit.get("definition_id") or "")
                if unit.get("cleanup_capable") or "cleanup" in def_id:
                    return True
            return False
        for uid in formation.get("unit_ids") or []:
            unit = self.state.units.get(uid)
            if unit is None or not unit.get("alive", True):
                continue
            arch = str(unit.get("archetype") or "")
            if arch in caps.get("units", set()):
                return True
        return False

    def treat(self, formation_id: str, cube_id: str) -> dict[str, Any]:
        active = self.state.clock.get("active_faction_id")
        formation = (getattr(self.state, "formations", {}) or {}).get(formation_id)
        if formation is None:
            return {"status": "rejected", "reason": "missing_formation"}
        if active is not None and str(formation.get("faction_id")) != str(active):
            return {"status": "rejected", "reason": "inactive_faction"}
        # Reserve activation — zero edges moved.
        turn = int(self.state.clock.get("turn", 0))
        if formation.get("movement_spent_turn") == turn:
            return {"status": "rejected", "reason": "already_acted"}
        cube = (self.service._cat().get("cubes") or {}).get(cube_id)
        if cube is None or not cube.get("active", True):
            return {"status": "noop", "reason": "already_removed", "removed": False}
        if not self._formation_can_treat(formation, cube):
            return {"status": "rejected", "reason": "ineligible"}
        result = self.service.remove_cube(cube_id, authority=f"responder:{formation_id}")
        formation["movement_spent_turn"] = turn
        formation["path"] = []
        return {
            "status": "treated",
            "cube_id": cube_id,
            "edges_moved": 0,
            "removal": result,
        }

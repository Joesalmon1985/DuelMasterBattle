"""Formation grouping over individual unit IDs (C07)."""

from __future__ import annotations

from typing import Any

from sim.dmb.military.units import MilitaryService


class FormationDirector:
    """Thin facade: grouping and strength live on MilitaryService."""

    def __init__(self, world_state: Any):
        self.state = world_state
        self.military = MilitaryService(world_state)

    def group(self, unit_ids: list[str], *, faction_id: str, node_id: str) -> dict[str, Any]:
        return self.military.group(unit_ids, faction_id=faction_id, node_id=node_id)

    def get(self, formation_id: str) -> dict[str, Any]:
        formations = getattr(self.state, "formations", {}) or {}
        return formations[formation_id]

    def strength(self, formation_id: str) -> int:
        return self.military.formation_strength(formation_id)

    def assert_exclusive_membership(self) -> None:
        seen: dict[str, str] = {}
        formations = getattr(self.state, "formations", {}) or {}
        for formation_id, formation in formations.items():
            for unit_id in formation.get("unit_ids", []):
                if unit_id in seen:
                    raise ValueError(f"unit {unit_id} in {seen[unit_id]} and {formation_id}")
                seen[unit_id] = formation_id
                unit = self.state.units.get(unit_id)
                if unit is not None and unit.get("formation_id") not in {None, formation_id}:
                    raise ValueError(f"unit {unit_id} formation pointer mismatch")

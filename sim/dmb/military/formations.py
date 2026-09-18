"""Formation grouping over individual unit IDs (C07)."""

from __future__ import annotations

from typing import Any, Sequence

from sim.dmb.military.units import MilitaryService


class FormationDirector:
    """Grouping plus strategic movement/withdrawal via StrategicMovement."""

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

    def _movement(self):
        from sim.dmb.military.movement import StrategicMovement

        return StrategicMovement(self.state)

    def legal_objectives(self, formation_id: str, *, active_faction_id: str) -> list[dict[str, Any]]:
        return self._movement().legal_objectives(formation_id, active_faction_id=active_faction_id)

    def activate(
        self,
        formation_id: str,
        path: Sequence[str],
        *,
        active_faction_id: str,
        turn: int | None = None,
    ) -> dict[str, Any]:
        return self._movement().activate(
            formation_id, path, active_faction_id=active_faction_id, turn=turn
        )

    def mark_withdrawal(
        self,
        formation_id: str,
        *,
        entry_effective_health: int | None = None,
    ) -> dict[str, Any]:
        return self._movement().mark_withdrawal(
            formation_id, entry_effective_health=entry_effective_health
        )

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

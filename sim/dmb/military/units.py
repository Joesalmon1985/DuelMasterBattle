"""Individual persistent military unit creation."""

from __future__ import annotations

from typing import Any


class MilitaryService:
    def __init__(self, world_state: Any):
        self.state = world_state

    def spawn(
        self,
        unit_def_id: str,
        *,
        home_node_id: str,
        faction_id: str,
        era: str,
        factory_id: str,
    ) -> dict[str, Any]:
        unit_id = self.state.ids.new("unit")
        record = {
            "id": unit_id,
            "definition_id": unit_def_id,
            "home_node_id": home_node_id,
            "node_id": home_node_id,
            "faction_id": faction_id,
            "era": era,
            "factory_id": factory_id,
            "status": "available",
            "alive": True,
        }
        self.state.units[unit_id] = record
        return record

"""Typed catastrophe cubes and placement cadence (C08 / T069)."""

from __future__ import annotations

from typing import Any

from sim.dmb.hazards.deck import HazardDeck
from sim.dmb.hazards.propagation import PropagationEngine

HAZARD_TYPES = ("demon", "alien", "machine", "nuclear", "pollution")
MAX_CUBES_PER_HEX = 3
CADENCE = {
    "standard": 3,
    "gentle": 5,
    "severe": 2,
}
OUTBREAK_TERMINAL = 8


def draw_count_for_era_rounds(era_completed_rounds: int) -> int:
    if era_completed_rounds < 4:
        return 1
    if era_completed_rounds < 8:
        return 2
    return 3


class CatastropheService:
    def __init__(self, world_state: Any, *, difficulty: str = "standard"):
        self.state = world_state
        self.difficulty = difficulty if difficulty in CADENCE else "standard"
        self.state.hazards.setdefault("catastrophe", {})
        self.deck = HazardDeck(world_state)

    def _cat(self) -> dict[str, Any]:
        return self.state.hazards["catastrophe"]

    def add_cube(self, hex_id: str, hazard_type: str, cause_id: str | None = None) -> dict[str, Any]:
        if hazard_type not in HAZARD_TYPES:
            raise ValueError(f"unknown hazard type {hazard_type!r}")
        cat = self._cat()
        cubes = cat.setdefault("cubes", {})
        on_hex = [c for c in cubes.values() if c.get("hex_id") == hex_id and c.get("active", True)]
        if len(on_hex) >= MAX_CUBES_PER_HEX:
            return {"status": "full", "hex_id": hex_id, "count": len(on_hex)}
        cube_id = self.state.ids.new("cube")
        cause = cause_id or self.state.ids.new("cause")
        record = {
            "id": cube_id,
            "hex_id": hex_id,
            "type": hazard_type,
            "cause_id": cause,
            "added_turn": int(self.state.clock.get("turn", 0)),
            "source_event": cat.get("propagation_event_id"),
            "active": True,
        }
        cubes[cube_id] = record
        # Mirror onto board for legacy queries.
        board_cubes = self.state.board.setdefault("hazard_cubes", {})
        board_cubes[cube_id] = {"hex_id": hex_id, "active": True, "type": hazard_type, "node_id": None}
        return {"status": "added", "cube": record}

    def remove_cube(self, cube_id: str, authority: str) -> dict[str, Any]:
        cat = self._cat()
        cube = cat.get("cubes", {}).get(cube_id)
        if cube is None or not cube.get("active", True):
            return {"status": "already_removed", "cube_id": cube_id, "authority": authority}
        cube["active"] = False
        cube["removed_by"] = authority
        board_cubes = self.state.board.get("hazard_cubes") or {}
        if cube_id in board_cubes:
            board_cubes[cube_id]["active"] = False
        return {"status": "removed", "cube_id": cube_id, "authority": authority}

    def cubes_on_hex(self, hex_id: str) -> list[dict[str, Any]]:
        return [
            c
            for c in (self._cat().get("cubes") or {}).values()
            if c.get("hex_id") == hex_id and c.get("active", True)
        ]

    def is_source_blocked(self, hex_id: str) -> bool:
        return len(self.cubes_on_hex(hex_id)) > 0

    def is_civilian_blocked(self, node_id: str) -> bool:
        from sim.dmb.hazards.queries import node_blocked_for_civilian

        return node_blocked_for_civilian(
            self.state.board, node_id, touching_hexes=lambda n: self._touching(n)
        )

    def _touching(self, node_id: str) -> list[str]:
        mapping = self.state.board.get("node_hexes") or {}
        return list(mapping.get(node_id) or [])

    def setup_initial(self, hex_ids: list[str], *, count: int = 3) -> list[dict[str, Any]]:
        """Place one demon on each of `count` distinct hexes."""
        self.deck = HazardDeck(self.state, hex_ids=list(hex_ids))
        picked = self.deck.draw(count)
        placed = []
        for hid in picked:
            placed.append(self.add_cube(hid, "demon"))
        self.deck.discard(picked)
        return placed

    def placement_due(self, *, difficulty: str | None = None) -> bool:
        diff = difficulty or self.difficulty
        cadence = CADENCE[diff]
        cat = self._cat()
        era_start = int(cat.get("era_start_turn") or 0)
        turn = int(self.state.clock.get("turn", 0))
        elapsed = turn - era_start
        if elapsed <= 0:
            return False
        return elapsed % cadence == 0

    def resolve_placement(self, step: dict[str, Any] | None = None) -> dict[str, Any]:
        """Scheduled placement: draw and place or overflow-propagate."""
        cat = self._cat()
        if not self.placement_due():
            return {"status": "skipped", "reason": "cadence"}
        era_rounds = int(self.state.clock.get("round", 0)) - int(cat.get("era_start_round", 0) or 0)
        n = draw_count_for_era_rounds(max(0, era_rounds))
        hazard_type = self._next_type()
        drawn = self.deck.draw(n)
        results = []
        engine = PropagationEngine(self.state)
        for hid in drawn:
            cat["placement_ordinal"] = int(cat.get("placement_ordinal", 0)) + 1
            on_hex = self.cubes_on_hex(hid)
            if len(on_hex) < MAX_CUBES_PER_HEX:
                results.append(self.add_cube(hid, hazard_type))
            else:
                results.append(engine.outbreak_from(hid, hazard_type))
                if self.state.clock.get("terminal"):
                    break
        self.deck.discard(drawn)
        return {"status": "resolved", "draws": drawn, "type": hazard_type, "results": results}

    def _next_type(self) -> str:
        cat = self._cat()
        era = str(self.state.clock.get("era") or "prehistoric").lower()
        ordinal = int(cat.get("placement_ordinal", 0))
        if era in {"prehistoric", "historic", "ancient"}:
            return "demon"
        if era == "modern":
            return "pollution" if ordinal % 2 == 0 else "alien"
        # future
        return "nuclear" if ordinal % 2 == 0 else "machine"

    def rollover(self, era: str) -> dict[str, Any]:
        cat = self._cat()
        cat["era_outbreaks"] = 0
        cat["era_start_turn"] = int(self.state.clock.get("turn", 0))
        cat["era_start_round"] = int(self.state.clock.get("round", 0))
        self.state.clock["era"] = era
        # Retain typed cubes and deck order.
        return {"status": "rollover", "era": era, "cubes_retained": len(cat.get("cubes") or {})}

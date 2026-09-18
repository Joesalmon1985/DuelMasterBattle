"""Bounded outbreak propagation and terminal threshold (C08 / T070)."""

from __future__ import annotations

from typing import Any

from sim.dmb.core.terminal import TerminalService

MAX_CUBES = 3
TERMINAL_OUTBREAKS = 8


class PropagationEngine:
    def __init__(self, world_state: Any):
        self.state = world_state

    def _cat(self) -> dict[str, Any]:
        return self.state.hazards.setdefault("catastrophe", {})

    def _adjacent(self, hex_id: str) -> list[str]:
        topo = self.state.board.get("topology") or {}
        hexes = topo.get("hexes") or self.state.board.get("hex_adjacency") or {}
        if isinstance(hexes, dict) and hex_id in hexes:
            entry = hexes[hex_id]
            if isinstance(entry, dict):
                return sorted(str(x) for x in (entry.get("neighbours") or entry.get("adjacent") or []))
            if isinstance(entry, list):
                return sorted(str(x) for x in entry)
        # Fallback adjacency map
        adj = self.state.board.get("hex_adjacency") or {}
        return sorted(str(x) for x in (adj.get(hex_id) or []))

    def _active_count(self, hex_id: str) -> int:
        cubes = (self._cat().get("cubes") or {}).values()
        return sum(1 for c in cubes if c.get("hex_id") == hex_id and c.get("active", True))

    def outbreak_from(self, hex_id: str, hazard_type: str) -> dict[str, Any]:
        """Fourth attempt: outbreak once per event, propagate in stable adjacency order."""
        cat = self._cat()
        event_id = cat.get("propagation_event_id") or self.state.ids.new("event")
        cat["propagation_event_id"] = event_id
        visited = set(cat.get("visited_outbreaks") or [])
        if hex_id in visited:
            return {"status": "already_outbreaked", "hex_id": hex_id, "event_id": event_id}

        visited.add(hex_id)
        cat["visited_outbreaks"] = sorted(visited)
        cat["era_outbreaks"] = int(cat.get("era_outbreaks", 0)) + 1
        cat["lifetime_outbreaks"] = int(cat.get("lifetime_outbreaks", 0)) + 1

        if cat["era_outbreaks"] >= TERMINAL_OUTBREAKS:
            TerminalService(self.state).trigger("catastrophe_outbreak_threshold")
            return {
                "status": "terminal",
                "hex_id": hex_id,
                "era_outbreaks": cat["era_outbreaks"],
                "propagated": [],
            }

        propagated = []
        for neigh in self._adjacent(hex_id):
            if self.state.clock.get("terminal"):
                break
            if neigh in visited:
                continue
            count = self._active_count(neigh)
            if count < MAX_CUBES:
                from sim.dmb.hazards.service import CatastropheService

                CatastropheService(self.state).add_cube(neigh, hazard_type)
                propagated.append({"hex_id": neigh, "action": "add"})
            else:
                # Saturated neighbour outbreaks at most once this event.
                nested = self.outbreak_from(neigh, hazard_type)
                propagated.append({"hex_id": neigh, "action": "outbreak", "result": nested})
                if nested.get("status") == "terminal":
                    break
        return {
            "status": "outbreak",
            "hex_id": hex_id,
            "era_outbreaks": cat["era_outbreaks"],
            "propagated": propagated,
            "event_id": event_id,
        }

    def begin_event(self) -> str:
        cat = self._cat()
        event_id = self.state.ids.new("event")
        cat["propagation_event_id"] = event_id
        cat["visited_outbreaks"] = []
        return event_id

"""Road route planning and blockage checks (C05 / T034)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.hazards.queries import node_blocked_for_civilian
from sim.dmb.world.board import HexBoard


@dataclass
class RoutePlanner:
    state: WorldState
    board: HexBoard | None = None

    def _board(self) -> HexBoard:
        if self.board is not None:
            return self.board
        raw = self.state.board.get("topology") or self.state.board.get("hex_board")
        if raw:
            return HexBoard.from_dict(raw)
        return HexBoard.radius2()

    def constructed_edges(self, owner_faction: str | None = None) -> set[tuple[str, str]]:
        edges: set[tuple[str, str]] = set()
        for road in self.state.roads.values():
            if road.get("status") == "destroyed":
                continue
            # Own, allied, or explicitly trade-permitted — MVP: own or unmarked
            if owner_faction and road.get("faction_id") not in {owner_faction, None, "shared"}:
                # Allow travel on own roads; allies later
                if road.get("faction_id") != owner_faction and not road.get("public"):
                    continue
            a, b = str(road["a"]), str(road["b"])
            edges.add(tuple(sorted((a, b))))
        return edges

    def _touching(self, node_id: str):
        mapped = self.state.board.get("node_hexes", {}).get(node_id)
        if mapped is not None:
            return tuple(mapped)
        return self._board().touching_hexes(node_id)

    def is_node_blocked(self, node_id: str) -> bool:
        return node_blocked_for_civilian(self.state.board, node_id, touching_hexes=self._touching)

    def route(self, owner: str, source: str, target: str) -> dict[str, Any]:
        if source == target:
            return {"path": [source], "reason": "ok"}
        if self.is_node_blocked(source):
            return {"path": None, "reason": "source_blocked"}
        if self.is_node_blocked(target):
            return {"path": None, "reason": "destination_blocked"}
        edges = self.constructed_edges(owner)
        adj: dict[str, set[str]] = {}
        for a, b in edges:
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
        prev: dict[str, str | None] = {source: None}
        queue: deque[str] = deque([source])
        while queue:
            node = queue.popleft()
            for nxt in sorted(adj.get(node, ())):
                if nxt in prev:
                    continue
                if self.is_node_blocked(nxt) and nxt != target:
                    continue
                # Intermediate blocked nodes cannot be traversed
                if self.is_node_blocked(nxt):
                    continue
                prev[nxt] = node
                if nxt == target:
                    path = [target]
                    cur: str | None = target
                    while cur != source:
                        cur = prev[cur]
                        assert cur is not None
                        path.append(cur)
                    path.reverse()
                    return {"path": path, "reason": "ok"}
                queue.append(nxt)
        return {"path": None, "reason": "no_road_path"}

    def validate_next_edge(self, owner: str, current: str, nxt: str) -> tuple[bool, str]:
        edges = self.constructed_edges(owner)
        if tuple(sorted((current, nxt))) not in edges:
            return False, "no_constructed_road"
        if self.is_node_blocked(current):
            return False, "current_blocked"
        if self.is_node_blocked(nxt):
            return False, "next_blocked"
        return True, "ok"

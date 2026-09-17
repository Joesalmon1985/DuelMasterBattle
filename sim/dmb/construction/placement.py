"""Placement legality predicates (C04 / T031)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.world.board import HexBoard


@dataclass
class PlacementRules:
    state: WorldState
    board: HexBoard | None = None

    def _board(self) -> HexBoard:
        if self.board is not None:
            return self.board
        raw = self.state.board.get("topology") or self.state.board.get("hex_board")
        if raw:
            return HexBoard.from_dict(raw)
        return HexBoard.radius2()

    def _active_settlement_at(self, node_id: str) -> dict[str, Any] | None:
        for settlement in self.state.settlements.values():
            if settlement.get("node_id") != node_id:
                continue
            if settlement.get("status") in {"ruined", "inert", "destroyed"}:
                continue
            if settlement.get("ruin_only"):
                continue
            return settlement
        return None

    def _owned_road_endpoints(self, faction_id: str) -> set[str]:
        endpoints: set[str] = set()
        for road in self.state.roads.values():
            if road.get("faction_id") != faction_id:
                continue
            if road.get("status") == "destroyed":
                continue
            endpoints.add(str(road["a"]))
            endpoints.add(str(road["b"]))
        return endpoints

    def _node_owner(self, node_id: str) -> str | None:
        settlement = self._active_settlement_at(node_id)
        if settlement:
            return str(settlement.get("faction_id"))
        return None

    def can_settle(self, faction_id: str, node_id: str) -> tuple[bool, str]:
        if self._active_settlement_at(node_id) is not None:
            return False, "occupied"
        board = self._board()
        for neighbour in board.adjacent_nodes(node_id):
            other = self._active_settlement_at(neighbour)
            if other is not None:
                # Adjacent active settlement blocks regardless of owner/era.
                return False, "adjacent_settlement"
        endpoints = self._owned_road_endpoints(faction_id)
        if node_id not in endpoints:
            return False, "not_own_road_endpoint"
        return True, "ok"

    def can_city(self, faction_id: str, node_id: str) -> tuple[bool, str]:
        settlement = self._active_settlement_at(node_id)
        if settlement is None:
            return False, "no_settlement"
        if settlement.get("faction_id") != faction_id:
            return False, "not_owned"
        if settlement.get("tier") == "city":
            return False, "already_city"
        if settlement.get("era") not in (None, "current", settlement.get("current_era"), "ancient", "historic"):
            # Legacy unupgraded handled separately
            pass
        if settlement.get("legacy") and not settlement.get("upgraded"):
            return False, "legacy_requires_upgrade_path"
        return True, "ok"

    def can_upgrade_legacy(self, faction_id: str, node_id: str) -> tuple[bool, str]:
        settlement = self._active_settlement_at(node_id)
        if settlement is None:
            return False, "no_settlement"
        if settlement.get("faction_id") != faction_id:
            return False, "not_owned"
        if not settlement.get("legacy"):
            return False, "not_legacy"
        return True, "ok"

    def can_road(self, faction_id: str, node_a: str, node_b: str) -> tuple[bool, str]:
        board = self._board()
        try:
            edge = board.edge(node_a, node_b)
        except Exception:
            return False, "nonadjacent"
        if edge is None:
            return False, "nonadjacent"
        # Existing road?
        for road in self.state.roads.values():
            ends = {road.get("a"), road.get("b")}
            if ends == {node_a, node_b} and road.get("status") != "destroyed":
                return False, "road_exists"
        endpoints = self._owned_road_endpoints(faction_id)
        # Must extend from an owned road endpoint (or initial free placement flagged).
        if endpoints and node_a not in endpoints and node_b not in endpoints:
            return False, "not_connected"
        # Hostile node prevents extending a road *through* it.
        for node in (node_a, node_b):
            owner = self._node_owner(node)
            if owner is not None and owner != faction_id:
                # Endpoint at hostile settlement blocks through-extension.
                # Building a road that ends at hostile is blocked.
                return False, "hostile_node"
        return True, "ok"

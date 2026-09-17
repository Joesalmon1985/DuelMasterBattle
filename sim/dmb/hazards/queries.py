"""Pure hazard / cube query helpers (C04 / T029)."""

from __future__ import annotations

from typing import Any, Mapping


def hex_has_catastrophe(board: Mapping[str, Any], hex_id: str) -> bool:
    cubes = board.get("hazard_cubes") or board.get("cubes") or {}
    if isinstance(cubes, dict):
        for cube in cubes.values():
            if str(cube.get("hex_id")) == hex_id and cube.get("active", True):
                return True
        # Also allow hex_id -> cube list
        entry = cubes.get(hex_id)
        if entry:
            return True
    if isinstance(cubes, list):
        for cube in cubes:
            if str(cube.get("hex_id")) == hex_id and cube.get("active", True):
                return True
    hazards = board.get("hazard_hexes") or []
    return hex_id in set(hazards)


def node_blocked_for_civilian(board: Mapping[str, Any], node_id: str, *, touching_hexes) -> bool:
    """Any catastrophe cube on a hex touching the node blocks civilian/cart entry.

    Also honour cubes that name a player-graph node_id directly (FX-CARGO playable path).
    """
    cubes = board.get("hazard_cubes") or board.get("cubes") or {}
    if isinstance(cubes, dict):
        for cube in cubes.values():
            if not cube.get("active", True):
                continue
            if str(cube.get("node_id") or "") == node_id:
                return True
    for hex_id in touching_hexes(node_id):
        if hex_has_catastrophe(board, hex_id):
            return True
    return False


def catan_grant_suppressed(board: Mapping[str, Any], hex_id: str) -> bool:
    return hex_has_catastrophe(board, hex_id)


def industrial_blocked(board: Mapping[str, Any], hex_id: str) -> bool:
    """Source catastrophe blocks industrial channels (same cube state as Catan)."""
    return hex_has_catastrophe(board, hex_id)

"""Pure hazard / cube query helpers (C04 / C08)."""

from __future__ import annotations

from typing import Any, Mapping


def _iter_cubes(board: Mapping[str, Any]):
    cubes = board.get("hazard_cubes") or board.get("cubes") or {}
    if isinstance(cubes, dict):
        for cube in cubes.values():
            yield cube
    elif isinstance(cubes, list):
        for cube in cubes:
            yield cube


def hex_has_catastrophe(board: Mapping[str, Any], hex_id: str) -> bool:
    for cube in _iter_cubes(board):
        if str(cube.get("hex_id")) == hex_id and cube.get("active", True):
            return True
    entry = (board.get("hazard_cubes") or {}).get(hex_id) if isinstance(board.get("hazard_cubes"), dict) else None
    if entry:
        return True
    hazards = board.get("hazard_hexes") or []
    return hex_id in set(hazards)


def node_blocked_for_civilian(board: Mapping[str, Any], node_id: str, *, touching_hexes) -> bool:
    """Any catastrophe cube on a hex touching the node blocks civilian/cart entry."""
    for cube in _iter_cubes(board):
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


def changed_cause_ids(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    before_ids = {
        str(c.get("cause_id") or c.get("id"))
        for c in _iter_cubes(before)
        if c.get("active", True)
    }
    after_ids = {
        str(c.get("cause_id") or c.get("id"))
        for c in _iter_cubes(after)
        if c.get("active", True)
    }
    return sorted(before_ids.symmetric_difference(after_ids))

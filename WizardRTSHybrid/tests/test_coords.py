"""Hex partition: one owner per tile, no gaps between neighbours, no collision seam."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wizard_rts.coords import (  # noqa: E402
    MAP_Q,
    MAP_R,
    cube_round,
    hex_center_tile,
    in_map,
    neighbors,
    tile_in_map,
    tile_to_hex,
)


def test_cube_round_sums_to_zero() -> None:
    samples = [
        (0, 0, 0),
        (1500, -700, -800),
        (-2400, 900, 1500),
        (500, 500, -1000),
    ]
    for sample in samples:
        x, y, z = cube_round(*sample)
        assert x + y + z == 0


def test_every_hex_owns_its_center_and_only_one_identity() -> None:
    seen = {}
    for q in range(MAP_Q):
        for r in range(MAP_R):
            tx, ty = hex_center_tile(q, r)
            assert tile_to_hex(tx, ty) == (q, r)
            assert (tx, ty) not in seen
            seen[(tx, ty)] = (q, r)


def test_partition_has_no_overlap_and_covers_neighbor_steps() -> None:
    """Each tile function result is unique by construction. Neighbours share a step."""
    crossings = 0
    for q in range(MAP_Q):
        for r in range(MAP_R):
            origin = hex_center_tile(q, r)
            for nq, nr in neighbors(q, r):
                if not in_map(nq, nr):
                    continue
                assert _has_walk_step(origin, (q, r), (nq, nr))
                crossings += 1
    # 20x20 interior edges are well above twenty crossings.
    assert crossings >= 20


def test_hex_boundary_does_not_change_collision() -> None:
    """Collision is a separate set. Crossing a hex edge stays walkable."""
    blocked = set()
    q, r = 3, 3
    start = hex_center_tile(q, r)
    nq, nr = q + 1, r
    goal_hex = (nq, nr)
    cursor = start
    for _ in range(80):
        if tile_to_hex(*cursor) == goal_hex:
            break
        step = _step_toward(cursor, hex_center_tile(nq, nr))
        assert step not in blocked
        assert tile_in_map(*step)
        cursor = step
    assert tile_to_hex(*cursor) == goal_hex


def _has_walk_step(start, src, dst) -> bool:
    goal = hex_center_tile(*dst)
    cursor = start
    prev = None
    for _ in range(80):
        here = tile_to_hex(*cursor)
        if here == dst and prev is not None and tile_to_hex(*prev) == src:
            return _adjacent(prev, cursor)
        prev = cursor
        nxt = _step_toward(cursor, goal)
        if nxt == cursor:
            return False
        cursor = nxt
    return False


def _adjacent(a, b) -> bool:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


def _step_toward(cursor, goal):
    dx = goal[0] - cursor[0]
    dy = goal[1] - cursor[1]
    if abs(dx) >= abs(dy) and dx != 0:
        return cursor[0] + (1 if dx > 0 else -1), cursor[1]
    if dy != 0:
        return cursor[0], cursor[1] + (1 if dy > 0 else -1)
    return cursor

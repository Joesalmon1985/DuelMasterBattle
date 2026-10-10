"""Square-grid topology for the hybrid world.

Every node is one integer tile (x, y). Movement and roads use four directions
(up, down, left, right). This replaces the Widelands six-neighbour offset
layout; see docs/DECISIONS.md D5 for the differences (adjacency, distance,
triangles, elevation, building spaces, road geometry).
"""

from __future__ import annotations

DIRS4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIRS8 = DIRS4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))


def neighbors4(x: int, y: int) -> list[tuple[int, int]]:
    return [(x + dx, y + dy) for dx, dy in DIRS4]


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def ring(cx: int, cy: int, r: int):
    """Tiles at Chebyshev distance exactly r, in a fixed order."""
    if r == 0:
        yield (cx, cy)
        return
    for dx in range(-r, r + 1):
        yield (cx + dx, cy - r)
        yield (cx + dx, cy + r)
    for dy in range(-r + 1, r):
        yield (cx - r, cy + dy)
        yield (cx + r, cy + dy)


def area(cx: int, cy: int, r: int):
    """Square block of tiles within Chebyshev radius r, row-major."""
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            yield (cx + dx, cy + dy)

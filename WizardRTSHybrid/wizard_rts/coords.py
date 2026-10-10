"""Integer hex ownership for one continuous tile plane.

Strategic coordinates are axial (q, r) with cube x + y + z = 0.
Local coordinates are integer tiles. Rendering multiplies tiles by the
Overworld tile pixel size. Ownership is a pure function of the tile, so
every tile has one hex and hex boundaries do not invent collision.

The arithmetic is fixed-point (milli-units) so Godot can repeat it without
binary float drift. Size is 16 tiles from hex center to corner.
"""

from __future__ import annotations

MAP_Q = 20
MAP_R = 20
HEX_SIZE_TILES = 16
_MILLI = 1000
_SIZE = HEX_SIZE_TILES * _MILLI
# sqrt(3) * 1000, rounded. Used only to document the inverse constants below.
_SQRT3_OVER_3_MILLI = 577  # floor(1000 * sqrt(3) / 3)

NEIGHBORS = (
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, 0),
    (-1, 1),
    (0, 1),
)


def _div_round(numer: int, denom: int) -> int:
    """Round half away from zero."""
    if numer >= 0:
        return (numer + denom // 2) // denom
    return -((-numer + denom // 2) // denom)


def cube_round(x_milli: int, y_milli: int, z_milli: int) -> tuple[int, int, int]:
    """Round a fractional cube coordinate. Tie-break keeps the largest error on z."""
    rx = _div_round(x_milli, _MILLI)
    ry = _div_round(y_milli, _MILLI)
    rz = _div_round(z_milli, _MILLI)
    dx = abs(rx * _MILLI - x_milli)
    dy = abs(ry * _MILLI - y_milli)
    dz = abs(rz * _MILLI - z_milli)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return rx, ry, rz


def tile_to_hex(tx: int, ty: int) -> tuple[int, int]:
    """Map a tile to exactly one axial hex, sampling the tile center."""
    x = tx * _MILLI + _MILLI // 2
    y = ty * _MILLI + _MILLI // 2
    q_milli = (_SQRT3_OVER_3_MILLI * x - (y * _MILLI) // 3) // _SIZE
    r_milli = ((2 * _MILLI * y) // 3) // _SIZE
    cx, _cy, cz = cube_round(q_milli, -q_milli - r_milli, r_milli)
    return cx, cz


def in_map(q: int, r: int) -> bool:
    return 0 <= q < MAP_Q and 0 <= r < MAP_R


def tile_in_map(tx: int, ty: int) -> bool:
    q, r = tile_to_hex(tx, ty)
    return in_map(q, r)


def neighbors(q: int, r: int) -> list[tuple[int, int]]:
    return [(q + dq, r + dr) for dq, dr in NEIGHBORS]


def hex_center_tile(q: int, r: int) -> tuple[int, int]:
    """Tile nearest the geometric center that this function maps back to (q, r)."""
    # Inverse of the pointy-top layout, in milli-tiles, then a local search.
    x = _div_round(_SIZE * (1732 * q + 866 * r), _MILLI)
    y = _div_round(_SIZE * 3 * r, 2)
    base_tx = _div_round(x, _MILLI)
    base_ty = _div_round(y, _MILLI)
    best: tuple[int, int] | None = None
    best_d = 10**9
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            tx = base_tx + dx
            ty = base_ty + dy
            if tile_to_hex(tx, ty) != (q, r):
                continue
            # Distance of the tile center from the geometric center.
            cx = tx * _MILLI + _MILLI // 2
            cy = ty * _MILLI + _MILLI // 2
            dist = (cx - x) * (cx - x) + (cy - y) * (cy - y)
            if dist < best_d:
                best_d = dist
                best = (tx, ty)
    if best is None:
        raise ValueError(f"hex {(q, r)} owns no tile near its center")
    return best


def iter_hexes():
    for q in range(MAP_Q):
        for r in range(MAP_R):
            yield q, r


def map_bounds() -> tuple[int, int, int, int]:
    """Inclusive tile bounds of every tile owned by the 20 by 20 hex map."""
    min_tx = min_ty = 10**9
    max_tx = max_ty = -10**9
    for q, r in iter_hexes():
        tx, ty = hex_center_tile(q, r)
        # A hex of size 16 fits inside a 40-tile window.
        for dy in range(-24, 25):
            for dx in range(-24, 25):
                x = tx + dx
                y = ty + dy
                if tile_to_hex(x, y) != (q, r):
                    continue
                min_tx = min(min_tx, x)
                min_ty = min(min_ty, y)
                max_tx = max(max_tx, x)
                max_ty = max(max_ty, y)
    return min_tx, min_ty, max_tx, max_ty

"""The campaign on the island (D54): the 80 nodes are the locations, the corridors the links; each location belongs to one of four threat families by
the quarter of the island it lies in (so each family has a home quarter, as the published map's colours do); the six field posts stand at the six
factions' bases (their best village of the age); the six responders are one per faction, roles by faction order, manufactured at the base."""

from __future__ import annotations

import math
from typing import Any

from . import rules as R


def families_by_quarter(board) -> dict[str, str]:
    xs = [board.node_xy(n)[0] for n in board.nodes]
    ys = [board.node_xy(n)[1] for n in board.nodes]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    out = {}
    for n in sorted(board.nodes):
        x, y = board.node_xy(n)
        ang = math.atan2(y - cy, x - cx)  # -pi..pi
        q = int(((ang + math.pi) / (2 * math.pi)) * 4.0) % 4
        out[n] = R.FAMILIES[q]
    return out


def bases(world) -> dict[str, str]:
    """Each faction's base node this age: its highest-ranked operational village (the carried one), else its first."""
    from .. import ages as _ages

    out = {}
    for fid in world.fids:
        ranked = _ages.rank_villages(world, fid)
        if ranked:
            out[fid] = ranked[0]["node"]
        else:
            vs = [v for v in world.villages.values() if v["faction"] == fid and v["status"] in ("operational", "rebuilding", "building")]
            out[fid] = vs[0]["node"] if vs else sorted(world.board.nodes)[0]
    return out


def build(world) -> dict[str, Any]:
    board = world.board
    fams = families_by_quarter(board)
    links = {n: sorted(board.adjacency[n]) for n in board.nodes}
    base = bases(world)
    posts = []
    for fid in world.fids:
        if base[fid] not in posts:
            posts.append(base[fid])
    responders = [{"id": f"r{i}", "role": R.ROLES[i % len(R.ROLES)], "faction": fid, "home": base[fid]} for i, fid in enumerate(world.fids)]
    return {"locations": fams, "links": links, "posts": posts, "responders": responders, "bases": base}

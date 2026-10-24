"""The strategic board of God World: the explicit 30-cell 5-6 player Catan layout, its 80 nodes and 109 edges, roles and number tokens.

Topology is integer-keyed (no float merging): the board is a pointy-top hex grid whose rows are the axial `q` lines of lengths 3,4,5,6,5,4,3.
A hex at row `q`, column `r` has its centre at lattice units `(2r + q, 3q)` where one x unit is `sqrt(3)/2` of the hex circumradius and one y
unit is half of it; its six corners are the integer offsets (±1, ±1) and (0, ±2). Shared corners therefore share a key. World positions for
the viewer are derived from the same units, so the Python projection and the Godot picture agree.

`generate(seed)` assigns roles and tokens with the saved layout written out explicitly; `from_dict` rebuilds exactly that layout and never a
regular 19- or 37-hex board (AC03)."""

from __future__ import annotations

import math
import random
from collections import deque
from typing import Any, Iterable

from . import rules

SHAPE = "catan_5_6"
SQRT3_2 = math.sqrt(3.0) / 2.0

AXIAL_DIRS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))
CORNER_OFFSETS = ((0, -2), (1, -1), (1, 1), (0, 2), (-1, 1), (-1, -1))  # clockwise from the top corner, in lattice units


def catan_5_6_cells() -> list[tuple[int, int]]:
    return [(q, r) for q in range(-3, 4) for r in range(-3, 3) if -2 <= -q - r <= 3]


def hex_id(q: int, r: int) -> str:
    return f"hex:{q},{r}"


def parse_hex_id(hid: str) -> tuple[int, int]:
    q_s, r_s = hid.split(":", 1)[1].split(",", 1)
    return int(q_s), int(r_s)


def hex_units(q: int, r: int) -> tuple[int, int]:
    return (2 * r + q, 3 * q)


def units_to_xy(xu: int | float, yu: int | float) -> tuple[float, float]:
    """Lattice units to world units with circumradius 1 (the viewer multiplies by its hex pixel size)."""
    return (float(xu) * SQRT3_2, float(yu) * 0.5)


class GodBoard:
    """Immutable topology plus the mutable-by-save layout (roles and tokens are fixed once generated)."""

    def __init__(self, cells: Iterable[tuple[int, int]], roles: dict[str, str] | None = None, tokens: dict[str, int] | None = None, shape: str = SHAPE) -> None:
        self.shape = shape
        self.cells: list[tuple[int, int]] = sorted((int(q), int(r)) for q, r in cells)
        self.hexes: list[str] = [hex_id(q, r) for q, r in self.cells]
        self._axial: dict[str, tuple[int, int]] = {hex_id(q, r): (q, r) for q, r in self.cells}
        self.node_units: dict[str, tuple[int, int]] = {}
        self._unit_node: dict[tuple[int, int], str] = {}
        self.hex_nodes: dict[str, tuple[str, ...]] = {}
        node_hexes: dict[str, list[str]] = {}
        for q, r in self.cells:
            hid = hex_id(q, r)
            cx, cy = hex_units(q, r)
            ordered = []
            for ox, oy in CORNER_OFFSETS:
                key = (cx + ox, cy + oy)
                nid = self._unit_node.get(key)
                if nid is None:
                    nid = f"node:{len(self._unit_node) + 1}"
                    self._unit_node[key] = nid
                    self.node_units[nid] = key
                ordered.append(nid)
                node_hexes.setdefault(nid, []).append(hid)
            self.hex_nodes[hid] = tuple(ordered)
        self.nodes: list[str] = list(self.node_units)
        self.node_hexes: dict[str, tuple[str, ...]] = {nid: tuple(sorted(hs)) for nid, hs in node_hexes.items()}
        self.edge_endpoints: dict[str, tuple[str, str]] = {}
        self._endpoint_edge: dict[tuple[str, str], str] = {}
        adjacency: dict[str, set[str]] = {nid: set() for nid in self.nodes}
        for hid in self.hexes:
            ring = self.hex_nodes[hid]
            for i, a in enumerate(ring):
                b = ring[(i + 1) % 6]
                pair = (a, b) if a < b else (b, a)
                if pair in self._endpoint_edge:
                    continue
                eid = f"edge:{len(self._endpoint_edge) + 1}"
                self._endpoint_edge[pair] = eid
                self.edge_endpoints[eid] = pair
                adjacency[a].add(b)
                adjacency[b].add(a)
        self.edges: list[str] = list(self.edge_endpoints)
        self.adjacency: dict[str, tuple[str, ...]] = {nid: tuple(sorted(adjacency[nid])) for nid in self.nodes}
        self.roles: dict[str, str] = dict(roles or {})
        self.tokens: dict[str, int] = {k: int(v) for k, v in (tokens or {}).items()}
        self.node_edges: dict[str, tuple[str, ...]] = {nid: tuple(self._endpoint_edge[(nid, o) if nid < o else (o, nid)] for o in self.adjacency[nid]) for nid in self.nodes}
        self.embedding: dict[str, Any] | None = None
        self.attach_embedding(None)
        self.validate()

    # ------------------------------------------------------------------ the terrain embedding (god_world/embedding.py)
    def attach_embedding(self, emb: dict[str, Any] | None, grid: Any = None) -> None:
        """Physical positions from a terrain embedding: node plots, region centroids, road corridors, work sites, the coast. Topology is untouched.
        With the map grid, the role-dependent dressing (work sites, trees) is computed for this board's roles."""
        self.embedding = emb
        self.dressing: dict[str, Any] = {"work_sites": {}, "trees": []}
        if emb is not None and grid is not None:
            from . import embedding as _emb

            self.dressing = _emb.dress(emb, self, grid)
        if emb is None:
            self.unit = 1.0
            xs = [units_to_xy(*u)[0] for u in self.node_units.values()]
            ys = [units_to_xy(*u)[1] for u in self.node_units.values()]
            self.bounds = (min(xs), min(ys), max(xs), max(ys))
        else:
            self.unit = float(emb["unit"])
            self.bounds = (0.0, 0.0, float(emb.get("map_w", 192)), float(emb.get("map_h", 192)))
        self.centre = ((self.bounds[0] + self.bounds[2]) / 2.0, (self.bounds[1] + self.bounds[3]) / 2.0)

    def corridor(self, eid: str) -> list[tuple[float, float]]:
        """The road's world path from endpoint a to endpoint b (a straight chord without an embedding)."""
        a, b = self.edge_endpoints[eid]
        if self.embedding is not None:
            return [(float(x), float(y)) for x, y in self.embedding["corridors"][eid]]
        return [self.node_xy(a), self.node_xy(b)]

    def work_site(self, hid: str) -> tuple[float, float]:
        ws = self.dressing.get("work_sites", {}).get(hid)
        if ws is not None:
            return float(ws[0]), float(ws[1])
        return self.hex_xy(hid)

    @property
    def trees(self) -> list[dict[str, Any]]:
        return list(self.dressing.get("trees", []))

    def region_corners(self, hid: str) -> list[tuple[float, float]]:
        if self.embedding is not None:
            return [(float(x), float(y)) for x, y in self.embedding["regions"][hid]["corners"]]
        return [self.node_xy(n) for n in self.hex_nodes[hid]]

    def coast(self, nid: str) -> tuple[float, float]:
        """An exterior endpoint for bank caravans: the nearest shore outward from the node."""
        if self.embedding is not None:
            x, y = self.embedding["coast"][nid]
            return float(x), float(y)
        px, py = self.node_xy(nid)
        cx, cy = self.centre
        dx, dy = px - cx, py - cy
        d = (dx * dx + dy * dy) ** 0.5 or 1.0
        return px + dx / d * 2.2 * self.unit, py + dy / d * 2.2 * self.unit

    # ------------------------------------------------------------------ topology queries
    def axial(self, hid: str) -> tuple[int, int]:
        return self._axial[hid]

    def hex_xy(self, hid: str) -> tuple[float, float]:
        if self.embedding is not None:
            x, y = self.embedding["regions"][hid]["centroid"]
            return float(x), float(y)
        return units_to_xy(*hex_units(*self._axial[hid]))

    def node_xy(self, nid: str) -> tuple[float, float]:
        if self.embedding is not None:
            x, y = self.embedding["nodes"][nid]
            return float(x), float(y)
        return units_to_xy(*self.node_units[nid])

    def edge(self, a: str, b: str) -> str | None:
        if a == b:
            return None
        return self._endpoint_edge.get((a, b) if a < b else (b, a))

    def edge_xy(self, eid: str) -> tuple[tuple[float, float], tuple[float, float]]:
        a, b = self.edge_endpoints[eid]
        return self.node_xy(a), self.node_xy(b)

    def other_end(self, eid: str, nid: str) -> str:
        a, b = self.edge_endpoints[eid]
        return b if nid == a else a

    def hex_neighbours(self, hid: str) -> list[str]:
        q, r = self._axial[hid]
        return [hex_id(q + dq, r + dr) for dq, dr in AXIAL_DIRS if hex_id(q + dq, r + dr) in self._axial]

    def token(self, hid: str) -> int:
        return int(self.tokens.get(hid, 0))

    def role(self, hid: str) -> str:
        return self.roles.get(hid, rules.DESERT)

    def productive_hexes(self, nid: str) -> list[tuple[str, str, int]]:
        """(hex, role, token) for every touching hex that produces."""
        out = []
        for hid in self.node_hexes[nid]:
            role = self.role(hid)
            if role != rules.DESERT and self.token(hid):
                out.append((hid, role, self.token(hid)))
        return out

    def node_pips(self, nid: str) -> int:
        return sum(rules.pips(t) for _h, _r, t in self.productive_hexes(nid))

    def is_boundary(self, nid: str) -> bool:
        return len(self.node_hexes[nid]) < 3

    # ------------------------------------------------------------------ validation and serialisation
    def validate(self) -> None:
        if self.shape == SHAPE:
            if len(self.hexes) != 30 or len(self.nodes) != 80 or len(self.edges) != 109:
                raise ValueError(f"catan_5_6 must be 30/80/109, got {len(self.hexes)}/{len(self.nodes)}/{len(self.edges)}")
        for nid, nbrs in self.adjacency.items():
            if len(nbrs) > 3:
                raise ValueError(f"{nid} has degree {len(nbrs)}")
            for o in nbrs:
                if nid not in self.adjacency[o]:
                    raise ValueError(f"adjacency not reciprocal {nid}->{o}")
        for nid, hs in self.node_hexes.items():
            if not 1 <= len(hs) <= 3:
                raise ValueError(f"{nid} touches {len(hs)} hexes")
        seen = {self.nodes[0]}
        queue = deque([self.nodes[0]])
        while queue:
            n = queue.popleft()
            for o in self.adjacency[n]:
                if o not in seen:
                    seen.add(o)
                    queue.append(o)
        if len(seen) != len(self.nodes):
            raise ValueError("node graph is not connected")
        if self.roles:
            if set(self.roles) != set(self.hexes):
                raise ValueError("every hex needs a role")
            spec = rules.board_spec()
            for role, want in spec["role_counts"].items():
                have = sum(1 for h in self.hexes if self.roles[h] == role)
                if have != int(want):
                    raise ValueError(f"{role}: {have} hexes, expected {want}")
            productive = [h for h in self.hexes if self.roles[h] != rules.DESERT]
            if sorted(self.tokens.get(h, 0) for h in productive) != sorted(int(t) for t in spec["tokens"]):
                raise ValueError("token inventory does not match the rules")
            if any(h in self.tokens for h in self.hexes if self.roles[h] == rules.DESERT):
                raise ValueError("a desert carries no token")

    def to_dict(self) -> dict[str, Any]:
        return {"shape": self.shape, "cells": [list(c) for c in self.cells], "roles": dict(self.roles), "tokens": {k: int(v) for k, v in self.tokens.items()},
                "nodes": {nid: list(u) for nid, u in self.node_units.items()}, "edges": {eid: list(ab) for eid, ab in self.edge_endpoints.items()}}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GodBoard":
        if "cells" not in payload:
            raise ValueError("a God World board is saved as an explicit cell list, never a radius")
        board = cls([tuple(c) for c in payload["cells"]], payload.get("roles", {}), payload.get("tokens", {}), str(payload.get("shape", SHAPE)))
        saved_nodes = payload.get("nodes")
        if saved_nodes and {k: tuple(v) for k, v in saved_nodes.items()} != board.node_units:
            raise ValueError("saved node ids do not match the rebuilt topology")
        saved_edges = payload.get("edges")
        if saved_edges and {k: tuple(v) for k, v in saved_edges.items()} != board.edge_endpoints:
            raise ValueError("saved edge ids do not match the rebuilt topology")
        return board

    # ------------------------------------------------------------------ the age's renewal (D48)
    def reshuffle_tokens(self, rng: random.Random) -> dict[str, Any]:
        """Shuffle the productive hexes' number tokens (the same multiset) under the keep-apart rule; roles and deserts untouched. Returns before/after."""
        spec = rules.board_spec()
        keep_apart = {int(t) for t in spec.get("keep_apart", [])}
        productive = [h for h in self.hexes if self.roles.get(h) != rules.DESERT]
        before = {h: int(self.tokens[h]) for h in productive}
        pool = [before[h] for h in productive]
        for _attempt in range(10_000):
            rng.shuffle(pool)
            tokens = {h: pool[i] for i, h in enumerate(productive)}
            ok = True
            for h in productive:
                if tokens[h] in keep_apart and any(tokens.get(o) in keep_apart for o in self.hex_neighbours(h)):
                    ok = False
                    break
            if ok:
                self.tokens = tokens
                self.validate()
                return {"before": before, "after": dict(tokens)}
        raise RuntimeError("could not reshuffle the tokens under the keep-apart rule")

    # ------------------------------------------------------------------ generation
    @classmethod
    def generate(cls, seed: int) -> "GodBoard":
        """A seeded layout: roles shuffled over the 30 cells, tokens over the productive ones, re-drawn until no 6 shares an edge with a 6 or an
        8 (and no 8 with an 8). The result is saved explicitly, so a reload never re-rolls it."""
        spec = rules.board_spec()
        rng = random.Random(int(seed) * 1_000_003 + 17)
        base = cls(catan_5_6_cells())
        roles_pool: list[str] = []
        for role, n in spec["role_counts"].items():
            roles_pool += [role] * int(n)
        keep_apart = {int(t) for t in spec.get("keep_apart", [])}
        for _attempt in range(10_000):
            rng.shuffle(roles_pool)
            roles = {h: roles_pool[i] for i, h in enumerate(base.hexes)}
            tokens_pool = [int(t) for t in spec["tokens"]]
            rng.shuffle(tokens_pool)
            productive = [h for h in base.hexes if roles[h] != rules.DESERT]
            tokens = {h: tokens_pool[i] for i, h in enumerate(productive)}
            ok = True
            for h in productive:
                if tokens[h] in keep_apart:
                    for o in base.hex_neighbours(h):
                        if tokens.get(o) in keep_apart:
                            ok = False
                            break
                if not ok:
                    break
            if ok:
                return cls(base.cells, roles, tokens)
        raise RuntimeError("could not lay out a board that keeps the red tokens apart")

"""Immutable radius-2 axial hex topology (C04 / T025).

Geometry uses integer cube coordinates only — no float equality for merging.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable

# Cube directions for pointy-top neighbours (q,r) == (x,z).
_HEX_NEIGHBOURS = (
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, 0),
    (-1, 1),
    (0, 1),
)

# Corners of a hex expressed as offsets from hex*3 in cube space (x,y,z).
# Sum of each offset is 0; absolute corner coords stay on the integer lattice.
_CORNER_OFFSETS = (
    (2, -1, -1),
    (1, 1, -2),
    (-1, 2, -1),
    (-2, 1, 1),
    (-1, -1, 2),
    (1, -2, 1),
)


def axial_to_cube(q: int, r: int) -> tuple[int, int, int]:
    return (q, -q - r, r)


def cube_to_axial(x: int, _y: int, z: int) -> tuple[int, int]:
    return (x, z)


def hexes_radius(radius: int) -> list[tuple[int, int]]:
    cells: list[tuple[int, int]] = []
    for q in range(-radius, radius + 1):
        r1 = max(-radius, -q - radius)
        r2 = min(radius, -q + radius)
        for r in range(r1, r2 + 1):
            cells.append((q, r))
    return cells


def _corner_key(x: int, y: int, z: int) -> tuple[int, int, int]:
    if x + y + z != 0:
        raise ValueError(f"non-planar corner {(x, y, z)}")
    return (x, y, z)


@dataclass(frozen=True)
class HexBoard:
    """Immutable shared-corner hex board."""

    radius: int
    hexes: tuple[tuple[int, int], ...]
    nodes: tuple[str, ...]
    edges: tuple[str, ...]
    _node_corners: dict[str, tuple[int, int, int]]
    _corner_nodes: dict[tuple[int, int, int], str]
    _hex_nodes: dict[tuple[int, int], tuple[str, ...]]
    _node_hexes: dict[str, tuple[tuple[int, int], ...]]
    _adjacency: dict[str, tuple[str, ...]]
    _edge_endpoints: dict[str, tuple[str, str]]
    _endpoint_edge: dict[tuple[str, str], str]

    @classmethod
    def radius2(cls) -> "HexBoard":
        return cls.build(radius=2)

    @classmethod
    def build(cls, radius: int = 2) -> "HexBoard":
        hex_list = tuple(sorted(hexes_radius(radius)))
        corner_to_hexes: dict[tuple[int, int, int], set[tuple[int, int]]] = defaultdict(set)
        for q, r in hex_list:
            cx, cy, cz = axial_to_cube(q, r)
            hx, hy, hz = cx * 3, cy * 3, cz * 3
            for ox, oy, oz in _CORNER_OFFSETS:
                key = _corner_key(hx + ox, hy + oy, hz + oz)
                corner_to_hexes[key].add((q, r))

        corners = sorted(corner_to_hexes.keys())
        node_ids: list[str] = []
        node_corners: dict[str, tuple[int, int, int]] = {}
        corner_nodes: dict[tuple[int, int, int], str] = {}
        for index, corner in enumerate(corners, start=1):
            nid = f"node:{index}"
            node_ids.append(nid)
            node_corners[nid] = corner
            corner_nodes[corner] = nid

        hex_nodes: dict[tuple[int, int], tuple[str, ...]] = {}
        node_hexes: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for q, r in hex_list:
            cx, cy, cz = axial_to_cube(q, r)
            hx, hy, hz = cx * 3, cy * 3, cz * 3
            ordered: list[str] = []
            for ox, oy, oz in _CORNER_OFFSETS:
                nid = corner_nodes[_corner_key(hx + ox, hy + oy, hz + oz)]
                ordered.append(nid)
                node_hexes[nid].append((q, r))
            hex_nodes[(q, r)] = tuple(ordered)

        # Edges: consecutive corners around each hex; undirected endpoint-sorted.
        endpoint_edge: dict[tuple[str, str], str] = {}
        edge_endpoints: dict[str, tuple[str, str]] = {}
        adjacency: dict[str, set[str]] = defaultdict(set)
        for nodes_around in hex_nodes.values():
            for i, a in enumerate(nodes_around):
                b = nodes_around[(i + 1) % 6]
                pair = tuple(sorted((a, b)))
                if pair in endpoint_edge:
                    continue
                eid = f"edge:{len(endpoint_edge) + 1}"
                endpoint_edge[pair] = eid  # type: ignore[index]
                edge_endpoints[eid] = (pair[0], pair[1])
                adjacency[pair[0]].add(pair[1])
                adjacency[pair[1]].add(pair[0])

        frozen_node_hexes = {
            nid: tuple(sorted(set(hexes))) for nid, hexes in node_hexes.items()
        }
        frozen_adj = {nid: tuple(sorted(neighbours)) for nid, neighbours in adjacency.items()}

        board = cls(
            radius=radius,
            hexes=hex_list,
            nodes=tuple(node_ids),
            edges=tuple(edge_endpoints.keys()),
            _node_corners=node_corners,
            _corner_nodes=corner_nodes,
            _hex_nodes=hex_nodes,
            _node_hexes=frozen_node_hexes,
            _adjacency=frozen_adj,
            _edge_endpoints=edge_endpoints,
            _endpoint_edge={pair: eid for pair, eid in endpoint_edge.items()},
        )
        board.validate()
        return board

    def validate(self) -> None:
        if self.radius == 2:
            if len(self.hexes) != 19:
                raise ValueError(f"expected 19 hexes, got {len(self.hexes)}")
            if len(self.nodes) != 54:
                raise ValueError(f"expected 54 nodes, got {len(self.nodes)}")
            if len(self.edges) != 72:
                raise ValueError(f"expected 72 edges, got {len(self.edges)}")
        for nid, neighbours in self._adjacency.items():
            if len(neighbours) > 3:
                raise ValueError(f"node {nid} degree {len(neighbours)} > 3")
            for other in neighbours:
                if nid not in self._adjacency[other]:
                    raise ValueError(f"adjacency not reciprocal: {nid}→{other}")
        for nid, hexes in self._node_hexes.items():
            if len(hexes) > 3:
                raise ValueError(f"node {nid} touches {len(hexes)} hexes")
            for hq in hexes:
                if nid not in self._hex_nodes[hq]:
                    raise ValueError(f"hex {hq} missing node {nid}")

    def adjacent_nodes(self, node: str) -> tuple[str, ...]:
        return self._adjacency.get(node, ())

    def touching_hexes(self, node: str) -> tuple[tuple[int, int], ...]:
        return self._node_hexes.get(node, ())

    def nodes_of_hex(self, hex_qr: tuple[int, int]) -> tuple[str, ...]:
        return self._hex_nodes[hex_qr]

    def edge(self, a: str, b: str) -> str | None:
        if a == b:
            return None
        return self._endpoint_edge.get(tuple(sorted((a, b))))

    def edge_nodes(self, edge_id: str) -> tuple[str, str]:
        return self._edge_endpoints[edge_id]

    def distance(self, a: str, b: str) -> int:
        if a == b:
            return 0
        if a not in self._adjacency or b not in self._adjacency:
            raise KeyError("unknown node")
        seen = {a}
        queue: deque[tuple[str, int]] = deque([(a, 0)])
        while queue:
            node, dist = queue.popleft()
            for nxt in self._adjacency[node]:
                if nxt in seen:
                    continue
                if nxt == b:
                    return dist + 1
                seen.add(nxt)
                queue.append((nxt, dist + 1))
        raise ValueError(f"no path {a}→{b}")

    def shortest_path(self, a: str, b: str) -> tuple[str, ...]:
        if a == b:
            return (a,)
        prev: dict[str, str | None] = {a: None}
        queue: deque[str] = deque([a])
        while queue:
            node = queue.popleft()
            for nxt in self._adjacency[node]:
                if nxt in prev:
                    continue
                prev[nxt] = node
                if nxt == b:
                    path = [b]
                    cur: str | None = b
                    while cur != a:
                        cur = prev[cur]
                        assert cur is not None
                        path.append(cur)
                    path.reverse()
                    return tuple(path)
                queue.append(nxt)
        raise ValueError(f"no path {a}→{b}")

    def to_dict(self) -> dict:
        return {
            "radius": self.radius,
            "hexes": [list(h) for h in self.hexes],
            "nodes": list(self.nodes),
            "edges": list(self.edges),
            "adjacency": {k: list(v) for k, v in self._adjacency.items()},
            "node_hexes": {k: [list(h) for h in v] for k, v in self._node_hexes.items()},
            "edge_endpoints": {k: list(v) for k, v in self._edge_endpoints.items()},
        }

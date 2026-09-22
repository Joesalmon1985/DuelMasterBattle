"""Strategic world map projection — read-only presentation of board truth."""

from __future__ import annotations

from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.world.board import HexBoard


def export_world_map(state: WorldState, *, reveal_all: bool = False) -> dict[str, Any]:
    """Build a vector world-map payload from authoritative hex topology + state.

    Node coordinates come from HexBoard corner geometry (not hex-centre averages).
    Ordinary play should pass reveal_all=False. Formations/carts are omitted from
    the strategic presentation layer (see presentation.omitted).
    """
    board = _resolve_board(state)
    coords = board.map_coordinates()

    topo = state.board.get("topology") or {}
    hex_ids = list(topo.get("hexes") or board.hexes)
    terrain = state.board.get("hex_terrain") or {}
    tokens = state.board.get("hex_token") or {}
    axial = topo.get("hex_axial") or {hid: list(board.hex_axial(hid)) for hid in board.hexes}

    hexes = []
    for hid in hex_ids:
        hid = str(hid)
        ax = axial.get(hid) or _parse_axial(hid)
        if isinstance(ax, (list, tuple)) and len(ax) >= 2:
            q, r = int(ax[0]), int(ax[1])
        elif hid in board.hexes:
            q, r = board.hex_axial(hid)
        else:
            q, r = _parse_axial(hid)
        hexes.append(
            {
                "id": hid,
                "q": q,
                "r": r,
                "terrain": terrain.get(hid),
                "number": tokens.get(hid),
                "corners": [list(p) for p in board.hex_corner_positions(hid)],
            }
        )

    settlements_by_node = {
        str(s.get("node_id")): s
        for s in (state.settlements or {}).values()
        if not s.get("staging") and s.get("node_id")
    }
    # Include all topology nodes so Godot has 54 coordinates even without recs.
    node_recs = dict(state.board.get("nodes") or {})
    for nid in board.nodes:
        node_recs.setdefault(nid, {})

    nodes = []
    for nid in board.nodes:
        rec = node_recs.get(nid) or {}
        settle = settlements_by_node.get(nid)
        mx, my = coords[nid]
        nodes.append(
            {
                "id": nid,
                "label": str((rec or {}).get("label") or (settle or {}).get("label") or "Place"),
                "settlement_id": str((settle or {}).get("id") or ""),
                "faction_id": str((settle or {}).get("faction_id") or ""),
                "is_settlement": settle is not None,
                "site_kind": _site_kind(settle) if settle is not None else "",
                "map_position": [mx, my],
                "touching_hexes": [str(h) for h in board.touching_hexes(nid)],
            }
        )

    edges = []
    for eid in board.edges:
        a, b = board.edge_nodes(eid)
        ax, ay = coords[a]
        bx, by = coords[b]
        edges.append(
            {
                "id": eid,
                "a": a,
                "b": b,
                "a_map": [ax, ay],
                "b_map": [bx, by],
            }
        )

    roads = []
    for rid, road in sorted((state.roads or {}).items(), key=lambda kv: str(kv[0])):
        if str(road.get("status") or "") != "built":
            continue
        a = str(road.get("a"))
        b = str(road.get("b"))
        roads.append(
            {
                "id": str(rid),
                "a": a,
                "b": b,
                "faction_id": str(road.get("faction_id") or ""),
                "edge_id": board.edge(a, b) or "",
            }
        )

    player = state.player or {}
    john_node = str(player.get("node_id") or "")
    john = {
        "node_id": john_node,
        "map_position": list(coords[john_node]) if john_node in coords else [],
        "position": list(player.get("position") or []),
    }

    hazards = []
    cubes = ((state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
    by_hex: dict[str, list[dict[str, Any]]] = {}
    for cid, cube in sorted(cubes.items()):
        if not cube.get("active", True) and not reveal_all:
            continue
        if not cube.get("active", True):
            continue
        hid = str(cube.get("hex_id") or "")
        by_hex.setdefault(hid, []).append(
            {
                "cube_id": str(cid),
                "hex_id": hid,
                "type": str(cube.get("type") or ""),
            }
        )
    for hid, group in sorted(by_hex.items()):
        for index, row in enumerate(group):
            row["stack_index"] = index
            row["stack_count"] = len(group)
            hazards.append(row)

    return {
        "schema_version": 2,
        "reveal_all": bool(reveal_all),
        "hexes": hexes,
        "nodes": nodes,
        "edges": edges,
        "roads": roads,
        "john": john,
        "hazards": hazards,
        # Strategic map omits formations/carts — cluttered at board scale.
        "formations": [],
        "carts": [],
        "presentation": {
            "formations": "omitted",
            "carts": "omitted",
            "geometry": "hex_board_corners",
        },
        "start_node_id": str((state.board.get("g05") or {}).get("start_node_id") or john_node),
    }


def _resolve_board(state: WorldState) -> HexBoard:
    topo = state.board.get("topology") or {}
    radius = int(topo.get("radius") or 2)
    return HexBoard.build(radius=radius)


def _site_kind(settle: dict[str, Any] | None) -> str:
    if not settle:
        return ""
    if settle.get("ruin_only") or str(settle.get("status") or "") in {"ruined", "inert", "destroyed"}:
        return "ruin"
    if settle.get("historic_core"):
        return "historic_core"
    if settle.get("legacy"):
        return "legacy"
    tier = str(settle.get("tier") or "settlement")
    if tier == "city":
        return "city"
    return "settlement"


def _parse_axial(hex_id: str) -> tuple[int, int]:
    raw = str(hex_id).split(":", 1)[-1]
    parts = raw.split(",")
    try:
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 0, 0

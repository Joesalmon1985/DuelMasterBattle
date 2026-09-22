"""Strategic world map projection — read-only presentation of board truth."""

from __future__ import annotations

from typing import Any

from sim.dmb.core.state import WorldState


def export_world_map(state: WorldState, *, reveal_all: bool = False) -> dict[str, Any]:
    """Build a crude vector world-map payload from authoritative state.

    Ordinary play should pass reveal_all=False (knowledge-filtered later).
    Developer toggle may set reveal_all=True.
    """
    topo = state.board.get("topology") or {}
    hex_ids = list(topo.get("hexes") or [])
    terrain = state.board.get("hex_terrain") or {}
    tokens = state.board.get("hex_token") or {}
    axial = topo.get("hex_axial") or {}

    hexes = []
    for hid in hex_ids:
        hid = str(hid)
        ax = axial.get(hid) or _parse_axial(hid)
        hexes.append(
            {
                "id": hid,
                "q": ax[0],
                "r": ax[1],
                "terrain": terrain.get(hid),
                "number": tokens.get(hid),
            }
        )

    nodes = []
    node_recs = (state.board.get("nodes") or {})
    node_hexes = state.board.get("node_hexes") or {}
    settlements_by_node = {
        str(s.get("node_id")): s
        for s in (state.settlements or {}).values()
        if not s.get("staging") and s.get("node_id")
    }
    for nid, rec in sorted(node_recs.items(), key=lambda kv: str(kv[0])):
        nid = str(nid)
        settle = settlements_by_node.get(nid)
        touching = list(node_hexes.get(nid) or [])
        if not touching and topo.get("node_hexes"):
            touching = list((topo.get("node_hexes") or {}).get(nid) or [])
        nodes.append(
            {
                "id": nid,
                "label": str((rec or {}).get("label") or (settle or {}).get("label") or "Place"),
                "settlement_id": str((settle or {}).get("id") or ""),
                "faction_id": str((settle or {}).get("faction_id") or ""),
                "is_settlement": settle is not None,
                "touching_hexes": [str(h) for h in touching],
            }
        )

    roads = []
    for rid, road in sorted((state.roads or {}).items(), key=lambda kv: str(kv[0])):
        if str(road.get("status") or "") != "built":
            continue
        roads.append(
            {
                "id": str(rid),
                "a": str(road.get("a")),
                "b": str(road.get("b")),
                "faction_id": str(road.get("faction_id") or ""),
            }
        )

    player = state.player or {}
    john = {
        "node_id": str(player.get("node_id") or ""),
        "position": list(player.get("position") or []),
    }

    hazards = []
    cubes = ((state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
    for cid, cube in sorted(cubes.items()):
        if not cube.get("active", True) and not reveal_all:
            continue
        if not cube.get("active", True):
            continue
        hazards.append(
            {
                "cube_id": str(cid),
                "hex_id": str(cube.get("hex_id") or ""),
                "type": str(cube.get("type") or ""),
            }
        )

    formations = []
    for uid, unit in sorted((state.units or {}).items()):
        if unit.get("status") == "dead" or not unit.get("alive", True):
            continue
        formations.append(
            {
                "unit_id": str(uid),
                "person_id": str(unit.get("person_id") or ""),
                "node_id": str(unit.get("node_id") or unit.get("home_node_id") or ""),
                "faction_id": str(unit.get("faction_id") or ""),
                "archetype": str(unit.get("archetype") or ""),
            }
        )

    carts = []
    for cid, cart in sorted((state.carts or {}).items()):
        node = str(cart.get("current_node") or cart.get("node_id") or "")
        if not node and not reveal_all:
            continue
        cargo = [
            str(lot.get("good_id"))
            for lot in (cart.get("cargo_lots") or [])
            if lot.get("good_id")
        ]
        carts.append(
            {
                "cart_id": str(cid),
                "node_id": node,
                "faction_id": str(cart.get("owner_faction") or ""),
                "status": str(cart.get("status") or ""),
                "cargo": cargo,
            }
        )

    return {
        "schema_version": 1,
        "reveal_all": bool(reveal_all),
        "hexes": hexes,
        "nodes": nodes,
        "roads": roads,
        "john": john,
        "hazards": hazards,
        "formations": formations if reveal_all else formations,
        "carts": carts,
        "start_node_id": str((state.board.get("g05") or {}).get("start_node_id") or john["node_id"]),
    }


def _parse_axial(hex_id: str) -> tuple[int, int]:
    # hex:q,r
    raw = str(hex_id).split(":", 1)[-1]
    parts = raw.split(",")
    try:
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 0, 0

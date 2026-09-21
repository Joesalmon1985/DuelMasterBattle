"""Dense natural geography across the Prehistoric board (presentation only)."""

from __future__ import annotations

from collections import deque

from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.board import HexBoard
from sim.dmb.world.overworld_export import export_overworld_area
from sim.dmb.world.projection import KNOWN_HEX_TERRAINS, LocalProjectionService

_SOLID = frozenset({"T", "#", "R", "f", "~", "r", " ", "X", "t"})


def _walkable_exits(
    rows: list[str], centre: tuple[int, int], exit_cells: set[tuple[int, int]]
) -> set[tuple[int, int]]:
    h, w = len(rows), len(rows[0]) if rows else 0
    sx, sy = centre
    if not (0 <= sx < w and 0 <= sy < h) or rows[sy][sx] in _SOLID:
        return set()
    seen = {(sx, sy)}
    q = deque([(sx, sy)])
    found: set[tuple[int, int]] = set()
    while q:
        x, y = q.popleft()
        if (x, y) in exit_cells:
            found.add((x, y))
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < w and 0 <= ny < h) or (nx, ny) in seen:
                continue
            if rows[ny][nx] in _SOLID:
                continue
            seen.add((nx, ny))
            q.append((nx, ny))
    return found


def test_all_54_nodes_natural_geography_seed_507() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    state = sim.state
    proj = LocalProjectionService(state)
    board = HexBoard.from_dict(state.board.get("topology") or {})
    hex_terrain = state.board.get("hex_terrain") or {}
    node_hexes = state.board.get("node_hexes") or {}

    assert len(board.nodes) == 54

    for nid in board.nodes:
        nid = str(nid)
        touching = [str(h) for h in (node_hexes.get(nid) or [])]
        view1 = proj.project_node(nid)
        geo1 = list(view1.get("geography") or [])
        by_hex = {str(p["hex_id"]): p for p in geo1}
        assert set(by_hex) == set(touching), nid

        for hid in touching:
            expected = str(hex_terrain.get(hid) or "fields")
            if expected not in KNOWN_HEX_TERRAINS:
                expected = "fields"
            patch = by_hex[hid]
            assert patch["terrain"] == expected, (nid, hid, patch["terrain"], expected)
            assert patch["terrain"] in KNOWN_HEX_TERRAINS
            props = list(patch.get("natural_props") or [])
            assert props, (nid, hid, expected)
            for prop in props:
                assert "kind" in prop and "grid" in prop and "marker" in prop
                gx, gy = int(prop["grid"][0]), int(prop["grid"][1])
                ox, oy = int(patch["grid"][0]), int(patch["grid"][1])
                fw, fh = int(patch["footprint"][0]), int(patch["footprint"][1])
                assert ox <= gx < ox + fw and oy <= gy < oy + fh

        # Persistence across two project calls (durable layout, not reroll).
        view2 = proj.project_node(nid)
        assert view2["geography"] == view1["geography"]

        # Exits not fully blocked after dense geography paint (paths overlay corridors).
        area = export_overworld_area(state, nid)
        rows = list(area["rows"])
        cx, cy = int(view1["centre"][0]), int(view1["centre"][1])
        start = (cx, cy)
        if rows[cy][cx] in _SOLID:
            found = None
            for rad in range(1, 8):
                for dy in range(-rad, rad + 1):
                    for dx in range(-rad, rad + 1):
                        x, y = cx + dx, cy + dy
                        if 0 <= x < len(rows[0]) and 0 <= y < len(rows) and rows[y][x] not in _SOLID:
                            found = (x, y)
                            break
                    if found:
                        break
                if found:
                    start = found
                    break
        exit_cells = {
            (int(e["pos"][0]), int(e["pos"][1]))
            for e in area["entities"]
            if e.get("kind") == "exit" and e.get("pos")
        }
        assert exit_cells, nid
        reached = _walkable_exits(rows, start, exit_cells)
        assert reached, (nid, "all exits blocked after natural geography paint")


def test_export_emits_nature_without_unrelated_terrain() -> None:
    sim = load_fixture("FX-VILLAGE", seed=507)
    start = str(sim.state.board["g05"]["start_node_id"])
    touching = set(sim.state.board.get("node_hexes", {}).get(start) or [])
    expected = {
        str((sim.state.board.get("hex_terrain") or {}).get(h) or "fields") for h in touching
    }
    area = export_overworld_area(sim.state, start)
    nature = [
        e
        for e in area["entities"]
        if e.get("presentation") == "nature" or e.get("kind") == "nature"
    ]
    assert nature
    for ent in nature:
        if ent.get("terrain"):
            assert ent["terrain"] in expected
            assert ent["terrain"] in KNOWN_HEX_TERRAINS
        assert not ent.get("bridge_entity")
        if ent.get("ambient"):
            assert ent.get("kind") == "deco"
    signs = [
        e
        for e in area["entities"]
        if e.get("kind") == "sign" and str(e.get("id") or "").startswith("sign.nature.")
    ]
    assert signs
    for sign in signs:
        assert (sign.get("semantic") or {}).get("quiet_label") is True

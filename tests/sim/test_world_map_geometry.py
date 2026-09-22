"""World map geometry: exact HexBoard corners, not hex-centre averages."""

from __future__ import annotations

import math

from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.board import HexBoard
from sim.dmb.world.fx_era_world import FX_ERA_SEED
from sim.dmb.world.world_map import export_world_map


def _axial_pixel(q: float, r: float, size: float = 1.0) -> tuple[float, float]:
    x = size * (math.sqrt(3.0) * q + math.sqrt(3.0) / 2.0 * r)
    y = size * (1.5 * r)
    return (x, y)


def test_board_public_map_coordinates_unique() -> None:
    board = HexBoard.radius2()
    coords = board.map_coordinates()
    assert len(coords) == 54
    assert len(set(coords.values())) == 54
    for nid in board.nodes:
        assert board.node_corner(nid) is not None
        assert board.node_map_position(nid) == coords[nid]


def test_all_72_edges_are_hex_sides() -> None:
    board = HexBoard.radius2()
    # Every edge must equal one consecutive corner pair of some hex.
    hex_sides: set[tuple[str, str]] = set()
    for hid in board.hexes:
        nodes = board.nodes_of_hex(hid)
        for i, a in enumerate(nodes):
            b = nodes[(i + 1) % 6]
            hex_sides.add(tuple(sorted((a, b))))
    assert len(board.edges) == 72
    assert len(hex_sides) == 72
    for eid in board.edges:
        a, b = board.edge_nodes(eid)
        assert tuple(sorted((a, b))) in hex_sides
        ax, ay = board.node_map_position(a)
        bx, by = board.node_map_position(b)
        # Edge length in unit axial-pixel space is exactly 1.
        pa = _axial_pixel(ax, ay)
        pb = _axial_pixel(bx, by)
        dist = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
        assert abs(dist - 1.0) < 1e-9


def test_one_touch_node_is_not_hex_centre() -> None:
    board = HexBoard.radius2()
    found = False
    for nid in board.nodes:
        touching = board.touching_hexes(nid)
        if len(touching) != 1:
            continue
        found = True
        hid = touching[0]
        hq, hr = board.hex_axial(hid)
        mx, my = board.node_map_position(nid)
        # Must not coincide with hex centre (the old average-of-one bug).
        assert abs(mx - hq) > 1e-9 or abs(my - hr) > 1e-9
        # Must be one of the six geometric corners.
        corners = board.hex_corner_positions(hid)
        assert any(abs(mx - c[0]) < 1e-9 and abs(my - c[1]) < 1e-9 for c in corners)
    assert found


def test_export_geometry_counts_and_no_centre_settlements() -> None:
    board = HexBoard.radius2()
    sim = load_fixture("FX-VILLAGE", seed=507)
    payload = export_world_map(sim.state)
    assert payload["schema_version"] == 2
    assert payload["presentation"]["geometry"] == "hex_board_corners"
    assert payload["presentation"]["formations"] == "omitted"
    assert payload["formations"] == []
    assert payload["carts"] == []
    assert len(payload["hexes"]) == 19
    assert len(payload["nodes"]) == 54
    assert len(payload["edges"]) == 72
    positions = [tuple(n["map_position"]) for n in payload["nodes"]]
    assert len(set(positions)) == 54
    # No settlement sits on a hex centre (catches one-touch → centre bug).
    for n in payload["nodes"]:
        if not n.get("is_settlement"):
            continue
        mx, my = n["map_position"]
        px, py = _axial_pixel(mx, my)
        min_d = min(
            math.hypot(px - _axial_pixel(float(h["q"]), float(h["r"]))[0], py - _axial_pixel(float(h["q"]), float(h["r"]))[1])
            for h in payload["hexes"]
        )
        assert min_d > 0.4  # unit hex radius is 1; centre→vertex distance is 1
    # Built roads are genuine edges.
    for road in payload["roads"]:
        assert board.edge(road["a"], road["b"]) is not None
        assert road.get("edge_id")


def test_fx_era_seed_507_map_semantics() -> None:
    sim = load_fixture("FX-ERA", seed=FX_ERA_SEED)
    state = sim.state
    payload = export_world_map(state)
    tokens = dict(state.board.get("hex_token") or {})
    assert len(payload["hexes"]) == 19
    rendered = {h["id"]: h.get("number") for h in payload["hexes"]}
    for hid, num in tokens.items():
        assert hid in rendered
        assert rendered[hid] == num
    # Every numbered hex keeps its number even if hazard present.
    hazard_hexes = {h["hex_id"] for h in payload["hazards"]}
    for hid in hazard_hexes:
        if hid in tokens:
            assert rendered.get(hid) == tokens[hid]
    john = payload["john"]
    assert john["node_id"]
    assert len(john["map_position"]) == 2
    jpos = tuple(john["map_position"])
    node_map = {n["id"]: tuple(n["map_position"]) for n in payload["nodes"]}
    assert node_map[john["node_id"]] == jpos
    # Settlements on genuine nodes
    for n in payload["nodes"]:
        if n.get("is_settlement"):
            assert n["id"] in node_map
            assert n["site_kind"] in {"settlement", "city", "historic_core", "legacy", "ruin"}
    # Hazards carry stack metadata for non-overlapping draw
    for h in payload["hazards"]:
        assert "stack_index" in h and "stack_count" in h


def test_post_transition_site_kinds_distinct() -> None:
    from sim.dmb.time.runner import TurnRunner
    from sim.dmb.time.turns import TurnScheduler

    sim = load_fixture("FX-ERA", seed=FX_ERA_SEED)
    state = sim.state
    winner = state.board["fx_era"]["winner_faction_id"]
    runner = TurnRunner(state, TurnScheduler(state.clock))
    state.clock["scheduled_faction_ids"] = sorted(state.factions)
    state.clock["active_faction_id"] = winner
    runner.execute_wait("node:35", "map-geom-wait")
    assert state.clock.get("era") == "historic"
    payload = export_world_map(state)
    kinds = {n["site_kind"] for n in payload["nodes"] if n.get("is_settlement")}
    assert "historic_core" in kinds
    assert "ruin" in kinds or "legacy" in kinds

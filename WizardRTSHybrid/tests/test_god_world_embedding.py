"""The terrain embedding (docs/PLAN_GOD_WORLD_LIVING.md stage A; the brief's V02, V03, V04): the checked-in geometry matches the map, covers every node and
edge, keeps plots apart and on buildable land, routes corridors over passable ground without crossings, and the world's journeys follow it while the
strategic rules do not move."""

from __future__ import annotations

import json

from wizard_rts import wl_map
from wizard_rts.god_world import embedding, rules
from wizard_rts.god_world.board import GodBoard, catan_5_6_cells
from wizard_rts.god_world.world import GodWorld


def test_the_checked_in_embedding_matches_the_map_and_validates():
    grid = wl_map.load(embedding.DEFAULT_MAP)
    emb = embedding.load(embedding.DEFAULT_MAP)
    assert emb is not None and emb["map_static_hash"] == grid.static_hash()
    board = GodBoard(catan_5_6_cells())
    report = embedding.validate(emb, board, grid)
    assert report["nodes"] == 80 and report["edges"] == 109 and report["poor_plots"] == []
    assert 8.0 <= report["unit"] <= 20.0
    assert report["corridor_tiles_max"] < 4 * report["unit"]  # no corridor wanders across the island
    # the graph is untouched: the embedded corridors join exactly the logical endpoints
    for eid, (a, b) in board.edge_endpoints.items():
        poly = emb["corridors"][eid]
        assert poly[0] == emb["nodes"][a] and poly[-1] == emb["nodes"][b]


def test_building_the_embedding_is_deterministic():
    grid = wl_map.load(embedding.DEFAULT_MAP)
    board = GodBoard(catan_5_6_cells())
    a = embedding.build(board, grid, embedding.DEFAULT_MAP)
    b = embedding.build(board, grid, embedding.DEFAULT_MAP)
    assert a["nodes"] == b["nodes"] and a["corridors"] == b["corridors"]
    assert a["nodes"] == embedding.load(embedding.DEFAULT_MAP)["nodes"]


def test_dressing_follows_the_roles_of_each_world():
    w0 = GodWorld(seed=0)
    w1 = GodWorld(seed=1)
    assert w0.board.embedding["nodes"] == w1.board.embedding["nodes"]  # geometry is per map
    wood0 = {h for h in w0.board.hexes if w0.board.role(h) == "WOOD"}
    per0 = {}
    for t in w0.board.trees:
        per0[t["hex"]] = per0.get(t["hex"], 0) + 1
    assert all(per0.get(h, 0) >= 30 for h in wood0), per0
    assert sum(per0.get(h, 0) for h in w0.board.hexes if w0.board.role(h) != "WOOD") < sum(per0.get(h, 0) for h in wood0)
    from wizard_rts import terrain as T

    ore_ok = ore_n = 0
    for h in w0.board.hexes:
        x, y = w0.board.work_site(h)
        cls = w0.terrain.cls[int(y) * w0.terrain.w + int(x)]
        if w0.board.role(h) == "ORE":
            ore_n += 1
            ore_ok += int(cls == T.MINEABLE)
        elif w0.board.role(h) in ("WOOD", "WHEAT"):
            assert cls == T.ARABLE, h
    assert ore_ok >= ore_n - 1, (ore_ok, ore_n)  # a region without a mountain near its centre keeps a flat work site: the role still produces


def test_journeys_follow_corridors_and_the_rules_do_not_move():
    w = GodWorld(seed=3)
    seq = 0
    while not any(j["type"] == "expedition" for j in w.journeys.values()) and seq < 6000:
        seq += 1
        w.advance(1000, seq, snapshot=False)
    exp = next(j for j in w.journeys.values() if j["type"] == "expedition")
    assert len(exp["legs"]) >= len(exp["route"])  # a winding corridor has more legs than edges
    for leg in exp["legs"]:
        assert leg["ms"] >= 100
    # per edge the travel time is still the declared road time
    by_edge: dict[str, int] = {}
    for leg in exp["legs"]:
        by_edge[leg["edge"]] = by_edge.get(leg["edge"], 0) + int(leg["ms"])
    for eid, ms in by_edge.items():
        assert abs(ms - rules.timing("edge_travel_road")) <= 100 * len([l for l in exp["legs"] if l["edge"] == eid])
    # the same seed without a map plays the same strategic game (positions are presentation; durations per edge are the rule)
    bare = GodWorld(seed=3, map_name=None)
    mapped = GodWorld(seed=3)
    s = 0
    for _ in range(900):
        s += 1
        bare.advance(1000, s, snapshot=False)
        mapped.advance(1000, s, snapshot=False)
    assert bare.last_roll == mapped.last_roll
    assert {f: bare.vp(f) for f in bare.fids} == {f: mapped.vp(f) for f in mapped.fids}
    assert bare.ledger.hands == mapped.ledger.hands


def test_a_saved_world_keeps_its_map_and_positions():
    w = GodWorld(seed=5)
    d = json.loads(json.dumps(w.to_dict()))
    assert d["map"] == embedding.DEFAULT_MAP
    w2 = GodWorld.from_dict(d)
    assert w2.board.node_xy("node:1") == w.board.node_xy("node:1") and w2.board.unit == w.board.unit

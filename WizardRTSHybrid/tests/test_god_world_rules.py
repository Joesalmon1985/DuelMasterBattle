"""God World (docs/GOD_WORLD_PRD.md) executable rules: board, odds, ledger, costs, scoring, composition. The acceptance ids are the PRD's."""

from __future__ import annotations

import json

import pytest

from wizard_rts.god_world import ages, composition, rules
from wizard_rts.god_world.board import GodBoard, catan_5_6_cells
from wizard_rts.god_world.ledger import Ledger, LedgerError
from wizard_rts.god_world.world import GodWorld


# ------------------------------------------------------------------ AC02 / AC03: the board

def test_ac02_board_is_30_80_109_with_the_declared_inventory():
    assert len(catan_5_6_cells()) == 30
    b = GodBoard.generate(7)
    assert (len(b.hexes), len(b.nodes), len(b.edges)) == (30, 80, 109)
    rows = {}
    for q, r in b.cells:
        rows.setdefault(q, []).append(r)
    assert [len(rows[q]) for q in sorted(rows)] == [3, 4, 5, 6, 5, 4, 3]
    counts = {}
    for h in b.hexes:
        counts[b.role(h)] = counts.get(b.role(h), 0) + 1
    assert counts == {"WOOD": 6, "BRICK": 5, "SHEEP": 6, "WHEAT": 6, "ORE": 5, "DESERT": 2}
    tokens = sorted(b.token(h) for h in b.hexes if b.role(h) != "DESERT")
    assert tokens == sorted([2, 2, 12, 12] + [t for t in (3, 4, 5, 6, 8, 9, 10, 11) for _ in range(3)])
    for n in b.nodes:
        assert 1 <= len(b.node_hexes[n]) <= 3 and len(b.adjacency[n]) <= 3
        for o in b.adjacency[n]:
            assert n in b.adjacency[o]
    # 6 and 8 never share an edge
    for h in b.hexes:
        if b.token(h) in (6, 8):
            assert all(b.token(o) not in (6, 8) for o in b.hex_neighbours(h))


def test_ac03_save_round_trip_is_the_same_explicit_layout_and_never_a_radius_board():
    b = GodBoard.generate(3)
    d = json.loads(json.dumps(b.to_dict()))
    b2 = GodBoard.from_dict(d)
    assert b2.cells == b.cells and b2.roles == b.roles and b2.tokens == b.tokens
    assert b2.nodes == b.nodes and b2.edge_endpoints == b.edge_endpoints
    with pytest.raises(ValueError):
        GodBoard.from_dict({"radius": 2})
    different = GodBoard.generate(4)
    assert different.roles != b.roles or different.tokens != b.tokens


def test_board_generation_is_deterministic_per_seed():
    assert GodBoard.generate(11).to_dict() == GodBoard.generate(11).to_dict()


# ------------------------------------------------------------------ AC05 / AC06: production

def test_pips_and_odds():
    assert [rules.pips(n) for n in range(2, 13)] == [1, 2, 3, 4, 5, 6 - 6, 5, 4, 3, 2, 1][:5] + [0] + [5, 4, 3, 2, 1]
    assert rules.pips(7) == 0 and rules.odds_text(6) == "5/36 (13.89%)"


def _world_running(seed=1):
    w = GodWorld(seed=seed)
    w.pandemic_enabled = False  # the economy-only regression (the campaign has its own tests)
    seq = 0
    while w.phase == "SETUP":
        seq += 1
        w.advance(1000, seq, snapshot=False)
    return w


def _force_roll(w, total):
    """Roll a chosen total through the authoritative pulse (the RNG is replaced for that one pulse)."""
    class Fixed:
        def __init__(self, a, b):
            self.vals = [a, b]

        def randint(self, lo, hi):
            return self.vals.pop(0)

    real = w.rng
    w.rng = Fixed(total - 1, 1) if total > 1 else Fixed(1, 1)
    w.next_roll_ms = w.game_ms
    w._roll()
    w.rng = real


def test_ac05_a_controlled_roll_credits_settlements_once_cities_twice_deserts_and_sevens_nothing():
    w = _world_running()
    board = w.board
    v = sorted(w.villages.values(), key=lambda v: v["id"])[0]
    fid = v["faction"]
    hid, role, token = board.productive_hexes(v["node"])[0]
    before = w.ledger.available(fid)[role]
    expect = sum(int(x["level"]) for x in w.villages.values() if x["status"] == "operational" and x["faction"] == fid and any(h == hid or (t == token and r == role) for h, r, t in board.productive_hexes(x["node"])))
    _force_roll(w, token)
    gained = w.ledger.available(fid)[role] - before
    assert gained == sum(g["n"] for g in w.last_roll["grants"] if g["faction"] == fid and g["role"] == role)
    assert gained >= 1
    v["level"] = 2
    before = w.ledger.available(fid)[role]
    _force_roll(w, token)
    assert any(g["village"] == v["id"] and g["n"] == 2 for g in w.last_roll["grants"])
    totals = {r: sum(h.values()) for r, h in [(f, w.ledger.available(f)) for f in w.fids]}
    _force_roll(w, 7)
    assert w.last_roll["grants"] == [] and {r: sum(h.values()) for r, h in [(f, w.ledger.available(f)) for f in w.fids]} == totals
    desert = [h for h in board.hexes if board.role(h) == "DESERT"]
    assert all(g["hex"] not in desert for g in w.last_roll["grants"])
    w.check()


def test_ac06_all_36_pairs_give_five_tokens_to_a_settlement_on_a_6_and_ten_to_a_city_whatever_the_station_count():
    w = _world_running(seed=2)
    board = w.board
    six = next(h for h in board.hexes if board.token(h) == 6)
    node = board.hex_nodes[six][0]
    # a settlement alone on that corner, counting only its 6
    for v in list(w.villages.values()):
        if v["node"] in board.adjacency[node] or v["node"] == node:
            v["status"] = "historical"
    v = w._create_village("f1", node, 1, "operational")
    for level in (1, 2):
        v["level"] = level
        gained = 0
        for a in range(1, 7):
            for b in range(1, 7):
                class Fixed:
                    def __init__(self, a, b):
                        self.vals = [a, b]

                    def randint(self, lo, hi):
                        return self.vals.pop(0)

                w.rng = Fixed(a, b)
                w.next_roll_ms = w.game_ms
                w._roll()
                gained += sum(g["n"] for g in w.last_roll["grants"] if g["village"] == v["id"] and g["hex"] == six)
        assert gained == 5 * level
        lay = composition.layout(board, v, 1, level=level)
        d = next(d for d in lay["districts"] if d["hex"] == six)
        assert d["count"] == 5 * level  # stations are a picture, not a multiplier


# ------------------------------------------------------------------ AC07 / AC08 / ledger

def test_ac07_only_five_roles_and_nothing_cosmetic_can_be_spent():
    led = Ledger(["a"])
    with pytest.raises(LedgerError):
        led.grant("a", {"planks": 1}, "roll")
    with pytest.raises(LedgerError):
        led.grant("a", {"WOOD": -1}, "roll")
    led.grant("a", {"WOOD": 2}, "roll")
    assert set(led.available("a")) == set(rules.ROLES)
    led.check()


def test_ac08_costs_charged_once_refunds_and_rejections_change_nothing():
    w = _world_running(seed=3)
    w.ai_enabled = False
    fid = w.fids[0]
    w.ledger.grant(fid, {"WOOD": 5, "BRICK": 5, "SHEEP": 5, "WHEAT": 5, "ORE": 5}, "initial")
    before = w.ledger.available(fid)
    # an unconnected edge is rejected without mutation
    far = next(e for e in w.board.edges if not any(w.node_connects(fid, n) for n in w.board.edge_endpoints[e]) and w.road_at(e) is None)
    assert w.build_road(fid, far)["status"] == "rejected" and w.ledger.available(fid) == before
    eid = next(e for e in w.board.edges if any(w.node_connects(fid, n) for n in w.board.edge_endpoints[e]) and w.road_at(e) is None)
    assert w.build_road(fid, eid)["status"] == "ok"
    assert w.build_road(fid, eid)["status"] == "rejected"  # duplicate
    mid = w.ledger.available(fid)
    assert mid["WOOD"] == before["WOOD"] - 1 and mid["BRICK"] == before["BRICK"] - 1
    assert w.ledger.reservations and w.ledger.check() is None
    seq = 0
    for _ in range(rules.timing("road_build") // 1000 + 1):
        seq += 1
        w.advance(1000, seq, snapshot=False)
    assert w.roads[eid]["status"] == "complete" and w.ledger.available(fid) == mid  # consumed once, no second charge
    assert w.ledger.sinks["build"]["WOOD"] >= 1
    # a city reservation refunded by cancellation (the transition's reconciliation path)
    v = w.faction_villages(fid)[0]
    assert w.upgrade_city(fid, v["id"])["status"] == "ok"
    assert w.upgrade_city(fid, v["id"])["status"] == "rejected"
    rid = v["upgrade"]["rid"]
    w.ledger.release(rid)
    v["upgrade"] = None
    assert w.ledger.available(fid) == mid
    w.check()


# ------------------------------------------------------------------ AC09 / scoring vector

def test_ac09_scoring_vector_two_settlements_and_three_cities_are_eight_then_nine_then_ten_once():
    w = _world_running(seed=4)
    fid = w.fids[0]
    for v in list(w.villages.values()):
        if v["faction"] == fid:
            v["status"] = "historical"
    free = [n for n in w.board.nodes if w.node_free(n)]
    made = []
    for i in range(5):
        n = next(x for x in free if w.node_free(x))
        made.append(w._create_village(fid, n, 2 if i < 3 else 1, "operational"))
    assert w.vp(fid) == 8
    made[3]["level"] = 2
    assert w.vp(fid) == 9
    made[4]["level"] = 2
    w.pending_completions.append({"kind": "city", "faction": fid, "village": made[4]["id"]})
    w._drain_completions()
    assert w.vp(fid) == 2  # the transition restarted the carried pair as settlements
    assert len(w.history["age_winners"]) == 1 and w.history["age_winners"][0]["winner"] == fid and w.age == 2
    # five cities reach ten without any cap, card or combat (AC09)
    assert 5 * rules.vp_for_level(2) == rules.vp_target()


# ------------------------------------------------------------------ AC10 / AC11 / AC12: composition

def test_ac10_ac11_ac12_one_warehouse_station_counts_from_pips_and_level_separate_districts_no_desert_workshop():
    w = _world_running(seed=5)
    b = w.board
    for v in w.faction_villages(w.fids[0]):
        for level in (1, 2):
            lay = composition.layout(b, v, 1, level=level)
            assert lay["warehouse"]["id"] == f"{v['id']}:wh"
            assert len(lay["districts"]) == len(b.node_hexes[v["node"]])
            for d in lay["districts"]:
                if d["role"] == "DESERT":
                    assert d["count"] == 0 and d["stations"] == []
                else:
                    assert d["count"] == rules.pips(d["token"]) * level == len(d["stations"])
                    for s in d["stations"]:
                        assert len(s["buildings"]) == len(rules.role_buildings(1, d["role"]))
            ids = [s["id"] for d in lay["districts"] for s in d["stations"]]
            assert len(ids) == len(set(ids))
        l1 = composition.layout(b, v, 1, level=1)["stations_total"]
        l2 = composition.layout(b, v, 1, level=2)["stations_total"]
        assert l2 == 2 * l1
    # same-role adjacent hexes keep separate districts
    for n in b.nodes:
        roles = [b.role(h) for h in b.node_hexes[n] if b.role(h) != "DESERT"]
        if len(roles) != len(set(roles)):
            lay = composition.layout(b, {"id": "vx", "node": n, "level": 1}, 1, level=1)
            hexes = [d["hex"] for d in lay["districts"]]
            assert len(hexes) == len(set(hexes)) == len(b.node_hexes[n])
            break
    # age two pairs double the buildings, not the stations
    v = w.faction_villages(w.fids[0])[0]
    a2 = composition.layout(b, v, 2, level=1)
    wood = [d for d in a2["districts"] if d["role"] == "WOOD"]
    for d in wood:
        assert all(len(s["buildings"]) == 2 for s in d["stations"])


def test_worst_case_city_layout_stays_inside_its_hexes_and_clear_of_the_warehouse():
    b = GodBoard.generate(0)
    best = max(b.nodes, key=lambda n: b.node_pips(n))
    lay = composition.layout(b, {"id": "big", "node": best, "level": 2}, 2, level=2)
    px, py = b.node_xy(best)
    for d in lay["districts"]:
        cx, cy = b.hex_xy(d["hex"])
        for s in d["stations"]:
            for bld in s["buildings"]:
                # inside the source hex (closer to its centre than to any other hex centre) and outside the clear ring
                dist_own = (bld["x"] - cx) ** 2 + (bld["y"] - cy) ** 2
                for other in b.hexes:
                    if other != d["hex"]:
                        ox, oy = b.hex_xy(other)
                        assert dist_own <= (bld["x"] - ox) ** 2 + (bld["y"] - oy) ** 2 + 1e-6
                assert ((bld["x"] - px) ** 2 + (bld["y"] - py) ** 2) ** 0.5 >= composition.CLEAR_RADIUS
    assert lay["stations_total"] == 2 * b.node_pips(best)


# ------------------------------------------------------------------ AC19 / carry-over vector

def test_ac19_ranking_uses_theoretical_output_not_recent_rolls():
    w = _world_running(seed=6)
    b = w.board
    fid = w.fids[0]
    for v in list(w.villages.values()):
        if v["faction"] == fid:
            v["status"] = "historical"
    by_pips = sorted(b.nodes, key=lambda n: (-b.node_pips(n), n))
    strong = next(n for n in by_pips if w.node_free(n) and b.node_pips(n) >= 12)
    s = w._create_village(fid, strong, 1, "operational")
    weak_node = next(n for n in reversed(by_pips) if w.node_free(n) and 0 < b.node_pips(n) <= 2)
    c = w._create_village(fid, weak_node, 2, "operational")
    mid_node = next(n for n in by_pips if w.node_free(n) and 4 <= b.node_pips(n) <= 10)
    m = w._create_village(fid, mid_node, 1, "operational")
    c["produced"] = {"WOOD": 40}  # lucky recent rolls must not count
    ranked = ages.rank_villages(w, fid)
    assert ranked[0]["village"] == s["id"]
    assert [r["village"] for r in ranked[:2]] == [s["id"], m["id"]] or ranked[1]["expected"] >= ranked[2]["expected"]
    assert ranked[-1]["village"] == c["id"]

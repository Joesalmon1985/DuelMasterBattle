"""God World journeys and conservation: founding expeditions, caravans with escrow, bank trade, trails, save/load in every phase (AC13-AC17)."""

from __future__ import annotations

import json

from wizard_rts.god_world import rules
from wizard_rts.god_world.ledger import Ledger
from wizard_rts.god_world.world import GodWorld


def _running(seed=1):
    w = GodWorld(seed=seed)
    w.pandemic_enabled = False  # the economy-only regression (the campaign has its own tests)
    w.ai_enabled = False  # these tests drive the commands themselves (setup placement is not the AI pass and still happens)
    seq = [0]

    def step(ms=1000):
        seq[0] += 1
        w.advance(ms, seq[0], snapshot=False)

    while w.phase == "SETUP":
        step()
    return w, step


def _rich(w, fid, n=6):
    w.ledger.grant(fid, {r: n for r in rules.ROLES}, "initial")


def test_ledger_vector_one_for_one_trade_balances_in_every_phase_and_replays_change_nothing():
    led = Ledger(["A", "B"])
    led.grant("A", {"WOOD": 2}, "initial")
    led.grant("B", {"BRICK": 2}, "initial")
    cid = led.load_cargo("A", {"WOOD": 1}, "j1")
    eid = led.escrow("B", {"BRICK": 1}, "j1")
    assert led.available("A")["WOOD"] == 1 and led.available("B")["BRICK"] == 1
    assert led.cargo[cid]["goods"] == {"WOOD": 1} and led.escrows[eid]["goods"] == {"BRICK": 1}
    led.check()
    assert led.unload_cargo(cid, "B") and not led.unload_cargo(cid, "B")  # a replayed arrival pays nothing
    ret = led.escrow_to_cargo(eid, "A", "j1")
    assert led.escrow_to_cargo(eid, "A", "j1") is None
    assert led.available("B") == {"WOOD": 1, "BRICK": 1, "SHEEP": 0, "WHEAT": 0, "ORE": 0}
    led.check()
    assert led.unload_cargo(ret) and not led.unload_cargo(ret)
    assert led.available("A") == {"WOOD": 1, "BRICK": 1, "SHEEP": 0, "WHEAT": 0, "ORE": 0}
    t = led.totals()["held"]
    assert t["WOOD"] == 2 and t["BRICK"] == 2
    led.check()


def test_ac13_ac14_a_village_stays_pending_until_the_party_arrives_and_builds_and_sites_exclude_neighbours():
    w, step = _running(seed=8)
    fid = w.fids[0]
    _rich(w, fid)
    # build roads until a legal site is reachable
    for _ in range(40):
        if w.legal_sites(fid):
            break
        from wizard_rts.god_world import ai

        targets = ai.frontier_targets(w, fid)
        assert targets, "a fresh board must offer a frontier"
        r = w.build_road(fid, targets[0][2][0])
        assert r["status"] == "ok", r
        while w.roads[targets[0][2][0]]["status"] != "complete":
            step()
        _rich(w, fid, 2)
    sites = w.legal_sites(fid)
    node = sorted(sites)[0]
    vp0 = w.vp(fid)
    hand0 = w.ledger.available(fid)
    r = w.found_settlement(fid, node)
    assert r["status"] == "ok", r
    v = w.villages[r["village"]]
    assert v["status"] == "pending" and w.vp(fid) == vp0
    assert all(hand0[k] - w.ledger.available(fid)[k] == rules.cost("settlement").get(k, 0) for k in rules.ROLES)
    # the node and its neighbours are no longer free for anyone
    other = w.fids[1]
    assert not w.node_free(node) and all(not w.node_free(o) for o in w.board.adjacency[node])
    assert w.found_settlement(other, node)["status"] == "rejected"
    assert w.found_settlement(fid, node)["status"] == "rejected"
    # incomplete roads never enable expansion: a road still building does not make its far end reachable; a completed one does
    nxt = next((e for e in w.board.node_edges[node] if w.road_at(e) is None and w.active_village_at(w.board.other_end(e, node)) is None), None)
    if nxt is not None:
        far = w.board.other_end(nxt, node)
        assert w.build_road(fid, nxt)["status"] == "ok"  # our completed road reaches this node, so a road may continue from it
        assert far not in w.reachable(fid)
        while w.roads[nxt]["status"] == "building":
            step(100)
        assert far in w.reachable(fid)
    j = w.journeys[r["journey"]]
    while j["phase"] == "outbound":
        assert v["status"] == "pending"
        step(100)
    assert v["status"] == "building" and j["phase"] == "building" and w.vp(fid) == vp0
    while v["status"] == "building":
        step(100)
    assert v["status"] == "operational" and v["level"] == 1 and w.vp(fid) == vp0 + 1
    assert r["journey"] not in w.journeys and node not in w.node_reserved
    assert w.ledger.reservations == {} or all(rec["purpose"] != "settlement" for rec in w.ledger.reservations.values())
    w.check()


def test_ac15_ac16_a_real_trade_reserves_both_sides_exchanges_once_and_survives_save_load_in_each_phase():
    w, step = _running(seed=9)
    a, b = w.fids[0], w.fids[1]
    w.ledger.grant(a, {"WOOD": 3}, "initial")
    w.ledger.grant(b, {"ORE": 3}, "initial")
    # make the partner want it: its plan needs WOOD (roads) and has spare ORE beyond any plan
    r = w.offer_trade(a, b, {"WOOD": 1}, {"ORE": 1})
    if r["status"] == "rejected" and r["reason"] == "declined":
        w.ledger.grant(b, {"ORE": 6}, "initial")
        r = w.offer_trade(a, b, {"WOOD": 1}, {"ORE": 1})
    assert r["status"] == "ok", r
    jid = r["journey"]
    j = w.journeys[jid]
    ore_b = w.ledger.available(b)["ORE"]
    assert j["escrow"] in w.ledger.escrows and j["cargo"] in w.ledger.cargo
    # the partner cannot spend what it escrowed
    assert w.ledger.reserve(b, {"ORE": ore_b + 1}, "x") is None
    phases = set()
    guard = 0
    while jid in w.journeys and guard < 100000:
        guard += 1
        phases.add(w.journeys[jid]["phase"])
        step(100)
        w.ledger.check()  # held = sources - sinks in every phase (rolls add, nothing vanishes)
        jj = w.journeys.get(jid)
        if jj is not None:
            assert (jj["cargo"] in w.ledger.cargo) and (jj["escrow"] is None or jj["escrow"] in w.ledger.escrows)
        if guard % 7 == 0:  # save/load mid-journey keeps every token where it is
            w = GodWorld.from_dict(json.loads(json.dumps(w.to_dict())))
            seq = [w.clock_sequence]

            def step(ms=1000, _w=w, _seq=seq):  # noqa: E306
                _seq[0] += 1
                _w.advance(ms, _seq[0], snapshot=False)
    assert phases >= {"outbound", "return"}
    assert w.counters["trades"] == 1
    assert w.ledger.available(b)["WOOD"] >= 1 and w.ledger.available(a)["ORE"] >= 1
    w.check()


def test_ac17_isolated_factions_trade_over_trails_and_the_bank_needs_no_port_or_consent():
    w, step = _running(seed=10)
    a = w.fids[0]
    # no roads but setup roads: a route between two factions exists only over trails
    v_a = w.faction_villages(a)[0]
    other = next(f for f in w.fids if f != a)
    v_b = w.faction_villages(other)[0]
    legs, total = w.route_any(v_a["node"], v_b["node"])
    assert legs and total >= rules.timing("edge_travel_trail")
    # expeditions still need owned completed roads: nothing beyond the setup road is reachable
    assert all(n in w.network_nodes(a) for n in w.reachable(a))
    # the bank
    w.ledger.grant(a, {"SHEEP": 4}, "initial")
    before = w.ledger.available(a)
    r = w.bank_trade(a, "SHEEP", "ORE")
    assert r["status"] == "ok"
    assert w.ledger.available(a)["SHEEP"] == before["SHEEP"] - 4
    jid = r["journey"]
    while jid in w.journeys:
        step(500)
        w.ledger.check()
    after = w.ledger.available(a)
    assert after["ORE"] == before["ORE"] + 1 and after["SHEEP"] == before["SHEEP"] - 4
    assert w.ledger.grants["bank_import"]["ORE"] == 1 and w.ledger.sinks["bank_export"]["SHEEP"] == 4
    assert any(rc["kind"] == "bank" for rc in w.ledger.receipts)
    assert w.bank_trade(a, "SHEEP", "SHEEP")["status"] == "rejected"
    assert w.bank_trade(a, "WOOD", "ORE")["status"] == "rejected"  # cannot afford four
    w.check()


def test_trade_offers_reject_bad_goods_and_duplicates_cannot_double_reserve():
    w, step = _running(seed=11)
    a, b = w.fids[0], w.fids[1]
    assert w.offer_trade(a, b, {"WOOD": 0}, {"ORE": 1})["status"] == "rejected"
    assert w.offer_trade(a, b, {"WOOD": -1}, {"ORE": 1})["status"] == "rejected"
    assert w.offer_trade(a, a, {"WOOD": 1}, {"ORE": 1})["status"] == "rejected"
    assert w.offer_trade(a, b, {"gold": 1}, {"ORE": 1})["status"] == "rejected"
    w.ledger.grant(a, {"WOOD": 1}, "initial")
    w.ledger.grant(b, {"ORE": 9}, "initial")
    n = w.ledger.available(a)["WOOD"]
    r1 = w.offer_trade(a, b, {"WOOD": n}, {"ORE": 1})
    if r1["status"] == "ok":
        assert w.offer_trade(a, b, {"WOOD": 1}, {"ORE": 1})["status"] == "rejected"  # every wood is already cargo
    w.check()

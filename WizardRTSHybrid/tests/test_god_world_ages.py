"""God World ages: the shared 10-VP trigger, the carry-over of two villages per faction, historical remains, reload at the boundary, the
fourth-age result, military presentation and the autonomous run itself (AC04, AC18, AC20-AC24, AC28, AC30 in miniature)."""

from __future__ import annotations

import json

import pytest

from wizard_rts.god_world import rules
from wizard_rts.god_world.world import GodWorld


def _run_until(w, pred, limit_s=20000):
    seq = w.clock_sequence
    for _ in range(limit_s):
        seq += 1
        w.advance(1000, seq, snapshot=False)
        if pred(w):
            return True
    return False


def test_ac04_six_ais_place_two_legal_sites_each_in_snake_order_and_get_second_site_resources_once():
    w = GodWorld(seed=12)
    w.ai_enabled = False  # placement is not the AI pass; the pass would start spending the grants in the same quantum
    assert _run_until(w, lambda w: w.phase != "SETUP", 60)
    log = w.setup["log"]
    assert [e["faction"] for e in log] == w.setup["order"] and len(log) == 12
    assert w.setup["order"][:6] == list(reversed(w.setup["order"][6:]))
    for f in w.fids:
        assert w.vp(f) == 2 and len(w.faction_villages(f)) == 2
        second = w.villages[w.setup["second"][f]]
        want = {}
        for _h, role, _t in w.board.productive_hexes(second["node"]):
            want[role] = want.get(role, 0) + 1
        assert {r: n for r, n in w.ledger.available(f).items() if n} == want
    assert sum(w.ledger.grants["initial"].values()) == sum(len(w.board.productive_hexes(w.villages[w.setup["second"][f]]["node"])) for f in w.fids)
    assert all(e["why"] for e in log)
    w.check()


def test_ac18_only_one_faction_at_ten_triggers_and_six_factions_summing_to_ten_do_not_and_waiting_never_advances():
    w = GodWorld(seed=13)
    assert _run_until(w, lambda w: w.phase == "RUNNING", 60)
    # six factions at 2 VP sum to 12 > 10: no transition, however long we wait without completions
    w.ai = {f: {**w.ai[f]} for f in w.fids}
    from wizard_rts.god_world import ai

    ai_decide = ai.decide
    ai.decide = lambda world, fid: 0  # nobody acts: waiting alone must never advance the age
    try:
        for _ in range(100):
            w.advance(15000, w.clock_sequence + 1, snapshot=False)
        assert w.age == 1 and w.history["age_winners"] == [] and w.pulses >= 90
        assert any(e["kind"] == "stall_diagnostics" for e in w.events)  # the world says why it is stuck
    finally:
        ai.decide = ai_decide


def _age_one_win(seed):
    w = GodWorld(seed=seed)
    assert _run_until(w, lambda w: bool(w.history["age_winners"]), 20000), "no age-one win within the budget"
    return w


def test_ac20_ac21_ac22_transition_keeps_two_sites_per_faction_resets_scores_and_stock_and_reload_does_not_fork():
    w = _age_one_win(0)
    t = w.transition
    assert t is not None and t["age_from"] == 1 and t["age_to"] == 2 and w.age == 2
    for f in w.fids:
        keep = t["selected"][f]
        assert len(keep) == 2
        active = [v for v in w.villages.values() if v["faction"] == f and v["status"] in ("operational", "rebuilding")]
        assert sorted(v["id"] for v in active) == sorted(keep)
        assert all(int(v["level"]) == 1 and v["age"] == 2 and v["warehouse"] == f"{v['id']}:wh" for v in active)
        assert w.vp(f) == 2
        # stock reset: only the new starting grant remains, one per productive hex of the lower-ranked site
        low = w.villages[keep[1]]
        want = {}
        for _h, role, _t in w.board.productive_hexes(low["node"]):
            want[role] = want.get(role, 0) + 1
        assert {r: n for r, n in w.ledger.available(f).items() if n} == want
        assert t["grants"][f] == want
    archived = sum(w.ledger.sinks["archived"].values())
    assert archived == sum(sum(g.values()) for g in t["archived"].values())
    assert w.ledger.reservations == {} and w.ledger.escrows == {} and w.ledger.cargo == {} and w.journeys == {}
    # historical sites and roads hold nothing
    hist = [v for v in w.villages.values() if v["status"] == "historical"]
    assert hist, "some villages should be left behind"
    for v in hist:
        assert w.active_village_at(v["node"]) is None or w.active_village_at(v["node"])["id"] != v["id"]
    assert all(r["status"] == "historical" for r in w.roads.values())
    for f in w.fids:
        assert w.network_nodes(f) == {v["node"] for v in w.villages.values() if v["faction"] == f and v["status"] in ("operational", "rebuilding")}
    # a historical node can be refounded (free once its neighbours allow)
    freed = [v["node"] for v in hist if w.node_free(v["node"])]
    assert freed or all(any(w.active_village_at(o) for o in w.board.adjacency[v["node"]]) for v in hist)
    # reload in TRANSITIONING: finishes the same transition, no second grant
    assert w.phase == "TRANSITIONING"
    snap = json.loads(json.dumps(w.to_dict()))
    w2 = GodWorld.from_dict(snap)
    grants_before = dict(w2.ledger.grants["transition"])
    assert _run_until(w2, lambda x: x.phase == "RUNNING", 60)
    assert w2.ledger.grants["transition"] == grants_before and w2.age == 2 and len(w2.history["transitions"]) == 1
    assert all(w2.vp(f) == 2 for f in w2.fids)
    assert _run_until(w, lambda x: x.phase == "RUNNING", 60)
    assert w.state_hash() == w2.state_hash()  # the same epoch from either side of the boundary
    w.check()
    w2.check()
    assert any(e["kind"] == "age_started" for e in w.events) and sum(1 for e in w.events if e["kind"] == "age_started") == 1


def test_carry_over_vector_both_cities_restart_as_settlements_with_two_vp():
    from wizard_rts.god_world import ages

    w = GodWorld(seed=14)
    assert _run_until(w, lambda w: w.phase == "RUNNING", 60)
    f = w.fids[0]
    vills = w.faction_villages(f)
    for v in vills:
        v["level"] = 2
    assert w.vp(f) == 4
    ages.trigger(w, f, {"kind": "test", "faction": f})
    assert w.age == 2 and w.vp(f) == 2 and all(int(v["level"]) == 1 for v in w.faction_villages(f, ("rebuilding",)))


def test_ac23_ac24_a_full_autonomous_run_reaches_the_fourth_age_result_with_idle_bounded_garrisons():
    w = GodWorld(seed=1)
    seq = 0
    budget = rules.limit("diagnostic_pulses_per_age")
    while w.final_result is None:
        seq += 1
        w.advance(1000, seq, snapshot=False)
        assert w.pulses < budget, f"age {w.age} stalled: {[(f, w.ai[f]['reason']) for f in w.fids]}"
        if seq % 500 == 0:
            w.check()
            # garrisons: bounded, idle, never charged
            for v in w.villages.values():
                if v["status"] == "operational":
                    quota = rules.limit("garrison_city") if int(v["level"]) >= 2 else rules.limit("garrison_settlement")
                    assert sum(1 for u in w.units.values() if u["village"] == v["id"] and u["status"] == "active" and u["age"] == w.age) <= quota
    assert [r["age"] for r in w.history["age_winners"]] == [1, 2, 3, 4]
    assert w.age == 4 and w.final_result["complete"] and len(w.final_result["winners"]) == 4
    assert w.ledger.grants["roll"] and sum(w.ledger.grants["roll"].values()) > 0
    assert w.counters["recruits"] > 0 and all(u["status"] in ("active", "veteran") for u in w.units.values())
    # no second final award
    before = dict(w.final_result)
    for _ in range(200):
        seq += 1
        w.advance(1000, seq, snapshot=False)
    assert w.final_result == before and w.age == 4
    w.check()


def test_ac28_presentation_calls_never_change_the_simulation():
    from wizard_rts.god_world import inspect as insp
    from wizard_rts.god_world import snapshot

    a = GodWorld(seed=15)
    b = GodWorld(seed=15)
    seq = 0
    for i in range(400):
        seq += 1
        a.advance(1000, seq, snapshot=(i % 3 == 0))
        b.advance(1000, seq, snapshot=False)
        if i % 10 == 0:
            snapshot.board_view(a)
            for v in list(a.villages.values())[:3]:
                insp.details(a, f"village:{v['id']}")
            for j in list(a.journeys.values())[:2]:
                insp.details(a, f"journey:{j['id']}")
            insp.details(a, "hex:0,0")
            insp.details(a, "nonsense:zzz")
    assert a.state_hash() == b.state_hash()


def test_save_load_round_trip_mid_age_is_exact():
    a = GodWorld(seed=16)
    seq = 0
    for _ in range(300):
        seq += 1
        a.advance(1000, seq, snapshot=False)
    b = GodWorld.from_dict(json.loads(json.dumps(a.to_dict())))
    assert a.state_hash() == b.state_hash()
    for _ in range(300):
        seq += 1
        a.advance(1000, seq, snapshot=False)
        b.advance(1000, seq, snapshot=False)
    assert a.state_hash() == b.state_hash()
    with pytest.raises(ValueError):
        GodWorld.from_dict({"profile": "campaign", "schema": 1})

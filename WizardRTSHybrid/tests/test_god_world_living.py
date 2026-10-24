"""The living village (docs/PLAN_GOD_WORLD_LIVING.md stage B; the brief's V05, V06, V07, V12, V15, V17, V18): the planner builds a mixed network from
capacity, workers and carriers perform real routed tasks with facing from motion, a log travels from a tree through a sawmill to the hub, goods are
conserved in operating units, saves resume mid-haul, and none of it moves the strategic layer."""

from __future__ import annotations

import json
import math

from wizard_rts import terrain as T
from wizard_rts.god_world import ages, local_ops, planner, rules
from wizard_rts.god_world.world import GodWorld


def _running(seed=0):
    w = GodWorld(seed=seed)
    w.ai_enabled = False
    seq = [0]

    def step(ms=1000):
        seq[0] += 1
        w.advance(ms, seq[0], snapshot=False)

    while w.phase == "SETUP":
        step()
    return w, step


def _sites(v, kind=None):
    return [s for s in v["ops"]["sites"].values() if kind is None or s["kind"] == kind]


def test_v05_capacity_is_a_budget_not_a_copy_count():
    w, step = _running(0)
    for v in w.villages.values():
        if v["status"] != "operational":
            continue
        ops = local_ops.ensure(w, v)
        caps = planner.budget(w.board, v["node"], int(v["level"]))
        for hid, cap in caps.items():
            producers = [s for s in _sites(v, "producer") if s["hex"] == hid]
            assert 1 <= len(producers) <= planner.MAX_PRODUCERS
            assert len(producers) == max(1, min(planner.MAX_PRODUCERS, math.ceil(cap / 3.0))), (hid, cap, len(producers))
        assert len(_sites(v, "hub")) == 1
        assert len(_sites(v, "military")) == 1
        # a city doubles capacity: more producers or workers, never a uniform doubling of every sprite
        v["level"] = 2
        ops2 = local_ops.ensure(w, v)
        p1 = sum(1 for s in ops["sites"].values() if s["kind"] == "producer")
        p2 = sum(1 for s in ops2["sites"].values() if s["kind"] == "producer")
        w2 = sum(int(s.get("workers", 0)) for s in ops2["sites"].values() if s["kind"] == "producer")
        assert p2 >= p1 and p2 <= 2 * p1 + 1 and w2 >= p2
        v["level"] = 1
        local_ops.ensure(w, v)
        break


def test_sites_stand_on_buildable_ground_clear_of_the_hub_corridors_and_each_other():
    w, step = _running(1)
    corridor = {tuple(t) for t in w.board.embedding["corridor_tiles"]}
    for v in w.villages.values():
        if v["status"] != "operational":
            continue
        local_ops.ensure(w, v)
        hub = _sites(v, "hub")[0]
        pts = []
        for s in v["ops"]["sites"].values():
            x, y = float(s["x"]), float(s["y"])
            cls = w.terrain.cls[int(y) * w.terrain.w + int(x)]
            assert cls in (T.ARABLE, T.WALKABLE, T.MINEABLE), (s["id"], cls)
            assert cls != T.WATER
            if s["kind"] != "hub":
                assert (int(x), int(y)) not in corridor, s["id"]
                assert math.hypot(x - hub["x"], y - hub["y"]) >= planner.HUB_CLEAR - 1e-6, s["id"]
            pts.append((x, y, s["id"]))
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d = math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
                if "hub" in (pts[i][2], pts[j][2]):
                    continue
                assert d >= 2.2 - 1e-6, (pts[i][2], pts[j][2], d)


def test_v06_workers_perform_routed_tasks_and_face_the_way_they_walk():
    w, step = _running(2)
    v = next(v for v in w.villages.values() if v["status"] == "operational")
    local_ops.ensure(w, v)
    seen_phases = set()
    facing_ok = True
    moved = 0
    last = {}
    for _ in range(1200):
        step(100)
        for a in v["ops"]["agents"].values():
            seen_phases.add((a["kind"], a["phase"]))
            p = last.get(a["id"])
            if p is not None and (p[0] != a["x"] or p[1] != a["y"]):
                moved += 1
                dx, dy = a["x"] - p[0], a["y"] - p[1]
                ang = math.atan2(dy, dx)
                h = math.atan2(a["hy"], a["hx"])
                if abs((ang - h + math.pi) % (2 * math.pi) - math.pi) > 0.05:
                    facing_ok = False
            last[a["id"]] = (a["x"], a["y"])
    assert moved > 50
    assert facing_ok, "heading must follow the actual motion"
    kinds = {k for k, _p in seen_phases}
    assert "worker" in kinds and "carrier" in kinds
    assert ("worker", "to_work") in seen_phases or ("worker", "working") in seen_phases
    assert ("carrier", "to_deliver") in seen_phases
    assert v["ops"]["hub"]["received"] > 0


def test_v07_a_log_goes_from_a_tree_through_the_sawmill_to_the_hub_and_the_woodland_regrows():
    w, step = _running(3)
    # move the world to the historic age (the sawmill chain) with the existing transition
    f = w.fids[0]
    for v in w.faction_villages(f):
        v["level"] = 2
    for v in w.faction_villages(f):
        pass
    ages.trigger(w, f, {"kind": "test", "faction": f})
    while w.phase != "RUNNING":
        step()
    wood = next((v for v in w.villages.values() if v["status"] == "operational" and any(w.board.role(h) == "WOOD" for h in w.board.node_hexes[v["node"]])), None)
    assert wood is not None
    ops = local_ops.ensure(w, wood)
    assert int(wood["age"]) == 2
    cutters = [s for s in ops["sites"].values() if s["kind"] == "producer" and s["task"] == "fell"]
    mills = [s for s in ops["sites"].values() if s["kind"] == "processor" and s["good"] == "planks"]
    assert cutters and mills and ops["trees"], (len(cutters), len(mills), len(ops["trees"]))
    felled = False
    planks_at_hub = False
    sawmill_consumed = False
    for _ in range(4000):
        step(100)
        if any(t["stage"] == "stump" for t in ops["trees"].values()):
            felled = True
        if int(mills[0].get("produced", 0)) > 0:
            sawmill_consumed = True
        if int(ops["hub"]["stock"].get("planks", 0)) > 0:
            planks_at_hub = True
            break
    assert felled and sawmill_consumed and planks_at_hub
    # conservation in operating units: logs made = logs in the mill + logs consumed + logs waiting + logs in transit
    logs_made = int(ops["throughput"].get("log", 0))
    logs_in_mill = sum(int(s["in"].get("log", 0)) for s in mills)
    logs_waiting = sum(int(s["out"].get("log", 0)) for s in cutters)
    logs_carried = sum(1 for a in ops["agents"].values() if a["cargo"] == "log")
    logs_consumed = sum(2 * (int(s.get("produced", 0)) + (1 if s["state"] == "working" else 0)) for s in mills)
    logs_at_hub = int(ops["hub"]["stock"].get("log", 0)) + int(ops["hub"]["shipped"].get("log", 0))
    assert logs_made == logs_in_mill + logs_waiting + logs_carried + logs_consumed + logs_at_hub, (logs_made, logs_in_mill, logs_waiting, logs_carried, logs_consumed, logs_at_hub)
    # a forester replants: a stump becomes a sapling, then a tree again
    foresters = [s for s in ops["sites"].values() if s["kind"] == "support" and s["task"] == "plant"]
    if foresters:
        sap = False
        for _ in range(2500):
            step(100)
            if any(t["stage"] == "sapling" for t in ops["trees"].values()):
                sap = True
                break
        assert sap


def test_v12_v18_operating_goods_never_touch_the_hand_and_the_layer_is_strategically_invisible():
    a = GodWorld(seed=6)
    b = GodWorld(seed=6)
    b.local_ops_enabled = False
    for i in range(1800):
        a.advance(1000, i + 1, snapshot=False)
        b.advance(1000, i + 1, snapshot=False)
    assert a.last_roll == b.last_roll and a.ledger.hands == b.ledger.hands and {f: a.vp(f) for f in a.fids} == {f: b.vp(f) for f in b.fids}
    assert a.history["age_winners"] == b.history["age_winners"]
    # the ledger has no entry point for an operating good
    from wizard_rts.god_world.ledger import LedgerError

    try:
        a.ledger.grant(a.fids[0], {"log": 1}, "roll")
    except LedgerError:
        pass
    else:
        raise AssertionError("an operating good must not be grantable")
    total_ops = sum(int(n) for v in a.villages.values() if v.get("ops") for n in v["ops"]["hub"]["stock"].values())
    assert total_ops > 0  # the villages worked
    a.check()


def test_v17_save_and_load_mid_haul_keeps_jobs_cargo_and_buffers():
    w, step = _running(7)
    for _ in range(600):
        step(100)
    carrying = [a for v in w.villages.values() if v.get("ops") for a in v["ops"]["agents"].values() if a["cargo"]]
    assert carrying, "somebody should be carrying something after a minute"
    d = json.loads(json.dumps(w.to_dict()))
    w2 = GodWorld.from_dict(d)
    assert w2.state_hash() == w.state_hash()
    seq = w.clock_sequence
    for _ in range(600):
        seq += 1
        w.advance(100, seq, snapshot=False)
        w2.advance(100, seq, snapshot=False)
    assert w2.state_hash() == w.state_hash()
    for v in w.villages.values():
        if v.get("ops"):
            assert v["ops"] == w2.villages[v["id"]]["ops"]


def test_the_hub_changes_with_the_age_and_stays_one():
    w, step = _running(8)
    v = next(v for v in w.villages.values() if v["status"] == "operational")
    local_ops.ensure(w, v)
    assert _sites(v, "hub")[0]["art"] == "widelands.barbarians_wood_hardener"
    for age in (2, 3, 4):
        v["age"] = age
        local_ops.ensure(w, v)
        hubs = _sites(v, "hub")
        assert len(hubs) == 1 and hubs[0]["art"] == planner.hub_spec(age, 1)["art"] and hubs[0]["id"] == f"{v['id']}:hub"
    v["age"] = 4
    v["level"] = 2
    local_ops.ensure(w, v)
    assert _sites(v, "hub")[0]["art"] == "mindustry.block.core_foundation"

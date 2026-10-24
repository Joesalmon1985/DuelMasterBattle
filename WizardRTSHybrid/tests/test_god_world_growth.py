"""Organic growth and construction (docs/PLAN_GOD_WORLD_PANDEMIC.md stage 2; the brief's P05 to P09): a village begins with seeds, each successful
matching roll unlocks one further place in that district (once per receipt, never past pips x level), the sequence is mixed, processing exists in
every age, every building passes through the saved construction lifecycle under a bounded crew, nothing works before completion, and a save made
mid-build resumes the same build."""

from __future__ import annotations

import json

from wizard_rts.god_world import local_ops, planner, rules
from wizard_rts.god_world.world import GodWorld


def _running(seed=0):
    w = GodWorld(seed=seed, map_name="Egyptian_Mandala_v1.2")
    w.local_ops_enabled = True
    w.ai_enabled = False
    seq = [0]

    def step(ms=1000):
        seq[0] += 1
        w.advance(ms, seq[0], snapshot=False)

    while w.phase == "SETUP":
        step()
    return w, step


def _first_village(w):
    return next(v for vid, v in sorted(w.villages.items()) if v["status"] == "operational")


def test_p05_a_village_begins_with_seeds_and_each_matching_roll_unlocks_one_place_once_per_receipt():
    w, step = _running(0)
    v = _first_village(w)
    ops = local_ops.ensure(w, v)
    dev = v["dev"]
    caps = planner.budget(w.board, v["node"], 1)
    assert set(dev) == set(caps)
    for hid, rec in dev.items():
        assert rec["cap"] == caps[hid] and rec["unlocked"] == 1
        assert local_ops.district_commissioned(ops, hid) == 1
        seed_site = next(s for s in ops["sites"].values() if s.get("district") == hid and s["commissioned"] and not s.get("allowance"))
        assert seed_site["kind"] == "producer" and seed_site["slot"] == 0
    assert ops["allowance"] >= 0
    hid = max(dev, key=lambda h: dev[h]["cap"])
    before = dev[hid]["unlocked"]
    assert local_ops.growth_ticket(w, v, hid, "1:7:v:x")
    assert dev[hid]["unlocked"] == before + 1
    assert not local_ops.growth_ticket(w, v, hid, "1:7:v:x")  # the same receipt never counts twice
    assert dev[hid]["unlocked"] == before + 1
    assert local_ops.district_commissioned(ops, hid) == before + 1
    # never past the cap
    n = 0
    while local_ops.growth_ticket(w, v, hid, f"1:{100 + n}:v:x"):
        n += 1
    assert dev[hid]["unlocked"] == dev[hid]["cap"]
    assert not local_ops.growth_ticket(w, v, hid, "1:999:v:x")
    assert local_ops.district_commissioned(ops, hid) <= dev[hid]["cap"]
    # a region the village does not touch, and a retired village, get no project (P06)
    other = next(h for h in w.board.hexes if h not in dev)
    assert not local_ops.growth_ticket(w, v, other, "1:5:v:y")
    v["status"] = "historical"
    assert not local_ops.growth_ticket(w, v, hid, "1:6:v:z")
    v["status"] = "operational"


def test_p06_the_roll_itself_unlocks_a_place_for_each_matching_village_and_the_receipt_is_the_roll():
    w, step = _running(0)
    v = _first_village(w)
    local_ops.ensure(w, v)
    unlocked0 = {h: r["unlocked"] for h, r in v["dev"].items()}
    while w.last_roll is None or not any(g["village"] == v["id"] for g in w.last_roll["grants"]):
        step()
        if w.pulses > 80:
            break
    grants = [g for g in w.last_roll["grants"] if g["village"] == v["id"]]
    assert grants
    for g in grants:
        rec = v["dev"][g["hex"]]
        assert rec["unlocked"] == min(rec["cap"], unlocked0[g["hex"]] + 1)
        assert f"{w.epoch}:{w.pulses}:{v['id']}:{g['hex']}" in rec["receipts"]


def test_p07_the_sequence_is_mixed_and_every_age_has_a_processor():
    w, step = _running(0)
    v = _first_village(w)
    for age in (1, 2, 3, 4):
        v["age"] = age
        w.age = age
        v.pop("ops", None)
        v.pop("dev", None)
        ops = local_ops.ensure(w, v)
        kinds_by_district = {}
        for s in ops["sites"].values():
            if s.get("district"):
                kinds_by_district.setdefault(s["district"], []).append((s["slot"], s["kind"]))
        assert any(s["kind"] == "processor" for s in ops["sites"].values()), age
        for hid, slots in kinds_by_district.items():
            seq = [k for _, k in sorted(slots)]
            assert seq[0] == "producer"
            if len(seq) >= 3 and "processor" in seq:
                assert seq.index("processor") <= 3  # a processor comes before the third producer
            assert seq != ["producer"] * len(seq) or len(seq) <= 2
        chain_ok = all(planner.chain(age, r) is not None and "processor" in planner.chain(age, r) for r in ("WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"))
        assert chain_ok, age


def _fresh_village(w):
    """A village placed directly on a free node (the test watches its construction from the first plan; founding has its own tests)."""
    f = w.fids[0]
    free = next(n for n in sorted(w.board.nodes) if w.node_free(n) and w.board.node_hexes[n])
    vid = f"v{len(w.villages) + 1}"
    w.villages[vid] = {"id": vid, "node": free, "faction": f, "level": 1, "status": "operational", "age": int(w.age), "name": "Fresh", "founded_ms": int(w.game_ms), "units": [], "history": []}
    return w.villages[vid]


def test_p08_construction_runs_through_the_lifecycle_under_a_bounded_crew_and_nothing_works_before_completion():
    w, step = _running(0)
    v = _fresh_village(w)
    ops = local_ops.ensure(w, v)
    crews = [a for a in ops["agents"].values() if a["kind"] == "builder"]
    assert len(crews) == 1  # a settlement's crew
    seen = {}
    produced_before_complete = False
    for _ in range(1200):
        step(100)
        for s in ops["sites"].values():
            if not s["commissioned"]:
                continue
            seen.setdefault(s["id"], []).append(s["state"])
            if s["state"] in local_ops.CONSTRUCTION and (s.get("produced", 0) > 0 or any(s["out"].values())):
                produced_before_complete = True
        active = [s for s in ops["sites"].values() if s.get("crew")]
        assert len(active) <= 1  # one job at a time per builder
        if all(local_ops.built(s) for s in ops["sites"].values() if s["commissioned"]):
            break
    assert not produced_before_complete
    hub_states = []
    for st in seen[f"{v['id']}:hub"]:
        if not hub_states or hub_states[-1] != st:
            hub_states.append(st)
    assert hub_states[:4] == ["planned", "reserved", "foundation", "building"] or hub_states[:3] == ["reserved", "foundation", "building"]
    assert hub_states[-1] not in local_ops.CONSTRUCTION
    hub = ops["sites"][f"{v['id']}:hub"]
    assert 8000 <= hub["build_ms"] <= 20000
    # workers appear only on completion
    for s in ops["sites"].values():
        if s["kind"] == "producer" and s["commissioned"]:
            assert any(a["site"] == s["id"] for a in ops["agents"].values()) == local_ops.built(s)
    # a city has two crews
    v["level"] = 2
    ops2 = local_ops.ensure(w, v)
    assert sum(1 for a in ops2["agents"].values() if a["kind"] == "builder") == 2
    for hid, rec in v["dev"].items():
        assert rec["cap"] == planner.budget(w.board, v["node"], 2)[hid]
        assert rec["unlocked"] <= rec["cap"]


def test_p09_a_save_mid_build_resumes_the_same_build():
    w, step = _running(0)
    v = _fresh_village(w)
    ops = local_ops.ensure(w, v)
    for _ in range(80):
        step(100)
        if any(s["state"] == "building" for s in ops["sites"].values()):
            break
    building = [s for s in ops["sites"].values() if s["state"] in ("foundation", "building")]
    assert building
    saved = json.loads(json.dumps(w.to_dict()))
    w2 = GodWorld.from_dict(saved)
    v2 = w2.villages[v["id"]]
    ops2 = v2["ops"]
    for s in building:
        s2 = ops2["sites"][s["id"]]
        assert s2["state"] == s["state"] and s2["work_done_ms"] == s["work_done_ms"] and s2["build_ms"] == s["build_ms"]
    assert v2["dev"] == v["dev"]
    seq = [1000]
    for _ in range(300):
        seq[0] += 1
        w.advance(100, seq[0], snapshot=False)
        w2.advance(100, seq[0], snapshot=False)
    for s in building:
        assert ops2["sites"][s["id"]]["state"] == ops["sites"][s["id"]]["state"]
        assert ops2["sites"][s["id"]]["work_done_ms"] == ops["sites"][s["id"]]["work_done_ms"]

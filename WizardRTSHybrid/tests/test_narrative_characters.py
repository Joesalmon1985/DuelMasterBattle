"""A.3: the simulation's own workers, carriers and soldiers as named, talkable characters (one Person per body)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from wizard_rts import magic, narrative, story
from wizard_rts.narrative import characters
from wizard_rts.world import HybridWorld

HERE = Path(__file__).resolve().parents[1]


def step(w, ms=100, n=1):
    for _ in range(n):
        seq = int(w.dmb.clock.get("clock_sequence", 0)) + 1
        w.advance(ms, seq, snapshot=False)


def run_until(w, until, limit_ms=600_000):
    for _ in range(limit_ms // 100):
        step(w)
        if until():
            return
    raise AssertionError("condition not reached")


def new_world():
    w = HybridWorld()
    w.dmb.hazards["catastrophe"]["cubes"][w.hazard_id]["active"] = False
    run_until(w, lambda: len(w.workers) >= 3, 60_000)  # the start spawns its workers a moment in; the layer is enabled after, so only the tests create characters
    narrative.enable(w)
    return w


def red(w, kind):
    return next(i for i, b in w.buildings.items() if b["kind"] == kind and b["faction_name"] == "Red")


def walking_lumberjack(w):
    """Run until a lumberjack has reserved a tree and is on its way to it."""
    run_until(w, lambda: any(r["role"] == "lumberjack" and r["path"] for r in w.workers.values()))
    return next(r for r in w.workers.values() if r["role"] == "lumberjack" and r["path"])


def stand_beside(w, row):
    w.player["tx"], w.player["ty"] = row["tx"], row["ty"]


def test_one_body_one_person_and_the_count_matches_the_links():
    w = new_world()
    wid = sorted(w.workers)[0]
    a = characters.person_for(w, "worker", wid)
    b = characters.person_for(w, "worker", wid)
    assert a == b and a is not None
    cid = sorted(w.carriers)[0]
    uid = sorted(w.units)[0]
    characters.person_for(w, "carrier", cid)
    characters.person_for(w, "unit", uid)
    assert len(w.dmb.people) == len(w.narrative["links"]) == 3
    rec = w.dmb.people[a]
    assert rec["link"]["kind"] == "worker" and rec["link"]["id"] == wid and rec["link"]["building"] == w.workers[wid]["building"]
    assert rec["identity"]["name"] == rec["name"] and rec["affiliation"] == w.workers[wid]["faction_name"]
    assert characters.person_for(w, "worker", "worker:nope") is None


def test_names_are_stable_across_processes_and_independent_of_meeting_order():
    code = ("import sys, json; sys.path[:0]=[%r, %r]\n"
            "from wizard_rts.world import HybridWorld\nfrom wizard_rts import narrative\nfrom wizard_rts.narrative import characters as c\n"
            "w = HybridWorld()\n"
            "for i in range(40): w.advance(100, i + 1, snapshot=False)\n"
            "narrative.enable(w)\n"
            "ids = sorted(w.workers)\n"
            "order = ids[::-1] if %s else ids\n"
            "print(json.dumps({i: w.dmb.people[c.person_for(w, 'worker', i)]['name'] for i in order}, sort_keys=True))\n")
    outs = []
    for hashseed, reverse in (("0", False), ("1", True)):
        env = dict(os.environ, PYTHONHASHSEED=hashseed)
        r = subprocess.run([sys.executable, "-c", code % (str(HERE), str(HERE.parent), reverse)], capture_output=True, text=True, env=env, cwd=HERE, check=True)
        outs.append(json.loads(r.stdout.strip().splitlines()[-1]))
    assert outs[0] == outs[1] and len(outs[0]) >= 3
    assert all(" " in n for n in outs[0].values())


def test_lifecycle_inside_and_working_away():
    w = new_world()
    hut = red(w, "producer")
    idle = next(r for r in w.workers.values() if r["building"] == hut)
    assert (idle["tx"], idle["ty"]) == (w.buildings[hut]["tx"], w.buildings[hut]["ty"]) and not idle["path"]
    pid = characters.person_for(w, "worker", idle["id"])
    assert characters.lifecycle(w, pid) == "inside"
    jack = walking_lumberjack(w)
    pj = characters.person_for(w, "worker", jack["id"])
    assert characters.lifecycle(w, pj) == "working_away"


def test_fire_magic_kills_the_person_and_leaves_a_tombstone():
    w = new_world()
    jack = walking_lumberjack(w)
    pid = characters.person_for(w, "worker", jack["id"])
    step(w, 1000)  # the watcher records where the worker stands
    stand_beside(w, w.workers[jack["id"]])
    assert magic.fire(w, jack["id"])["status"] == "ok"
    assert jack["id"] not in w.workers
    step(w, 1000, 2)
    assert characters.lifecycle(w, pid) == "dead"
    assert pid in w.dmb.tombstones and w.dmb.people[pid]["alive"] is False
    assert any(e["kind"] == "character_died" and e["person"] == pid for e in w.narrative["log"])
    assert not any(e["kind"].startswith("character_") for e in w.events)  # the simulation's event stream is untouched


def test_destroyed_hut_displaces_a_worker_outside_and_kills_one_inside():
    w = new_world()
    jack = walking_lumberjack(w)
    pj = characters.person_for(w, "worker", jack["id"])
    hut = jack["building"]
    step(w, 1000)
    w.damage_building(hut, 10**9, ["structure"], {}, by="test")
    run_until(w, lambda: jack["id"] not in w.workers)
    step(w, 1000, 2)
    assert characters.lifecycle(w, pj) == "displaced"
    assert w.dmb.people[pj]["alive"] and w.dmb.people[pj]["status"] == "displaced"

    w2 = new_world()
    ranger = next(r for r in w2.workers.values() if r["role"] != "lumberjack" and (r["tx"], r["ty"]) == (w2.buildings[r["building"]]["tx"], w2.buildings[r["building"]]["ty"]) and not r["path"])
    pi = characters.person_for(w2, "worker", ranger["id"])
    assert characters.lifecycle(w2, pi) == "inside"
    w2.damage_building(ranger["building"], 10**9, ["structure"], {}, by="test")
    run_until(w2, lambda: ranger["id"] not in w2.workers)
    step(w2, 1000, 2)
    assert characters.lifecycle(w2, pi) == "dead" and pi in w2.dmb.tombstones


def test_the_replacement_worker_is_a_new_person():
    w = new_world()
    jack = walking_lumberjack(w)
    old = characters.person_for(w, "worker", jack["id"])
    step(w, 1000)
    stand_beside(w, w.workers[jack["id"]])
    hut = jack["building"]
    assert magic.fire(w, jack["id"])["status"] == "ok"
    run_until(w, lambda: w.buildings[hut].get("worker_id") not in ("", None, jack["id"]), 300_000)
    new = w.workers[w.buildings[hut]["worker_id"]]
    assert characters.person_for(w, "worker", new["id"]) != old
    assert w.dmb.people[old]["alive"] is False


def test_talk_op_names_the_worker_and_respects_range():
    w = new_world()
    jack = walking_lumberjack(w)
    far = story.dispatch(w, {"op": "talk", "npc": jack["id"]})
    assert far["status"] == "rejected" and far["reason"] == "too_far"
    stand_beside(w, jack)
    r = story.dispatch(w, {"op": "talk", "npc": jack["id"]})
    assert r["status"] == "ok" and r["name"] == w.dmb.people[r["person"]]["name"] and r["name"] in r["lines"][0]
    assert len(r["lines"]) == 2 and r["choices"] == []
    assert story.dispatch(w, {"op": "talk", "npc": "worker:nope"})["reason"] == "no_such_person"
    again = story.dispatch(w, {"op": "talk", "npc": jack["id"]})
    assert again["person"] == r["person"] and again["lines"] == r["lines"]


def test_dead_soldiers_cannot_be_talked_to_and_die_as_persons():
    w = new_world()
    uid = sorted(w.units)[0]
    row = w.units[uid]
    pid = characters.person_for(w, "unit", uid)
    stand_beside(w, row)
    assert magic.fire(w, uid)["status"] == "ok"
    assert story.dispatch(w, {"op": "talk", "npc": uid})["reason"] == "dead"  # the corpse is still a row for a while
    step(w, 1000, 2)
    assert characters.lifecycle(w, pid) == "dead" and pid in w.dmb.tombstones


def test_snapshot_publishes_the_persons_near_the_wizard_and_the_tick_links_them():
    w = new_world()
    jack = walking_lumberjack(w)
    stand_beside(w, jack)
    step(w, 1000, 2)  # the tick creates characters for the bodies near the wizard
    persons = w.snapshot()["story"]["persons"]
    assert jack["id"] in persons and persons[jack["id"]]["name"] == w.dmb.people[persons[jack["id"]]["person_id"]]["name"]
    assert persons[jack["id"]]["has_quest"] is False
    # nobody far from the wizard has a character yet
    far = [i for i, r in w.workers.items() if max(abs(r["tx"] - w.player["tx"]), abs(r["ty"] - w.player["ty"])) > characters.LINK_RADIUS]
    assert all(characters.link_key("worker", i) not in w.narrative["links"] for i in far)


def test_without_the_layer_nothing_is_created():
    w = HybridWorld()
    step(w, 1000, 3)
    assert not w.dmb.people and "narrative" not in w.__dict__ and "persons" not in w.snapshot()["story"]

"""The Forest Dispute: a narrative-only quest played by the settlement's own workers, and the everyday talk of ordinary people."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import _nh as nh
from wizard_rts import magic, story
from wizard_rts.narrative import characters, conversation, graph, occupations, persist, quests, tutorial, wizard

HERE = Path(__file__).resolve().parents[1]
QID = "forest_dispute"


def cast_world(**kw):
    w = nh.world(unlock=True, **kw)
    r = quests.rec(w, QID)
    assert r["status"] == "cast"
    return w, r["bindings"]


def go(w, b):
    nh.stand_by(w, b["kind"], b["id"])
    return b["id"]


def hear_both(w, bind):
    for role in ("cutter", "planter"):
        k = go(w, bind[role])
        nh.talk(w, k)
        nh.pick(w, k, "what_happened")
        nh.end(w, k)


def decide(w, bind, choice):
    k = go(w, bind["witness"])
    nh.talk(w, k)
    nh.pick(w, k, choice)
    nh.end(w, k)


# ------------------------------------------------------------------ who plays it

def test_the_cast_are_existing_simulation_characters_and_nobody_is_created():
    w = nh.world()
    nh.learn(w)
    counts = (len(w.workers), len(w.carriers), len(w.units), len(w.buildings))
    people_before = len(w.dmb.people)
    nh.adv(w, 3)
    assert (len(w.workers), len(w.carriers), len(w.units), len(w.buildings)) == counts
    r = quests.rec(w, QID)
    b = r["bindings"]
    assert w.workers[b["cutter"]["id"]]["role"] == "lumberjack" and b["cutter"]["kind"] == "worker"
    assert w.workers[b["planter"]["id"]]["role"] == "ranger"
    assert b["witness"]["kind"] == "unit" and w.units[b["witness"]["id"]]["kind"] == "soldier"
    for role, bb in b.items():
        assert characters.person_for(w, bb["kind"], bb["id"]) == bb["pid"]  # one Person per body: the quest uses the body's own
        assert w.dmb.people[bb["pid"]]["link"]["id"] == bb["id"] and w.dmb.people[bb["pid"]]["affiliation"] == "Red"
    assert len(w.dmb.people) <= people_before + 3 + 16  # (the teacher, the three, the keeper and the rats, the mother, and whoever the tick linked beside the wizard): no copies of workers
    assert len({bb["pid"] for bb in b.values()}) == 3
    # their ordinary lives go on: the lumberjack still belongs to his hut
    hut = w.workers[b["cutter"]["id"]]["building"]
    assert w.buildings[hut]["worker_ids"]["lumberjack"] == b["cutter"]["id"]


def test_they_look_like_everybody_else():
    w, bind = cast_world()
    nh.adv(w, 1)
    rows = {r["id"]: r for r in w.snapshot()["entities"]}
    for role, b in bind.items():
        row = rows[b["id"]]
        assert row["class"] in ("worker", "unit") and "has_quest" not in row and "hint" not in row  # no marker, no special row
    assert not [r for r in rows.values() if r["class"] == "npc" and r["id"] != tutorial.state(w)["teacher"] and str(r.get("role", "")) not in ("keeper", "pest", "mother", "official", "contestant")]


def test_the_cast_is_deterministic_across_processes_and_stable_through_save_and_load(tmp_path):
    code = ("import sys, json; sys.path[:0]=[%r, %r]\nimport os; os.environ['HYBRID_AI']='0'\nimport _nh as nh\n"
            "w = nh.world(unlock=True)\n"
            "r = __import__('wizard_rts.narrative.quests', fromlist=['x']).rec(w, 'forest_dispute')\n"
            "print(json.dumps({k: [b['id'], w.dmb.people[b['pid']]['name']] for k, b in r['bindings'].items()}, sort_keys=True))\n")
    outs = [subprocess.run([sys.executable, "-c", code % (str(HERE), str(HERE / "tests"))], capture_output=True, text=True, cwd=HERE, check=True,
                           env=dict(os.environ, PYTHONHASHSEED=h)).stdout for h in ("0", "1")]
    assert outs[0] == outs[1] and "cutter" in outs[0]
    w, bind = cast_world()
    hear_both(w, bind)
    persist.save_world(w, tmp_path / "q.pkl")
    loaded, _ = persist.load_world(tmp_path / "q.pkl")
    assert quests.rec(loaded, QID)["bindings"] == quests.rec(w, QID)["bindings"]
    assert quests.status(loaded, QID) == "active" and graph.has(loaded, QID, "heard_cutter") and graph.has(loaded, QID, "heard_planter")
    assert quests.objective(loaded, QID).startswith("You have heard both")


# ------------------------------------------------------------------ playing it

def test_every_branch_of_the_quest_can_be_played_and_ends_in_the_journal():
    expectations = {"say_compromise": ("share", "outcome_compromise", "share the clearing"), "say_cutter": ("timber", "outcome_cutter", "Timber comes first"),
                    "say_planter": ("young", "outcome_planter", "staked"), "say_nothing": ("settle", "outcome_none", "still not speaking")}
    for choice, (_x, flag, note_part) in expectations.items():
        w, bind = cast_world()
        assert quests.status(w, QID) == "offered" and "Hear both sides" in quests.objective(w, QID)
        wit = go(w, bind["witness"])
        r = nh.talk(w, wit)
        assert "say_compromise" not in nh.ids(r)  # not before both sides are heard
        nh.pick(w, wit, "witness_saw")
        nh.end(w, wit)
        assert quests.status(w, QID) == "active"
        hear_both(w, bind)
        assert quests.objective(w, QID).startswith("You have heard both")
        wit = go(w, bind["witness"])
        r = nh.talk(w, wit)
        assert {"say_compromise", "say_cutter", "say_planter", "say_nothing"} <= set(nh.ids(r))
        names = quests.cast_names(w, QID)
        assert names["cutter"] in next(c["text"] for c in r["choices"] if c["id"] == "say_compromise")  # the choice names real people
        nh.pick(w, wit, choice)
        assert graph.has(w, QID, flag)
        r = nh.talk(w, wit)
        assert not {"say_compromise", "say_cutter", "say_planter", "say_nothing"} & set(nh.ids(r))  # decided once
        nh.end(w, wit)
        for role in ("cutter", "planter"):
            k = go(w, bind[role])
            r = nh.talk(w, k)
            assert graph.has(w, QID, "closed_" + role) and any(t for t in r["lines"]), (choice, role)
            nh.end(w, k)
        wit = go(w, bind["witness"])
        r = nh.talk(w, wit)
        assert quests.status(w, QID) == "done" and quests.objective(w, QID) == ""
        notes = wizard.wiz(w)["journal_notes"]
        assert len(notes) == 1 and "The Forest Dispute" in notes[0]["text"] and note_part in notes[0]["text"] and names["cutter"] in notes[0]["text"]
        nh.end(w, wit)


def test_after_the_quest_everyone_is_still_an_ordinary_person_who_remembers():
    w, bind = cast_world()
    hear_both(w, bind)
    decide(w, bind, "say_compromise")
    for role in ("cutter", "planter"):
        k = go(w, bind[role])
        nh.talk(w, k)
        nh.end(w, k)
    wit = go(w, bind["witness"])
    nh.talk(w, wit)
    nh.end(w, wit)
    for role in ("cutter", "planter", "witness"):
        k = go(w, bind[role])
        r = nh.talk(w, k)
        assert any(i.startswith("topic:") for i in nh.ids(r))  # everyday talk is still there
        assert "farewell" in nh.ids(r) or "leave" in nh.ids(r)
        assert any(("Thank you" in l or "over" in l or "settled" in l or "forest" in l or "behind us" in l) for l in r["lines"]), r["lines"]  # and they remember
        nh.end(w, k)


def test_every_choice_that_can_end_a_quest_conversation_ends_it_and_nothing_else_does():
    w, bind = cast_world()
    for role in ("cutter", "planter", "witness"):
        k = go(w, bind[role])
        r = nh.talk(w, k)
        assert r["ends"] is False
        for c in r["choices"]:
            if c["id"] in ("leave", "farewell"):
                continue
            w2, b2 = cast_world()
            k2 = go(w2, b2[role])
            nh.talk(w2, k2)
            out = nh.pick(w2, k2, c["id"])
            assert out["ends"] is False and (out["text"] or out["choices"]), (role, c["id"])
        end_id = "leave" if "leave" in nh.ids(r) else "farewell"
        out = nh.pick(w, k, end_id)
        assert out["ends"] is True and out["choices"] == [] and out["text"]
        nh.end(w, k)
    assert quests.status(w, QID) == "offered"  # saying goodbye changes nothing in the quest


def test_wrong_choices_are_refused_and_change_nothing():
    w, bind = cast_world()
    wit = go(w, bind["witness"])
    nh.talk(w, wit)
    r = story.dispatch(w, {"op": "choose", "npc": wit, "choice": "say_cutter"})
    assert r["status"] == "rejected" and r["reason"] == "choice_unavailable" and not graph.has(w, QID, "outcome_cutter")
    assert story.dispatch(w, {"op": "choose", "npc": wit, "choice": "topic:nope"})["reason"] == "choice_unavailable"


def test_the_quest_changes_nothing_in_the_simulation(monkeypatch):
    """Played from start to finish, the quest writes nothing to the simulation: with the conversation hold switched off (the hold is the one thing a
    conversation does to a body, and it is documented), the world is bit-for-bit the world that nobody talked in."""
    from wizard_rts import hold

    monkeypatch.setattr(hold, "hold", lambda *a, **k: None)
    w, bind = cast_world()
    twin, _ = cast_world()
    hear_both(w, bind)
    decide(w, bind, "say_cutter")
    for role in ("cutter", "planter"):
        nh.talk(w, go(w, bind[role]))
        nh.end(w, bind[role]["id"])
    k = go(w, bind["witness"])
    nh.talk(w, k)
    nh.end(w, k)
    assert quests.status(w, QID) == "done"
    w.player.update(tx=twin.player["tx"], ty=twin.player["ty"])  # (the wizard walked about; that is his, not the simulation's)
    nh.adv(w, 1)
    nh.adv(twin, int(w.dmb.clock["game_ms"] // 1000) - int(twin.dmb.clock["game_ms"] // 1000))
    raw = lambda x: hashlib.sha1(json.dumps({k: getattr(x, k) for k in ("buildings", "stocks", "workers", "carriers", "units", "trees", "rocks", "animals", "stats",
                                                                         "faction_info", "tech")}, sort_keys=True, default=str).encode()).hexdigest()
    assert raw(w) == raw(twin)
    assert w.rng.getstate() == twin.rng.getstate() and w.events.total == twin.events.total


# ------------------------------------------------------------------ when the world changes

def test_a_lost_participant_is_replaced_by_another_worker_not_resurrected():
    w, bind = cast_world()
    cutter = bind["cutter"]
    old_pid, old_name = cutter["pid"], w.dmb.people[cutter["pid"]]["name"]
    hut = w.workers[cutter["id"]]["building"]
    w.player["tx"], w.player["ty"] = w.workers[cutter["id"]]["tx"], w.workers[cutter["id"]]["ty"]
    w._fire_ready_ms = 0
    assert magic.fire(w, cutter["id"])["status"] == "ok"
    nh.adv(w, 2)
    assert w.dmb.people[old_pid]["alive"] is False
    assert quests.status(w, QID) in ("offered", "active")  # still within the grace period
    nh.adv(w, 45)  # the hut sends a new lumberjack
    new = quests.rec(w, QID)["bindings"]["cutter"]
    assert new["id"] != cutter["id"] and w.workers[new["id"]]["role"] == "lumberjack" and w.workers[new["id"]]["building"] == hut
    assert new["pid"] != old_pid and w.dmb.people[old_pid]["alive"] is False  # a different person; the dead stay dead
    assert any(old_name in n["text"] and "taken their side" in n["text"] for n in wizard.wiz(w)["journal_notes"])
    k = go(w, new)
    r = nh.talk(w, k)
    assert w.dmb.people[new["pid"]]["name"] == r["name"] and r["name"] != old_name
    assert quests.cast_names(w, QID)["cutter"] == r["name"]


def test_a_quest_nobody_can_continue_is_interrupted_honestly():
    w, bind = cast_world()
    pl = bind["planter"]
    hut = w.workers[pl["id"]]["building"]
    w.player["tx"], w.player["ty"] = w.workers[pl["id"]]["tx"], w.workers[pl["id"]]["ty"]
    w._fire_ready_ms = 0
    w.damage_building(hut, 10**9, ["structure"], {}, by="test")  # the forester's hut is destroyed: no replacement will ever come
    nh.adv(w, quests.GRACE_MS // 1000 + 10)
    assert quests.status(w, QID) == "interrupted" and "cannot be settled" in quests.objective(w, QID)
    assert any("nobody else can take their place" in n["text"] for n in wizard.wiz(w)["journal_notes"])
    # the others are ordinary people again, and the quest is not offered to anyone else
    k = go(w, bind["cutter"])
    r = nh.talk(w, k)
    assert "what_happened" not in nh.ids(r) and any(i.startswith("topic:") for i in nh.ids(r))
    t = tutorial.state(w)["teacher"]
    tile = w.narrative["residents"][t]["tile"]
    w.player["tx"], w.player["ty"] = tile[0] + 1, tile[1]
    ids = nh.ids(conversation.talk(w, t))
    assert "ask_village" not in ids and "ask_village_none" in ids


def test_without_the_roles_the_quest_is_not_forced_into_the_settlement():
    w = nh.world()
    ranger = nh.find_worker(w, "ranger")
    hut = w.workers[ranger]["building"]
    w.damage_building(hut, 10**9, ["structure"], {}, by="test")
    nh.adv(w, 130)  # the hut burns down and its forester is gone
    nh.learn(w)
    nh.adv(w, 3)
    r = quests.rec(w, QID)
    assert r["status"] == "unavailable" and r["why"] == "planter" and quests.status(w, QID) == "unavailable"
    assert [q for q in quests.snapshot(w) if q["id"] == QID] == []
    t = tutorial.state(w)["teacher"]
    tile = w.narrative["residents"][t]["tile"]
    w.player["tx"], w.player["ty"] = tile[0] + 1, tile[1]
    ids = nh.ids(nh.talk(w, t))
    assert "ask_village_none" in ids and "ask_village" not in ids
    out = nh.pick(w, t, "ask_village_none")
    assert "Come back when you have heard something" in out["text"] and wizard.lesson_done(w, "world")


# ------------------------------------------------------------------ everyday talk

def test_ordinary_people_talk_as_what_they_are_and_only_say_what_is_true():
    w = nh.world()
    jack, ranger, mason = nh.find_worker(w, "lumberjack"), nh.find_worker(w, "ranger"), nh.find_worker(w, "stonemason")
    seen = {}
    for eid in (jack, ranger, mason):
        nh.stand_by(w, "worker", eid)
        r = nh.talk(w, eid)
        seen[eid] = r
        assert r["name"] in r["lines"][0] and r["subtitle"].split(" of ")[0] in ("Lumberjack", "Forester", "Stonemason")
        nh.end(w, eid)
    assert len({tuple(r["lines"]) for r in seen.values()}) == 3  # they do not all sound the same
    uid = sorted(w.units)[0]
    nh.stand_by(w, "unit", uid)
    answers = []
    r = nh.talk(w, uid)
    for c in r["choices"]:
        if c["id"].startswith("topic:"):
            answers.append(nh.pick(w, uid, c["id"])["text"])
    text = " ".join(answers + r["lines"])
    assert "castle" not in text.lower() and "wall" not in text.lower() and "fortress" not in text.lower()
    nh.end(w, uid)
    facts = occupations.facts_for(w, conversation.resolve(w, uid))
    assert facts["has_barracks"] is False
    barr = occupations.topic(w, conversation.resolve(w, uid), {"name": "x", "facts": facts}, "no_barracks")
    assert barr["lines"] == ["No barracks yet. We are few and the settlement is small."]
    assert occupations.topic(w, conversation.resolve(w, uid), {"name": "x", "facts": facts}, "barracks") is None  # it is not claimed


def test_everyday_lines_follow_the_facts_of_the_world():
    w = nh.world()
    jack = nh.find_worker(w, "lumberjack")
    sp = conversation.resolve(w, jack)
    f = occupations.facts_for(w, sp)
    topics = {t["id"] for t in occupations.data()["roles"]["lumberjack"]["topics"] if graph.holds(w, "occupation", t.get("when"), {"facts": f})}
    assert ("forest_thick" in topics) != ("forest_thin" in topics)  # exactly one of the two claims about the forest holds
    assert ("store" in topics) != ("store_empty" in topics)
    assert "strangers" not in topics or f["hostile_near"]
    # make the facts different and the lines follow
    for t in list(w.trees):
        if abs(w.trees[t]["tx"] - sp["tile"][0]) <= occupations.RADIUS and abs(w.trees[t]["ty"] - sp["tile"][1]) <= occupations.RADIUS:
            w.trees.pop(t)
    f2 = occupations.facts_for(w, sp)
    assert f2["trees_big"] == 0 and f2["saplings"] == 0
    assert occupations.topic(w, sp, {"name": "x", "facts": f2}, "forest_thin") and not occupations.topic(w, sp, {"name": "x", "facts": f2}, "forest_thick")
    assert not occupations.topic(w, sp, {"name": "x", "facts": f2}, "young")  # "the young trees" is not said when there are none


def test_repeated_conversations_vary_and_do_not_repeat_the_introduction():
    w = nh.world()
    jack = nh.find_worker(w, "lumberjack")
    nh.stand_by(w, "worker", jack)
    first = nh.talk(w, jack)
    nh.end(w, jack)
    seconds = []
    shown = [set(nh.ids(first))]
    for _ in range(4):
        r = nh.talk(w, jack)
        seconds.append(tuple(r["lines"]))
        shown.append(set(nh.ids(r)))
        nh.end(w, jack)
    assert first["lines"][0] not in [l for s in seconds for l in s]  # the introduction is said once
    assert len({frozenset(s) for s in shown}) > 1  # a different selection of things to ask


# ------------------------------------------------------------------ the content itself

def test_every_line_uses_only_placeholders_that_exist():
    known = {"name", "mentor", "attacker", "faction", "workplace", "settlement", "trees_big", "saplings", "rocks", "animals", "logs", "soldiers", "barracks", "carrying",
             "cutter", "planter", "witness", "cutter_where", "planter_where", "witness_where", "cutter_role", "planter_role", "witness_role",
             "previous", "generation", "idle_minutes", "played_minutes", "visits", "food_left",  # conversation.common_facts (18 Oct 2026)
             "trade", "tribe", "this_village", "home_village", "home_distance", "gate_distance", "gate_compass"}  # occupations.facts_for (tribes, the gate)
    def strings(o):
        if isinstance(o, str):
            yield o
        elif isinstance(o, dict):
            for v in o.values():
                yield from strings(v)
        elif isinstance(o, list):
            for x in o:
                yield from strings(x)
    for name in ("tutorial", "forest_dispute", "occupations", "aftermath", "campaign_scenes"):
        data = json.loads((HERE / "wizard_rts" / "data" / "narrative" / "dialogue" / f"{name}.json").read_text())
        n = 0
        for line in strings(data):
            for ph in re.findall(r"\{(\w+)\}", line):
                assert ph in known, (name, ph, line)
            n += 1
        assert n > 20, name


def test_the_dialogue_data_is_well_formed():
    d = graph.load(QID)
    assert set(d["cast"]) == set(d["speakers"]) == {"cutter", "planter", "witness"}
    for role, sp in d["speakers"].items():
        node = sp["nodes"]["hub"]
        assert node["variants"][-1].get("when") in (None, {}), role  # the last variant is the default: someone always has something to say
        ids = [c["id"] for c in node["choices"]]
        assert len(ids) == len(set(ids)), role
        assert any(c.get("ends") for c in node["choices"]), role  # every speaker has an explicit way out
    t = graph.load("tutorial")["speakers"]["teacher"]["nodes"]["hub"]["choices"]
    assert [c["id"] for c in t if c.get("ends")] == ["farewell"]

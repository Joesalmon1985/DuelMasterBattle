"""The conversation lifecycle and the hold: explicit endings, one person stopped while the world goes on, release on every way out."""
import copy

import pytest

import _nh as nh
from wizard_rts import hold, magic, narrative, story
from wizard_rts.narrative import characters, conversation, duel_lease, persist, wizard


def test_a_conversation_has_a_beginning_responses_and_a_declared_end():
    w = nh.world()
    jack = nh.find_worker(w, "lumberjack")
    nh.stand_by(w, "worker", jack)
    r = nh.talk(w, jack)
    assert r["ends"] is False and r["subtitle"].startswith("Lumberjack") and r["lines"] and "farewell" in nh.ids(r)
    assert jack in conversation.table(w) and "held_until_ms" in w.workers[jack]
    topics = [c for c in nh.ids(r) if c.startswith("topic:")]
    assert 1 <= len(topics) <= 3
    r2 = nh.pick(w, jack, topics[0])
    assert r2["ends"] is False and r2["text"] and topics[0] not in nh.ids(r2)  # an answered question is not offered again in the same conversation
    assert "farewell" in nh.ids(r2)
    r3 = nh.pick(w, jack, "farewell")
    assert r3["ends"] is True and r3["choices"] == [] and r3["text"] == "Goodbye."
    assert jack in conversation.table(w)  # the person is released when the closing line is acknowledged (end_talk), not before it can be read
    assert nh.end(w, jack)["ended"] == 1
    assert jack not in conversation.table(w) and "held_until_ms" not in w.workers[jack]


def test_every_choice_of_the_teacher_either_continues_or_declares_its_end():
    w = nh.world()
    t = w.narrative["tutorial"]["teacher"]
    nh.stand_by_res = None
    tile = w.narrative["residents"][t]["tile"]
    w.player["tx"], w.player["ty"] = tile[0] + 1, tile[1]
    r = nh.talk(w, t)
    assert r["ends"] is False
    r = nh.pick(w, t, "farewell")
    assert r["ends"] is True and r["choices"] == [] and r["text"].startswith("Walk well")
    nh.end(w, t)
    nh.talk(w, t)
    nh.pick(w, t, "learn_colours")  # a continuing choice keeps the conversation open with new choices
    r = nh.talk(w, t)
    assert r["ends"] is False and "told_practice" in nh.ids(r)
    d = nh.pick(w, t, "told_practice")
    assert d["ends"] is True and d["duel_lease"]["status"] == "started" and d["text"].startswith("My Ward is")  # the line is shown, then the board opens
    nh.end(w, t)
    assert duel_lease.abandon(w)["closed"]


def test_the_person_stops_and_everyone_else_keeps_working():
    w = nh.world()
    jack = nh.find_worker(w, "lumberjack")
    # let him get going: he is outside walking or cutting
    for _ in range(120):
        nh.adv(w, 1)
        if w.workers[jack]["path"]:
            break
    assert w.workers[jack]["path"], "fixture: a lumberjack on his way to a tree"
    nh.stand_by(w, "worker", jack)
    here = nh.pos(w, "worker", jack)
    others = {i: (r["tx"], r["ty"], r["status"], r["anim"], r["carrying"]) for i, r in w.workers.items() if i != jack}
    carriers = {i: (r["tx"], r["ty"]) for i, r in w.carriers.items()}
    nh.talk(w, jack)
    row = w.workers[jack]
    assert row["anim"] == "idle" and row["held_prev"]["anim"] in ("walk", "walkload")  # he stands instead of walking on the spot
    for _ in range(10):
        nh.adv(w, 1)
        assert nh.pos(w, "worker", jack) == here and row["path"]  # not a step, and his route is kept
    now_others = {i: (r["tx"], r["ty"], r["status"], r["anim"], r["carrying"]) for i, r in w.workers.items() if i != jack}
    assert now_others != others  # the rest of the world went on
    nh.end(w, jack)
    assert "held_until_ms" not in row and "held_prev" not in row and row["anim"] in ("walk", "walkload", "hack", "idle")
    nh.adv(w, 6)
    assert nh.pos(w, "worker", jack) != here  # he resumes his walk


def test_held_workers_resume_and_the_economy_carries_on():
    from wizard_rts import ledger

    w = nh.world()
    books = ledger.snapshot_totals(w)  # the books as they stand when the talking starts
    jack = nh.find_worker(w, "lumberjack")
    hut = w.workers[jack]["building"]
    start = w.stats.get("made_log", 0)
    for _ in range(30):
        nh.adv(w, 1)
        if w.workers[jack]["path"]:
            break
    nh.stand_by(w, "worker", jack)
    carried = w.workers[jack]["carrying"]
    nh.talk(w, jack)
    nh.adv(w, 25)  # held for a while mid-programme
    assert w.workers[jack]["carrying"] == carried and w.buildings[hut]["worker_ids"]["lumberjack"] == jack  # nothing duplicated, nothing lost, still his hut
    nh.end(w, jack)
    nh.adv(w, 240)
    assert w.stats.get("made_log", 0) > start  # logs are being made again
    assert ledger.check(w, books) == []  # and every ware is still accounted for: none duplicated, none lost
    assert w.workers[jack]["status"] != "held" and "held_until_ms" not in w.workers[jack]
    assert not any(r.get("held_until_ms") for r in w.workers.values())


@pytest.mark.parametrize("kind,finder", [
    ("worker", lambda w: nh.find_worker(w, "ranger")),
    ("carrier", lambda w: sorted(w.carriers)[0]),
    ("unit", lambda w: sorted(w.units)[0]),
    ("worker", lambda w: nh.find_worker(w, "stonemason")),
])
def test_every_kind_of_body_is_held_in_place_and_released(kind, finder):
    w = nh.world()
    eid = finder(w)
    nh.stand_by(w, kind, eid)
    row = nh.body(w, kind, eid)
    pid = characters.person_for(w, kind, eid)
    here = nh.pos(w, kind, eid)
    r = nh.talk(w, eid)
    assert r["person"] == pid and r["name"] == w.dmb.people[pid]["name"]
    nh.adv(w, 15)
    assert nh.pos(w, kind, eid) == here
    nh.end(w, eid)
    assert "held_until_ms" not in row
    assert characters.person_for(w, kind, eid) == pid  # the same person afterwards


def test_a_moving_soldier_keeps_his_order_and_a_fighting_one_is_not_held():
    w = nh.world()
    uid = sorted(w.units)[0]
    u = w.units[uid]
    nh.stand_by(w, "unit", uid)
    u["order"] = {"kind": "move", "tx": u["tx"] + 6, "ty": u["ty"]}
    saved = copy.deepcopy(u["order"])
    nh.talk(w, uid)
    nh.adv(w, 5)
    assert u["order"] == saved and (u["tx"], u["ty"]) == (w.player["tx"] - 1, w.player["ty"])
    nh.end(w, uid)
    u["target"] = "unit:99"
    r = nh.talk(w, uid)
    assert r["ends"] is True and "busy" in r["lines"][0] and "held_until_ms" not in u and uid not in conversation.table(w)


def test_ways_out_of_a_conversation_all_release_the_person():
    w = nh.world()
    jack = nh.find_worker(w, "lumberjack")
    row = w.workers[jack]
    # walking away
    nh.stand_by(w, "worker", jack)
    nh.talk(w, jack)
    w.player["tx"] += 12
    nh.adv(w, 2)
    assert jack not in conversation.table(w) and "held_until_ms" not in row
    # an idle conversation expires (game time), so nobody is stranded by a client that vanished
    nh.stand_by(w, "worker", jack)
    nh.talk(w, jack)
    nh.adv(w, conversation.IDLE_MS // 1000 + 3)
    assert jack not in conversation.table(w) and "held_until_ms" not in row
    # the sim's own failsafe: even with no narrative tick the hold runs out
    nh.stand_by(w, "worker", jack)
    hold.hold(w, row, 2000)
    assert hold.is_held(w, row)
    nh.adv(w, 3)
    assert "held_until_ms" not in row
    # another conversation ends the first
    other = nh.find_worker(w, "ranger")
    nh.stand_by(w, "worker", jack)
    nh.talk(w, jack)
    w.player["tx"], w.player["ty"] = w.workers[other]["tx"] + 1, w.workers[other]["ty"]
    nh.talk(w, other)
    assert jack not in conversation.table(w) and other in conversation.table(w)
    nh.end(w, None)


def test_a_person_who_dies_or_goes_ends_the_conversation_and_the_world_goes_on():
    w = nh.world()
    jack = nh.find_worker(w, "lumberjack")
    hut = w.workers[jack]["building"]
    pid = characters.person_for(w, "worker", jack)
    nh.stand_by(w, "worker", jack)
    nh.talk(w, jack)
    w.player["tx"], w.player["ty"] = w.workers[jack]["tx"], w.workers[jack]["ty"]
    w._fire_ready_ms = 0
    assert magic.fire(w, jack)["status"] == "ok"
    nh.adv(w, 2)
    assert jack not in conversation.table(w) and w.dmb.people[pid]["alive"] is False
    nh.adv(w, 45)
    assert w.buildings[hut]["worker_ids"].get("lumberjack") not in (None, "", jack)  # the hut sends a replacement
    assert story.dispatch(w, {"op": "talk", "npc": jack})["reason"] == "no_such_person"
    # a soldier
    uid = sorted(w.units)[0]
    nh.stand_by(w, "unit", uid)
    nh.talk(w, uid)
    w.player["tx"], w.player["ty"] = w.units[uid]["tx"], w.units[uid]["ty"]
    w._fire_ready_ms = 0
    magic.fire(w, uid)
    nh.adv(w, 2)
    assert uid not in conversation.table(w)


def test_save_and_load_close_conversations_and_clear_every_hold(tmp_path):
    w = nh.world()
    jack = nh.find_worker(w, "lumberjack")
    nh.stand_by(w, "worker", jack)
    nh.talk(w, jack)
    cid = sorted(w.carriers)[0]
    hold.hold(w, w.carriers[cid])
    persist.save_world(w, tmp_path / "c.pkl")
    loaded, _ = persist.load_world(tmp_path / "c.pkl")
    assert not conversation.table(loaded)
    assert not any("held_until_ms" in r for t in (loaded.workers, loaded.carriers, loaded.units) for r in t.values())
    before = {i: (r["tx"], r["ty"]) for i, r in loaded.workers.items()}
    nh.adv(loaded, 40)  # and the loaded world keeps running normally
    assert {i: (r["tx"], r["ty"]) for i, r in loaded.workers.items()} != before


def test_a_lesson_duel_ends_the_conversation_with_the_teacher():
    w = nh.world()
    t = w.narrative["tutorial"]["teacher"]
    tile = w.narrative["residents"][t]["tile"]
    w.player["tx"], w.player["ty"] = tile[0] + 1, tile[1]
    nh.talk(w, t)
    nh.pick(w, t, "learn_colours")
    d = nh.pick(w, t, "told_practice")
    assert d["ends"] and t in conversation.table(w)  # still held while the final line is read
    from test_wizard_duel_lease import play

    rec = d["duel_lease"]["payload"]["duel"]
    out = story.dispatch(w, {"op": "duel_resolve", "duel_id": rec["id"], **play(rec, win=True)})
    assert out["status"] == "resolved" and out["follow_up"]["status"] == "ok"
    assert conversation.table(w)[t]["pid"] == t  # the follow-up is a new conversation with the same person


# ------------------------------------------------------------------ asking someone out of a building

def _someone_inside(w):
    """Advance until some worker of the Red settlement is inside their building (a ranger, stonemason or hunter pause there between jobs)."""
    for _ in range(300):
        for role in ("ranger", "stonemason", "hunter", "lumberjack"):
            wid = nh.find_worker(w, role)
            if characters.lifecycle(w, characters.person_for(w, "worker", wid)) == "inside":
                return wid
        nh.adv(w, 1)
    raise AssertionError("nobody was ever inside")


def test_a_worker_inside_can_be_called_out_and_work_resumes():
    w = nh.world(enable_after=2)
    rid = _someone_inside(w)
    row = w.workers[rid]
    hut = row["building"]
    before_job = (row["program"], row["pc"])
    info = conversation.inspect_building(w, hut)
    me = next(p for p in info["people"] if p["id"] == rid)
    assert me["inside"] is True
    w.player["tx"], w.player["ty"] = w.buildings[hut]["tx"] + 4, w.buildings[hut]["ty"] + 3
    r = story.dispatch(w, {"op": "call_out", "npc": rid})
    assert r["status"] == "coming" and r["steps"] >= 1 and "held_until_ms" in row
    nh.adv(w, 5)
    assert (row["tx"], row["ty"]) == tuple(r["door"])
    assert characters.lifecycle(w, characters.person_for(w, "worker", rid)) != "inside"  # he is out, and drawn
    w.player["tx"], w.player["ty"] = row["tx"] + 1, row["ty"]
    t = nh.talk(w, rid)
    assert t["name"] == me["name"]
    nh.adv(w, 20)
    assert (row["tx"], row["ty"]) == tuple(r["door"])  # he waits at the door while you talk
    nh.end(w, rid)
    assert "held_until_ms" not in row
    start = (w.stats.get("made_log", 0), w.stats.get("planted", 0), w.stats.get("made_granite", 0))
    nh.adv(w, 180)
    assert rid in w.workers and w.workers[rid]["building"] == hut  # still his hut
    assert (w.stats.get("made_log", 0), w.stats.get("planted", 0), w.stats.get("made_granite", 0)) != start or w.workers[rid]["status"] != "idle"  # the economy carried on


def test_call_out_is_refused_when_it_makes_no_sense():
    w = nh.world()
    jack = nh.find_worker(w, "lumberjack")
    for _ in range(60):
        nh.adv(w, 1)
        if w.workers[jack]["path"]:
            break
    assert story.dispatch(w, {"op": "call_out", "npc": jack})["reason"] == "not_inside"  # he is out working
    ranger = nh.find_worker(w, "ranger")
    w.player["tx"], w.player["ty"] = 200, 200
    assert story.dispatch(w, {"op": "call_out", "npc": ranger})["reason"] in ("too_far", "not_inside")

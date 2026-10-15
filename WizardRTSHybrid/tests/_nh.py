"""Shared helpers for the narrative tests: a campaign world with the Wizard Mode layer, stepping, standing beside people, driving the ops."""
from wizard_rts import narrative, story
from wizard_rts.narrative import characters, graph, tutorial, wizard
from wizard_rts.world import HybridWorld

TABLE = {"worker": "workers", "carrier": "carriers", "unit": "units"}


def world(seed=507, unlock=False, enable_after=40):
    """The real campaign world after `enable_after` game seconds (so workers exist and are working), AIs off, narrative on, teacher cast."""
    w = HybridWorld(seed, profile="campaign")
    w.ai_enabled = False
    adv(w, enable_after)
    narrative.enable(w)
    tutorial.start(w)
    if unlock:
        learn(w)
        adv(w, 3)
    return w


def adv(w, seconds, ms=1000):
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(int(seconds * 1000 // ms)):
        w.advance(ms, base + i + 1, snapshot=False)


def learn(w):
    for lesson in ("meet", "colours", "told_ward", "hidden_ward"):
        wizard.complete_lesson(w, lesson)
    wizard.learn(w, [0, 1, 6], 3)


def body(w, kind, eid):
    return getattr(w, TABLE[kind])[eid]


def stand_by(w, kind, eid):
    row = body(w, kind, eid)
    w.player["tx"], w.player["ty"] = row["tx"] + 1, row["ty"]


def pos(w, kind, eid):
    row = body(w, kind, eid)
    return row["tx"], row["ty"]


def talk(w, key):
    r = story.dispatch(w, {"op": "talk", "npc": key})
    assert r["status"] == "ok", r
    return r


def pick(w, key, choice):
    r = story.dispatch(w, {"op": "choose", "npc": key, "choice": choice})
    assert r["status"] == "ok", r
    return r


def end(w, key):
    return story.dispatch(w, {"op": "end_talk", "npc": key})


def ids(reply):
    return [c["id"] for c in reply["choices"]]


def find_worker(w, role, faction="Red"):
    """The (first) worker with this role in the wizard's own settlement (ids sort as strings, so the first id is not necessarily the Red one)."""
    return next(i for i, r in sorted(w.workers.items()) if r["role"] == role and r["faction_name"] == faction)

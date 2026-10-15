"""Helpers that play the opening campaign through the real ops (no client): reach the attack, answer the scenes, fight the lethal duel."""
import _nh as nh
from test_wizard_duel_lease import play
from wizard_rts import story
from wizard_rts.narrative import campaign, residents, tutorial, wizard


def quick(monkeypatch, min_ms=20_000, fallback_ms=60_000, aftermath_fallback_ms=40_000):
    """The exploration and aftermath timings, shortened for tests (they are configuration, `config.json` `campaign`)."""
    monkeypatch.setenv("HYBRID_EXPLORE_MIN_MS", str(min_ms))
    monkeypatch.setenv("HYBRID_EXPLORE_FALLBACK_MS", str(fallback_ms))
    monkeypatch.setenv("HYBRID_AFTERMATH_FALLBACK_MS", str(aftermath_fallback_ms))


def mentor(w):
    return tutorial.state(w)["teacher"]


def finished_training(w):
    """The essential lessons done the way the mentor does them: the spells are learned, the lessons recorded."""
    nh.learn(w)
    nh.adv(w, 2)
    assert campaign.stage(w) == "explore"


def meet_people(w, n=3):
    """Talk (and end) to `n` ordinary people so the exploration counts as real."""
    done = 0
    for kind, table in (("worker", w.workers), ("carrier", w.carriers)):
        for eid, row in sorted(table.items()):
            if row["faction_name"] != "Red" or done >= n:
                continue
            nh.stand_by(w, kind, eid)
            r = story.dispatch(w, {"op": "talk", "npc": eid})
            if r["status"] == "ok":
                nh.end(w, eid)
                done += 1
    return done


def to_arrival(w, contacts=3):
    finished_training(w)
    meet_people(w, contacts)
    for _ in range(400):
        nh.adv(w, 1)
        if campaign.stage(w) == "arrival":
            return
    raise AssertionError("the stranger never arrived: %s" % campaign.explore_due(w))


def walk_in(w):
    """Acknowledge the notice, let the stranger walk in, and wait for the confrontation scene."""
    assert story.dispatch(w, {"op": "scene_next"})["status"] == "ok"
    for _ in range(120):
        nh.adv(w, 1)
        if campaign.active_scene(w):
            return
    raise AssertionError("the confrontation never began")


def through_scene(w, pick=None):
    """Acknowledge every page of the open scene, answering the pages that need an answer with `pick` (a response id, default the first open one)."""
    last = {}
    for _ in range(40):
        v = campaign.scene_view(w)
        if v is None:
            return last
        if v["needs_answer"]:
            cid = next((c["id"] for c in v["choices"] if pick and c["id"].endswith(":" + pick)), None) or v["choices"][0]["id"]
            assert story.dispatch(w, {"op": "scene_choose", "choice": cid})["status"] == "ok"
        last = story.dispatch(w, {"op": "scene_next"})
        assert last["status"] == "ok", last
    raise AssertionError("the scene never ended")


def to_duel(w, pick=None):
    to_arrival(w)
    walk_in(w)
    r = through_scene(w, pick)
    assert "duel_lease" in r and campaign.stage(w) == "duel", r
    return r["duel_lease"]["payload"]["duel"]


def fight(w, rec, win):
    report = play(rec, win=win)
    return story.dispatch(w, {"op": "duel_resolve", "duel_id": rec["id"], **report})


def to_aftermath(w):
    rec = to_duel(w)
    fight(w, rec, True)
    assert campaign.stage(w) == "victory"
    r = through_scene(w)
    assert campaign.stage(w) == "aftermath", r

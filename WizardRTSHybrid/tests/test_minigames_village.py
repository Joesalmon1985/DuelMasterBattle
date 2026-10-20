"""The village minigames in the world (docs/PLAN_VILLAGE_MINIGAMES.md): the games village has every host, a game is offered and played through the
real ops (story.dispatch and MultiplayerSession.dispatch), the host is held while the table is open, nothing in the world changes because of a
game, the table goes with the conversation, a loaded save has no table, and the magic ladder's rung waits for the table to close."""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

import pytest

HYB = Path(__file__).resolve().parents[1]
for entry in (str(HYB), str(HYB.parent), str(HYB / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)
os.environ.setdefault("DMB_NO_NATIVE", "1")

import _nh as nh  # noqa: E402
from _party import Table  # noqa: E402
from wizard_rts import story  # noqa: E402
from wizard_rts.minigames import catalogue, table as game_table  # noqa: E402
from wizard_rts.narrative import campaign, conversation, games_village, residents, tutorial  # noqa: E402
from wizard_rts.net import protocol  # noqa: E402


@pytest.fixture(scope="module")
def village():
    w = nh.world()
    out = games_village.ensure(w)
    assert out["status"] == "ok"
    return w


def stand_by(w, key):
    sp = conversation.resolve(w, key)
    w.player["tx"], w.player["ty"] = sp["tile"][0] + 1, sp["tile"][1]
    return sp


def world_fingerprint(w) -> dict:
    """What a game must never change: every stock, the clock, the behaviour ledger, every relationship, the world's magic."""
    from wizard_rts.narrative import ledger, progression

    return {"stocks": copy.deepcopy(w.stocks), "game_ms": int(w.dmb.clock.get("game_ms", 0)), "ledger": copy.deepcopy(w.narrative.get("ledger", {})),
            "rel": {pid: dict(p.get("relationships", {})) for pid, p in w.dmb.people.items()}, "progression": copy.deepcopy(progression.state(w)),
            "buildings": sorted(w.buildings)}


# ------------------------------------------------------------------ the village

def test_games_village_has_every_host_and_the_early_buildings(village):
    w = village
    kinds = {b["kind"] for b in w.buildings.values() if b["faction_name"] == "Red" and b.get("operational", True)}
    for kind in ("warehouse", "producer", "ranger", "processor", "quarry", "hunter", "well", "farm", "tavern", "bakery", "fisher"):
        assert kind in kinds, kind
    roles = {r["role"] for r in residents.table(w).values() if r["status"] == "present"}
    for role in ("mentor", "mother", "keeper", "sawyer", "water_carrier", "official", "contestant"):
        assert role in roles, role
    assert w.narrative["games_village"] is True
    assert not campaign.explore_due(w)["due"]
    # the extra buildings are joined to the warehouse by road and are operational (their workers come with the economy's own quantum)
    wh = next(b for b in w.buildings.values() if b["faction_name"] == "Red" and b["kind"] == "warehouse")
    for b in w.buildings.values():
        if b["faction_name"] == "Red" and b["kind"] in ("farm", "tavern", "bakery", "fisher"):
            assert b.get("operational", True) and not b.get("constructing")
            assert w.adjacency.get(b["id"]) or b["id"] in w.adjacency.get(wh["id"], {}), b["kind"]
    # every playable game has a host standing in this village
    hosted = set()
    for h in games_village.hosts(w):
        hosted |= set(h["games"])
    for gid in catalogue.ENGINES:
        assert gid in hosted, f"{gid} has no host in the games village"


def test_games_village_is_idempotent(village):
    w = village
    before = (len(residents.table(w)), len(w.buildings))
    games_village.ensure(w)
    assert (len(residents.table(w)), len(w.buildings)) == before


def test_building_panel_names_the_games_played_there(village):
    w = village
    for b in w.buildings.values():
        if b["faction_name"] != "Red":
            continue
        rep = story.dispatch(w, {"op": "inspect_building", "building": b["id"]})
        assert rep["status"] == "ok" and "games" in rep
        for g in rep["games"]:
            assert catalogue.playable(g["id"])


# ------------------------------------------------------------------ playing through the ops

def test_rps_with_the_mentor_through_the_story_ops(village):
    w = village
    mentor = tutorial.state(w)["teacher"]
    sp = stand_by(w, mentor)
    rep = story.dispatch(w, {"op": "talk", "npc": mentor})
    assert rep["status"] == "ok"
    offer = next(c for c in rep["choices"] if c["id"] == "game:rps")
    assert offer["text"] == catalogue.entry("rps")["offer"] and offer["available"]
    rep = story.dispatch(w, {"op": "choose", "npc": mentor, "choice": "game:rps"})
    assert rep["status"] == "ok" and rep["ends"] is True and rep["choices"] == []
    assert rep["text"].startswith("Before a knot")
    mg = rep["minigame"]
    assert mg["status"] == "ok" and mg["game"] == "rps" and mg["npc"] == mentor and mg["view"]["actions"]
    assert mentor in conversation.table(w), "the conversation stays open under the table"
    assert game_table.is_open(w)
    fp = world_fingerprint(w)  # from here to the table's closing, nothing in the world may move (talking itself is a contact, and counted)
    # a stale or wrong action is refused and the table stands
    bad = story.dispatch(w, {"op": "minigame_act", "action": {"id": "sign:9"}})
    assert bad["status"] == "rejected" and bad["reason"] == "illegal" and game_table.is_open(w)
    n = 0
    v = mg["view"]
    while not v["over"] and n < 30:
        rep = story.dispatch(w, {"op": "minigame_act", "action": {"id": v["actions"][n % 3]["id"]}})
        assert rep["status"] == "ok", rep
        v = rep["view"]
        n += 1
    assert v["over"] and v["result"] in ("win", "lose")
    # finished: another move is refused, the table is still there to look at
    assert story.dispatch(w, {"op": "minigame_act", "action": {"id": "sign:0"}})["reason"] == "finished"
    rep = story.dispatch(w, {"op": "minigame_leave"})
    assert rep["status"] == "ok" and rep["finished"] and rep["result"] == v["result"]
    follow = rep["follow_up"]
    assert follow["status"] == "ok" and follow["npc"] == mentor
    assert follow["text"] in catalogue.entry("rps")["lines"][v["result"]]
    again = next(c for c in follow["choices"] if c["id"] == "game:rps")
    assert again["text"] == catalogue.entry("rps")["lines"]["again"]
    assert not game_table.is_open(w) and mentor in conversation.table(w)
    # nothing in the world moved because of the game
    assert world_fingerprint(w) == fp
    kinds = [e["kind"] for e in w.narrative["log"][-6:]]
    assert "minigame_played" in kinds
    j = tutorial.snapshot(w)["games"]
    assert j["found"][0]["id"] == "rps" and j["played"][-1]["result"] == v["result"]
    story.dispatch(w, {"op": "end_talk", "npc": mentor})
    assert mentor not in conversation.table(w)


def test_leaving_the_table_early_is_a_quit(village):
    w = village
    mentor = tutorial.state(w)["teacher"]
    stand_by(w, mentor)
    story.dispatch(w, {"op": "talk", "npc": mentor})
    rep = story.dispatch(w, {"op": "choose", "npc": mentor, "choice": "game:rps"})
    assert rep["minigame"]["status"] == "ok"
    story.dispatch(w, {"op": "minigame_act", "action": {"id": "sign:0"}})
    rep = story.dispatch(w, {"op": "minigame_leave"})
    assert rep["status"] == "ok" and not rep["finished"] and rep["result"] == ""
    assert rep["follow_up"]["text"] in catalogue.entry("rps")["lines"]["quit"]
    assert w.narrative["log"][-2]["kind"] == "minigame_abandoned" or any(e["kind"] == "minigame_abandoned" for e in w.narrative["log"][-4:])
    story.dispatch(w, {"op": "end_talk", "npc": mentor})


def test_the_table_goes_with_the_conversation(village):
    w = village
    mentor = tutorial.state(w)["teacher"]
    stand_by(w, mentor)
    story.dispatch(w, {"op": "talk", "npc": mentor})
    story.dispatch(w, {"op": "choose", "npc": mentor, "choice": "game:rps"})
    assert game_table.is_open(w)
    # walking away ends the conversation: the table is cleared with it, and the host's closing line has nobody to hear it
    w.player["tx"] += 12
    conversation.tick(w)
    assert mentor not in conversation.table(w)
    assert not game_table.is_open(w)
    assert story.dispatch(w, {"op": "minigame_leave"})["reason"] == "no_table"
    assert story.dispatch(w, {"op": "minigame_view"})["reason"] == "no_table"


def test_a_table_is_not_idle_and_a_load_drops_it(village):
    w = village
    mentor = tutorial.state(w)["teacher"]
    stand_by(w, mentor)
    story.dispatch(w, {"op": "talk", "npc": mentor})
    story.dispatch(w, {"op": "choose", "npc": mentor, "choice": "game:rps"})
    conv = conversation.table(w)[mentor]
    conv["last_ms"] = conversation.now(w) - conversation.IDLE_MS - 5000  # long untouched, but a table is on it
    conversation.tick(w)
    assert mentor in conversation.table(w) and game_table.is_open(w)
    conversation.close_all(w, "loaded")
    assert not game_table.is_open(w)


def test_protocol_and_story_register_the_ops():
    for op in ("minigame_act", "minigame_leave", "minigame_view"):
        assert op in protocol.PLAYER_OPS and op in protocol.PASSTHROUGH_OPS and op in story.WIZARD_OPS


# ------------------------------------------------------------------ the session

def test_session_plays_a_game_and_the_rung_waits_for_the_table():
    from wizard_rts.narrative import progression

    t = Table(humans=1, ai=0, seed=507)
    games_village.ensure(t.world)
    h = t.people[0]
    t.advance(2)
    mentor = t.mentor
    h.stand_by_resident(mentor)
    rep = h.op("talk", npc=mentor)
    assert rep["status"] == "ok", rep
    rep = h.op("choose", npc=mentor, choice="game:rps")
    assert rep["status"] == "ok" and rep["minigame"]["status"] == "ok", rep
    assert h.op("minigame_view")["status"] == "ok"
    # a rung that falls due now is told only when the table closes (the owner's default: a table is a board)
    progression.state(t.world)["pending"][str(h.id)] = {"id": "light", "rung": 1, "by": "duels", "gain": "Light"}
    before = len([n for n in h.state()["notices"] if n["kind"] == "rung"])
    t.advance(1)
    assert len([n for n in h.state()["notices"] if n["kind"] == "rung"]) == before, "the rung interrupted a game on the table"
    v = rep["minigame"]["view"]
    n = 0
    while not v["over"] and n < 30:
        r = h.op("minigame_act", action={"id": v["actions"][n % 3]["id"]})
        assert r["status"] == "ok", r
        v = r["view"]
        n += 1
    r = h.op("minigame_leave")
    assert r["status"] == "ok" and r["finished"] and r["follow_up"]["status"] == "ok"
    t.advance(1)
    assert len([n for n in h.state()["notices"] if n["kind"] == "rung"]) > before, "the rung should come once the table is closed"


def test_session_refuses_a_move_without_a_table_or_when_dead():
    from wizard_rts.narrative import mortality

    t = Table(humans=1, ai=0, seed=507)
    games_village.ensure(t.world)
    h = t.people[0]
    t.advance(1)
    assert h.op("minigame_act", action={"id": "x"})["reason"] == "no_table"
    with t.session.acting(h.link):
        mortality.die(t.world, h.id, "test")
    assert mortality.is_dead(t.world, h.id)
    assert h.op("minigame_act", action={"id": "x"})["reason"] == "dead"

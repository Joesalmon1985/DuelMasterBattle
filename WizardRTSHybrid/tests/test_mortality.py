"""Mortal apprentices (plan M1): a duel between apprentices is to the death, the body stays, the survivor resurrects by standing beside it, the
mother grounds a killer inside the village, Mira has to be provoked and brings a dead friend back, and the session ends only when no human is left.

Everything is driven through the real `MultiplayerSession` (the messages a phone sends), with a clock the test advances (`tests/_party.py`)."""
from __future__ import annotations

import pytest
from _party import Table

from wizard_rts.narrative import ledger, mortality, mother, party, residents, wizard

WARD = [0, 1, 3]
OTHER = [1, 3, 0]


def beside(t: Table, a, b) -> None:
    """Put `a` on a free tile next to `b`."""
    p = b.pose
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        tile = (int(p["tx"]) + dx, int(p["ty"]) + dy)
        if tile not in t.world.blocked and not t.world.solid_for_wizard(tile) and t.world.tile_in_map(*tile):
            a.pose["tx"], a.pose["ty"] = tile
            return
    raise AssertionError("no free tile beside the other wizard")


def duel_to_the_death(t: Table, winner, loser, loser_ward=WARD) -> dict:
    """`winner` challenges `loser`, both lock a Ward, `winner` breaks the loser's Ward with one cast."""
    beside(t, winner, loser)
    r = winner.op("pvp_challenge", target=loser.id)
    assert r["status"] == "ok", r
    assert loser.op("pvp_respond", duel_id=r["duel_id"], accept=True)["status"] == "ok"
    assert winner.op("pvp_ward", ward=OTHER)["status"] == "ok"
    assert loser.op("pvp_ward", ward=list(loser_ward))["status"] == "ok"
    assert not t.world.dmb.clock.get("pause_tokens"), "a duel never stops the world in Wizard World"
    cast = winner.op("pvp_cast", attack=list(loser_ward), cast_seq=1)
    assert cast["status"] == "ok" and cast["broken"], cast
    winner.op("pvp_leave")
    loser.op("pvp_leave")
    return cast


def body_row(t: Table, h):
    pid = mortality.body_of(t.world, h.id)
    assert pid, "a dead wizard leaves a body"
    return pid, residents.table(t.world)[pid]


def test_the_loser_of_a_duel_dies_and_leaves_a_body_and_cannot_act():
    t = Table(humans=2)
    joe, ann = t.people
    duel_to_the_death(t, joe, ann)
    assert mortality.is_dead(t.world, ann.id) and not mortality.is_dead(t.world, joe.id)
    pid, body = body_row(t, ann)
    assert body["status"] == "dead" and body["role"] == "body" and tuple(body["tile"]) == (ann.pose["tx"], ann.pose["ty"])
    rows = [e for e in t.world.snapshot()["entities"] if e.get("id") == pid]
    assert rows and rows[0]["dead"] and rows[0]["body"] and rows[0]["seat"] == ann.id and rows[0]["label"] == "Ann"
    for op in ({"op": "move", "seq": 1, "tx": ann.pose["tx"] + 1, "ty": ann.pose["ty"], "facing": "right"}, {"op": "talk", "npc": t.mentor},
               {"op": "pvp_challenge", "target": joe.id}, {"op": "fire", "target": "x"}, {"op": "resurrect", "target": joe.id}):
        assert ann.op(**op)["reason"] == "dead", op
    view = ann.state()
    assert view["you_dead"]["cause"] == "duel" and view["you_dead"]["by"] == joe.id and view["you_dead"]["body"] == pid
    me = next(p for p in view["snapshot"]["players"] if p["you"])
    assert me["dead"] and me["body"] == pid
    assert joe.op("pvp_challenge", target=ann.id)["reason"] == "target_dead"
    assert ledger.count(t.world, "kills", joe.id) == 1 and ledger.count(t.world, "deaths", ann.id) == 1
    assert t.session.ending is None, "one human is alive: the game goes on"
    assert ann.op("state")["status"] == "ok", "the dead spectate"


def test_resurrection_is_a_channel_beside_the_body_that_brings_everything_back():
    t = Table(humans=2)
    joe, ann = t.people
    with ann.seat_state():
        wizard.learn(t.world, [0, 1, 6], 3)
        wizard.learn_fact(t.world, "something")
    duel_to_the_death(t, joe, ann)
    pid, body = body_row(t, ann)
    joe.pose["tx"], joe.pose["ty"] = body["tile"][0] + 40, body["tile"][1]
    assert joe.op("resurrect", target=ann.id)["reason"] == "too_far"
    joe.pose["tx"], joe.pose["ty"] = body["tile"][0] + 1, body["tile"][1]
    r = joe.op("resurrect", target=pid)  # by the body's id or by the seat: both work
    assert r["status"] == "started" and r["ms"] == mortality.resurrect_ms(), r
    assert joe.op("resurrect", target=ann.id)["reason"] == "already_channelling"
    assert joe.state()["resurrection"]["target"] == ann.id
    t.advance(mortality.resurrect_ms() / 1000.0 + 1.5)
    assert not mortality.is_dead(t.world, ann.id)
    assert pid not in residents.table(t.world) and pid not in t.world.dmb.people
    assert (ann.pose["tx"], ann.pose["ty"]) == tuple(body["tile"]), "she stands where her body lay"
    with ann.seat_state():
        assert wizard.spells(t.world) == [0, 1, 6] and wizard.knows_fact(t.world, "something") and wizard.wiz(t.world)["resurrections"] == 1
    assert ann.op("move", seq=1, tx=ann.pose["tx"], ty=ann.pose["ty"], facing="up")["status"] == "ok", "alive again"
    assert ledger.count(t.world, "resurrections", joe.id) == 1
    kinds = [n["kind"] for n in ann.state()["notices"]] + [n["kind"] for n in joe.state()["notices"]]
    assert "wizard_resurrected" in kinds


def test_walking_away_abandons_the_channel():
    t = Table(humans=2)
    joe, ann = t.people
    duel_to_the_death(t, joe, ann)
    pid, body = body_row(t, ann)
    joe.pose["tx"], joe.pose["ty"] = body["tile"][0] + 1, body["tile"][1]
    assert joe.op("resurrect", target=ann.id)["status"] == "started"
    t.advance(2)
    joe.pose["tx"], joe.pose["ty"] = body["tile"][0] + 6, body["tile"][1]
    t.advance(mortality.resurrect_ms() / 1000.0 + 2)
    assert mortality.is_dead(t.world, ann.id) and mortality.channel_of(t.world, joe.id) is None


def test_the_mother_grounds_a_killer_inside_the_village_until_the_friend_lives():
    t = Table(humans=2)
    joe, ann = t.people
    assert mother.pid_of(t.world, joe.id) and mother.pid_of(t.world, ann.id), "every apprentice has a mother in the village"
    assert mother.pid_of(t.world, joe.id) != mother.pid_of(t.world, ann.id)
    duel_to_the_death(t, joe, ann)
    assert mother.is_grounded(t.world, joe.id) and not mother.is_grounded(t.world, ann.id)
    assert joe.state()["grounded"] is True
    home = mother.home_tile(t.world)
    # a step that leaves the home territory is refused in her words; steps inside it are not
    r = int(mother.config.get("mortality", "home_radius", 20))
    joe.pose["tx"], joe.pose["ty"] = home[0] + r, home[1]
    refused = joe.op("move", seq=1, tx=home[0] + r + 1, ty=home[1], facing="right")
    assert refused["reason"] == "grounded" and refused["line"] and refused["name"], refused
    assert (joe.pose["tx"], joe.pose["ty"]) == (home[0] + r, home[1])
    inside = joe.op("move", seq=2, tx=home[0] + r - 1, ty=home[1], facing="left")
    assert inside["status"] in ("ok", "rejected") and inside.get("reason") != "grounded"
    # she walks up to him and has words (a conversation she opens, pushed as a notice)
    mum = mother.pid_of(t.world, joe.id)
    for _ in range(90):
        t.advance(1)
        notices = [n for n in joe.state()["notices"] if n["kind"] == "conversation"]
        if notices:
            break
    else:
        raise AssertionError("the mother never came to have words")
    n = notices[0]
    assert n["npc"] == mum and "put them back" in " ".join(n["reply"]["lines"]).lower()
    ids = [c["id"] for c in n["reply"]["choices"]]
    assert "protest" in ids and "will_do" in ids
    reply = joe.op("choose", npc=mum, choice="protest")
    assert "Resurrect them" in reply["text"] and ledger.count(t.world, "protests", joe.id) == 1
    assert joe.op("choose", npc=mum, choice="will_do")["ends"]
    # once Ann lives the grounding lifts
    pid, body = body_row(t, ann)
    joe.pose["tx"], joe.pose["ty"] = body["tile"][0] + 1, body["tile"][1]
    assert joe.op("resurrect", target=ann.id)["status"] == "started"
    t.advance(mortality.resurrect_ms() / 1000.0 + 1.5)
    assert not mother.is_grounded(t.world, joe.id)
    joe.pose["tx"], joe.pose["ty"] = home[0] + r, home[1]
    assert joe.op("move", seq=3, tx=home[0] + r + 1, ty=home[1], facing="right").get("reason") != "grounded"
    again = joe.op("talk", npc=mum) if abs(joe.pose["tx"] - residents.table(t.world)[mum]["tile"][0]) + abs(joe.pose["ty"] - residents.table(t.world)[mum]["tile"][1]) <= 3 else None
    if again and again["status"] == "ok":
        assert "Was that so hard" in " ".join(again["lines"])


def test_the_mother_escalates_on_the_second_killing():
    t = Table(humans=2)
    joe, ann = t.people
    for n in (1, 2):
        duel_to_the_death(t, joe, ann)
        mum = mother.pid_of(t.world, joe.id)
        joe.pose["tx"], joe.pose["ty"] = residents.table(t.world)[mum]["tile"][0] + 1, residents.table(t.world)[mum]["tile"][1]
        reply = joe.op("talk", npc=mum)
        assert reply["status"] == "ok", reply
        text = " ".join(reply["lines"])
        assert ("Again?" in text) == (n == 2), text
        joe.op("end_talk", npc=mum)
        pid, body = body_row(t, ann)
        joe.pose["tx"], joe.pose["ty"] = body["tile"][0] + 1, body["tile"][1]
        assert joe.op("resurrect", target=ann.id)["status"] == "started"
        t.advance(mortality.resurrect_ms() / 1000.0 + 1.5)
        assert not mortality.is_dead(t.world, ann.id)


def test_a_killing_outside_the_village_does_not_ground():
    t = Table(humans=2)
    joe, ann = t.people
    home = mother.home_tile(t.world)
    r = int(mother.config.get("mortality", "home_radius", 20))
    ann.pose["tx"], ann.pose["ty"] = home[0] + r + 6, home[1]
    duel_to_the_death(t, joe, ann)
    assert mortality.is_dead(t.world, ann.id) and not mother.is_grounded(t.world, joe.id)


def test_both_dead_ends_the_shared_session_and_the_world_is_saved(tmp_path, monkeypatch):
    monkeypatch.setenv("DMB_RUNS", str(tmp_path))
    t = Table(humans=2)
    joe, ann = t.people
    duel_to_the_death(t, joe, ann)
    # Joe cannot resurrect himself; a second death through the stranger's lethal lease would do, but here Ann comes back and kills Joe
    pid, body = body_row(t, ann)
    joe.pose["tx"], joe.pose["ty"] = body["tile"][0] + 1, body["tile"][1]
    assert joe.op("resurrect", target=ann.id)["status"] == "started"
    t.advance(mortality.resurrect_ms() / 1000.0 + 1.5)
    duel_to_the_death(t, ann, joe)
    assert mortality.is_dead(t.world, joe.id) and t.session.ending is None
    # Ann dies too (she has nobody to bring her back): the stranger's lease path is one way; here mortality.die stands for any lethal end
    mortality.die(t.world, ann.id, "trap", terminal=False)
    t.session.tick(t.now)
    assert t.session.ending and t.session.ending["kind"] == "all_dead"
    assert ann.op("move", seq=9, tx=ann.pose["tx"], ty=ann.pose["ty"], facing="up")["reason"] == "ending"
    view = ann.state()
    assert view["status"] == "ok" and view["ending"]["kind"] == "all_dead"
    assert mortality.fate_of(t.world, joe.id)["terminal"] and mortality.fate_of(t.world, ann.id)["terminal"]
    # the world with its two bodies is a valid save
    from wizard_rts.narrative import persist

    out = persist.save_world(t.world, tmp_path / "ended.pkl")
    loaded, _info = persist.load_world(out["path"])
    assert len(loaded.narrative["mortality"]["bodies"]) == 2 and loaded.narrative["campaign"]["stage"] != "game_over"


def test_a_private_session_ends_when_its_human_dies_and_the_host_saves(tmp_path, monkeypatch):
    monkeypatch.setenv("DMB_RUNS", str(tmp_path))
    t = Table(humans=1, ai=1)
    joe = t.people[0]
    (ai,) = t.session.ais.values()
    mortality.die(t.world, joe.id, "duel", by=ai.link.id, terminal=False)
    t.session.tick(t.now)
    assert t.session.ending["kind"] == "human_dead"
    handled = []
    t.session.on_ending = lambda s: handled.append(s.ending["kind"])
    t.advance(t.session.ending_grace_s + 1)
    assert handled == ["human_dead"]
    assert not mortality.is_dead(t.world, ai.link.id), "Mira lives on in the world"


def test_mira_declines_until_provoked_then_fights_seriously():
    t = Table(humans=1, ai=1)
    joe = t.people[0]
    (ai,) = t.session.ais.values()
    beside(t, joe, type("P", (), {"pose": t.world.players[ai.link.id]})())
    declines = 0
    mira_p = type("P", (), {"pose": t.world.players[ai.link.id]})()
    for n in range(3):
        beside(t, joe, mira_p)  # she keeps company and may have shifted her weight a tile while she answered
        r = joe.op("pvp_challenge", target=ai.link.id)
        assert r["status"] == "ok", r
        t.advance(5)
        if joe.link.duel_id and t.session.duels.get(joe.link.duel_id) and t.session.duels[joe.link.duel_id].state != "finished":
            break
        declines += 1
        notices = [x for x in joe.state()["notices"] if x["kind"] == "ai_says"]
        assert any(x["line"] == "decline" for x in notices), notices
    assert declines == 2, "two declines, then the duel"
    assert ledger.count(t.world, "provocations", joe.id) == 2
    duel = t.session.duels[joe.link.duel_id]
    assert duel.state == "setup"
    assert any(x["line"] == "provoked" for x in joe.state()["notices"] if x["kind"] == "ai_says")


def test_mira_killed_by_the_human_is_resurrected_and_remembers_it():
    t = Table(humans=1, ai=1)
    joe = t.people[0]
    (ai,) = t.session.ais.values()
    mira = type("P", (), {"pose": t.world.players[ai.link.id], "id": ai.link.id})()
    beside(t, joe, mira)
    for _ in range(2):
        beside(t, joe, mira)
        assert joe.op("pvp_challenge", target=ai.link.id)["status"] == "ok"
        t.advance(5)
    beside(t, joe, mira)
    r = joe.op("pvp_challenge", target=ai.link.id)
    assert r["status"] == "ok"
    t.advance(5)
    duel = t.session.duels[joe.link.duel_id]
    assert joe.op("pvp_ward", ward=OTHER)["status"] == "ok"
    t.advance(6)
    assert duel.state == "active"
    mira_ward = duel.wards[ai.link.id]
    cast = joe.op("pvp_cast", attack=list(mira_ward), cast_seq=1)
    assert cast["broken"]
    joe.op("pvp_leave")
    t.advance(4)
    assert mortality.is_dead(t.world, ai.link.id) and mother.is_grounded(t.world, joe.id), "killing Mira in the village grounds the human too"
    before = ai.relationship(joe.id)
    pid, body = body_row(t, mira)
    joe.pose["tx"], joe.pose["ty"] = body["tile"][0] + 1, body["tile"][1]
    assert joe.op("resurrect", target=ai.link.id)["status"] == "started"
    t.advance(mortality.resurrect_ms() / 1000.0 + 2)
    assert not mortality.is_dead(t.world, ai.link.id) and not mother.is_grounded(t.world, joe.id)
    t.advance(1)
    assert any(x["line"] == "i_died" for x in joe.state()["notices"] if x["kind"] == "ai_says")
    assert ai.relationship(joe.id) == before + int(ai.c["resurrected_relationship"])


def test_mira_walks_to_a_dead_friend_and_brings_them_back_when_the_game_goes_on():
    """In a shared world (two humans) Mira does not exist; this stands in for any AI wizard with a dead human beside it: the session is told not to
    end (as a world with another living human would not), and Mira walks over and channels."""
    t = Table(humans=1, ai=1)
    joe = t.people[0]
    (ai,) = t.session.ais.values()
    t.session._check_ending = lambda now: None  # another human is alive somewhere: the game goes on
    mortality.die(t.world, joe.id, "trap", terminal=False)
    for _ in range(120):
        t.advance(1)
        if not mortality.is_dead(t.world, joe.id):
            break
    assert not mortality.is_dead(t.world, joe.id), "Mira brought Joe back"
    lines = [x["line"] for x in joe.state()["notices"] if x["kind"] == "ai_says"]
    assert "resurrecting" in lines and "resurrected_you" in lines


def test_a_blocked_body_is_moved_to_a_free_tile():
    t = Table(humans=2)
    joe, ann = t.people
    duel_to_the_death(t, joe, ann)
    pid, body = body_row(t, ann)
    t.world.blocked.add(tuple(body["tile"]))
    t.advance(6)
    assert tuple(residents.table(t.world)[pid]["tile"]) not in t.world.blocked


def test_a_forfeit_by_choice_is_a_death_but_a_lost_connection_is_not():
    t = Table(humans=2)
    joe, ann = t.people
    beside(t, joe, ann)
    r = joe.op("pvp_challenge", target=ann.id)
    assert ann.op("pvp_respond", duel_id=r["duel_id"], accept=True)["status"] == "ok"
    assert ann.op("pvp_forfeit")["status"] == "ok"
    assert mortality.is_dead(t.world, ann.id)
    joe.op("pvp_leave")
    ann.op("pvp_leave")
    pid, body = body_row(t, ann)
    joe.pose["tx"], joe.pose["ty"] = body["tile"][0] + 1, body["tile"][1]
    assert joe.op("resurrect", target=ann.id)["status"] == "started"
    t.advance(mortality.resurrect_ms() / 1000.0 + 1.5)
    beside(t, joe, ann)
    r = joe.op("pvp_challenge", target=ann.id)
    assert ann.op("pvp_respond", duel_id=r["duel_id"], accept=True)["status"] == "ok"
    ann.drop()
    t.advance(t.session.disconnect_grace_s + 1)
    duel = t.session.duels[joe.link.duel_id]
    assert duel.state == "finished" and duel.reason == "disconnected"
    assert not mortality.is_dead(t.world, ann.id), "bad Wi-Fi is not cowardice"


def test_narrative_off_worlds_are_untouched():
    """A world without the narrative layer (training, the harness) has none of this."""
    from wizard_rts.net.host import new_world

    w = new_world(507, "small", "campaign", wizard=False)
    assert "narrative" not in w.__dict__
    assert mortality.is_dead(w, "p1") is False and ledger.count(w, "kills") == 0 and mother.is_grounded(w, "p1") is False


# ---------------------------------------------------------------- four colours between players (17 Oct 2026)

def test_a_duel_has_three_colours_for_the_first_three_duels_and_four_from_the_fourth():
    t = Table(humans=2)
    joe, ann = t.people
    seen = []
    for n in range(5):
        for h in (joe, ann):
            h.op("pvp_leave")
            if mortality.is_dead(t.world, h.id):
                with party.as_player(t.world, h.id):
                    pass
        # a fresh pair of the living: bring the dead back by the game's own channel, then challenge
        for dead in (joe, ann):
            if mortality.is_dead(t.world, dead.id):
                other = ann if dead is joe else joe
                beside(t, other, dead)
                assert other.op("resurrect", target=dead.id)["status"] == "started"
                t.advance(mortality.resurrect_ms() / 1000.0 + 1.5)
        beside(t, joe, ann)
        r = joe.op("pvp_challenge", target=ann.id)
        assert r["status"] == "ok", (n, r)
        seen.append((r["format"]["colours"], r["format"]["slots"]))
        assert ann.op("pvp_respond", duel_id=r["duel_id"], accept=True)["status"] == "ok"
        view = joe.op("state")["duel"]
        assert len(view["format"]["pool"]) == r["format"]["colours"], "the board is told which colours"
        assert joe.op("pvp_ward", ward=[view["format"]["pool"][0]] * 3)["status"] == "ok"
        assert ann.op("pvp_ward", ward=[view["format"]["pool"][-1]] * 3)["status"] == "ok"
        cast = joe.op("pvp_cast", attack=[view["format"]["pool"][-1]] * 3, cast_seq=1)
        assert cast["broken"]
        joe.op("pvp_leave")
        ann.op("pvp_leave")
    assert seen == [(3, 3), (3, 3), (3, 3), (4, 3), (4, 3)], seen
    r = joe.op("pvp_ward", ward=[0, 0, 0])  # (the duel is over: nothing more to set)
    assert r["status"] == "rejected"


def test_a_named_format_is_still_as_named_and_a_world_without_counts_stays_at_three():
    from wizard_rts.net import pvp

    assert pvp.make_format("three", 99)["colours"] == 3
    assert pvp.make_format(None, 99)["colours"] == 4 and pvp.make_format("auto", 3)["colours"] == 4 and pvp.make_format("auto", 2)["colours"] == 3
    assert pvp.make_format(None, None)["colours"] == 3 and pvp.make_format("classic", 0)["colours"] == 6
    assert pvp.make_format(None, 5)["pool"] == [0, 1, 3, 4]

"""The AI wizard: a participant that uses the same actions and the same duel interface as a human, and stands in for the missing second wizard of a
single-player game. Nothing here pokes the AI; the tests act as the human and watch what the AI does through the session."""
from __future__ import annotations

import _campaign as camp
import pytest
from _party import Table

from wizard_rts.narrative import campaign, party, wizard
from wizard_rts.net import ai_wizard


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    camp.quick(monkeypatch, min_ms=20_000, fallback_ms=60_000, aftermath_fallback_ms=40_000)


def solo() -> Table:
    t = Table(humans=1, ai=1)
    t.advance(1)
    return t


def ai_of(t: Table):
    (ai,) = t.session.ais.values()
    return ai


def walk(t: Table, human, steps: int) -> None:
    """Walk the human away across open ground: keep the heading while it works, otherwise turn to a way that does."""
    heading = (1, 0)
    names = {(1, 0): "right", (-1, 0): "left", (0, 1): "down", (0, -1): "up"}
    for _ in range(steps):
        for d in [heading] + [x for x in names if x != heading]:
            p = human.pose
            human.seq += 1
            r = human.op("move", seq=human.seq, tx=p["tx"] + d[0], ty=p["ty"] + d[1], facing=names[d])
            if r["status"] == "ok":
                heading = d
                break
        t.advance(0.25)


def bring_together(t: Table, human, ai) -> None:
    """Put the human next to the AI (the way a player would walk up to somebody)."""
    a = t.world.players[ai.link.id]
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        tile = (int(a["tx"]) + dx, int(a["ty"]) + dy)
        if tile not in t.world.blocked and not t.world.solid_for_wizard(tile) and t.world.tile_in_map(*tile):
            human.pose["tx"], human.pose["ty"] = tile
            return
    raise AssertionError("no tile beside the AI wizard")


def challenge(t: Table, human, ai) -> dict:
    return human.op("pvp_challenge", target=ai.link.id)


def accept_and_lock(t: Table, human, ai, ward=(0, 1, 6)):
    """She declines the first challenges (`accept_after_challenges`); a human who keeps asking gets the duel."""
    for _ in range(1 + int(ai.c.get("accept_after_challenges", 0))):
        r = challenge(t, human, ai)
        assert r["status"] == "ok", r
        t.advance(5)  # a person takes a moment to answer
        if human.link.duel_id and human.link.duel_id in t.session.duels:
            break
    duel = t.session.duels[human.link.duel_id]
    assert duel.state == "setup", "the AI accepted"
    assert human.op("pvp_ward", ward=list(ward))["status"] == "ok"
    t.advance(6)
    assert duel.state == "active", "and locked a Ward of its own"
    return duel


# ------------------------------------------------------------------ presence and company

def test_a_single_player_game_has_one_ai_companion_who_is_a_participant_not_a_prop():
    t = solo()
    ai = ai_of(t)
    joe = t.people[0]
    assert len(t.session.links) == 2 and ai.link.ai and ai.link.id in t.world.players and t.world.players[ai.link.id]["ai"] is True
    assert party.seats(t.world)[ai.link.id]["human"] is False
    with party.as_player(t.world, ai.link.id):
        assert wizard.spells(t.world) == [0, 1, 6] and not wizard.wiz(t.world)["lessons"]  # a wizard record of its own: the colours from the start, no lesson taken
    # the snapshot a client draws shows it as another wizard
    rows = {p["id"]: p for p in joe.state()["snapshot"]["players"]}
    assert rows[ai.link.id]["ai"] is True and rows[ai.link.id]["name"] == "Mira" and rows[joe.id]["you"] is True
    # a human seat is still free for a person (the AI never takes one): the lobby counts people only
    assert t.session.info()["players"] == 1 and t.session.info()["max_players"] == 1


def test_the_ai_keeps_company_and_is_not_a_cheat():
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    me, mira = joe.pose, t.world.players[ai.link.id]
    start = abs(me["tx"] - mira["tx"]) + abs(me["ty"] - mira["ty"])
    walk(t, joe, 24)
    t.advance(20)
    dist = abs(me["tx"] - mira["tx"]) + abs(me["ty"] - mira["ty"])
    assert dist <= 8, ("she followed", start, dist)
    # she moves like anybody: one validated tile at a time, never faster than a walking wizard
    assert ai.link.move_seq > 3 and ai.link.move_seq < 400
    for line in t.session.command_log:
        assert line["op"] in ("move",) or line["player"] != ai.link.id or line["op"].startswith("pvp"), line


def test_she_greets_the_player_once_in_her_own_voice():
    t = solo()
    joe = t.people[0]
    t.advance(30)
    said = [n for n in joe.state()["notices"] if n["kind"] == "ai_says"]
    assert len(said) == 1 and said[0]["name"] == "Mira" and said[0]["text"] in ai_wizard.characters()["wizards"]["mira"]["lines"]["greet"]
    t.advance(30)
    assert not [n for n in joe.state()["notices"] if n["kind"] == "ai_says"]


# ------------------------------------------------------------------ the race

def test_a_human_can_guess_several_times_while_the_ai_is_still_thinking_and_wins_by_breaking_her_ward():
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    bring_together(t, joe, ai)
    duel = accept_and_lock(t, joe, ai)
    # the AI's Ward is hidden from the human's view; the test plays a good guesser using only feedback, as a person would
    from wizard_rts.duel.ward import Combatant, WeaveBot

    me = Combatant(id="j", weave_size=3, attack_pool=duel.fmt["pool"], ward_size=3, ward_pool=duel.fmt["pool"])
    bot = WeaveBot(me, me, 3)
    casts_before = len(duel.history[ai.link.id])
    mine = 0
    while duel.state == "active" and mine < 6:
        guess = bot.make_guess()
        r = joe.op("pvp_cast", attack=guess, cast_seq=mine + 1)
        assert r["status"] == "ok", r
        mine += 1
        bot.register_feedback(guess, r["fracture"], r["echo"])
        t.advance(0.4)  # a quick player
    assert duel.state == "finished" and duel.result["winner"] == joe.id
    assert mine >= 2
    assert len(duel.history[ai.link.id]) - casts_before <= 1, "the AI is slower than a quick human: it had at most one guess in the time he had several"
    # the AI took its defeat in character: a line, a grudge, a memory
    t.advance(3)
    notices = [n for n in joe.state()["notices"] if n["kind"] == "ai_says"]
    assert any(n["line"] == "lose" for n in notices)
    spec = ai_wizard.characters()["wizards"]["mira"]
    assert ai.memory()["duels"]["lost"] == 1 and ai.relationship(joe.id) == spec["start_relationship"] + spec["loss_relationship"] + spec["killed_relationship"]
    from wizard_rts.narrative import mortality

    assert mortality.is_dead(t.world, ai.link.id), "a duel between apprentices is to the death: Mira lies where she fell until Joe brings her back"
    t.advance(4)
    assert joe.link.duel_id and t.session.duels[joe.link.duel_id].state == "finished"
    assert joe.op("pvp_leave")["status"] == "ok"
    assert not t.world.dmb.clock.get("pause_tokens"), "the world is running again"


def test_the_ai_solves_a_ward_with_the_retained_heuristic_and_wins_a_slow_humans_duel():
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    bring_together(t, joe, ai)
    duel = accept_and_lock(t, joe, ai, ward=(6, 6, 0))
    t.advance(120)  # the human is thinking
    assert duel.state == "finished" and duel.result["winner"] == ai.link.id
    hist = duel.history[ai.link.id]
    assert 1 <= len(hist) <= 10 and hist[-1]["broken"] and not any(h["auto"] for h in hist)
    # every guess was spaced like a thoughtful person's, and she only ever knew the feedback she was given
    assert ai.memory()["duels"]["won"] == 1
    assert ai.relationship(joe.id) > ai_wizard.characters()["wizards"]["mira"]["start_relationship"]
    assert len(duel.history[joe.id]) <= 1, "the human made at most the host's auto-cast"


def test_an_unfriendly_relationship_makes_her_decline():
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    bring_together(t, joe, ai)
    ai.memory()["relationship"][joe.id] = -40
    assert challenge(t, joe, ai)["status"] == "ok"
    t.advance(6)
    assert not joe.link.duel_id, "no duel began"
    notices = [n for n in joe.state()["notices"] if n["kind"] == "declined"]
    assert notices and any(n.get("by") == ai.link.id for n in notices)


def test_the_ai_memory_is_saved_with_the_world(tmp_path, monkeypatch):
    monkeypatch.setenv("DMB_RUNS", str(tmp_path))
    from wizard_rts.net.host import load_saved_world
    from wizard_rts.net.session import MultiplayerSession

    t = solo()
    joe, ai = t.people[0], ai_of(t)
    ai._adjust(joe.id, 17)
    rel = ai.relationship(joe.id)
    assert joe.op("save", slot="quit")["status"] == "ok"
    world = load_saved_world("campaign")
    assert world is not None and world.players == {}
    # a new session over the saved world: the same companion, remembering the player
    s2 = MultiplayerSession(world, name="again", join_code="1", host_secret="s", max_players=1, ai_companions=1)
    from wizard_rts.net import protocol

    conn = object()
    s2.handle(conn, {"op": "hello", "protocol": protocol.PROTOCOL_VERSION, "game": protocol.GAME_VERSION, "secret": "s", "name": "Joe"}, 0.0)
    s2.handle(conn, {"op": "start"}, 0.0)
    (ai2,) = s2.ais.values()
    assert ai2.link.id == ai.link.id and ai2.relationship("p1") == rel


def test_an_ai_never_exists_in_a_two_human_game_and_never_takes_a_humans_seat():
    t = Table(humans=2, ai=0)
    assert not t.session.ais and len(t.session.links) == 2
    t2 = Table(humans=2, ai=1)  # even if one were asked for, it only fills a seat nobody else has
    assert not t2.session.ais


def test_the_campaign_with_an_ai_companion_in_the_world_is_still_completable_by_one_human():
    t = solo()
    joe = t.people[0]
    assert party.multi(t.world), "two wizards share the settlement"
    t.learn(joe)
    t.advance(3)
    assert campaign.stage(t.world) == "explore", "the AI does not hold the lessons back"
    with party.as_player(t.world, ai_of(t).link.id):
        assert wizard.spells(t.world) == [0, 1, 6], "when the lessons end she knows the colours too"
    t.meet_people(joe, 3)
    t.wait_for_stage("arrival")
    t.through_scene(joe)
    t.wait_for_stage("confrontation")
    out = t.through_scene(joe)
    rec = out["duel_lease"]["payload"]["duel"]
    from test_wizard_duel_lease import play

    assert joe.op("duel_resolve", duel_id=rec["id"], **play(rec, win=True))["outcome"] == "won"
    t.through_scene(joe)
    t.meet_people(joe, 2)
    t.advance(60)
    assert campaign.stage(t.world) == "complete"

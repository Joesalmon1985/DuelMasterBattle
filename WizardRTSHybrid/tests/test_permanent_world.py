"""The permanent world (plan M2, the brief's eight acceptance tests): characters come and go, the world never starts over.

1. A single-player wizard dies and the session ends; the next start seats a new wizard in the same world (the body stays, the game time goes on).
2. One multiplayer wizard dies, the survivor resurrects them (test_mortality.py).
3. Both multiplayer wizards die; the world is saved with both bodies and the next session seats two new wizards.
4. A new wizard after the mentor died: the mentor stays dead, the mother says so.
5. The host closes and reopens: the offline catch-up is paid once, in slices, under a budget, and written off at once.
6. A reconnect or a second start right after never applies the debt twice.
7. Several generations of wizards in one world stay consistent and loadable.
8. Repeated save, load and catch-up never duplicate deaths, raise the dead or forget the mentor's death.
"""
from __future__ import annotations

import time

import pytest
from _party import Table

from wizard_rts.narrative import campaign, clockdebt, mortality, mother, party, persist, residents, wizard
from wizard_rts.net import host as nethost
from wizard_rts.net.session import MultiplayerSession

pytestmark = pytest.mark.usefixtures("runs_dir")


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DMB_RUNS", str(tmp_path))
    return tmp_path


def save(t: Table, slot: str = "quit", closed_at: float | None = None) -> dict:
    path = persist.slot_path("campaign", slot)
    return persist.save_world(t.world, path, wall_clock=(lambda: closed_at) if closed_at is not None else None)


def reopen(now: float | None = None, **kw) -> tuple:
    world, info = nethost.prepare_world("campaign", 507, "small", now=now, **kw)
    return world, info


def hash_without_players(w) -> str:
    """The world's hash with the session's player records set aside (a loaded world has none until a session seats people)."""
    saved = w.players
    w.players = {}
    try:
        return w.state_hash()
    finally:
        w.players = saved


def kill_host(t: Table) -> None:
    joe = t.people[0]
    mortality.die(t.world, joe.id, "trap", terminal=False)
    t.session.tick(t.now)
    assert t.session.ending is not None


# ------------------------------------------------------------------ 1

def test_a_single_player_death_ends_the_session_and_new_game_seats_a_new_wizard_in_the_same_world():
    t = Table(humans=1, ai=1)
    joe = t.people[0]
    seed, ms_before = t.world.seed, t.world.dmb.clock["game_ms"]
    t.advance(2)
    kill_host(t)
    assert t.session.ending["kind"] == "human_dead"
    save(t)  # what the host does on an ending
    world, info = reopen()
    assert info["loaded"] and info["host_was_dead"] and info["retired"] and world.seed == seed and world.dmb.clock["game_ms"] >= ms_before
    t2 = Table(humans=1, ai=1, world=world)
    joe2 = t2.people[0]
    assert not mortality.is_dead(t2.world, joe2.id), "the new wizard is alive"
    assert party.generation(t2.world) == 2 and party.host_actor(t2.world) == "player:2"
    bodies = t2.world.narrative["mortality"]["bodies"]
    assert list(bodies) == ["gone:p1:1"], bodies
    body = residents.table(t2.world)[bodies["gone:p1:1"]]
    assert body["status"] == "dead" and body["seat"] == "gone:p1:1"
    with joe2.seat_state():
        assert wizard.spells(t2.world) == [0, 1, 6] and not wizard.wiz(t2.world)["lessons"], "a fresh apprentice: the colours from the first moment, no lesson taken"
    assert joe2.op("move", seq=1, tx=joe2.pose["tx"], ty=joe2.pose["ty"], facing="up")["status"] == "ok"
    assert mother.pid_of(t2.world, joe2.id) and mother.pid_of(t2.world, joe2.id) != t2.world.narrative["mothers"]["by_seat"]["gone:p1:1"], "a mother of their own"
    (mira,) = t2.session.ais.values()
    assert mira.link.id == "a1" and "a1" in party.seats(t2.world), "Mira is the same Mira, with her memory"


def test_new_game_in_a_session_seats_a_new_wizard_in_place():
    t = Table(humans=1, ai=1)
    joe = t.people[0]
    with joe.seat_state():
        wizard.learn(t.world, [0, 1, 6], 3)
    r = joe.op("new_game")
    assert r["status"] == "ok" and r["new_wizard"] and r["retired"] == "gone:p1:1" and r["generation"] == 2
    with joe.seat_state():
        assert not wizard.wiz(t.world)["lessons"] and wizard.wiz(t.world)["duels"]["won"] == 0, "a new person: nothing learned yet"
    assert party.retired(t.world)["gone:p1:1"]["name"] == "Joe"
    assert t.world.narrative["ledger"]["recent"][-1]["kind"] == "wizard_left"


# ------------------------------------------------------------------ 3

def test_both_multiplayer_wizards_dead_the_world_is_saved_and_the_next_session_seats_two_new_wizards():
    t = Table(humans=2)
    joe, ann = t.people
    mortality.die(t.world, joe.id, "trap", terminal=False)
    mortality.die(t.world, ann.id, "trap", terminal=False)
    t.session.tick(t.now)
    assert t.session.ending["kind"] == "all_dead"
    save(t)
    world, info = reopen()
    assert sorted(info["retired"]) == ["gone:p1:1", "gone:p2:1"]
    t2 = Table(humans=2, world=world)
    assert all(not mortality.is_dead(t2.world, h.id) for h in t2.people)
    assert len(t2.world.narrative["mortality"]["bodies"]) == 2
    assert t2.people[0].op("state")["status"] == "ok"


# ------------------------------------------------------------------ 4

def test_a_new_wizard_after_the_mentors_death_finds_the_mentor_dead_and_is_told_so(monkeypatch):
    import _campaign as camp

    camp.quick(monkeypatch, min_ms=20_000, fallback_ms=60_000, aftermath_fallback_ms=40_000)
    t = Table(humans=1)
    joe = t.people[0]
    t.learn(joe)
    t.advance(2)
    t.meet_people(joe, 3)
    t.wait_for_stage("arrival")
    t.through_scene(joe)
    t.wait_for_stage("confrontation")
    rec = t.through_scene(joe)["duel_lease"]["payload"]["duel"]
    assert campaign.state(t.world)["mentor_fate"] == "killed_by_stranger"
    from test_wizard_duel_lease import play

    assert joe.op("duel_resolve", duel_id=rec["id"], **play(rec, win=True))["outcome"] == "won"  # the stranger withdraws; later Joe dies of something else
    t.through_scene(joe)
    mentor = t.mentor
    kill_host(t)
    save(t)
    world, info = reopen()
    assert world.dmb.people[mentor]["alive"] is False, "the mentor stays dead"
    assert campaign.state(world)["mentor_fate"] == "killed_by_stranger"
    t2 = Table(humans=1, world=world)
    joe2 = t2.people[0]
    assert joe2.op("talk", npc=mentor)["reason"] == "dead"
    mum = mother.pid_of(t2.world, joe2.id)
    facts = mother.facts(t2.world, mum)
    assert facts["mentor_dead"] == 1 and facts["arrived_after"] == 1 and facts["previous"] == "Joe"
    joe2.pose["tx"], joe2.pose["ty"] = residents.table(t2.world)[mum]["tile"][0] + 1, residents.table(t2.world)[mum]["tile"][1]
    reply = joe2.op("talk", npc=mum)
    assert reply["status"] == "ok", reply
    text = " ".join(reply["lines"])
    assert "after it all happened" in text and "Joe" in text, text


# ------------------------------------------------------------------ 5 and 6

def test_the_offline_catch_up_is_bounded_paid_in_slices_and_written_off_once():
    t = Table(humans=1, ai=1)
    t.advance(1)
    ms_saved = int(t.world.dmb.clock["game_ms"])
    closed = 1_000_000.0
    save(t, closed_at=closed)
    s = clockdebt.settings()
    assert clockdebt.owed_ms(closed, closed + 30) == 0, "half a minute away is nothing"
    assert clockdebt.owed_ms(closed, closed + 3600) == int(s["minutes_per_real_hour"] * 60_000), "an hour away: the hourly rate"
    assert clockdebt.owed_ms(closed, closed + 40 * 86400) == 0, "a clock that jumped is not believed"
    assert clockdebt.owed_ms(closed, closed + 8 * 3600) == int(s["cap_minutes"] * 60_000), "a night away is capped"
    world, info = reopen(now=closed + 8 * 3600)
    assert info["owed_ms"] == int(s["cap_minutes"] * 60_000)
    session = MultiplayerSession(world, name="x", join_code="1", host_secret="s", max_players=1, ai_companions=1, clock=lambda: 0.0)
    host = nethost.HostServer(world, session, bind="127.0.0.1", port=0, discovery_port=None, clock=time.monotonic)
    host.permanent = True
    host.begin_catch_up(info["owed_ms"])
    assert session.lobby_view()["catch_up"]["active"]
    slices = 0
    while host.catch_up["active"] and slices < 100_000:
        host._catch_up_slice()
        slices += 1
    assert not host.catch_up["active"] and host.catch_up["written_off"]
    assert host.catch_up["paid_ms"] == info["owed_ms"] and host.catch_up["forfeited_ms"] == 0
    assert int(world.dmb.clock["game_ms"]) == ms_saved + info["owed_ms"]
    # written off: the save now carries the record and a fresh closed_at, so reopening at once owes nothing
    again, info2 = reopen(now=time.time())
    assert info2["owed_ms"] == 0 and info2["last_catch_up"]["paid_ms"] == info["owed_ms"]
    assert int(again.dmb.clock["game_ms"]) == ms_saved + info["owed_ms"], "the catch-up was applied exactly once"


def test_enter_now_forfeits_the_rest_and_the_budget_stops_a_slow_host():
    t = Table(humans=1, ai=1)
    closed = 1_000_000.0
    save(t, closed_at=closed)
    world, info = reopen(now=closed + 8 * 3600)
    session = MultiplayerSession(world, name="x", join_code="1", host_secret="s", max_players=1, ai_companions=1, clock=lambda: 0.0)
    host = nethost.HostServer(world, session, bind="127.0.0.1", port=0, discovery_port=None, clock=time.monotonic)
    host.permanent = True
    host.begin_catch_up(info["owed_ms"])
    host._catch_up_slice()
    conn = object()
    from wizard_rts.net import protocol

    assert session.handle(conn, {"op": "hello", "protocol": protocol.PROTOCOL_VERSION, "game": protocol.GAME_VERSION, "secret": "s", "name": "Joe"}, 0.0)["status"] == "ok"
    assert session.handle(conn, {"op": "start"}, 0.0)["status"] == "ok"
    assert not host.catch_up["active"] and host.catch_up["forfeited_ms"] > 0
    host._catch_up_slice()
    assert host.catch_up["written_off"]
    _w, info2 = reopen(now=time.time())
    assert info2["last_catch_up"]["forfeited_ms"] == host.catch_up["forfeited_ms"]
    # the budget
    t3 = Table(humans=1)
    save(t3, closed_at=closed)
    world3, info3 = reopen(now=closed + 8 * 3600)
    s3 = MultiplayerSession(world3, name="x", join_code="1", host_secret="s", max_players=1, clock=lambda: 0.0)
    h3 = nethost.HostServer(world3, s3, bind="127.0.0.1", port=0, discovery_port=None, clock=time.monotonic)
    h3.permanent = True
    h3.begin_catch_up(info3["owed_ms"])
    h3.catch_up["budget_s"] = 0.0
    h3._catch_up_slice()
    assert not h3.catch_up["active"] and h3.catch_up["paid_ms"] <= 100 and h3.catch_up["forfeited_ms"] >= info3["owed_ms"] - 100


# ------------------------------------------------------------------ 7 and 8

def test_three_generations_in_one_world_stay_consistent_and_loadable():
    t = Table(humans=1, ai=1)
    names = []
    for gen in range(1, 4):
        joe = t.people[0]
        names.append(joe.name)
        t.advance(1)
        kill_host(t)
        save(t)
        world, info = reopen()
        assert info["host_was_dead"]
        t = Table(humans=1, ai=1, world=world)
    assert party.generation(t.world) == 4
    bodies = t.world.narrative["mortality"]["bodies"]
    assert sorted(bodies) == ["gone:p1:1", "gone:p1:2", "gone:p1:3"]
    assert all(residents.table(t.world)[pid]["status"] == "dead" for pid in bodies.values())
    assert len({residents.table(t.world)[pid]["tile"][0] for pid in bodies.values()}) >= 1
    h1 = hash_without_players(t.world)
    save(t)
    world, _ = reopen()
    assert hash_without_players(world) == h1, "a save and a load change nothing"
    assert len(world.narrative["mothers"]["by_seat"]) >= 4, "every apprentice had a mother"


def test_repeated_save_load_and_catch_up_never_duplicate_or_resurrect(monkeypatch):
    import _campaign as camp

    camp.quick(monkeypatch, min_ms=20_000, fallback_ms=60_000, aftermath_fallback_ms=40_000)
    t = Table(humans=2)
    joe, ann = t.people
    for h in (joe, ann):
        t.learn(h)
    t.advance(3)
    t.meet_people(joe, 3)
    t.wait_for_stage("arrival")
    t.through_scene(joe)
    t.through_scene(ann)
    t.wait_for_stage("confrontation")
    rec = t.through_scene(joe)["duel_lease"]["payload"]["duel"]
    from test_wizard_duel_lease import play

    assert joe.op("duel_resolve", duel_id=rec["id"], **play(rec, win=True))["outcome"] == "won"  # the stranger withdrew: nothing lethal is open at the save
    mentor = t.mentor
    mortality.die(t.world, ann.id, "trap", terminal=False)
    deaths = t.world.narrative["ledger"]["world"]["deaths"]
    died = [e for e in t.world.narrative["log"] if e["kind"] == "wizard_died"]
    closed = 1_000_000.0
    for i in range(3):
        save(t, closed_at=closed + i * 7200)
        world, info = reopen(now=closed + i * 7200 + 7200)
        session = MultiplayerSession(world, name="x", join_code="1", host_secret="s", max_players=2, clock=lambda: 0.0)
        host = nethost.HostServer(world, session, bind="127.0.0.1", port=0, discovery_port=None, clock=time.monotonic)
        host.permanent = True
        host.begin_catch_up(info["owed_ms"])
        while host.catch_up["active"]:
            host._catch_up_slice()
        assert world.dmb.people[mentor]["alive"] is False
        assert world.narrative["ledger"]["world"]["deaths"] == deaths
        assert len([e for e in world.narrative["log"] if e["kind"] == "wizard_died"]) == len(died)
        assert len(world.narrative["mortality"]["bodies"]) == 1 and all(residents.table(world)[p]["status"] == "dead" for p in world.narrative["mortality"]["bodies"].values())
        t = Table(humans=2, world=world)

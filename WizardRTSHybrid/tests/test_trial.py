"""The Trial of Champions, zones A to D (plan M5; the brief's scenarios E, F, G): a gate on the map a short walk from the village, entered with no
lesson taken; one shared run per world with a position for every wizard; the book's choices; creatures as Ward Duel leases; death inside leaves the
body in the zone, a friend walks back and resurrects beside it; when every wizard inside is dead the run ends and the bodies stay for the next."""
from __future__ import annotations

import pytest
from _party import Table
from test_wizard_duel_lease import play

from wizard_rts.narrative import ledger, mortality, residents, wizard
from wizard_rts.trial import run as trial
from wizard_rts.trial import zones


def at_gate(t: Table, h) -> None:
    g = trial.gate_tile(t.world)
    assert g is not None, "the gate was placed"
    h.pose["tx"], h.pose["ty"] = g[0], g[1] + 1
    if (h.pose["tx"], h.pose["ty"]) in t.world.blocked:
        h.pose["tx"], h.pose["ty"] = g[0] + 1, g[1]


def enter(t: Table, h) -> dict:
    at_gate(t, h)
    r = h.op("trial_enter")
    assert r["status"] == "ok", r
    return r


def goto(t: Table, h, zone: str, x: int, y: int) -> None:
    """A test shortcut: put the wizard on a tile of a zone (the walking is tested separately)."""
    rec = trial.seat_rec(t.world, h.id)
    assert rec and rec["inside"]
    rec.update(zone=zone, x=x, y=y)


def step(h, dx: int, dy: int) -> dict:
    return h.op("trial_move", dx=dx, dy=dy)


def test_the_gate_is_on_the_map_near_the_village_with_the_rollkeeper_and_the_contestants():
    t = Table(humans=1)
    joe = t.people[0]
    g = trial.gate_tile(t.world)
    assert g is not None
    from wizard_rts.narrative import tutorial

    home = t.world.dmb.settlements[tutorial.state(t.world)["settlement"]]["tile"]
    assert trial.GATE_DISTANCE[0] <= max(abs(g[0] - home[0]), abs(g[1] - home[1])) <= trial.GATE_DISTANCE[1] + 2
    rows = [e for e in t.world.snapshot()["entities"] if e.get("kind") == "trial_gate"]
    assert rows and rows[0]["label"] == "The Trial of Champions" and (rows[0]["tx"], rows[0]["ty"]) == g
    official = trial.state(t.world)["official"]
    assert residents.table(t.world)[official]["role"] == "official"
    assert len(trial.state(t.world)["contestants"]) == 5
    joe.stand_by_resident(official)
    reply = joe.op("talk", npc=official)
    assert reply["status"] == "ok" and "roll" in " ".join(reply["lines"]).lower()
    assert "unprepared_anyway" in [c["id"] for c in reply["choices"]], "an apprentice with no lesson taken is noticed"
    far = joe.op("trial_enter")
    assert far["reason"] == "too_far"


def test_entering_unprepared_starts_a_run_and_the_contestants_go_in_ahead():
    t = Table(humans=1)
    joe = t.people[0]
    r = enter(t, joe)
    v = r["view"]
    assert v["zone"] == "dd_entrance" and v["pos"] == list(zones.ENTRY_POS) and v["name"] == "Crystal Entrance"
    assert ledger.count(t.world, "trial_entered_unprepared", joe.id) == 1
    assert all(residents.table(t.world)[pid]["status"] == "gone" for pid in trial.state(t.world)["contestants"].values()), "they went in ahead"
    assert joe.op("move", seq=1, tx=joe.pose["tx"] + 1, ty=joe.pose["ty"], facing="right")["reason"] == "inside_trial"
    assert joe.op("trial_enter")["reason"] == "already_inside"
    st = joe.state()
    assert st["trial"]["zone"] == "dd_entrance" and next(p for p in st["snapshot"]["players"] if p["you"])["trial"]["zone"] == "dd_entrance"


def test_walking_the_entrance_the_fork_and_the_galleries_with_real_steps():
    t = Table(humans=1)
    joe = t.people[0]
    enter(t, joe)
    # the entrance: a corridor of path north to the fork; a wall to the east
    assert step(joe, 1, 0)["status"] == "ok"  # (11, 11) is floor
    assert step(joe, 1, 0)["status"] == "ok"
    blocked = step(joe, 1, 0)  # (13, 11) ... then (14,11) is T
    while blocked["status"] == "ok":
        blocked = step(joe, 1, 0)
    assert blocked["status"] == "blocked"
    goto(t, joe, "dd_entrance", 9, 1)
    r = step(joe, 0, -1)
    assert r["status"] == "ok" and r["changed_zone"] and r["zone"] == "dd_fork" and r["pos"] == [9, 12]
    rec = trial.seat_rec(t.world, joe.id)
    assert rec["visited"] == ["dd_entrance", "dd_fork"]
    goto(t, joe, "dd_fork", 1, 6)
    r = step(joe, -1, 0)
    assert r["changed_zone"] and r["zone"] == "dd_galleries"
    v = joe.op("trial_view")["view"]
    assert {e["id"] for e in v["entities"]} >= {"dd_old_man", "dd_knight_statue", "dd_torch", "dog_gal1"}


def test_signs_pickups_and_the_riddle_are_interactions_with_consequences():
    t = Table(humans=1)
    joe = t.people[0]
    enter(t, joe)
    goto(t, joe, "dd_entrance", 11, 4)
    r = joe.op("trial_interact", entity="dd_crystal")
    assert r["status"] == "ok" and "Crystal" in r["text"]
    goto(t, joe, "dd_entrance", 7, 6)
    r = joe.op("trial_interact", entity="aid_box")
    assert r["status"] == "ok" and r["item"]["id"] == "sukumvit_note" and "SUKUMVIT" in r["text"]
    v = joe.op("trial_view")["view"]
    assert "aid_box" not in {e["id"] for e in v["entities"]} and v["pockets"][0]["id"] == "sukumvit_note"
    goto(t, joe, "dd_galleries", 9, 5)
    r = joe.op("trial_interact", entity="dd_old_man")
    assert r["status"] == "ok" and r["event"] == "statue_riddle" and [c["id"] for c in r["prompt"]["choices"]] == ["100", "150", "200"]
    r = joe.op("trial_choose", entity="dd_old_man", choice="200")
    assert "hurt" in r["prompt"]["text"] and "wounded" in joe.op("trial_view")["view"]["conditions"]
    with joe.seat_state():
        assert wizard.wiz(t.world)["wounded"]
    r = joe.op("trial_interact", entity="dd_old_man")
    assert r["prompt"]["choices"] == [] and "own counsel" in r["prompt"]["text"], "answered once a run"


def test_a_creature_is_a_lease_a_win_clears_it_for_both_and_the_fly_lets_you_escape():
    t = Table(humans=2)
    joe, ann = t.people
    enter(t, joe)
    enter(t, ann)
    goto(t, joe, "dd_fork", 15, 6)
    r = joe.op("trial_interact", entity="fly_east")
    assert r["status"] == "started" and r["enemy"] == "giant_fly" and not r["lethal"]
    rec = r["duel_lease"]["payload"]["duel"]
    enc = rec["encounter"]
    assert enc["enemy_combatant"]["ward_pool"] == [1, 6] and enc["enemy_combatant"]["max_casts"] == 6 and enc["player_combatant"]["max_casts"] == 8
    out = joe.op("duel_resolve", duel_id=rec["id"], **play(rec, win=False))
    assert out["trial"]["wounded"] and not mortality.is_dead(t.world, joe.id), "the Giant Fly lets you escape, hurt"
    for attempt in range(8):  # a draw (both Wards broken in one round) leaves the fly alive; the next attempt is a new lease
        r = joe.op("trial_interact", entity="fly_east")
        assert r["status"] == "started", r
        rec = r["duel_lease"]["payload"]["duel"]
        if attempt == 0:
            assert rec["encounter"]["player_combatant"]["max_casts"] == 7, "wounded: one cast fewer"
        out = joe.op("duel_resolve", duel_id=rec["id"], **play(rec, win=True))
        assert out["status"] == "resolved", out
        if out["outcome"] == "won":
            break
        assert (out["trial"].get("draw") or out["trial"].get("wounded")) and not mortality.is_dead(t.world, joe.id), "the fly never kills"
    assert out["trial"]["killed"]
    goto(t, ann, "dd_fork", 15, 6)
    assert "fly_east" not in {e["id"] for e in ann.op("trial_view")["view"]["entities"]}, "shared: Ann finds it already dead"


def test_a_lethal_creature_kills_the_body_lies_in_the_zone_and_a_friend_resurrects_beside_it():
    t = Table(humans=2)
    joe, ann = t.people
    enter(t, joe)
    enter(t, ann)
    goto(t, joe, "dd_galleries", 13, 8)
    r = joe.op("trial_interact", entity="dog_gal1")
    assert r["status"] == "started" and r["lethal"]
    rec = r["duel_lease"]["payload"]["duel"]
    assert rec["encounter"]["enemy_combatant"]["fixed_ward"] == [1, 1, 1], "the mastiff's one-colour Ward, in three places"
    out = joe.op("duel_resolve", duel_id=rec["id"], **play(rec, win=False))
    assert out["trial"]["dead"] and mortality.is_dead(t.world, joe.id)
    body = trial.body_of(t.world, joe.id)
    assert body and body["zone"] == "dd_galleries" and (body["x"], body["y"]) == (13, 8)
    assert mortality.body_of(t.world, joe.id) == "trial:" + joe.id
    assert joe.op("trial_move", dx=0, dy=1)["reason"] == "dead"
    assert trial.run(t.world)["ended"] is None, "Ann is alive inside: the run goes on"
    v = ann.op("trial_view")["view"]
    assert v["zone"] == "dd_entrance" and v["bodies"] == []
    assert ann.op("resurrect", target=joe.id)["reason"] == "too_far"
    goto(t, ann, "dd_galleries", 12, 8)
    v = ann.op("trial_view")["view"]
    assert v["bodies"] and v["bodies"][0]["seat"] == joe.id
    r = ann.op("trial_interact", entity="body:" + joe.id)
    assert r["status"] == "ok" and "call them back" in r["text"]
    assert ann.op("resurrect", target=joe.id)["status"] == "started"
    t.advance(mortality.resurrect_ms() / 1000.0 + 1.5)
    assert not mortality.is_dead(t.world, joe.id)
    rec_j = trial.seat_rec(t.world, joe.id)
    assert rec_j["inside"] and rec_j["zone"] == "dd_galleries" and (rec_j["x"], rec_j["y"]) == (13, 8)
    assert step(joe, 0, 1)["status"] in ("ok", "blocked")


def test_both_dead_inside_ends_the_run_and_the_next_contestants_find_the_bodies():
    t = Table(humans=2)
    joe, ann = t.people
    enter(t, joe)
    enter(t, ann)
    goto(t, joe, "dd_galleries", 13, 8)
    joe.op("trial_interact", entity="dd_torch") if False else None
    goto(t, joe, "dd_galleries", 5, 12)
    assert joe.op("trial_interact", entity="dd_torch")["item"]["id"] == "torch"
    mortality.die(t.world, joe.id, "trial:test", terminal=False)
    mortality.die(t.world, ann.id, "trial:test", terminal=False)
    t.advance(1)
    r = trial.run(t.world)
    assert r["ended"] and r["ended"]["why"] == "all_dead" and t.session.ending and t.session.ending["kind"] == "all_dead"
    dead = trial.state(t.world)["dead"]
    assert len(dead) == 2 and any(b["pockets"] == ["torch"] for b in dead.values())
    # the next run: new seats (as the host does after an ending), the bodies lie where they fell, the torch is on one of them, the dog is back
    from wizard_rts.narrative import party

    party.retire_humans(t.world, "session_over")
    t2 = Table(humans=1, world=t.world)
    cy = t2.people[0]
    enter(t2, cy)
    r2 = trial.run(t2.world)
    assert r2["id"] != r["id"] and r2["ended"] is None
    goto(t2, cy, "dd_galleries", 5, 11)
    v = cy.op("trial_view")["view"]
    assert any(b.get("old") and b["pockets"] == ["torch"] for b in v["bodies"]), v["bodies"]
    assert "dog_gal1" in {e["id"] for e in v["entities"]}, "creatures reset for the next run"
    who = next(b["seat"] for b in v["bodies"] if b.get("old") and b["pockets"] == ["torch"])
    r = cy.op("trial_interact", entity="body:" + who)
    assert r["status"] == "ok" and r["took"] == ["a dry torch"]
    assert "torch" in [p["id"] for p in cy.op("trial_view")["view"]["pockets"]]


def test_throms_pit_the_first_to_cross_decides_for_both():
    t = Table(humans=2)
    joe, ann = t.people
    enter(t, joe)
    enter(t, ann)
    goto(t, joe, "dd_pit", 7, 6)
    r = joe.op("trial_interact", entity="dd_throm")
    assert r["event"] == "throm_pit" and [c["id"] for c in r["prompt"]["choices"]] == ["lowered", "lower_him", "jump", "alone"]
    r = joe.op("trial_choose", entity="dd_throm", choice="lower_him")
    assert [c["id"] for c in r["prompt"]["choices"]] == ["after_him", "leave_him"]
    r = joe.op("trial_choose", entity="dd_throm", choice="leave_him")
    assert "remember this" in r["prompt"]["text"] and trial.run(t.world)["throm"] == "betrayed"
    goto(t, ann, "dd_pit", 7, 6)
    r = ann.op("trial_interact", entity="dd_throm")
    assert r["prompt"]["choices"] == [] and "Nobody is holding it" in r["prompt"]["text"], "the pit is crossed for everyone: Ann finds the rope slack"
    assert ledger.count(t.world, "trial_betrayals", joe.id) == 1


def test_the_lower_route_the_red_book_grows_the_weave_and_the_troll_is_lethal():
    t = Table(humans=1)
    joe = t.people[0]
    enter(t, joe)
    goto(t, joe, "dd_lower", 5, 5)
    r = joe.op("trial_interact", entity="red_book")
    assert r["weave"] == 4
    with joe.seat_state():
        assert wizard.wiz(t.world)["weave_size"] == 4
    goto(t, joe, "dd_lower", 6, 5)
    r = joe.op("trial_interact", entity="black_book")
    assert r["item"]["id"] == "vial" and r["event"] == "black_book" and [c["id"] for c in r["prompt"]["choices"]] == ["drink", "rub", "leave"]
    r = joe.op("trial_choose", entity="black_book", choice="drink")
    assert "poisoned" in joe.op("trial_view")["view"]["conditions"]
    goto(t, joe, "dd_lower", 14, 7)
    r = joe.op("trial_interact", entity="troll_lower1")
    assert r["status"] == "started" and r["lethal"] and "Throm" in r["intro"]
    rec = r["duel_lease"]["payload"]["duel"]
    assert rec["encounter"]["player_combatant"]["weave_size"] == 4, "the red book's fourth place is real on the board"
    out = joe.op("duel_resolve", duel_id=rec["id"], **play(rec, win=True))
    assert out["status"] == "resolved", out
    if out["outcome"] == "won":
        assert out["trial"]["killed"] and trial.run(t.world)["throm"] == "wounded" and trial.run(t.world)["flags"].get("troll_down")
        v = joe.op("trial_view")["view"]
        assert "bone_ring" in {e["id"] for e in v["entities"]}
    elif out["outcome"] == "lost":
        assert mortality.is_dead(t.world, joe.id), "a Cave Troll finishes a losing apprentice"
    else:
        assert out["trial"]["draw"] and not mortality.is_dead(t.world, joe.id)


def test_leaving_by_the_door_puts_the_wizard_back_at_the_gate_and_the_run_goes_on():
    t = Table(humans=1)
    joe = t.people[0]
    enter(t, joe)
    assert joe.op("trial_leave")["status"] == "ok"
    g = trial.gate_tile(t.world)
    assert max(abs(joe.pose["tx"] - g[0]), abs(joe.pose["ty"] - g[1])) <= 2
    assert not trial.inside(t.world, joe.id) and trial.run(t.world)["ended"] is None
    r = enter(t, joe)
    assert r["run"] == trial.run(t.world)["id"], "the same run, resumed from the door"
    goto(t, joe, "dd_fork", 5, 5)
    assert joe.op("trial_leave")["reason"] == "not_at_the_door"


def test_the_stranger_comes_while_both_are_inside_and_the_world_goes_on(monkeypatch):
    import _campaign as camp

    camp.quick(monkeypatch, min_ms=20_000, fallback_ms=60_000, aftermath_fallback_ms=40_000)
    t = Table(humans=2)
    joe, ann = t.people
    for h in (joe, ann):
        t.learn(h)
    t.advance(2)
    t.meet_people(joe, 3)
    enter(t, joe)
    enter(t, ann)
    from wizard_rts.narrative import campaign

    for _ in range(400):
        t.advance(1)
        if campaign.stage(t.world) in ("aftermath", "complete"):
            break
    assert campaign.stage(t.world) in ("aftermath", "complete") and t.world.dmb.people[t.mentor]["alive"] is False
    assert trial.inside(t.world, joe.id) and trial.inside(t.world, ann.id), "nobody was dragged out"

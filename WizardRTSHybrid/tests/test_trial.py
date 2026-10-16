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


# ---------------------------------------------------------------- the second half (plan M6): zones E to K

from wizard_rts.narrative import duel_lease
from wizard_rts.trial import events as trial_events


def win(rec: dict) -> dict:
    """A verified victory in one cast: the exact enemy Ward (Python reproduces it from the lease) breaks it. Deterministic, unlike playing the bot."""
    ward_ = duel_lease.expected_enemy_ward(rec)
    size = int(rec["encounter"]["player_combatant"]["weave_size"])
    pattern = (list(ward_) + [ward_[0]] * size)[:size]
    return {"outcome": "victory", "player_casts": 1, "enemy_casts": 1, "history": [{"pattern": pattern, "fracture": size, "echo": 0, "broke": True}],
            "enemy_ward": list(ward_), "player_ward": (list(rec["encounter"]["player_combatant"]["attack_pool"]) * size)[:size]}


def lose(rec: dict) -> dict:
    """A verified defeat: a cast that cannot break the Ward (a colour outside it in every place), then the enemy breaks ours."""
    enc = rec["encounter"]
    size = int(enc["player_combatant"]["weave_size"])
    ward_ = duel_lease.expected_enemy_ward(rec)
    pool = list(enc["player_combatant"]["attack_pool"])
    miss = [c for c in pool if c not in ward_]
    pattern = [miss[0] if miss else ward_[0]] * size
    from wizard_rts.duel import ward

    r = ward.score_attack(ward_, pattern)
    return {"outcome": "defeat", "player_casts": 1, "enemy_casts": 2, "history": [{"pattern": pattern, "fracture": r["fracture"], "echo": r["echo"], "broke": bool(r["broken"])}],
            "enemy_ward": list(ward_), "player_ward": (pool * size)[:size]}


def fight_and(h, entity: str, report, expect="started", **kw) -> dict:
    r = h.op("trial_interact", entity=entity, **kw)
    assert r["status"] == expect, r
    rec = r["duel_lease"]["payload"]["duel"]
    return h.op("duel_resolve", duel_id=rec["id"], **report(rec))


def test_the_dwarfs_tests_teach_stone_throms_forced_duel_opens_the_concealed_way():
    t = Table(humans=2)
    joe, ann = t.people
    enter(t, joe)
    enter(t, ann)
    goto(t, joe, "dd_trialmaster", 9, 5)
    r = joe.op("trial_interact", entity="dd_dwarf")
    assert r["status"] == "ok" and "speciality" in " ".join(r["lines"]) and [c["id"] for c in r["prompt"]["choices"]] == ["accept"], "no pit alliance, no attack option"
    r = joe.op("trial_choose", entity="dd_dwarf", choice="accept")
    assert [c["id"] for c in r["prompt"]["choices"]] == ["same", "less", "more"]
    r = joe.op("trial_choose", entity="dd_dwarf", choice="less")
    assert "The cup lifts:" in r["prompt"]["text"] and [c["id"] for c in r["prompt"]["choices"]] == ["gaze", "snatch"]
    r = joe.op("trial_choose", entity="dd_dwarf", choice="gaze")
    assert "fourth colour: Stone" in r["prompt"]["text"] and r["prompt"]["choices"] == []
    with joe.seat_state():
        assert wizard.knows(t.world, 3) and wizard.knows_fact(t.world, "dwarf_map")
    flags = trial.run(t.world)["flags"]
    assert flags["trial_ready"] and not flags.get("trial_done")
    # the second apprentice finds the procedure complete
    goto(t, ann, "dd_trialmaster", 9, 5)
    r = ann.op("trial_interact", entity="dd_dwarf")
    assert "waits in the arena" in r["prompt"]["text"] and r["prompt"]["choices"] == []
    # the way west is shut until Throm is dealt with: the edge tile is a tile, not an exit
    goto(t, joe, "dd_trialmaster", 1, 8)
    r = step(joe, -1, 0)
    assert r["status"] == "ok" and not r.get("changed_zone") and r["zone"] == "dd_trialmaster"
    # Throm, delirious, in the arena: a person faced like a creature, lethal
    assert "throm_arena" in {e["id"] for e in joe.op("trial_view")["view"]["entities"]}
    goto(t, joe, "dd_trialmaster", 5, 7)
    r = joe.op("trial_interact", entity="throm_arena")
    assert r["status"] == "started" and r["lethal"] and r["enemy"] == "throm_duel" and r["name"] == "Throm, Delirious" and "crossbow" in r["intro"]
    rec = r["duel_lease"]["payload"]["duel"]
    assert rec["encounter"]["enemy_combatant"]["archetype"] == "throm_duel" and rec["encounter"]["player_combatant"]["max_casts"] == 10, "a boss: the board shows his face, the apprentice has ten casts"
    out = joe.op("duel_resolve", duel_id=rec["id"], **win(rec))
    assert out["outcome"] == "won" and "Good fight" in out["trial"]["text"]
    run = trial.run(t.world)
    assert run["throm"] == "dead" and run["contestants"]["throm"] == "dead" and run["flags"]["trial_done"]
    goto(t, joe, "dd_trialmaster", 1, 8)
    r = step(joe, -1, 0)
    assert r["changed_zone"] and r["zone"] == "dd_idol"
    r = ann.op("trial_interact", entity="dd_dwarf")
    assert "The way is open" in r["prompt"]["text"]


def test_a_betrayed_throm_means_the_dwarf_opens_the_way_without_a_duel():
    t = Table(humans=1)
    joe = t.people[0]
    enter(t, joe)
    goto(t, joe, "dd_pit", 7, 6)
    joe.op("trial_interact", entity="dd_throm")
    joe.op("trial_choose", entity="dd_throm", choice="lower_him")
    joe.op("trial_choose", entity="dd_throm", choice="leave_him")
    goto(t, joe, "dd_trialmaster", 9, 5)
    r = joe.op("trial_interact", entity="dd_dwarf")
    assert "Alone" in r["prompt"]["text"]
    joe.op("trial_choose", entity="dd_dwarf", choice="accept")
    joe.op("trial_choose", entity="dd_dwarf", choice="more")
    r = joe.op("trial_choose", entity="dd_dwarf", choice="snatch")
    assert "still standing" in r["prompt"]["text"] and trial.run(t.world)["flags"]["trial_done"] and "wounded" in joe.op("trial_view")["view"]["conditions"]
    assert "throm_arena" not in {e["id"] for e in joe.op("trial_view")["view"]["entities"]}, "no Throm to fight: he was left at the pit"


def test_the_idol_the_false_eye_wakes_the_second_guardian_and_the_emerald_waits_for_it():
    t = Table(humans=1)
    joe = t.people[0]
    enter(t, joe)
    goto(t, joe, "dd_idol", 11, 3)
    ids = {e["id"] for e in joe.op("trial_view")["view"]["entities"]}
    assert "false_eye" in ids and "emerald_eye" not in ids, "the true eye waits for the second guardian"
    r = joe.op("trial_interact", entity="false_eye")
    assert r["status"] == "ok" and [c["id"] for c in r["prompt"]["choices"]] == ["take", "leave"], "a choice-first pickup: nothing taken yet"
    assert "false_eye" in {e["id"] for e in joe.op("trial_view")["view"]["entities"]}
    r = joe.op("trial_choose", entity="false_eye", choice="take")
    assert r["status"] == "started" and r["enemy"] == "flying_guardian" and r["lethal"] and "finds you" in r["intro"]
    assert "glass_eye" in [p["id"] for p in joe.op("trial_view")["view"]["pockets"]] and trial.run(t.world)["flags"]["idol_alarmed"]
    rec = r["duel_lease"]["payload"]["duel"]
    out = joe.op("duel_resolve", duel_id=rec["id"], **win(rec))
    assert out["trial"]["killed"] and out["trial"]["entity"] == "guard_idol2" and "emerald eye" in out["trial"]["text"]
    ids = {e["id"] for e in joe.op("trial_view")["view"]["entities"]}
    assert "emerald_eye" in ids and "guard_idol2" not in ids and "false_eye" not in ids
    goto(t, joe, "dd_idol", 8, 3)
    r = joe.op("trial_interact", entity="emerald_eye")
    assert r["gem"] == "emerald" and joe.op("trial_view")["view"]["gems"] == ["emerald"]


def test_the_grotto_and_the_vaults_the_boa_the_elf_the_bread_the_charm_and_the_false_diamond():
    t = Table(humans=1)
    joe = t.people[0]
    enter(t, joe)
    goto(t, joe, "dd_grotto", 9, 9)
    r = joe.op("trial_interact", entity="dd_elf")
    assert "the snake" in r["prompt"]["text"] and r["prompt"]["choices"] == []
    goto(t, joe, "dd_grotto", 10, 5)
    out = fight_and(joe, "boa_grotto1", win)
    assert "breathes" in out["trial"]["text"]
    goto(t, joe, "dd_grotto", 9, 9)
    r = joe.op("trial_interact", entity="dd_elf")
    assert [c["id"] for c in r["prompt"]["choices"]] == ["stay", "take"]
    r = joe.op("trial_choose", entity="dd_elf", choice="stay")
    assert "brave" in r["prompt"]["text"] and ledger.count(t.world, "trial_mercies", joe.id) == 1
    with joe.seat_state():
        assert wizard.knows_fact(t.world, "diamond_is_cold")
    rec = trial.seat_rec(t.world, joe.id)
    with joe.seat_state():
        trial_events.wound(t.world, rec, "test")
    assert "wounded" in joe.op("trial_view")["view"]["conditions"]
    goto(t, joe, "dd_grotto", 8, 10)
    r = joe.op("trial_interact", entity="elf_bread")
    assert r["item"]["id"] == "bread" and r["cleared"] and joe.op("trial_view")["view"]["conditions"] == []
    goto(t, joe, "dd_grotto", 11, 10)
    assert joe.op("trial_interact", entity="elf_charm")["item"]["id"] == "charm"
    # the vaults: the sapphire and its key, the false diamond seals the inner vault
    goto(t, joe, "dd_vaults", 9, 3)
    r = joe.op("trial_interact", entity="sapphire_box")
    assert r["gem"] == "sapphire" and trial.run(t.world)["flags"]["iron_key"]
    goto(t, joe, "dd_vaults", 14, 11)
    r = joe.op("trial_interact", entity="false_diamond")
    assert "the real one is cold" in r["prompt"]["text"]
    r = joe.op("trial_choose", entity="false_diamond", choice="take")
    assert "glass" in r["prompt"]["text"] and trial.run(t.world)["flags"]["vault_alarm"] and "wounded" in joe.op("trial_view")["view"]["conditions"]
    goto(t, joe, "dd_vaults", 11, 2)
    r = step(joe, 0, -1)
    assert not r.get("changed_zone"), "the inner vault locked itself"


def test_the_service_tunnels_the_prisoner_the_basket_and_ivy_paid_with_the_torch():
    t = Table(humans=2)
    joe, ann = t.people
    enter(t, joe)
    enter(t, ann)
    goto(t, joe, "dd_galleries", 5, 12)
    assert joe.op("trial_interact", entity="dd_torch")["item"]["id"] == "torch"
    goto(t, joe, "dd_service", 9, 11)
    r = joe.op("trial_interact", entity="dd_basket")
    assert "Sort her out" in r["prompt"]["text"]
    goto(t, joe, "dd_service", 6, 7)
    r = joe.op("trial_interact", entity="dd_prisoner")
    assert [c["id"] for c in r["prompt"]["choices"]] == ["free", "leave"]
    r = joe.op("trial_choose", entity="dd_prisoner", choice="free")
    assert "HATES the green" in r["prompt"]["text"] and trial.run(t.world)["flags"]["blood_weakness"]
    goto(t, joe, "dd_service", 9, 11)
    r = joe.op("trial_interact", entity="dd_basket")
    assert "Heard what you did" in r["prompt"]["text"] and trial.run(t.world)["flags"]["basket_ok"]
    goto(t, joe, "dd_service", 9, 12)
    r = step(joe, 0, 1)
    assert r["changed_zone"] and r["zone"] == "dd_vault_inner" and "basket" in r["travel_text"].lower()
    goto(t, joe, "dd_vault_inner", 7, 5)
    assert joe.op("trial_interact", entity="true_diamond")["gem"] == "diamond"
    # Ivy takes the torch; the second apprentice finds her paid
    goto(t, joe, "dd_service", 12, 7)
    r = joe.op("trial_interact", entity="dd_ivy")
    assert [c["id"] for c in r["prompt"]["choices"]] == ["torch", "leave", "attack"]
    r = joe.op("trial_choose", entity="dd_ivy", choice="torch")
    assert "Walk soft" in r["prompt"]["text"] and "torch" not in [p["id"] for p in joe.op("trial_view")["view"]["pockets"]]
    goto(t, ann, "dd_service", 12, 7)
    assert "Paid in full" in ann.op("trial_interact", entity="dd_ivy")["prompt"]["text"]


def test_attacking_ivy_is_a_lethal_duel_and_a_loss_leaves_the_body_in_the_tunnels():
    t = Table(humans=1)
    joe = t.people[0]
    enter(t, joe)
    goto(t, joe, "dd_service", 12, 7)
    joe.op("trial_interact", entity="dd_ivy")
    r = joe.op("trial_choose", entity="dd_ivy", choice="attack")
    assert r["status"] == "started" and r["enemy"] == "poison_ivy" and r["lethal"]
    rec = r["duel_lease"]["payload"]["duel"]
    out = joe.op("duel_resolve", duel_id=rec["id"], **lose(rec))
    assert out["trial"]["dead"] and mortality.is_dead(t.world, joe.id) and trial.body_of(t.world, joe.id)["zone"] == "dd_service"


def test_the_mirrors_smashed_give_light_and_the_bloodbeast_cannot_weave_vine_once_you_know():
    t = Table(humans=1)
    joe = t.people[0]
    enter(t, joe)
    goto(t, joe, "dd_mirror", 10, 5)
    r = joe.op("trial_interact", entity="dd_mirrors")
    assert [c["id"] for c in r["prompt"]["choices"]] == ["smash", "leave"]
    r = joe.op("trial_choose", entity="dd_mirrors", choice="smash")
    assert "without a duel" in r["prompt"]["text"]
    ids = {e["id"] for e in joe.op("trial_view")["view"]["entities"]}
    assert "demon_mirror1" not in ids and "light_shard" in ids
    goto(t, joe, "dd_mirror", 10, 3)
    r = joe.op("trial_interact", entity="light_shard")
    assert r["spell"] == 4
    with joe.seat_state():
        assert wizard.knows(t.world, 4)
    goto(t, joe, "dd_blood", 8, 6)
    r = joe.op("trial_interact", entity="blood_clue")
    assert r["item"]["id"] == "herbs" and trial.run(t.world)["flags"]["blood_weakness"]
    goto(t, joe, "dd_blood", 12, 8)
    r = joe.op("trial_interact", entity="beast_blood1")
    rec = r["duel_lease"]["payload"]["duel"]
    enemy = rec["encounter"]["enemy_combatant"]
    assert 6 not in enemy["ward_pool"] and 4 in enemy["ward_pool"] and enemy["archetype"] == "bloodbeast" and enemy["max_casts"] == 8
    out = joe.op("duel_resolve", duel_id=rec["id"], **win(rec))
    assert out["trial"]["spell"] == 5 and "SHADOW" in out["trial"]["text"]
    with joe.seat_state():
        assert wizard.knows(t.world, 5)


def test_the_grub_tunnels_stone_braces_the_boulder_and_jams_the_chest():
    t = Table(humans=1)
    joe = t.people[0]
    enter(t, joe)
    goto(t, joe, "dd_grub", 10, 6)
    r = joe.op("trial_interact", entity="boulder_sign")
    assert [c["id"] for c in r["prompt"]["choices"]] == ["run", "hold"], "no Stone yet"
    with joe.seat_state():
        wizard.learn(t.world, [3])
    r = joe.op("trial_interact", entity="boulder_sign")
    assert [c["id"] for c in r["prompt"]["choices"]] == ["run", "brace", "hold"]
    r = joe.op("trial_choose", entity="boulder_sign", choice="brace")
    assert "loses" in r["prompt"]["text"] and trial.run(t.world)["flags"]["boulder_braced"]
    goto(t, joe, "dd_grub", 15, 9)
    r = joe.op("trial_interact", entity="trapped_chest")
    assert [c["id"] for c in r["prompt"]["choices"]] == ["jam", "side", "headon", "leave"]
    r = joe.op("trial_choose", entity="trapped_chest", choice="jam")
    assert "gold" in r["prompt"]["text"] and "gold" in [p["id"] for p in joe.op("trial_view")["view"]["pockets"]]
    assert "trapped_chest" not in {e["id"] for e in joe.op("trial_view")["view"]["entities"]}


def test_the_troglodytes_rite_the_reed_and_the_undertow_back_to_the_grotto():
    t = Table(humans=1)
    joe = t.people[0]
    enter(t, joe)
    goto(t, joe, "dd_troglodytes", 10, 6)
    r = joe.op("trial_interact", entity="dd_trog_elder")
    assert [c["id"] for c in r["prompt"]["choices"]] == ["join", "run", "attack"]
    r = joe.op("trial_choose", entity="dd_trog_elder", choice="join")
    assert "sincerity" in r["prompt"]["text"] and trial.run(t.world)["flags"]["trog_rite"]
    goto(t, joe, "dd_troglodytes", 11, 5)
    assert not step(joe, 0, -1).get("changed_zone"), "the undertow needs the reed"
    goto(t, joe, "dd_troglodytes", 16, 5)
    assert joe.op("trial_interact", entity="dd_tube")["item"]["id"] == "reed"
    goto(t, joe, "dd_troglodytes", 11, 5)
    r = step(joe, 0, -1)
    assert r["changed_zone"] and r["zone"] == "dd_grotto" and "reed" in r["travel_text"].lower()


def test_the_troglodyte_champion_is_a_duel_from_a_choice():
    t = Table(humans=1)
    joe = t.people[0]
    enter(t, joe)
    goto(t, joe, "dd_troglodytes", 10, 6)
    joe.op("trial_interact", entity="dd_trog_elder")
    r = joe.op("trial_choose", entity="dd_trog_elder", choice="attack")
    assert r["status"] == "started" and r["enemy"] == "trog_champion"
    rec = r["duel_lease"]["payload"]["duel"]
    out = joe.op("duel_resolve", duel_id=rec["id"], **win(rec))
    assert "champion falls" in out["trial"]["text"] and trial.run(t.world)["flags"]["trog_beaten"]
    assert "dd_trog_elder" not in {e["id"] for e in joe.op("trial_view")["view"]["entities"]}


def test_the_manticore_hates_light_and_igbuts_door_crowns_a_champion_and_ends_the_run_for_everyone():
    t = Table(humans=2)
    joe, ann = t.people
    enter(t, joe)
    enter(t, ann)
    goto(t, joe, "dd_galleries", 9, 5)
    joe.op("trial_interact", entity="dd_old_man")
    joe.op("trial_choose", entity="dd_old_man", choice="150")
    with joe.seat_state():
        wizard.learn(t.world, [3, 4])
    goto(t, joe, "dd_manticore", 10, 5)
    r = joe.op("trial_interact", entity="manticore_gate1")
    rec = r["duel_lease"]["payload"]["duel"]
    assert 4 not in rec["encounter"]["enemy_combatant"]["ward_pool"] and rec["encounter"]["enemy_combatant"]["max_casts"] == 8
    out = joe.op("duel_resolve", duel_id=rec["id"], **win(rec))
    assert "lets you pass" in out["trial"]["text"]
    # Igbut's door: the gems, a wrong order bites, the right order opens on daylight
    goto(t, joe, "dd_igbut", 8, 7)
    r = joe.op("trial_interact", entity="dd_igbut")
    assert [c["id"] for c in r["prompt"]["choices"]] == ["face", "later"]
    r = joe.op("trial_choose", entity="dd_igbut", choice="face")
    assert "THREE are required" in r["prompt"]["text"]
    trial.seat_rec(t.world, joe.id)["gems"] = ["emerald", "sapphire", "diamond"]
    r = joe.op("trial_choose", entity="dd_igbut", choice="face")
    assert len(r["prompt"]["choices"]) == 6
    r = joe.op("trial_choose", entity="dd_igbut", choice="ESD")
    assert "1 placed true, 2 displaced" in r["prompt"]["text"] and "wounded" in joe.op("trial_view")["view"]["conditions"]
    goto(t, ann, "dd_fork", 9, 10)
    r = joe.op("trial_choose", entity="dd_igbut", choice="SED")
    assert r["champion"] and "CHAMPION" in r["prompt"]["text"]
    run = trial.run(t.world)
    assert run["ended"]["why"] == "champion" and run["ended"]["seat"] == joe.id and run["flags"]["champion"] == joe.id
    assert not trial.inside(t.world, joe.id) and not trial.inside(t.world, ann.id), "the doors open for everyone"
    g = trial.gate_tile(t.world)
    for h in (joe, ann):
        assert max(abs(h.pose["tx"] - g[0]), abs(h.pose["ty"] - g[1])) <= 3
    assert ledger.count(t.world, "trial_champion", joe.id) == 1
    with joe.seat_state():
        assert wizard.knows_fact(t.world, "champion_of_the_trial")
    assert joe.state()["trial"] == {}
    enter(t, ann)
    assert trial.run(t.world)["id"] != run["id"], "the next entrant begins a new run"


def test_three_wrong_orders_scatter_the_gems_to_be_picked_up_again():
    t = Table(humans=1)
    joe = t.people[0]
    enter(t, joe)
    goto(t, joe, "dd_igbut", 8, 7)
    trial.seat_rec(t.world, joe.id)["gems"] = ["emerald", "sapphire", "diamond"]
    joe.op("trial_interact", entity="dd_igbut")
    joe.op("trial_choose", entity="dd_igbut", choice="face")
    for order in ("ESD", "EDS"):
        joe.op("trial_choose", entity="dd_igbut", choice=order)
    r = joe.op("trial_choose", entity="dd_igbut", choice="DSE")
    assert "Pick up your stones" in r["prompt"]["text"] and r["prompt"]["choices"] == []
    v = joe.op("trial_view")["view"]
    assert v["gems"] == [] and trial.run(t.world)["flags"]["gems_scattered"]
    assert {"scattered_emerald", "scattered_sapphire", "scattered_diamond"} <= {e["id"] for e in v["entities"]}
    goto(t, joe, "dd_igbut", 4, 5)
    assert joe.op("trial_interact", entity="scattered_emerald")["gem"] == "emerald"
    assert joe.op("trial_view")["view"]["gems"] == ["emerald"]
    assert not trial.run(t.world).get("ended")


# ---------------------------------------------------------------- playtest fixes (17 Oct 2026): duels in the dungeon, scenes wait outside

def test_two_wizards_in_the_same_zone_can_duel_and_the_loser_dies_in_the_dungeon():
    from test_mortality import OTHER, WARD

    t = Table(humans=2)
    joe, ann = t.people
    enter(t, joe)
    enter(t, ann)
    goto(t, joe, "dd_galleries", 9, 9)
    goto(t, ann, "dd_fork", 9, 9)
    assert joe.op("pvp_challenge", target=ann.id)["reason"] == "inside_trial", "a different zone is out of reach"
    goto(t, ann, "dd_galleries", 20, 9)
    assert joe.op("pvp_challenge", target=ann.id)["reason"] == "too_far", "the zone's own tiles measure the distance"
    goto(t, ann, "dd_galleries", 10, 9)
    r = joe.op("pvp_challenge", target=ann.id)
    assert r["status"] == "ok", r
    assert ann.op("pvp_respond", duel_id=r["duel_id"], accept=True)["status"] == "ok"
    assert joe.op("trial_move", dx=1, dy=0)["reason"] == "in_duel", "no walking in the middle of a duel"
    assert joe.op("pvp_ward", ward=OTHER)["status"] == "ok" and ann.op("pvp_ward", ward=list(WARD))["status"] == "ok"
    assert joe.op("pvp_cast", attack=list(WARD), cast_seq=1)["broken"]
    joe.op("pvp_leave")
    ann.op("pvp_leave")
    assert mortality.is_dead(t.world, ann.id)
    body = trial.body_of(t.world, ann.id)
    assert body and body["zone"] == "dd_galleries" and (body["x"], body["y"]) == (10, 9), "she lies where she fell, inside"
    assert joe.op("resurrect", target=ann.id)["status"] == "started"
    t.advance(mortality.resurrect_ms() / 1000.0 + 1.5)
    assert not mortality.is_dead(t.world, ann.id) and trial.inside(t.world, ann.id)


def test_mira_can_be_challenged_again_inside_the_dungeon_after_being_brought_back():
    t = Table(humans=1, ai=1)
    t.advance(1)
    joe = t.people[0]
    (ai,) = t.session.ais.values()
    mira = ai.link
    at_gate(t, joe)
    t.world.players[mira.id]["tx"], t.world.players[mira.id]["ty"] = joe.pose["tx"] + 1, joe.pose["ty"]
    assert joe.op("trial_enter")["status"] == "ok"
    t.advance(10)
    assert trial.inside(t.world, mira.id)
    d = trial.zone_distance(t.world, joe.id, mira.id)
    assert d is not None
    got = None
    for _ in range(4):  # she declines twice (accept_after_challenges), then the third is accepted
        r = joe.op("pvp_challenge", target=mira.id)
        if r["status"] == "rejected" and r["reason"] == "too_far":
            goto(t, joe, trial.seat_rec(t.world, mira.id)["zone"], trial.seat_rec(t.world, mira.id)["x"], trial.seat_rec(t.world, mira.id)["y"] + 1)
            r = joe.op("pvp_challenge", target=mira.id)
        assert r["status"] == "ok", r
        t.advance(6)
        if joe.link.duel_id and joe.link.duel_id in t.session.duels:
            got = t.session.duels[joe.link.duel_id]
            break
    assert got is not None and got.state == "setup", "Mira accepted a duel inside the Trial"


def test_the_stranger_scene_waits_until_the_wizard_is_out_of_the_dungeon(monkeypatch):
    import _campaign as camp

    camp.quick(monkeypatch, min_ms=20_000, fallback_ms=60_000, aftermath_fallback_ms=40_000)
    t = Table(humans=1)
    joe = t.people[0]
    t.learn(joe)
    t.advance(2)
    t.meet_people(joe, 3)
    enter(t, joe)
    from wizard_rts.narrative import campaign, party

    for _ in range(300):
        t.advance(1)
        with party.as_player(t.world, joe.id):
            if campaign.active_scene(t.world) is not None:
                break
    with party.as_player(t.world, joe.id):
        assert campaign.active_scene(t.world) is not None, "the stranger came while she was inside"
        assert campaign.scene_view(t.world) is None, "but she is not interrupted in the dungeon"
    with party.as_player(t.world, joe.id):
        assert campaign.snapshot(t.world)["scene"] is None, "the journal the client reads carries no scene to open"
    goto(t, joe, "dd_entrance", 10, 11)
    assert joe.op("trial_leave")["status"] == "ok"
    with party.as_player(t.world, joe.id):
        assert campaign.scene_view(t.world) is not None, "the scene is waiting for her outside"

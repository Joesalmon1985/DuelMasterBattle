"""The world's magic ladder (plan `docs/PLAN_PLAYER_STRESS_AND_PROGRESSION.md` section 4, the owner's rules of 18 Oct 2026): three duels of any kind bring the
fourth colour whatever else has happened; an hour of play brings four slots and six colours without a single duel; whichever trigger comes first fires;
the gain is the world's (death, a new apprentice, save and load, the catch-up), the same format for every duel and every wizard, Mira included; a due rung
interrupts a conversation but waits for a duel on the board; an authored Ward keeps its own size."""
from __future__ import annotations

import pytest
from _party import Table
from test_ai_wizard import accept_and_lock, bring_together
from test_village import fight_pest
from test_wizard_duel_lease import play

from wizard_rts.duel.ward import Combatant, WeaveBot
from wizard_rts.narrative import duel_lease, ledger, mortality, party, persist, pests, progression, wizard
from wizard_rts.net import host as nethost
from wizard_rts.net import pvp


@pytest.fixture(autouse=True)
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DMB_RUNS", str(tmp_path))
    return tmp_path


def solo(ai: int = 1) -> Table:
    t = Table(humans=1, ai=ai)
    t.advance(1)
    return t


def ai_of(t: Table):
    (ai,) = t.session.ais.values()
    return ai


def rungs_told(h) -> list[dict]:
    return [n for n in h.state()["notices"] if n["kind"] == "rung"]


def fight_rats(t: Table, h, n: int) -> None:
    inf = pests.live(t.world)
    for i in range(n):
        pid = pests.pests_of(t.world, inf)[0]
        fight_pest(t, h, pid, win=(i % 2 == 0))  # wins and losses alike: a duel fought to a verdict is a duel


def my_pool(t: Table, h) -> tuple[list[int], int]:
    with h.seat_state():
        c = wizard.combatant(t.world)
    return list(c["attack_pool"]), int(c["weave_size"])


# ------------------------------------------------------------------ the ladder itself

def test_the_world_starts_at_three_by_three_and_the_ladder_is_configuration():
    t = solo()
    joe = t.people[0]
    v = joe.state()["progression"]
    assert v["rung"] == 0 and v["colours"] == [0, 1, 6] and v["colour_names"] == ["Flame", "Frost", "Vine"] and v["weave"] == 3 and v["duels"] == 0
    assert v["next"]["id"] == "light" and v["next"]["in_duels"] == 3 and 11.0 <= v["next"]["in_minutes"] <= 12.0
    assert [r["id"] for r in progression.rungs()] == ["light", "weave4", "stone", "shadow"]
    f = pvp.make_format(None, t.world)
    assert (f["slots"], f["colours"], f["pool"]) == (3, 3, [0, 1, 6]), "a PvP duel plays the same three colours as the lessons (Vine, not Stone)"
    assert my_pool(t, joe) == ([0, 1, 6], 3)
    assert pvp.make_format("classic", t.world)["pool"] == [0, 1, 6, 4, 3, 5], "a named format is as named, in the ladder's order"


def test_three_duels_of_any_kind_bring_the_fourth_colour_to_everyone_and_the_mentor_says_so():
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    fight_rats(t, joe, 2)
    assert progression.state(t.world)["rung"] == 0 and not rungs_told(joe)
    fight_rats(t, joe, 1)
    t.advance(0.5)
    st = progression.state(t.world)
    assert st["duels"] == 3 and st["rung"] == 1 and st["history"][0]["by"] == "duels"
    assert progression.colours(t.world) == [0, 1, 6, 4] and progression.weave(t.world) == 3
    assert my_pool(t, joe) == ([0, 1, 6, 4], 3), "the apprentice's own duels have the colour"
    with party.as_player(t.world, ai.link.id):
        assert 4 in wizard.spells(t.world), "Mira has it the same moment"
    f = pvp.make_format(None, t.world)
    assert (f["slots"], f["colours"], f["pool"]) == (3, 4, [0, 1, 6, 4])
    bring_together(t, joe, ai)
    assert joe.op("pvp_challenge", target=ai.link.id)["format"]["colours"] == 4
    told = rungs_told(joe)
    assert len(told) == 1 and told[0]["id"] == "light" and told[0]["rung"] == 1 and told[0]["gain"].startswith("a fourth colour")
    assert told[0]["speaker"] == "mentor" and told[0]["text"] and "{" not in told[0]["text"], told[0]
    assert told[0]["colours"] == [0, 1, 6, 4] and told[0]["weave"] == 3
    assert not progression.state(t.world)["pending"], "told once"


def test_an_hour_of_play_brings_four_slots_and_six_colours_without_a_single_duel():
    t = solo()
    joe = t.people[0]
    seen = []
    for minute in range(62):
        t.advance(60, step_ms=500)
        for n in rungs_told(joe):
            seen.append((minute + 1, n["id"], n["by"]))
    st = progression.state(t.world)
    assert st["duels"] == 0 and st["rung"] == 4, st
    assert [s[1] for s in seen] == ["light", "weave4", "stone", "shadow"] and all(s[2] == "time" for s in seen), seen
    assert seen[0][0] <= 13 and seen[1][0] <= 26 and seen[2][0] <= 41 and seen[3][0] <= 61, seen
    assert progression.colours(t.world) == [0, 1, 6, 4, 3, 5] and progression.weave(t.world) == 4
    assert my_pool(t, joe) == ([0, 1, 6, 4, 3, 5], 4)
    f = pvp.make_format("auto", t.world)
    assert (f["slots"], f["colours"], f["pool"]) == (4, 6, [0, 1, 6, 4, 3, 5])
    v = joe.state()["progression"]
    assert v["next"] is None and v["played_min"] >= 60


def test_whichever_trigger_comes_first_fires_and_the_other_is_not_counted_twice():
    t = solo()
    joe = t.people[0]
    fight_rats(t, joe, 2)
    progression.state(t.world)["played_ms"] = 12 * 60000 - 2000
    t.advance(4)
    st = progression.state(t.world)
    assert st["rung"] == 1 and st["history"][0]["by"] == "time", st["history"]
    fight_rats(t, joe, 3)  # five duels: the fourth slot, by duels, even though the clock is nowhere near 25 minutes
    st = progression.state(t.world)
    assert st["duels"] == 5 and st["rung"] == 2 and st["history"][1] == {**st["history"][1], "id": "weave4", "by": "duels"}
    assert progression.weave(t.world) == 4 and my_pool(t, joe)[1] == 4
    assert [n["id"] for n in rungs_told(joe)] == ["light", "weave4"]


def test_a_due_rung_interrupts_a_conversation_but_waits_for_a_duel_on_the_board():
    t = solo()
    joe = t.people[0]
    inf = pests.live(t.world)
    # a story duel is open: the clock passes the rung, nothing is told until the board closes
    pid = pests.pests_of(t.world, inf)[0]
    r = __import__("wizard_rts.narrative.residents", fromlist=["table"]).table(t.world)[pid]
    joe.pose["tx"], joe.pose["ty"] = r["tile"][0] + 1, r["tile"][1]
    if (joe.pose["tx"], joe.pose["ty"]) in t.world.blocked:
        joe.pose["tx"], joe.pose["ty"] = r["tile"][0], r["tile"][1] + 1
    started = joe.op("pest_fight", target=pid)
    assert started["status"] == "started", started
    rec = started["duel_lease"]["payload"]["duel"]
    assert rec["encounter"]["player_combatant"]["attack_pool"] == [0, 1, 6], "the duel already on the board keeps its format"
    progression.state(t.world)["played_ms"] = 12 * 60000
    t.advance(3)
    assert progression.state(t.world)["rung"] == 1 and str(joe.id) in progression.state(t.world)["pending"] and not rungs_told(joe)
    joe.op("duel_resolve", duel_id=rec["id"], **play(rec, win=True))
    t.advance(0.5)
    told = rungs_told(joe)
    assert len(told) == 1 and told[0]["id"] == "light" and not told[0]["interrupted"]
    # a conversation is open: the rung closes it (the owner's rule) and says so
    k = inf["keeper"]
    joe.stand_by_resident(k)
    assert joe.op("talk", npc=k)["status"] == "ok"
    progression.state(t.world)["played_ms"] = 25 * 60000
    t.advance(3)
    told = rungs_told(joe)
    assert len(told) == 1 and told[0]["id"] == "weave4" and told[0]["interrupted"] is True
    from wizard_rts.narrative import conversation

    with joe.seat_state():
        assert not conversation.table(t.world), "the keeper was interrupted"
    # a PvP duel on the board: the rung waits for it too
    ai = ai_of(t)
    bring_together(t, joe, ai)
    duel = accept_and_lock(t, joe, ai, ward=(0, 1, 6, 4))
    progression.state(t.world)["played_ms"] = 40 * 60000
    t.advance(3)
    assert progression.state(t.world)["rung"] == 3 and not rungs_told(joe), "Stone waits: a duel is on the board"
    assert duel.fmt["slots"] == 4 and duel.fmt["colours"] == 4, "and that duel keeps the format it began with"
    joe.op("pvp_forfeit")
    t.advance(2)
    assert [n["id"] for n in rungs_told(joe)] == ["stone"]


def test_mira_duels_at_the_worlds_format_and_can_win_or_lose_a_four_by_six_duel():
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    progression.state(t.world).update(played_ms=61 * 60000)
    t.advance(2)
    assert progression.state(t.world)["rung"] == 4
    bring_together(t, joe, ai)
    duel = accept_and_lock(t, joe, ai, ward=(0, 4, 3, 5))
    assert (duel.fmt["slots"], duel.fmt["colours"], duel.fmt["pool"]) == (4, 6, [0, 1, 6, 4, 3, 5])
    assert len(duel.wards[ai.link.id]) == 4 and set(duel.wards[ai.link.id]) <= set(duel.fmt["pool"]), "her Ward is four of the six"
    me = Combatant(id="j", weave_size=4, attack_pool=duel.fmt["pool"], ward_size=4, ward_pool=duel.fmt["pool"])
    bot = WeaveBot(me, me, 3)
    for i in range(10):
        if duel.state != "active":
            break
        g = bot.make_guess()
        r = joe.op("pvp_cast", attack=g, cast_seq=i + 1)
        if r.get("status") == "ok":
            bot.register_feedback(g, r["fracture"], r["echo"])
        t.advance(2.5)  # a slow human: she gets her guesses in
    for _ in range(40):
        if duel.state == "finished":
            break
        t.advance(1)
    assert duel.state == "finished" and duel.result is not None
    assert all(len(h["attack"]) == 4 and set(h["attack"]) <= set(duel.fmt["pool"]) for h in duel.history[ai.link.id]), "every cast of hers is four of the six"


# ------------------------------------------------------------------ it belongs to the world

def test_the_ladder_survives_death_a_new_apprentice_save_load_and_the_catch_up():
    t = solo()
    joe = t.people[0]
    fight_rats(t, joe, 3)
    assert progression.state(t.world)["rung"] == 1
    # a new apprentice in the same world (the host retires their wizard): the rung stays, the new wizard has the colour from the first moment
    r = joe.op("new_game")
    assert r["status"] == "ok" and r["new_wizard"] and party.generation(t.world) == 2
    assert progression.state(t.world)["rung"] == 1 and progression.state(t.world)["duels"] == 3
    assert my_pool(t, joe) == ([0, 1, 6, 4], 3)
    # death, the ending, the save, and a reopened host
    mortality.die(t.world, joe.id, "trap", terminal=False)
    t.session.tick(t.now)
    assert t.session.ending is not None
    persist.save_world(t.world, persist.slot_path("campaign", "quit"))
    world, info = nethost.prepare_world("campaign", 507, "small")
    assert info["loaded"]
    t2 = Table(humans=1, ai=1, world=world)
    joe2 = t2.people[0]
    t2.advance(1)
    assert progression.state(t2.world)["rung"] == 1 and progression.state(t2.world)["duels"] == 3 and party.generation(t2.world) == 3
    assert my_pool(t2, joe2) == ([0, 1, 6, 4], 3) and joe2.state()["progression"]["colours"] == [0, 1, 6, 4]
    # the catch-up is not play: the clock does not move while the world runs on its own
    before = progression.state(t2.world)["played_ms"]
    t2.world.catching_up = True
    t2.advance(15 * 60, step_ms=1000)
    assert progression.state(t2.world)["played_ms"] == before and progression.state(t2.world)["rung"] == 1
    t2.world.catching_up = False
    t2.advance(60, step_ms=1000)
    assert progression.state(t2.world)["played_ms"] == before + 60_000


def test_a_world_from_before_the_ladder_is_back_filled_from_what_it_counted():
    t = solo()
    joe = t.people[0]
    fight_rats(t, joe, 2)
    t.world.narrative.pop("progression")
    ledger.bump(t.world, "pvp_duels", seat=joe.id)  # the two bumps one PvP duel makes
    ledger.bump(t.world, "pvp_duels", seat="other")
    st = progression.state(t.world)
    assert st["duels"] == 3 and st["rung"] == 0, "two story duels and one PvP duel, counted once each; nothing fires until the next event"
    fight_rats(t, joe, 1)
    assert progression.state(t.world)["rung"] == 1


def test_an_authored_ward_keeps_the_duels_size_and_the_dwarfs_stone_is_not_counted_twice():
    t = solo()
    joe = t.people[0]
    progression.state(t.world).update(played_ms=26 * 60000)
    t.advance(2)
    assert progression.weave(t.world) == 4 and progression.colours(t.world) == [0, 1, 6, 4]
    with joe.seat_state():
        r = duel_lease.begin(t.world, "opponent.teacher_told", purpose="told_ward", fixed_ward=[1, 6, 1])
        assert r["status"] == "started"
        enc = r["payload"]["duel"]["encounter"]
        assert enc["player_combatant"]["weave_size"] == 3 and enc["enemy_combatant"]["ward_size"] == 3 and enc["enemy_combatant"]["fixed_ward"] == [1, 6, 1], "the lesson's Ward of three stays a duel of three"
        assert enc["player_combatant"]["attack_pool"] == [0, 1, 6, 4], "with the colours the world has"
        duel_lease.abandon(t.world, "test")
        r = duel_lease.begin(t.world, "opponent.rat", purpose="pest:x")
        enc = r["payload"]["duel"]["encounter"]
        assert enc["player_combatant"]["weave_size"] == 4 and enc["enemy_combatant"]["ward_size"] == 4 and enc["enemy_combatant"]["ward_pool"] == [1, 6], "a rat's Ward grows with the weave but keeps its two colours"
        duel_lease.abandon(t.world, "test")
        wizard.learn(t.world, [3])  # the Dwarf's Stone, personal
        assert wizard.combatant(t.world)["attack_pool"] == [0, 1, 6, 4, 3]
    progression.state(t.world).update(played_ms=41 * 60000)
    t.advance(2)
    assert progression.colours(t.world) == [0, 1, 6, 4, 3] and my_pool(t, joe) == ([0, 1, 6, 4, 3], 4), "Stone once, not twice"

"""The village (plan M4, the brief's scenario C): the Central Warehouse's rats are real pests in a real warehouse, fought through Ward Duel leases,
with a keeper who reacts to how the apprentices behaved; two small situations among the settlement's own people; the mentor's log from the store."""
from __future__ import annotations

import pytest
from _party import Table
from test_mortality import duel_to_the_death
from test_wizard_duel_lease import play

from wizard_rts.narrative import ledger, mortality, pests, quests, residents, wizard


def fight_pest(t: Table, h, pid: str, win: bool = True) -> dict:
    r = residents.table(t.world)[pid]
    h.pose["tx"], h.pose["ty"] = r["tile"][0] + 1, r["tile"][1]
    if (h.pose["tx"], h.pose["ty"]) in t.world.blocked:
        h.pose["tx"], h.pose["ty"] = r["tile"][0], r["tile"][1] + 1
    started = h.op("pest_fight", target=pid)
    assert started["status"] == "started", started
    rec = started["duel_lease"]["payload"]["duel"]
    return h.op("duel_resolve", duel_id=rec["id"], **play(rec, win=win))


def clear_warehouse(t: Table, people, inf) -> None:
    """Fight every rat until none is left (a careful fight against the big rat is usually, not always, won)."""
    for _ in range(30):
        left = pests.pests_of(t.world, inf)
        if not left:
            return
        for i, pid in enumerate(list(left)):
            fight_pest(t, people[i % len(people)], pid, win=True)
    raise AssertionError("the warehouse never cleared")


def keeper_talk(t: Table, h) -> dict:
    keeper = next(iter(pests.state(t.world)["keepers"].values()))  # the keeper stays even when the warehouse is a ruin
    h.stand_by_resident(keeper)
    reply = h.op("talk", npc=keeper)
    assert reply["status"] == "ok", reply
    return reply


def test_the_rats_live_at_the_real_warehouse_and_eat_its_food():
    t = Table(humans=1)
    sid, b = pests.home(t.world)
    inf = pests.live(t.world)
    assert inf and inf["warehouse"] == b["id"] and len(pests.pests_of(t.world, inf)) == pests.settings()["count"]
    for pid in inf["pests"]:
        r = residents.table(t.world)[pid]
        assert r["role"] == "pest" and r["hostile"] and max(abs(r["tile"][0] - b["tx"]), abs(r["tile"][1] - b["ty"])) <= pests.RADIUS + 1
    rows = [e for e in t.world.snapshot()["entities"] if e.get("pest")]
    assert len(rows) == len(inf["pests"]) and {e["figure"] for e in rows} == {"pest:dagger", "pest:crawler"}
    assert any(e["pest"]["size"] == "big" for e in rows)
    before = sum(int(t.world.stocks[b["id"]].get(g, 0)) for g in pests.FOOD)
    t.advance(70)
    after = sum(int(t.world.stocks[b["id"]].get(g, 0)) for g in pests.FOOD)
    assert after < before and inf["eaten_total"] >= 1, "they eat the store"
    assert int(t.world.stocks["narrative:eaten"].get("ration", 0)) >= 1, "eaten wares go to a bin, nothing vanishes from the ledger"
    assert t.people[0].op("talk", npc=inf["pests"][0])["reason"] == "pest", "you do not talk to a rat"


def test_a_rat_is_fought_through_a_brief_ward_duel_and_a_win_removes_it():
    t = Table(humans=1)
    joe = t.people[0]
    inf = pests.live(t.world)
    pid = next(p for p in inf["pests"] if residents.table(t.world)[p]["pest"]["size"] == "small")
    far = joe.op("pest_fight", target=pid)
    assert far["reason"] == "too_far"
    r = residents.table(t.world)[pid]
    joe.pose["tx"], joe.pose["ty"] = r["tile"][0] + 1, r["tile"][1]
    started = joe.op("pest_fight", target=pid)
    assert started["status"] == "started"
    enc = started["duel_lease"]["payload"]["duel"]["encounter"]
    assert enc["enemy_combatant"]["ward_pool"] == [1, 6] and enc["enemy_combatant"]["max_casts"] == 4 and enc["enemy_combatant"]["display_name"] == "A rat"
    assert enc["player_combatant"]["attack_pool"] == [0, 1, 6], "the apprentice's own colours"
    rec = started["duel_lease"]["payload"]["duel"]
    out = joe.op("duel_resolve", duel_id=rec["id"], **play(rec, win=True))
    assert out["outcome"] == "won" and out["pest"]["killed"] and out["pest"]["left"] == len(inf["pests"]) - 1
    assert pid not in residents.table(t.world) and pid not in pests.pests_of(t.world, inf) and t.world.dmb.people[pid]["alive"] is False
    assert ledger.count(t.world, "pests_killed", joe.id) == 1
    assert any(n["kind"] == "pest_killed" for n in joe.state()["notices"])


def test_losing_to_a_rat_wounds_the_apprentice_and_the_rat_scurries_off():
    t = Table(humans=1)
    joe = t.people[0]
    inf = pests.live(t.world)
    pid = inf["pests"][1]
    before = list(residents.table(t.world)[pid]["tile"])
    out = fight_pest(t, joe, pid, win=False)
    assert out["outcome"] in ("lost", "draw") and not out["pest"]["killed"] and out["pest"]["wounded"]
    assert pests.is_pest(t.world, pid) and not mortality.is_dead(t.world, joe.id)
    with joe.seat_state():
        assert wizard.wiz(t.world)["wounded"]
    # the next duel has one cast fewer, then it heals
    pid2 = inf["pests"][2]
    r = residents.table(t.world)[pid2]
    joe.pose["tx"], joe.pose["ty"] = r["tile"][0] + 1, r["tile"][1]
    started = joe.op("pest_fight", target=pid2)
    assert started["status"] == "started", started
    enc = started["duel_lease"]["payload"]["duel"]["encounter"]
    assert enc["player_combatant"]["max_casts"] == 5 and enc["player_combatant"]["wounded"]
    with joe.seat_state():
        assert not wizard.wiz(t.world).get("wounded")


def test_two_apprentices_clear_the_warehouse_together_and_the_keeper_knows_it():
    t = Table(humans=2)
    joe, ann = t.people
    inf = pests.live(t.world)
    reply = keeper_talk(t, joe)
    assert "Rats" in " ".join(reply["lines"]) and "what_matter" in [c["id"] for c in reply["choices"]]
    r = joe.op("choose", npc=inf["keeper"], choice="what_matter")
    assert "Stand close to one" in r["text"] and inf["complained_ms"] is not None
    r = joe.op("choose", npc=inf["keeper"], choice="not_rats")
    assert "I know a rat" in r["text"]
    joe.op("end_talk", npc=inf["keeper"])
    pids = list(inf["pests"])
    clear_warehouse(t, [joe, ann], inf)
    assert inf["cleared_ms"] is not None and pests.live(t.world) is None
    facts = pests.facts(t.world, inf["keeper"])
    assert facts["cleared"] == 1 and facts["cooperated"] == 1 and facts["killed_total"] == len(pids)
    reply = keeper_talk(t, joe)
    assert "Both of you" in " ".join(reply["lines"]), reply["lines"]
    assert ledger.count(t.world, "keeper_thanked") == 1
    joe.op("end_talk", npc=inf["keeper"])
    reply = keeper_talk(t, ann)
    assert "Both of you" in " ".join(reply["lines"]), "she gets the same thanks (once each)"


def test_the_keeper_minds_duelling_instead_and_burning_the_warehouse():
    t = Table(humans=2)
    joe, ann = t.people
    inf = pests.live(t.world)
    keeper_talk(t, joe)
    joe.op("choose", npc=inf["keeper"], choice="what_matter")
    joe.op("end_talk", npc=inf["keeper"])
    for _ in range(2):
        duel_to_the_death(t, joe, ann)
        pid = mortality.body_of(t.world, ann.id)
        joe.pose["tx"], joe.pose["ty"] = residents.table(t.world)[pid]["tile"][0] + 1, residents.table(t.world)[pid]["tile"][1]
        assert joe.op("resurrect", target=ann.id)["status"] == "started"
        t.advance(mortality.resurrect_ms() / 1000.0 + 1.5)
    t.advance(60)
    reply = keeper_talk(t, joe)
    text = " ".join(reply["lines"])
    assert "throw Wards at each other" in text and "rats eat the winter" in text, text
    joe.op("end_talk", npc=inf["keeper"])
    # burning the warehouse
    sid, b = pests.home(t.world)
    joe.pose["tx"], joe.pose["ty"] = b["tx"] + 1, b["ty"] + 1
    with joe.seat_state():
        wizard.learn(t.world, [0], 3)
    r = joe.op("fire", target=b["id"])
    if r.get("status") == "ok":
        assert inf["burned_by"] == [joe.id] and ledger.count(t.world, "burned_warehouse", joe.id) == 1
        reply = keeper_talk(t, joe)
        assert "set fire to my warehouse" in " ".join(reply["lines"])


def test_mira_joins_once_somebody_has_heard_the_keeper_and_fights_on_the_core():
    t = Table(humans=1, ai=1)
    joe = t.people[0]
    (ai,) = t.session.ais.values()
    inf = pests.live(t.world)
    t.advance(20)
    assert len(pests.pests_of(t.world, inf)) == len(inf["pests"]), "she does not go hunting on her own"
    keeper_talk(t, joe)
    joe.op("choose", npc=inf["keeper"], choice="what_matter")
    joe.op("end_talk", npc=inf["keeper"])
    for _ in range(240):
        t.advance(1)
        if int(inf["killed_by"].get(ai.link.id, 0)) >= 1:
            break
    assert int(inf["killed_by"].get(ai.link.id, 0)) >= 1, "Mira walked to a rat and fought it"
    lines = [n["line"] for n in joe.state()["notices"] if n["kind"] == "ai_says"]
    assert "rat_won" in lines or "rat_lost" in lines
    with ai.link and __import__("wizard_rts.narrative.party", fromlist=["party"]).as_player(t.world, ai.link.id):
        assert wizard.wiz(t.world)["duels"]["attempts"], "her duel was a verified lease like anybody's"


def test_a_smaller_wave_returns_after_the_warehouse_is_cleared(monkeypatch):
    monkeypatch.setitem(pests.config._file()["pests"], "return_ms", 30_000)
    t = Table(humans=1)
    joe = t.people[0]
    inf = pests.live(t.world)
    clear_warehouse(t, [joe], inf)
    assert pests.live(t.world) is None
    t.advance(35)
    again = pests.live(t.world)
    assert again is not None and again["wave"] == 2 and len(again["pests"]) == pests.settings()["return_count"]
    reply = keeper_talk(t, joe)
    assert "They are back" in " ".join(reply["lines"])


def test_the_missing_granite_costs_the_store_a_load_only_when_the_mason_is_backed():
    t = Table(humans=1)
    joe = t.people[0]
    with joe.seat_state():
        from wizard_rts.narrative import tutorial

        for lesson in ("meet", "colours", "told_ward", "hidden_ward"):
            wizard.complete_lesson(t.world, lesson)
    t.advance(4)
    r = quests.rec(t.world, "smith_dispute")
    assert r and r["status"] == "cast", r
    sid, b = pests.home(t.world)
    granite = int(t.world.stocks[b["id"]].get("granite", 0))
    mason, hauler = r["bindings"]["mason"], r["bindings"]["hauler"]
    joe.stand_by(mason["kind"], mason["id"])
    assert joe.op("talk", npc=mason["id"])["status"] == "ok"
    joe.op("choose", npc=mason["id"], choice="what_happened")
    joe.op("end_talk", npc=mason["id"])
    joe.stand_by(hauler["kind"], hauler["id"])
    assert joe.op("talk", npc=hauler["id"])["status"] == "ok"
    joe.op("choose", npc=hauler["id"], choice="what_happened")
    joe.op("end_talk", npc=hauler["id"])
    joe.stand_by(mason["kind"], mason["id"])
    joe.op("talk", npc=mason["id"])
    out = joe.op("choose", npc=mason["id"], choice="back_mason")
    assert out["status"] == "ok" and out["ware"]["ok"]
    assert int(t.world.stocks[b["id"]].get("granite", 0)) == granite - 1 and int(t.world.stocks["narrative:consumed"]["granite"]) == 1
    assert quests.status(t.world, "smith_dispute") in ("active", "done")


def test_the_patrol_is_where_the_trial_is_first_spoken_of():
    t = Table(humans=1)
    joe = t.people[0]
    with joe.seat_state():
        for lesson in ("meet", "colours", "told_ward", "hidden_ward"):
            wizard.complete_lesson(t.world, lesson)
    t.advance(4)
    r = quests.rec(t.world, "ranger_patrol")
    assert r and r["status"] == "cast", r
    ranger = r["bindings"]["ranger"]
    joe.stand_by(ranger["kind"], ranger["id"])
    assert joe.op("talk", npc=ranger["id"])["status"] == "ok"
    joe.op("choose", npc=ranger["id"], choice="ask_patrol")
    out = joe.op("choose", npc=ranger["id"], choice="why_east")
    assert "gate" in out["text"] and "Trial" in out["text"]
    with joe.seat_state():
        assert wizard.knows_fact(t.world, "trial_rumour")


def test_the_mentor_asks_for_a_log_and_the_keeper_gives_one_from_the_real_store():
    t = Table(humans=1)
    joe = t.people[0]
    joe.stand_by_resident(t.mentor)
    joe.op("talk", npc=t.mentor)
    r = joe.op("choose", npc=t.mentor, choice="need_anything")
    assert "log" in r["text"]
    joe.op("end_talk", npc=t.mentor)
    sid, b = pests.home(t.world)
    logs = int(t.world.stocks[b["id"]].get("log", 0))
    inf = pests.live(t.world)
    reply = keeper_talk(t, joe)
    assert "log_for_mentor" in [c["id"] for c in reply["choices"]]
    out = joe.op("choose", npc=inf["keeper"], choice="log_for_mentor")
    assert out["ware"]["ok"] and int(t.world.stocks[b["id"]].get("log", 0)) == logs - 1
    joe.op("end_talk", npc=inf["keeper"])
    joe.stand_by_resident(t.mentor)
    reply = joe.op("talk", npc=t.mentor)
    assert "You brought the log" in " ".join(reply["lines"])


# ---------------------------------------------------------------- burning the rats, the ruin, the waves' end, the journal (18 Oct 2026, plan section 5)

def burn_rat(t: Table, h, pid: str) -> dict:
    r = residents.table(t.world)[pid]
    h.pose["tx"], h.pose["ty"] = r["tile"][0] + 1, r["tile"][1]
    if (h.pose["tx"], h.pose["ty"]) in t.world.blocked:
        h.pose["tx"], h.pose["ty"] = r["tile"][0], r["tile"][1] + 1
    return h.op("fire", target=pid)


def test_a_small_rat_burns_like_anything_else_and_the_big_one_takes_two():
    t = Table(humans=1)
    joe = t.people[0]
    inf = pests.live(t.world)
    small = next(p for p in inf["pests"] if residents.table(t.world)[p]["pest"]["size"] == "small")
    big = next(p for p in inf["pests"] if residents.table(t.world)[p]["pest"]["size"] == "big")
    far = joe.op("fire", target=small)
    assert far["reason"] == "too_far", far
    r = burn_rat(t, joe, small)
    assert r["status"] == "ok" and r["class"] == "pest" and r["killed"] and r["how"] == "burned", r
    assert small not in residents.table(t.world) and t.world.dmb.people[small]["alive"] is False
    assert ledger.count(t.world, "pests_killed", joe.id) == 1 and ledger.count(t.world, "pests_burned", joe.id) == 1
    assert any(n["kind"] == "pest_killed" and n.get("how") == "burned" for n in joe.state()["notices"])
    t.advance(1)
    r = burn_rat(t, joe, big)
    assert r["status"] == "ok" and not r["killed"] and r["scorched"], r
    assert pests.is_pest(t.world, big) and residents.table(t.world)[big]["pest"]["scorched"]
    t.advance(1)
    r = burn_rat(t, joe, big)
    assert r["status"] == "ok" and r["killed"], r
    assert big not in residents.table(t.world)
    assert inf["burned"][joe.id] == 2 and len(pests.pests_of(t.world, inf)) == len(inf["pests"]) - 2


def test_a_rat_burned_beside_the_warehouse_takes_a_food_ware_with_it_and_the_keeper_minds():
    t = Table(humans=1)
    joe = t.people[0]
    inf = pests.live(t.world)
    sid, b = pests.home(t.world)
    keeper_talk(t, joe)
    joe.op("choose", npc=inf["keeper"], choice="what_matter")
    joe.op("end_talk", npc=inf["keeper"])
    food_before = pests.food_left(t.world)
    small = next(p for p in inf["pests"] if residents.table(t.world)[p]["pest"]["size"] == "small")
    row = residents.table(t.world)[small]
    beside_tiles = [(b["tx"] + dx, b["ty"] + dy) for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1), (1, 1)) if (b["tx"] + dx, b["ty"] + dy) not in t.world.blocked]
    row["tile"] = [beside_tiles[0][0], beside_tiles[0][1]]
    t.world.dmb.people[small]["position"] = list(row["tile"])
    r = burn_rat(t, joe, small)
    assert r["status"] == "ok" and r["killed"]
    assert inf["food_burned"] == 1 and pests.food_left(t.world) <= food_before - 1
    assert sum(int(v) for v in t.world.stocks[pests.BURNED_BIN].values()) >= 1, "the ware went to a bin, nothing vanished from the ledger"
    reply = keeper_talk(t, joe)
    text = " ".join(reply["lines"])
    assert "Smoke in my grain store" in text and "1 loads" in text, text
    joe.op("end_talk", npc=inf["keeper"])
    for pid in list(pests.pests_of(t.world, inf)):
        for _ in range(2):
            if pests.is_pest(t.world, pid):
                t.advance(1)
                burn_rat(t, joe, pid)
    assert inf["cleared_ms"] is not None
    reply = keeper_talk(t, joe)
    assert "cooked" in " ".join(reply["lines"]), reply["lines"]


def test_a_burned_warehouse_scatters_the_rats_and_the_keeper_keeps_nothing():
    t = Table(humans=1)
    joe = t.people[0]
    inf = pests.live(t.world)
    sid, b = pests.home(t.world)
    joe.pose["tx"], joe.pose["ty"] = b["tx"] + 1, b["ty"] + 1
    assert joe.op("fire", target=b["id"])["status"] == "ok"
    t.advance(3)
    assert inf["ended"] == "burned" and pests.live(t.world) is None and not pests.pests_of(t.world, inf)
    assert all(residents.table(t.world)[p]["status"] == "gone" for p in inf["pests"])
    reply = keeper_talk(t, joe)
    text = " ".join(reply["lines"])
    assert "set fire to my warehouse" in text, text
    joe.op("end_talk", npc=inf["keeper"])
    reply = keeper_talk(t, joe)
    assert "There is no warehouse" in " ".join(reply["lines"]), reply["lines"]
    joe.op("end_talk", npc=inf["keeper"])
    with joe.seat_state():
        from wizard_rts.narrative import tutorial

        j = tutorial.snapshot(t.world)["quests"]
    assert j and j[0]["id"] == "rats" and j[0]["status"] == "done" and "burned" in j[0]["objective"]
    t.advance(40)
    assert pests.live(t.world) is None, "no wave comes to a ruin"


def test_the_keeper_thanks_again_each_wave_and_says_when_it_is_over(monkeypatch):
    monkeypatch.setitem(pests.config._file()["pests"], "return_ms", 20_000)
    monkeypatch.setitem(pests.config._file()["pests"], "max_waves", 3)
    t = Table(humans=1)
    joe = t.people[0]
    said = []
    for wave in range(3):
        inf = pests.live(t.world)
        if inf is None:
            t.advance(25)
            inf = pests.live(t.world)
        assert inf is not None and inf["wave"] == wave + 1
        if wave:
            reply = keeper_talk(t, joe)
            assert f"Wave {wave + 1}" in " ".join(reply["lines"]), reply["lines"]
            joe.op("end_talk", npc=inf["keeper"])
        clear_warehouse(t, [joe], inf)
        reply = keeper_talk(t, joe)
        said.append(" ".join(reply["lines"]))
        joe.op("end_talk", npc=inf["keeper"])
    assert all("All of them" in s for s in said[:2]), said
    assert "That was the last of them" in said[2], said[2]
    t.advance(30)
    assert pests.live(t.world) is None, "no fourth wave"
    with joe.seat_state():
        from wizard_rts.narrative import tutorial

        j = tutorial.snapshot(t.world)["quests"]
    assert j[0]["id"] == "rats" and j[0]["status"] == "done" and "for good" in j[0]["objective"]


def test_the_journal_lists_the_rats_once_the_apprentice_has_seen_them_and_the_keeper_minds_a_run_of_losses():
    t = Table(humans=1)
    joe = t.people[0]
    inf = pests.live(t.world)
    sid, b = pests.home(t.world)
    joe.pose["tx"], joe.pose["ty"] = b["tx"] + 30, b["ty"] + 30
    t.advance(2)
    with joe.seat_state():
        from wizard_rts.narrative import tutorial

        q = tutorial.snapshot(t.world)["quests"]
        assert not q or q[0]["id"] != "rats", "not seen yet"
    joe.pose["tx"], joe.pose["ty"] = b["tx"] + 6, b["ty"]
    t.advance(2)
    assert str(joe.id) in inf["noticed"]
    assert any(n["kind"] == "pests_noticed" for n in joe.state()["notices"])
    with joe.seat_state():
        j = tutorial.snapshot(t.world)["quests"]
        assert j[0]["id"] == "rats" and j[0]["status"] == "active" and "5 of 5" in j[0]["objective"]
        assert any(n["source"] == "rats" for n in wizard.wiz(t.world)["journal_notes"])
    for _ in range(3):
        fight_pest(t, joe, pests.pests_of(t.world, inf)[0], win=False)
        t.advance(1)
    reply = keeper_talk(t, joe)
    assert "not laughing" in " ".join(reply["lines"]), reply["lines"]


def test_the_rats_scurry_and_freeze_beside_a_wizard():
    t = Table(humans=1)
    joe = t.people[0]
    inf = pests.live(t.world)
    pid = inf["pests"][2]
    joe.pose["tx"], joe.pose["ty"] = 5, 5
    seen = {tuple(residents.table(t.world)[pid]["tile"])}
    for _ in range(12):
        t.advance(2)
        seen.add(tuple(residents.table(t.world)[pid]["tile"]))
    assert len(seen) >= 2, "a rat moves about the store"
    r = residents.table(t.world)[pid]
    joe.pose["tx"], joe.pose["ty"] = r["tile"][0] + 1, r["tile"][1]
    before = list(r["tile"])
    for _ in range(6):
        t.advance(2)
    assert list(residents.table(t.world)[pid]["tile"]) == before, "it stands still with the wizard beside it"

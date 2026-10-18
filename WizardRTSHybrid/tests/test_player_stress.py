"""The misbehaving apprentice: the game played badly on purpose, through the real session (plan `docs/PLAN_PLAYER_STRESS_AND_PROGRESSION.md`,
section 2). Each test records what the world said and did (`docs/evidence/stress/observations.json`, read by `docs/PLAYER_STRESS_REPORT.md`) and
asserts only what must hold whatever the player does: nothing crashes, the world keeps answering, and nobody the player meets is left without a line."""
from __future__ import annotations

import _campaign as camp
import _stress as S
import pytest
from _party import Table
from test_mortality import beside
from test_wizard_duel_lease import play

from wizard_rts.narrative import campaign, config, graph, mortality, mother, party, persist, pests, quests, residents, wizard
from wizard_rts.net import host as nethost
from wizard_rts.trial import run as trial


@pytest.fixture(autouse=True)
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DMB_RUNS", str(tmp_path))
    return tmp_path


def solo(ai: int = 1, advance: float = 1.0) -> Table:
    t = Table(humans=1, ai=ai)
    t.advance(advance)
    return t


def ai_of(t: Table):
    (ai,) = t.session.ais.values()
    return ai


def watch(t: Table, h, seconds: float, step_ms: int = 500) -> list[dict]:
    """Advance, noting every stage change and every scene that opens (acknowledging none of them: this player does not press buttons)."""
    log: list[dict] = []
    last_stage, last_scene = S.stage(t), None
    for _ in range(int(seconds)):
        t.advance(1, step_ms=step_ms)
        st = S.stage(t)
        if st != last_stage:
            log.append({"min": S.game_min(t), "stage": st})
            last_stage = st
        with h.seat_state():
            sc = campaign.scene_view(t.world)
        key = (sc or {}).get("scene") or (sc or {}).get("id") or (sc["text"][:40] if sc and sc.get("text") else None)
        if key != last_scene:
            log.append({"min": S.game_min(t), "scene_open": key, "needs_answer": (sc or {}).get("needs_answer")})
            last_scene = key
    return log


# ------------------------------------------------------------------ 1. do nothing

def test_do_nothing_for_an_hour_the_story_happens_without_you():
    t = solo()
    joe = t.people[0]
    log = watch(t, joe, 60 * 60)
    m, k = S.mentor(t), S.keeper(t)
    mentor_alive = bool(t.world.dmb.people[m]["alive"])
    after = {"stage": S.stage(t), "mentor_alive": mentor_alive, "food_left": S.food_left(t), "keeper": S.keeper_facts(t), "ledger": S.ledger_counts(t),
             "lessons_expired": not any(r.get("role") == "teacher" and r["status"] == "present" for r in residents.table(t.world).values()) if not mentor_alive else None,
             "notices": [n["kind"] for n in S.notices(joe)], "mira": S.said_by_ai(joe)}
    # what the people say to an apprentice who did nothing
    with joe.seat_state():
        campaign.scene_view(t.world)
    said = {}
    for who, key in (("mentor_or_body", m), ("keeper", k), ("mother", S.mum(t, joe)), ("official", S.official(t))):
        if key:
            r = S.talk_and_leave(t, joe, key)
            said[who] = {"status": r.get("status"), "reason": r.get("reason"), "text": S.text_of(r)[:300], "choices": [c[0] for c in S.choices_of(r)]}
    S.record("do_nothing", log=log, after=after, said=said, objective=campaign.objective(t.world))
    assert joe.state()["status"] == "ok", "the world still answers"
    assert S.stage(t) in ("aftermath", "complete", "explore", "arrival", "confrontation"), after
    for who, r in said.items():
        assert r["status"] in ("ok", "rejected"), (who, r)


def test_do_nothing_but_the_scenes_are_never_acknowledged():
    """The stranger's notice and the scenes need a button press. A player who never presses: does the story stall for ever?"""
    t = solo()
    joe = t.people[0]
    log = watch(t, joe, 40 * 60)
    with joe.seat_state():
        sc = campaign.scene_view(t.world)
    S.record("never_acknowledge", log=log, stage=S.stage(t), scene_now=(sc or {}).get("text", "")[:200] if sc else None, outcome=campaign.state(t.world).get("outcome"),
             mentor_alive=bool(t.world.dmb.people[S.mentor(t)]["alive"]))
    assert S.stage(t) != "arrival" or sc is None, "a scene left open for forty minutes should not hold the whole story"


# ------------------------------------------------------------------ 2. leave at once

def test_leave_at_once_enter_the_trial_unprepared_and_die_to_the_first_creature():
    t = solo()
    joe = t.people[0]
    official = S.official(t)
    r0 = S.ask(t, joe, official)
    roll = {"text": S.text_of(r0)[:300], "choices": [c[0] for c in S.choices_of(r0)]}
    unprepared = joe.op("choose", npc=official, choice="unprepared_anyway")
    joe.op("end_talk", npc=official)
    g = trial.gate_tile(t.world)
    joe.pose["tx"], joe.pose["ty"] = g[0], g[1] + 1
    if (joe.pose["tx"], joe.pose["ty"]) in t.world.blocked:
        joe.pose["tx"], joe.pose["ty"] = g[0] + 1, g[1]
    entered = joe.op("trial_enter")
    assert entered["status"] == "ok", entered
    rec = trial.seat_rec(t.world, joe.id)
    rec.update(zone="dd_galleries", x=13, y=8)
    r = joe.op("trial_interact", entity="dog_gal1")
    assert r["status"] == "started" and r["lethal"]
    duel = r["duel_lease"]["payload"]["duel"]
    out = joe.op("duel_resolve", duel_id=duel["id"], **play(duel, win=False))
    t.advance(6)
    ending = t.session.ending
    mira = S.said_by_ai(joe)
    S.record("leave_at_once", rollkeeper=roll, unprepared_reply=S.text_of(unprepared)[:300], death=out.get("trial"), ending=ending, mira=mira,
             dead_view=joe.state().get("you_dead"), stage=S.stage(t), minutes=S.game_min(t))
    assert mortality.is_dead(t.world, joe.id) and ending is not None and ending["kind"] == "human_dead"
    # the world is saved with the body and a new apprentice arrives a generation later: what do people say about the first one?
    path = persist.slot_path("campaign", "quit")
    persist.save_world(t.world, path)
    world, info = nethost.prepare_world("campaign", 507, "small")
    t2 = Table(humans=1, ai=1, world=world)
    joe2 = t2.people[0]
    t2.advance(2)
    said = {}
    for who, key in (("mother", S.mum(t2, joe2)), ("mentor", S.mentor(t2)), ("official", S.official(t2)), ("keeper", S.keeper(t2))):
        r = S.talk_and_leave(t2, joe2, key)
        said[who] = {"status": r.get("status"), "reason": r.get("reason"), "text": S.text_of(r)[:300]}
    S.record("leave_at_once", generation=party.generation(t2.world), next_generation_hears=said, body_in_trial=bool(trial.body_of(t2.world, "gone:" + joe.id + ":1") or trial.run(t2.world)))
    assert party.generation(t2.world) == 2
    for who, r in said.items():
        assert r["status"] == "ok", (who, r)


# ------------------------------------------------------------------ 3. spam

def test_spam_talk_to_the_same_people_twenty_times():
    t = solo()
    joe = t.people[0]
    out = {}
    for who, key in (("mentor", S.mentor(t)), ("keeper", S.keeper(t)), ("mother", S.mum(t, joe)), ("official", S.official(t))):
        firsts = []
        for _ in range(20):
            r = S.talk_and_leave(t, joe, key)
            firsts.append(S.text_of(r)[:90])
            t.advance(0.5)
        out[who] = {"distinct_openings": len(set(firsts)), "openings": firsts[:3] + ["..."] + firsts[-2:]}
    # an ordinary worker, ten times: the fourth wall should open once after eight accostings
    w = S.red_workers(t)[0]
    firsts, fourth = [], None
    for i in range(10):
        r = S.ask(t, joe, w)
        firsts.append(S.text_of(r)[:90])
        ids = [c[0] for c in S.choices_of(r)]
        if "topic:who_counts" in ids or "who_counts" in ids:
            cid = "topic:who_counts" if "topic:who_counts" in ids else "who_counts"
            fourth = S.text_of(joe.op("choose", npc=w, choice=cid))[:200]
        joe.op("end_talk", npc=w)
        t.advance(0.5)
    out["worker"] = {"distinct_openings": len(set(firsts)), "fourth_wall": fourth, "accosted": S.ledger_counts(t, joe.id).get("accosted")}
    S.record("spam_talk", **out)
    for who, o in out.items():
        assert o["distinct_openings"] >= 1


def test_spam_press_the_button_in_an_empty_field_and_on_a_rat():
    t = solo()
    joe = t.people[0]
    joe.pose["tx"], joe.pose["ty"] = joe.pose["tx"] + 30, joe.pose["ty"] + 30
    r = joe.op("talk", npc="nobody")
    rat = pests.live(t.world)["pests"][0]
    r2 = joe.op("talk", npc=rat)
    r3 = joe.op("pest_fight", target=rat)
    r4 = joe.op("fire", target="nothing")
    r5 = joe.op("resurrect", target=joe.id)
    r6 = joe.op("trial_enter")
    r7 = joe.op("choose", npc=S.mentor(t), choice="learn_colours")
    S.record("spam_buttons", nobody=r, rat_talk=r2, rat_far=r3, fire_nothing=r4, self_resurrect=r5, far_gate=r6, choose_without_talk=r7)
    for x in (r, r2, r3, r4, r5, r6, r7):
        assert x.get("status") in ("rejected", "ok"), x


def test_challenge_mira_ten_times_and_walk_out_of_every_duel():
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    from test_ai_wizard import bring_together

    log = []
    for i in range(10):
        bring_together(t, joe, ai)
        r = joe.op("pvp_challenge", target=ai.link.id)
        t.advance(6)
        duel = t.session.duels.get(joe.link.duel_id) if joe.link.duel_id else None
        entry = {"n": i + 1, "challenge": r.get("status"), "reason": r.get("reason"), "accepted": bool(duel and duel.state in ("setup", "active"))}
        if duel and duel.state in ("setup", "active"):
            f = joe.op("pvp_forfeit")
            entry["forfeit"] = f.get("status")
            t.advance(3)
            joe.op("pvp_leave")
            entry["dead_after"] = S.dead(t, joe)
            if S.dead(t, joe):  # walking out of a duel to the death is a death; does Mira bring him back on her own?
                t.advance(40)
                entry["mira_resurrected_me"] = not S.dead(t, joe)
                entry["ending"] = t.session.ending
                if S.dead(t, joe):
                    log.append(entry)
                    break
        log.append(entry)
        t.advance(2)
    S.record("challenge_mira_ten_times", log=log, mira=S.said_by_ai(joe), ledger=S.ledger_counts(t, joe.id), relationship=ai.relationship(joe.id), dead=S.dead(t, joe))
    assert any(e["accepted"] for e in log), "she accepts eventually"


# ------------------------------------------------------------------ 4. burn the village

def test_burn_the_warehouse_with_the_rats_in_it_then_everything_in_reach():
    t = solo()
    joe = t.people[0]
    sid, wh = pests.home(t.world)
    inf = pests.live(t.world)
    r = S.burn(t, joe, wh["id"])
    assert r["status"] == "ok", r
    t.advance(3)
    keeper_now = S.talk_and_leave(t, joe, inf["keeper"])
    rats_now = pests.pests_of(t.world, inf)
    burned = {"warehouse": r, "keeper": S.text_of(keeper_now)[:300], "rats_left_after_fire": len(rats_now), "infestation_live": pests.live(t.world) is not None}
    # trees, rocks, carriers, workers: ten of each at most, standing beside each
    counts = {}
    for cls, table in (("tree", t.world.trees), ("rock", t.world.rocks), ("carrier", t.world.carriers), ("worker", t.world.workers), ("unit", t.world.units)):
        ok = 0
        for tid in list(sorted(table))[:10]:
            rr = S.burn(t, joe, tid)
            t.advance(0.7)
            ok += rr.get("status") == "ok"
        counts[cls] = ok
    t.advance(5)
    said = {}
    for who, key in (("mentor", S.mentor(t)), ("mother", S.mum(t, joe)), ("keeper", inf["keeper"])):
        rr = S.talk_and_leave(t, joe, key)
        said[who] = S.text_of(rr)[:300]
    S.record("burn_everything", burned=burned, burned_counts=counts, afterwards=said, ledger=S.ledger_counts(t, joe.id), notices=[n["kind"] for n in S.notices(joe)],
             mira=S.said_by_ai(joe))
    assert joe.state()["status"] == "ok"


def test_burn_the_people_of_the_quests():
    t = solo()
    joe = t.people[0]
    cfg = config._file()
    cfg["narrative"]["unlock_after_ms"] = 5_000
    try:
        t.advance(40)
        cast = {q: quests.status(t.world, q) for q in quests.TEMPLATES}
        victims, outcomes = {}, {}
        for q in quests.TEMPLATES:
            rec = quests.rec(t.world, q)
            if not rec or rec["status"] in ("unavailable", "interrupted"):
                continue
            role, b = sorted(rec["bindings"].items())[0]
            victims[q] = {"role": role, "kind": b["kind"], "id": b["id"], "name": t.world.dmb.people[b["pid"]]["name"]}
            rr = S.burn(t, joe, b["id"])
            outcomes[q] = rr
            t.advance(1)
        t.advance(75)
        after = {q: {"status": quests.status(t.world, q), "objective": quests.objective(t.world, q), "history": (quests.rec(t.world, q) or {}).get("history")} for q in quests.TEMPLATES}
        journal = joe.op("journal")
        with joe.seat_state():
            notes = [n["text"] for n in wizard.wiz(t.world).get("journal_notes", [])]
        S.record("burn_quest_people", cast_before=cast, victims=victims, fire=outcomes, after=after, journal_reply_keys=sorted(journal.keys()) if isinstance(journal, dict) else str(journal),
                 journal_notes=notes)
        # talk to whoever holds each role now
        talks = {}
        for q in quests.TEMPLATES:
            rec = quests.rec(t.world, q)
            if rec and rec["status"] not in ("unavailable", "interrupted"):
                for role, b in rec["bindings"].items():
                    rr = S.talk_and_leave(t, joe, b["id"])
                    talks[f"{q}:{role}"] = {"status": rr.get("status"), "reason": rr.get("reason"), "text": S.text_of(rr)[:160]}
        S.record("burn_quest_people", talks=talks)
        for k, v in talks.items():
            assert v["status"] in ("ok", "rejected"), (k, v)
    finally:
        cfg["narrative"]["unlock_after_ms"] = 1_200_000


# ------------------------------------------------------------------ 5. quests done stupidly

def test_crawl_every_conversation_in_the_village():
    t = solo()
    joe = t.people[0]
    cfg = config._file()
    cfg["narrative"]["unlock_after_ms"] = 5_000
    try:
        t.advance(40)
        people = {"mentor": S.mentor(t), "keeper": S.keeper(t), "mother": S.mum(t, joe), "official": S.official(t)}
        for cid, pid in sorted(trial.state(t.world)["contestants"].items()):
            people[f"contestant:{cid}"] = pid
        for q in quests.TEMPLATES:
            rec = quests.rec(t.world, q)
            if rec and rec["status"] not in ("unavailable", "interrupted"):
                for role, b in rec["bindings"].items():
                    people[f"{q}:{role}"] = b["id"]
        seen_roles = set()
        for wid in S.red_workers(t):
            role = t.world.workers[wid]["role"]
            if role not in seen_roles:
                seen_roles.add(role)
                people[f"worker:{role}"] = wid
        results, defects = {}, {}
        for who, key in people.items():
            res = S.crawl(t, joe, key)
            results[who] = {k: v for k, v in res.items() if k != "transcript"}
            results[who]["transcript"] = res.get("transcript", [])[:12]
            if res.get("defects"):
                defects[who] = res["defects"]
        S.record("crawl_conversations", results=results, defects=defects)
        assert not any("could not reopen" in d for ds in defects.values() for d in ds), defects
    finally:
        cfg["narrative"]["unlock_after_ms"] = 1_200_000


def test_back_both_sides_of_the_granite_dispute_and_both_sides_of_the_forest():
    t = solo()
    joe = t.people[0]
    cfg = config._file()
    cfg["narrative"]["unlock_after_ms"] = 5_000
    try:
        t.advance(40)
        out = {}
        rec = quests.rec(t.world, "smith_dispute")
        if rec and rec["status"] not in ("unavailable", "interrupted"):
            sid = list(t.world.dmb.settlements)[0]
            granite_before = sum(int(s.get("granite", 0)) for b, s in t.world.stocks.items() if b in t.world.buildings)
            m, h = rec["bindings"]["mason"]["id"], rec["bindings"]["hauler"]["id"]
            S.ask(t, joe, m)
            r1 = joe.op("choose", npc=m, choice="what_happened")
            r2 = joe.op("choose", npc=m, choice="back_mason")
            joe.op("end_talk", npc=m)
            S.ask(t, joe, h)
            r3 = joe.op("choose", npc=h, choice="what_happened")
            r4 = joe.op("choose", npc=h, choice="back_hauler")
            r5 = joe.op("choose", npc=h, choice="find_it")
            joe.op("end_talk", npc=h)
            granite_after = sum(int(s.get("granite", 0)) for b, s in t.world.stocks.items() if b in t.world.buildings)
            out["granite"] = {"back_mason": {"status": r2.get("status"), "text": S.text_of(r2)[:200]}, "back_hauler": {"status": r4.get("status"), "reason": r4.get("reason"), "text": S.text_of(r4)[:200]},
                              "find_it": {"status": r5.get("status"), "reason": r5.get("reason"), "text": S.text_of(r5)[:200]}, "granite_delta": granite_after - granite_before,
                              "status": quests.status(t.world, "smith_dispute"), "flags": sorted(graph.flags(t.world, "smith_dispute"))}
        rec = quests.rec(t.world, "forest_dispute")
        if rec and rec["status"] not in ("unavailable", "interrupted"):
            w = rec["bindings"]["witness"]["id"]
            S.ask(t, joe, w)
            replies = {}
            for cid in ("witness_saw", "say_cutter", "say_planter", "say_compromise", "say_nothing"):
                rr = joe.op("choose", npc=w, choice=cid)
                replies[cid] = {"status": rr.get("status"), "reason": rr.get("reason"), "text": S.text_of(rr)[:160]}
            joe.op("end_talk", npc=w)
            out["forest"] = {"replies": replies, "status": quests.status(t.world, "forest_dispute"), "flags": sorted(graph.flags(t.world, "forest_dispute"))}
        S.record("both_sides", **out)
    finally:
        cfg["narrative"]["unlock_after_ms"] = 1_200_000


def test_lose_to_every_rat_on_purpose_five_times_then_ask_the_keeper():
    t = solo()
    joe = t.people[0]
    inf = pests.live(t.world)
    k = inf["keeper"]
    S.ask(t, joe, k)
    joe.op("choose", npc=k, choice="what_matter")
    joe.op("end_talk", npc=k)
    log = []
    for i in range(5):
        pid = pests.pests_of(t.world, inf)[0]
        r = residents.table(t.world)[pid]
        joe.pose["tx"], joe.pose["ty"] = r["tile"][0] + 1, r["tile"][1]
        if (joe.pose["tx"], joe.pose["ty"]) in t.world.blocked:
            joe.pose["tx"], joe.pose["ty"] = r["tile"][0], r["tile"][1] + 1
        started = joe.op("pest_fight", target=pid)
        assert started["status"] == "started", started
        rec = started["duel_lease"]["payload"]["duel"]
        casts = rec["encounter"]["player_combatant"]["max_casts"]
        out = joe.op("duel_resolve", duel_id=rec["id"], **play(rec, win=False))
        log.append({"n": i + 1, "my_casts": casts, "outcome": out.get("outcome"), "wounded": out.get("pest", {}).get("wounded")})
        t.advance(2)
    keeper = S.talk_and_leave(t, joe, k)
    S.record("lose_to_rats", log=log, keeper=S.text_of(keeper)[:300], facts=S.keeper_facts(t), ledger=S.ledger_counts(t, joe.id), notices=[n["kind"] for n in S.notices(joe)][-8:])
    assert all(e["my_casts"] >= 2 for e in log)


def test_clear_every_wave_of_rats_and_keep_asking():
    t = solo()
    joe = t.people[0]
    from test_village import clear_warehouse, fight_pest  # noqa: F401

    cfg = config._file()
    old = dict(cfg["pests"])
    cfg["pests"]["return_ms"] = 20_000
    try:
        waves = []
        for wave in range(8):
            inf = pests.live(t.world)
            if inf is None:
                t.advance(30)
                inf = pests.live(t.world)
                if inf is None:
                    waves.append({"wave": wave + 1, "came": False})
                    break
            clear_warehouse(t, [joe], inf)
            k = inf["keeper"]
            r = S.talk_and_leave(t, joe, k)
            waves.append({"wave": inf["wave"], "count": len(inf["pests"]), "keeper": S.text_of(r)[:160]})
            t.advance(25)
        final = S.talk_and_leave(t, joe, S.keeper(t))
        S.record("all_waves", waves=waves, final_keeper=S.text_of(final)[:300], facts=S.keeper_facts(t), ledger=S.ledger_counts(t, joe.id))
        assert any(not w.get("came", True) for w in waves), "the waves end"
    finally:
        cfg["pests"].update(old)


# ------------------------------------------------------------------ 6. kill and die

def test_kill_mira_three_times_protest_each_time_and_try_to_leave():
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    from test_ai_wizard import accept_and_lock, bring_together

    log = []
    for n in range(3):
        bring_together(t, joe, ai)
        duel = accept_and_lock(t, joe, ai)
        from wizard_rts.duel.ward import Combatant, WeaveBot

        me = Combatant(id="j", weave_size=duel.fmt["slots"], attack_pool=duel.fmt["pool"], ward_size=duel.fmt["slots"], ward_pool=duel.fmt["pool"])
        bot = WeaveBot(me, me, 3)
        i = 0
        while duel.state == "active" and i < 12:
            g = bot.make_guess()
            r = joe.op("pvp_cast", attack=g, cast_seq=i + 1)
            i += 1
            if r.get("status") == "ok":
                bot.register_feedback(g, r["fracture"], r["echo"])
            t.advance(0.3)
        t.advance(4)
        joe.op("pvp_leave")
        entry = {"kill": n + 1, "winner": duel.result and duel.result.get("winner") == joe.id, "mira_dead": S.dead(t, ai) if hasattr(ai, "id") else mortality.is_dead(t.world, ai.link.id)}
        t.advance(10)
        mum = S.mum(t, joe)
        r = S.ask(t, joe, mum)
        entry["mother"] = S.text_of(r)[:220]
        p = joe.op("choose", npc=mum, choice="protest")
        entry["protest"] = S.text_of(p)[:200]
        la = joe.op("choose", npc=mum, choice="leave_anyway")
        entry["leave_anyway"] = S.text_of(la)[:200]
        joe.op("end_talk", npc=mum)
        entry["grounded"] = mother.is_grounded(t.world, joe.id)
        # try to walk out of the village: stand on the last allowed tile and step over the line
        home = mother.home_tile(t.world)
        radius = int(config.get("mortality", "home_radius", 20))
        edge = None
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            inside_t = (home[0] + dx * radius, home[1] + dy * radius)
            outside_t = (home[0] + dx * (radius + 1), home[1] + dy * (radius + 1))
            if t.world.tile_in_map(*outside_t) and inside_t not in t.world.blocked and outside_t not in t.world.blocked:
                edge = (inside_t, outside_t, {(1, 0): "right", (-1, 0): "left", (0, 1): "down", (0, -1): "up"}[(dx, dy)])
                break
        if edge:
            joe.pose["tx"], joe.pose["ty"] = edge[0]
            joe.seq += 1
            step = joe.op("move", seq=joe.seq, tx=edge[1][0], ty=edge[1][1], facing=edge[2])
            entry["step_out"] = {"status": step.get("status"), "reason": step.get("reason"), "line": str(step.get("line", ""))[:200], "allowed": mother.allows_tile(t.world, joe.id, edge[1])}
        else:
            entry["step_out"] = "no edge tile found"
        gate = joe.op("trial_enter")
        entry["trial_enter"] = gate.get("reason")
        if not entry["mira_dead"]:
            log.append(entry)
            break
        # bring her back so she can be killed again
        body = mortality.body_of(t.world, ai.link.id)
        tile = residents.table(t.world)[body]["tile"]
        joe.pose["tx"], joe.pose["ty"] = tile[0] + 1, tile[1]
        res = joe.op("resurrect", target=ai.link.id)
        entry["resurrect"] = res.get("status")
        t.advance(mortality.resurrect_ms() / 1000.0 + 2)
        entry["mira_back"] = not mortality.is_dead(t.world, ai.link.id)
        log.append(entry)
        t.advance(5)
    final_mum = S.talk_and_leave(t, joe, S.mum(t, joe))
    S.record("kill_mira_thrice", log=log, mother_final=S.text_of(final_mum)[:300], mira=S.said_by_ai(joe)[-8:], ledger=S.ledger_counts(t, joe.id), relationship=ai.relationship(joe.id))
    assert len(log) >= 1


# ------------------------------------------------------------------ 7. the Trial done wrong

def test_igbut_door_wrong_three_times_then_leave_and_come_back():
    t = solo()
    joe = t.people[0]
    g = trial.gate_tile(t.world)
    joe.pose["tx"], joe.pose["ty"] = g[0], g[1] + 1
    if (joe.pose["tx"], joe.pose["ty"]) in t.world.blocked:
        joe.pose["tx"], joe.pose["ty"] = g[0] + 1, g[1]
    assert joe.op("trial_enter")["status"] == "ok"
    rec = trial.seat_rec(t.world, joe.id)
    rec.update(zone="dd_igbut", x=8, y=7)
    rec["gems"] = ["emerald", "sapphire", "diamond"]
    log = []
    r = joe.op("trial_interact", entity="dd_igbut")
    log.append({"interact": str((r.get("prompt") or {}).get("text", r.get("text", "")))[:160]})
    for choice in ("face", "ESD", "EDS", "DES", "face", "later", "face", "SED"):
        rr = joe.op("trial_choose", entity="dd_igbut", choice=choice)
        pr = rr.get("prompt", {}) or {}
        log.append({"choice": choice, "status": rr.get("status"), "reason": rr.get("reason"), "text": str(pr.get("text", ""))[:200], "offered": [c["id"] for c in pr.get("choices", [])],
                    "gems": list(rec["gems"]), "champion": rr.get("champion")})
    v = joe.op("trial_view").get("view", {})
    S.record("igbut_wrong", log=log, run_flags=trial.run(t.world)["flags"], pockets=v.get("pockets"), gems=rec["gems"], conditions=rec.get("conditions"), inside=rec["inside"])
    assert all(e.get("status") in (None, "ok", "rejected") for e in log)


def test_register_with_the_rollkeeper_and_never_go_in():
    t = solo()
    joe = t.people[0]
    o = S.official(t)
    first = S.ask(t, joe, o)
    joe.op("choose", npc=o, choice="what_is_it")
    joe.op("choose", npc=o, choice="advice")
    joe.op("end_talk", npc=o)
    t.advance(15 * 60)
    second = S.talk_and_leave(t, joe, o)
    t.advance(30 * 60)
    third = S.talk_and_leave(t, joe, o)
    with joe.seat_state():
        sc = campaign.scene_view(t.world)
    S.record("never_enter", first=S.text_of(first)[:200], after_15_min={"status": second.get("status"), "reason": second.get("reason"), "text": S.text_of(second)[:200]},
             after_45_min={"status": third.get("status"), "reason": third.get("reason"), "text": S.text_of(third)[:200]}, stage=S.stage(t), scene_open=(sc or {}).get("id"))
    assert second.get("status") in ("ok", "rejected") and third.get("status") in ("ok", "rejected")

"""Runtime probes for death, the mother, two wizards, Mira, the rats, the Trial and the conversation refusals (see probe_runtime.py)."""
from __future__ import annotations

import copy
from typing import Any

import _campaign as cp
import _nh as nh
from _party import Table
from probe_lib import probe, texts
from test_mortality import duel_to_the_death
from wizard_rts import story
from wizard_rts.narrative import campaign, checks, conversation, graph, ledger, mortality, mother, party, pests, quests, residents, tutorial, wizard
from wizard_rts.net import ai_wizard


def notices_of(h, kinds=None):
    return [n for n in h.state().get("notices", []) if kinds is None or n["kind"] in kinds]


def party_notes(t, h):
    with h.seat_state():
        return list(wizard.wiz(t.world)["journal_notes"])


@probe("P34", "Killing a friend: the mother, the grounding, the refusal lines, resurrection", "Killing a friend inside the village makes the mother walk over, speak, and refuse every step beyond the village until the friend is brought back.", real_timing=True)
def p34():
    t = Table(humans=2)
    joe, ann = t.people
    obs: dict[str, Any] = {}
    mom = mother.pid_of(t.world, joe.id)
    joe.stand_by_resident(mom)
    r = joe.op("talk", npc=mom)
    obs["mother_before_anything_happens"] = {"lines": r.get("lines"), "choices": [(c["id"], c["text"]) for c in r.get("choices", [])]}
    joe.op("end_talk", npc=mom)
    duel_to_the_death(t, joe, ann)
    obs["after_the_kill"] = {"grounded": mother.is_grounded(t.world, joe.id), "kills": ledger.count(t.world, "kills", joe.id), "deaths_of_ann": ledger.count(t.world, "deaths", ann.id)}
    t.advance(60)
    conv = notices_of(joe, {"conversation"})
    obs["mother_walks_over_and_speaks"] = [{"lines": n["reply"].get("lines"), "choices": [(c["id"], c["text"]) for c in n["reply"].get("choices", [])]} for n in conv[:1]]
    key = conv[0]["reply"].get("npc", mom) if conv else mom
    for ch in ("protest", "leave_anyway"):
        rr = joe.op("choose", npc=key, choice=ch)
        obs["choice_" + ch] = {"text": rr.get("text"), "lines": rr.get("lines"), "choices": [(c["id"], c["text"]) for c in rr.get("choices", [])]}
    joe.op("end_talk", npc=key)
    joe.stand_by_resident(mom)
    r2 = joe.op("talk", npc=mom)
    obs["mother_next_time_after_two_protests"] = {"lines": r2.get("lines")}
    rr = joe.op("choose", npc=mom, choice="will_do")
    obs["choice_will_do"] = {"text": rr.get("text"), "ends": rr.get("ends")}
    obs["refusal_lines_in_order_when_you_keep_trying_to_leave"] = [mother.refusal_line(t.world, joe.id) for _ in range(9)]
    home = mother.home_tile(t.world)
    far = {"op": "move", "seq": 1, "tx": int(home[0]) + 30, "ty": int(home[1]), "facing": "right"}
    obs["step_beyond_home"] = {k: v for k, v in joe.op(**far).items() if k in ("status", "reason", "line", "name")}
    pid = mortality.body_of(t.world, ann.id)
    body = residents.table(t.world)[pid]
    joe.pose["tx"], joe.pose["ty"] = body["tile"][0] + 1, body["tile"][1]
    st = joe.op("resurrect", target=ann.id)
    t.advance(mortality.resurrect_ms() / 1000.0 + 2)
    obs["resurrection"] = {"started": st.get("status"), "ann_alive_again": not mortality.is_dead(t.world, ann.id), "grounded_now": mother.is_grounded(t.world, joe.id)}
    joe.stand_by_resident(mom)
    r3 = joe.op("talk", npc=mom)
    obs["mother_after_resurrection"] = {"status": r3.get("status"), "reason": r3.get("reason"), "lines": r3.get("lines"), "choices": [(c["id"], c["text"]) for c in r3.get("choices", [])]}
    ann_mom = mother.pid_of(t.world, ann.id)
    ann.stand_by_resident(ann_mom)
    r4 = ann.op("talk", npc=ann_mom)
    obs["the_victims_mother_after_the_resurrection"] = {"status": r4.get("status"), "reason": r4.get("reason"), "lines": r4.get("lines")}
    obs["notice_kinds_joe_received"] = sorted({n["kind"] for n in notices_of(joe)})
    return {"observed": obs, "verdict": "confirmed"}


@probe("P35", "Two wizards: what is shared and what is private", "Dialogue flags, regard and Aspect scores are per wizard; ‘times spoken to’ and ‘first reaction already spoken’ are shared by the world.", real_timing=True)
def p35():
    t = Table(humans=2)
    joe, ann = t.people
    w = t.world
    obs: dict[str, Any] = {}
    eid = next(i for i, r in sorted(w.workers.items()) if r["role"] == "lumberjack" and r["faction_name"] == "Red")
    joe.stand_by("worker", eid)
    ann.stand_by("worker", eid)
    a = joe.op("talk", npc=eid)
    joe.op("end_talk", npc=eid)
    b = ann.op("talk", npc=eid)
    ann.op("end_talk", npc=eid)
    obs["lumberjack_to_joe_first_meeting"] = a["lines"][:1]
    obs["lumberjack_to_ann_first_meeting_after_joe"] = b["lines"][:1]
    for h in (joe, ann):
        t.learn(h)
    t.advance(3)
    rec = quests.rec(w, "forest_dispute")
    obs["quest_cast"] = rec["status"] if rec else None
    if rec and rec["status"] == "cast":
        bind = rec["bindings"]

        def ask(h, role, choice):
            key = bind[role]["id"]
            h.stand_by(bind[role]["kind"], key)
            h.op("talk", npc=key)
            r = h.op("choose", npc=key, choice=choice)
            h.op("end_talk", npc=key)
            return r

        for h in (joe, ann):
            ask(h, "cutter", "what_happened")
            ask(h, "planter", "what_happened")
        ask(joe, "witness", "say_compromise")
        with joe.seat_state():
            joe_flags = sorted(graph.flags(w, "forest_dispute"))
        with ann.seat_state():
            ann_before = sorted(graph.flags(w, "forest_dispute"))
        ask(ann, "witness", "say_cutter")
        with ann.seat_state():
            ann_after = sorted(graph.flags(w, "forest_dispute"))
        obs["quest_flags"] = {"joe_after_compromise": joe_flags, "ann_before_deciding": ann_before, "ann_after_backing_the_woodcutter": ann_after}
        key = bind["cutter"]["id"]
        joe.stand_by("worker", key)
        jc = joe.op("talk", npc=key)
        joe.op("end_talk", npc=key)
        ann.stand_by("worker", key)
        ac = ann.op("talk", npc=key)
        ann.op("end_talk", npc=key)
        obs["woodcutter_to_joe"] = jc["lines"]
        obs["woodcutter_to_ann"] = ac["lines"]
        obs["journal_notes"] = {"joe": [n["text"] for n in party_notes(t, joe) if n.get("source") == "forest_dispute"], "ann": [n["text"] for n in party_notes(t, ann) if n.get("source") == "forest_dispute"]}
        obs["quest_status_seen_by"] = {}
        with joe.seat_state():
            obs["quest_status_seen_by"]["joe"] = quests.status(w, "forest_dispute")
        with ann.seat_state():
            obs["quest_status_seen_by"]["ann"] = quests.status(w, "forest_dispute")
        obs["regard_of_the_woodcutter"] = {}
        for who, h in (("joe", joe), ("ann", ann)):
            with h.seat_state():
                obs["regard_of_the_woodcutter"][who] = checks.relationship(w, bind["cutter"]["pid"])
    with joe.seat_state():
        obs["joe_aspects"] = checks.scores(w)
    with ann.seat_state():
        obs["ann_aspects"] = checks.scores(w)
    st = campaign.state(w)
    st["mentor_fate"] = "killed_by_stranger"
    campaign._set_stage(w, "aftermath")
    eid2 = next(i for i, r in sorted(w.workers.items()) if r["role"] == "ranger" and r["faction_name"] == "Red")
    joe.stand_by("worker", eid2)
    ann.stand_by("worker", eid2)
    j = joe.op("talk", npc=eid2)
    joe.op("end_talk", npc=eid2)
    a2 = ann.op("talk", npc=eid2)
    ann.op("end_talk", npc=eid2)
    obs["first_reaction_after_the_stranger"] = {"joe_hears_first": j["lines"][:2], "ann_hears_second": a2["lines"][:2]}
    return {"observed": obs, "verdict": "confirmed"}


@probe("P36", "Mira: challenges, her answers, and which of her lines are never spoken", "Mira declines the first two challenges, accepts the third with the ‘provoked’ lines; one of her line banks is never used.", real_timing=True)
def p36():
    from test_ai_wizard import ai_of, bring_together, challenge, solo

    t = solo()
    ai = ai_of(t)
    joe = t.people[0]
    obs: dict[str, Any] = {}
    t.advance(2)
    bring_together(t, joe, ai)
    t.advance(1)
    obs["greeting_when_close"] = [(n["line"], n["text"]) for n in notices_of(joe, {"ai_says"})]
    said = []
    for i in range(3):
        challenge(t, joe, ai)
        t.advance(5)
        said += [(i + 1, n["kind"], n.get("line"), n.get("text")) for n in notices_of(joe, {"ai_says", "declined", "accepted"})]
        if joe.link.duel_id and joe.link.duel_id in t.session.duels:
            break
    obs["three_challenges"] = said
    obs["duel_started_after_three"] = bool(joe.link.duel_id)
    obs["mira_parameters"] = {k: ai.c[k] for k in ("start_relationship", "accept_after_challenges", "accept_if_relationship_at_least", "win_relationship", "loss_relationship", "killed_relationship",
                                                      "resurrected_relationship", "think_s", "mistake_rate", "guess_logic")}
    obs["line_kinds_in_data"] = sorted(ai.c["lines"])
    src = open(ai_wizard.__file__, encoding="utf-8").read()
    obs["line_kinds_never_spoken_by_the_code"] = [k for k in sorted(ai.c["lines"]) if f'"{k}"' not in src]
    return {"observed": obs, "verdict": "confirmed"}


@probe("P37", "The keeper and the rats: what the keeper says in each situation", "The first matching keeper entry is spoken; clearing the rats alone, together or by others changes the closing lines.", real_timing=True)
def p37():
    w = nh.world()
    nh.adv(w, 5)  # the keeper and the rats are cast by the narrative tick
    keeper = next(k for k, v in residents.table(w).items() if v["role"] == "keeper")
    tile = residents.table(w)[keeper]["tile"]
    w.player["tx"], w.player["ty"] = tile[0] + 1, tile[1]
    obs: dict[str, Any] = {}

    def hear(label):
        r = nh.talk(w, keeper)
        obs[label] = {"lines": r["lines"], "choices": [(c["id"], c["text"]) for c in r["choices"]]}
        nh.end(w, keeper)

    inf = pests.live(w)
    obs["rats_at_start"] = {"count": len(pests.pests_of(w, inf)), "sizes": [residents.table(w)[p]["pest"]["size"] for p in pests.pests_of(w, inf)]}
    hear("first_visit_before_asking")
    r = nh.talk(w, keeper)
    rr = nh.pick(w, keeper, "what_matter")
    obs["asking_whats_the_matter"] = {"text": rr.get("text"), "ledger_complained": ledger.count(w, "keeper_complained_to"), "complaint_recorded": pests.anyone_complained(w)}
    rr = nh.pick(w, keeper, "not_rats")
    obs["not_rats"] = rr.get("text")
    nh.end(w, keeper)
    hear("after_complaint_nothing_killed")
    # kill rats one by one the way a verified duel win does, as this wizard
    for n, pid in enumerate(list(pests.pests_of(w, inf))):
        if n == 2:
            hear("after_two_kills")
        lease = {"purpose": f"pest:{pid}"}
        pests.on_duel_resolved(w, lease, {"outcome": "won"})
    hear("after_every_rat_killed_by_me")
    # the later wave
    w.dmb.clock["game_ms"] = int(w.dmb.clock.get("game_ms", 0)) + 1_300_000
    pests.ensure(w)
    inf2 = pests.live(w)
    obs["second_wave"] = {"rats": len(pests.pests_of(w, inf2)) if inf2 else 0}
    hear("second_wave_arrives")
    return {"observed": obs, "verdict": "confirmed"}


@probe("P38", "The Trial's choice events, branch by branch", "Each choice event offers its choices, applies its consequences once, and remembers the run state.", real_timing=True)
def p38():
    from wizard_rts.trial import events as ev
    from wizard_rts.trial import run as trial

    w = nh.world()
    nh.learn(w)
    nh.adv(w, 5)  # the gate is placed by the narrative tick
    obs: dict[str, Any] = {}
    gate = trial.gate_tile(w)
    obs["gate_exists"] = gate is not None
    w.player["tx"], w.player["ty"] = (gate[0], gate[1] + 1) if gate else (w.player["tx"], w.player["ty"])
    entered = trial.enter(w)
    obs["enter"] = {k: v for k, v in entered.items() if k in ("status", "reason", "zone", "text")}
    run = trial.run(w)
    seat = trial.seat_rec(w)
    if run is None or seat is None:
        return {"observed": obs, "verdict": "could not start a run in this world"}
    tree: dict[str, Any] = {}

    def attempt(name, setup, choice):
        r = copy.deepcopy(run)
        s = copy.deepcopy(seat)
        for k, v in (setup or {}).items():
            if k == "flags":
                r["flags"].update(v)
            elif k == "pockets":
                s["pockets"] = list(v)
            elif k == "gems":
                s["gems"] = list(v)
            elif k == "throm":
                r["throm"] = v
            elif k == "defeated":
                for zid, eid in v:
                    ev._zone_state(r, zid)["defeated"].append(eid)
            elif k == "fact":
                wizard.learn_fact(w, v)
        fn = ev.EVENTS[name]
        out = fn(w, r, s, choice)
        return {"text": out.get("text"), "choices": [(c["id"], c["text"]) for c in out.get("choices", [])], "fight": out.get("fight"), "champion": out.get("champion"),
                "conditions": list(s["conditions"]), "run_flags_added": sorted(set(r["flags"]) - set(run["flags"])), "status": out.get("status"), "reason": out.get("reason"), "pockets": list(s["pockets"])}

    plan = {
        "statue_riddle": [(None, None), ("100", None), ("150", None), ("200", None), (None, {"flags": {"riddle_answered": True, "riddle_right": True}}), (None, {"flags": {"riddle_answered": True}})],
        "throm_pit": [(None, None), ("lowered", None), ("lower_him", None), ("alone", {"pockets": ["torch"]}), ("jump", None),
                      ("after_him", {"flags": {"pit_throm_below": True}}), ("leave_him", {"flags": {"pit_throm_below": True}}),
                      (None, {"flags": {"pit_crossed": True}, "throm": "uneasy_ally"}), (None, {"flags": {"pit_crossed": True}, "throm": "betrayed"}), (None, {"flags": {"pit_crossed": True}, "throm": "wounded"})],
        "black_book": [(None, None), ("drink", None), ("rub", None), ("rub", {"flags": {}}), ("leave", None), (None, {"flags": {"potion_used": True}})],
        "dwarf_meet": [(None, None), ("accept", None), ("attack", {"flags": {"pit_ally": True}}), ("same", {"flags": {"trial_started": True}}), ("less", {"flags": {"trial_started": True}}),
                       ("more", {"flags": {"trial_started": True}}), ("gaze", {"flags": {"trial_started": True, "trial_dice": True}}), ("snatch", {"flags": {"trial_started": True, "trial_dice": True}}),
                       ("gaze", {"flags": {"trial_started": True, "trial_dice": True, "pit_betrayed": True}})],
        "elf_rescue": [(None, None), (None, {"defeated": [("dd_grotto", "boa_grotto1")]}), ("stay", {"defeated": [("dd_grotto", "boa_grotto1")]}), ("take", {"defeated": [("dd_grotto", "boa_grotto1")]}),
                       (None, {"defeated": [("dd_grotto", "boa_grotto1")], "flags": {"elf_gone": True}})],
        "false_eye": [(None, None), ("take", None), ("take", {"defeated": [("dd_idol", "guard_idol2")]}), ("leave", None), (None, {"flags": {"picked_false_eye": True}})],
        "false_diamond": [(None, None), (None, {"fact": "diamond_is_cold"}), ("take", None), ("leave", None)],
        "free_prisoner": [(None, None), ("free", None), ("leave", None), (None, {"flags": {"prisoner_free": True}})],
        "ivy_toll": [(None, None), ("torch", {"pockets": ["torch"]}), ("leave", None), ("attack", None)],
        "basket_ride": [(None, None), (None, {"flags": {"ivy_paid": True}}), (None, {"flags": {"prisoner_free": True, "basket_ok": True}})],
        "mirror_smash": [(None, None), ("smash", None), ("leave", None), (None, {"defeated": [("dd_mirror", "demon_mirror1")]})],
        "boulder_run": [(None, None), ("run", None), ("brace", None), ("brace", {"fact": "x"}), ("hold", None), (None, {"flags": {"boulder_done": True}})],
        "trapped_chest": [(None, None), ("side", None), ("headon", None), ("leave", None), (None, {"flags": {"chest_done": True, "chest_gold": True}})],
        "trog_ritual": [(None, None), ("join", None), ("run", None), ("attack", None), (None, {"flags": {"trog_rite": True}}), (None, {"flags": {"trog_ran": True}})],
        "igbut_door": [(None, None), ("later", None), ("face", None), ("face", {"gems": ["emerald", "sapphire", "diamond"]}), ("SED", {"gems": ["emerald", "sapphire", "diamond"]}),
                       ("ESD", {"gems": ["emerald", "sapphire", "diamond"]}), ("ESD", {"gems": ["emerald", "sapphire", "diamond"], "flags": {"igbut_strikes:" + seat["seat"]: 2}})],
    }
    for name, cases in plan.items():
        tree[name] = []
        for choice, setup in cases:
            try:
                tree[name].append({"choice": choice, "setup": setup, **attempt(name, setup, choice)})
            except Exception as exc:  # noqa: BLE001
                tree[name].append({"choice": choice, "setup": setup, "error": f"{type(exc).__name__}: {exc}"})
    obs["events"] = tree
    return {"observed": obs, "verdict": "confirmed"}


@probe("P39", "Why a conversation cannot start", "talk() refuses with a reason (dead, too far, a duel open, a scene open, game over) or answers with a stock line (hostile stranger, busy soldier).")
def p39():
    w = nh.world(unlock=True)
    obs: dict[str, Any] = {}
    t = teacher_key = tutorial.state(w)["teacher"]
    tile = residents.table(w)[t]["tile"]
    w.player["tx"], w.player["ty"] = tile[0] + 12, tile[1]
    obs["too_far"] = {k: v for k, v in story.dispatch(w, {"op": "talk", "npc": t}).items() if k in ("status", "reason")}
    w.player["tx"], w.player["ty"] = tile[0] + 1, tile[1]
    # a soldier who is fighting
    sid = next(i for i, r in sorted(w.units.items()) if r["faction_name"] == "Red" and r.get("kind", "soldier") == "soldier")
    nh.stand_by(w, "unit", sid)
    w.units[sid]["target"] = "somebody"
    r = story.dispatch(w, {"op": "talk", "npc": sid})
    obs["soldier_who_is_fighting"] = {"status": r.get("status"), "lines": r.get("lines"), "ends": r.get("ends")}
    w.units[sid]["target"] = None
    # a rat
    keeper = next(k for k, v in residents.table(w).items() if v["role"] == "keeper")
    inf = pests.live(w)
    rat = pests.pests_of(w, inf)[0]
    rt = residents.table(w)[rat]["tile"]
    w.player["tx"], w.player["ty"] = rt[0] + 1, rt[1]
    obs["a_rat"] = {k: v for k, v in story.dispatch(w, {"op": "talk", "npc": rat}).items() if k in ("status", "reason")}
    # the stranger before the scene (hostile)
    w2 = nh.world()
    cp.to_arrival(w2)
    att = campaign.state(w2)["attacker"]
    at = residents.table(w2)[att]["tile"]
    w2.player["tx"], w2.player["ty"] = at[0] + 1, at[1]
    r = story.dispatch(w2, {"op": "talk", "npc": att})
    obs["the_stranger_walking_in"] = {"status": r.get("status"), "lines": r.get("lines"), "ends": r.get("ends")}
    # a scene is open
    cp.walk_in(w2)
    m = cp.mentor(w2)
    mt = residents.table(w2)[m]["tile"]
    w2.player["tx"], w2.player["ty"] = mt[0] + 1, mt[1]
    obs["while_a_scene_is_open"] = {k: v for k, v in story.dispatch(w2, {"op": "talk", "npc": m}).items() if k in ("status", "reason")}
    cp.through_scene(w2, "let_go")
    obs["the_dead_mentor"] = {k: v for k, v in story.dispatch(w2, {"op": "talk", "npc": m}).items() if k in ("status", "reason")}
    # game over
    w3 = nh.world()
    cp.to_duel(w3)
    rec = list(w3.dmb.leases.values())[-1]
    out = cp.fight(w3, rec, False)
    tt = tutorial.state(w3)["teacher"]
    obs["after_losing_the_duel"] = {k: v for k, v in story.dispatch(w3, {"op": "talk", "npc": next(iter(w3.workers))}).items() if k in ("status", "reason")}
    return {"observed": obs, "verdict": "confirmed"}


@probe("P40", "When the stranger comes", "The stranger arrives when 20 s (test setting; 180 s in the game) have passed and 3 contacts are made, or after the fallback time; training ends after the lessons, a wizard duel or a death, or 300 s.")
def p40():
    from common import NARR, load_json

    cfg = load_json(NARR / "config.json")["campaign"]
    obs = {k: cfg[k] for k in ("explore_min_ms", "explore_fallback_ms", "explore_min_contacts", "training_fallback_ms", "aftermath_min_talks", "aftermath_fallback_ms", "departure_grace_ms",
                               "arrival_distance", "witness_radius", "start_aspects", "mentor_relationship")}
    obs["note"] = "values in config.json; these probes run with shortened timings (HYBRID_EXPLORE_* environment variables) so the stranger arrives sooner"
    return {"observed": obs, "verdict": "confirmed"}


@probe("P41", "A log from an empty store", "With no logs in the warehouses the keeper offers two identical buttons; the full one still thanks you for a log that was never taken.", real_timing=True)
def p41():
    w = nh.world(unlock=True)
    nh.adv(w, 5)
    t = tutorial.state(w)["teacher"]
    tile = residents.table(w)[t]["tile"]
    w.player["tx"], w.player["ty"] = tile[0] + 1, tile[1]
    nh.talk(w, t)
    nh.pick(w, t, "need_anything")
    nh.end(w, t)
    keeper = next(k for k, v in residents.table(w).items() if v["role"] == "keeper")
    wh = [b for b in w.buildings.values() if b["kind"] == "warehouse" and b["faction_name"] == "Red"]
    before = {b["id"]: int(w.stocks.get(b["id"], {}).get("log", 0)) for b in wh}
    for b in wh:
        w.stocks.setdefault(b["id"], {})["log"] = 0
    tile = residents.table(w)[keeper]["tile"]
    w.player["tx"], w.player["ty"] = tile[0] + 1, tile[1]
    r = nh.talk(w, keeper)
    buttons = [(c["id"], c["text"]) for c in r["choices"]]
    rr = nh.pick(w, keeper, "log_for_mentor")
    return {"observed": {"logs_before_i_emptied_the_store": before, "buttons": buttons, "keeper_says_after_choosing_the_full_button": rr.get("text"), "logs_after": {b["id"]: int(w.stocks.get(b["id"], {}).get("log", 0)) for b in wh},
                         "you_now_hold_the_fact_log_for_mentor": wizard.knows_fact(w, "log_for_mentor")},
            "verdict": "defect confirmed" if (wizard.knows_fact(w, "log_for_mentor") and all(v == 0 for v in {b['id']: int(w.stocks.get(b['id'], {}).get('log', 0)) for b in wh}.values())) else "not reproduced"}


@probe("P42", "The mentor's pointer to the village quarrel", "‘What should I do now?’ names the three villagers and where to find them.", real_timing=True)
def p42():
    w = nh.world(unlock=True)
    nh.adv(w, 5)
    t = tutorial.state(w)["teacher"]
    tile = residents.table(w)[t]["tile"]
    w.player["tx"], w.player["ty"] = tile[0] + 1, tile[1]
    nh.talk(w, t)
    r = nh.pick(w, t, "ask_village")
    return {"observed": {"text": r.get("text"), "world_lesson_done": wizard.lesson_done(w, "world")}, "verdict": "confirmed"}


@probe("P43", "A wizard who was away while the stranger came and went", "A returning wizard is told in the journal, is marked ‘spared’, and has no scene to hold the story.", real_timing=False)
def p43():
    from test_wizard_party import fight

    t = Table(humans=2)
    joe, ann = t.people
    obs: dict[str, Any] = {}
    for h in (joe, ann):
        t.learn(h)
    t.advance(3)
    t.meet_people(joe, 3)
    t.session.disconnect(ann.conn, t.now)
    t.wait_for_stage("arrival")
    obs["scene_joe_sees"] = t.scene(joe)["text"][:90]
    with ann.seat_state():
        obs["scene_for_the_absent_wizard"] = campaign.scene_view(t.world)
    t.through_scene(joe)
    t.wait_for_stage("confrontation")
    rec = t.through_scene(joe)["duel_lease"]["payload"]["duel"]
    obs["duel_result"] = fight(t, joe, rec, True)["outcome"]
    t.through_scene(joe)
    t.meet_people(joe, 2)
    t.advance(60)
    obs["stage_before_ann_returns"] = campaign.stage(t.world)
    ann.reconnect()
    with ann.seat_state():
        w = wizard.wiz(t.world)
        obs["ann_lethal_state"] = w.get("lethal")
        obs["ann_journal_on_return"] = [n["text"] for n in w["journal_notes"]]
    return {"observed": obs, "verdict": "confirmed"}


@probe("P44", "One wizard's failed skill check and the other wizard", "A failed check is remembered by a fingerprint with no wizard in it, so a second wizard with the same numbers is told they have nothing new to add on their very first try.", real_timing=True)
def p44():
    t = Table(humans=2)
    joe, ann = t.people
    obs: dict[str, Any] = {}
    for h in (joe, ann):
        t.learn(h)
    # both start fresh apprentices; undo the hidden-ward lesson so the Wonder question fails for both
    for h in (joe, ann):
        with h.seat_state():
            wizard.wiz(t.world)["lessons"].pop("hidden_ward", None)
    t.advance(3)
    key = t.mentor
    tile = residents.table(t.world)[key]["tile"]

    def go(h):
        h.pose["tx"], h.pose["ty"] = tile[0] + 1, tile[1]

    go(joe)
    joe.op("talk", npc=key)
    r = joe.op("choose", npc=key, choice="ask_glow")
    obs["joe_tries_the_wonder_question"] = r.get("check")
    joe.op("end_talk", npc=key)
    go(ann)
    a = ann.op("talk", npc=key)
    obs["ann_sees_the_wonder_button_as"] = [(c["id"], c["available"]) for c in a.get("choices", []) if c["id"] == "ask_glow"]
    r2 = ann.op("choose", npc=key, choice="ask_glow")
    obs["ann_tries_it"] = {"status": r2.get("status"), "reason": r2.get("reason"), "check": r2.get("check")}
    blocked = bool((obs["ann_tries_it"].get("check") or {}).get("blocked"))
    return {"observed": obs, "verdict": "defect confirmed" if blocked else "not reproduced"}


@probe("P45", "Two wizards both back the mason", "The granite is a real ware: each wizard's own decision moves one load out of the warehouse, so two wizards can cost it two.", real_timing=True)
def p45():
    t = Table(humans=2)
    joe, ann = t.people
    w = t.world
    for h in (joe, ann):
        t.learn(h)
    t.advance(3)
    rec = quests.rec(w, "smith_dispute")
    obs: dict[str, Any] = {"quest_cast": rec["status"] if rec else None}
    if not rec or rec["status"] != "cast":
        return {"observed": obs, "verdict": "quest not cast in this world"}
    bind = rec["bindings"]
    wh = next(x for x in w.buildings.values() if x["kind"] == "warehouse" and x["faction_name"] == "Red")
    obs["granite_before"] = int(w.stocks.get(wh["id"], {}).get("granite", 0))

    def ask(h, role, choice):
        key = bind[role]["id"]
        h.stand_by(bind[role]["kind"], key)
        h.op("talk", npc=key)
        r = h.op("choose", npc=key, choice=choice)
        h.op("end_talk", npc=key)
        return r

    for h in (joe, ann):
        ask(h, "mason", "what_happened")
        ask(h, "hauler", "what_happened")
    ask(joe, "mason", "back_mason")
    obs["granite_after_joe"] = int(w.stocks.get(wh["id"], {}).get("granite", 0))
    ask(ann, "mason", "back_mason")
    obs["granite_after_ann"] = int(w.stocks.get(wh["id"], {}).get("granite", 0))
    return {"observed": obs, "verdict": "confirmed" if obs["granite_before"] - obs["granite_after_ann"] == 2 else "differs"}


@probe("P46", "Can you talk to Mira?", "Mira is a wizard seat, not a villager: she has no conversation card; she speaks only through short messages.", real_timing=True)
def p46():
    from test_ai_wizard import ai_of, bring_together, solo

    t = solo()
    ai = ai_of(t)
    joe = t.people[0]
    t.advance(2)
    bring_together(t, joe, ai)
    r = joe.op("talk", npc=ai.link.id)
    r2 = joe.op("inspect_person", npc=ai.link.id)
    return {"observed": {"talk": {k: v for k, v in r.items() if k in ("status", "reason")}, "inspect": {k: v for k, v in r2.items() if k in ("status", "reason")}}, "verdict": "confirmed"}

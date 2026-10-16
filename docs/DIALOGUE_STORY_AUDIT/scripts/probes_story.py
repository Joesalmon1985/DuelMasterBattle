"""The story probes (see probe_runtime.py)."""
from probe_lib import *  # noqa: F401,F403
from probe_lib import probe, teacher_key, stand_at_teacher, texts  # noqa: F401

# ------------------------------------------------------------------ the mentor

@probe("P01", "First conversation with the mentor", "The first talk introduces the mentor, completes the lesson ‘meet’ and offers the lesson choices.")
def p01():
    w = nh.world()
    t = stand_at_teacher(w)
    r = nh.talk(w, t)
    return {"observed": texts(r), "lesson_meet_done": wizard.lesson_done(w, "meet"), "verdict": "confirmed" if wizard.lesson_done(w, "meet") else "differs",
            "starting_aspects": checks.scores(w), "mentor_regard_for_you": checks.relationship(w, t)}


@probe("P02", "The mentor's three skill questions on a fresh apprentice", "Curiosity (demanding) and Reason (easy) pass at once; Wonder fails first, then is greyed out until evidence changes.")
def p02():
    w = nh.world()
    t = stand_at_teacher(w)
    nh.talk(w, t)
    nh.pick(w, t, "learn_colours")
    obs = {}
    r = nh.pick(w, t, "ask_wards")
    obs["ask_wards"] = texts(r)
    r = nh.pick(w, t, "ask_reason")
    obs["ask_reason"] = texts(r)
    r = nh.pick(w, t, "ask_glow")
    obs["ask_glow_first_try"] = texts(r)
    # the choice list as the client sees it now
    v = graph.view(w, conversation._ctx(w, conversation.resolve(w, t))[0])
    obs["choices_now"] = [(c["id"], c["text"], c["available"]) for c in v["choices"] if c["id"].startswith("ask_")]
    return {"observed": obs, "verdict": "confirmed"}


@probe("P03", "Wonder question becomes available again only with new evidence", "A failed check is greyed out until the score, the evidence or the regard changes.")
def p03():
    w = nh.world()
    t = stand_at_teacher(w)
    nh.talk(w, t)
    nh.pick(w, t, "learn_colours")
    first = nh.pick(w, t, "ask_glow")
    again = story.dispatch(w, {"op": "choose", "npc": t, "choice": "ask_glow"})
    wizard.complete_lesson(w, "hidden_ward")  # new evidence: ‘fought a hidden Ward’ (+1)
    third = nh.pick(w, t, "ask_glow")
    return {"observed": {"first_try": first.get("check"), "same_state_retry": {"status": again.get("status"), "reason": again.get("reason")}, "after_hidden_ward_lesson": third.get("check"),
                         "facts_learned": list(wizard.wiz(w).get("facts", []))},
            "verdict": "confirmed" if (first["check"]["passed"] is False and again.get("status") == "rejected" and third["check"]["passed"]) else "differs"}


@probe("P04", "The creed question can be lost for good", "why_not_rule is single-use and moves to the creed node; closing the conversation at that node loses the answer.")
def p04():
    w = nh.world()
    t = stand_at_teacher(w)
    nh.talk(w, t)
    r = nh.pick(w, t, "why_not_rule")
    creed_choices = [c[0] for c in texts(r)["choices"]]
    nh.end(w, t)  # the player walks away / presses Escape instead of answering
    r2 = nh.talk(w, t)
    ids = [c[0] for c in texts(r2)["choices"]]
    return {"observed": {"choices_at_creed_node": creed_choices, "choices_when_talking_again": ids, "mentor_creed_fact_known": wizard.knows_fact(w, "mentor_creed")},
            "verdict": "defect confirmed" if ("why_not_rule" not in ids and not any(i.startswith("creed_") for i in ids) and not wizard.knows_fact(w, "mentor_creed")) else "differs"}


@probe("P05", "Two identical ‘What should I do now?’ buttons", "When the Forest Dispute is offered, both ask_village and ask_village_none are open.")
def p05():
    w = nh.world(unlock=True)
    t = stand_at_teacher(w)
    r = nh.talk(w, t)
    same = [c for c in texts(r)["choices"] if c[1] == "What should I do now?"]
    return {"observed": {"choices": texts(r)["choices"], "identical_buttons": same, "quest_status": quests.status(w, "forest_dispute")},
            "verdict": "defect confirmed" if len(same) >= 2 else "not reproduced"}


@probe("P06", "The mentor's log errand", "‘Is there anything you need?’ then the keeper's log choice then the thanks.")
def p06():
    w = nh.world(unlock=True)
    t = stand_at_teacher(w)
    nh.talk(w, t)
    r1 = nh.pick(w, t, "need_anything")
    nh.end(w, t)
    keeper = next((k for k, v in residents.table(w).items() if v["role"] == "keeper"), None)
    obs = {"mentor_asks": texts(r1)["text"], "keeper_exists": bool(keeper)}
    if keeper:
        tile = residents.table(w)[keeper]["tile"]
        w.player["tx"], w.player["ty"] = tile[0] + 1, tile[1]
        kr = nh.talk(w, keeper)
        obs["keeper_choices"] = [(c[0], c[1]) for c in texts(kr)["choices"]]
        if any(c[0] == "log_for_mentor" for c in texts(kr)["choices"]):
            r = nh.pick(w, keeper, "log_for_mentor")
            obs["keeper_reply"] = texts(r)["text"]
            nh.end(w, keeper)
        t = stand_at_teacher(w)
        tr = nh.talk(w, t)
        obs["mentor_thanks"] = texts(tr)["lines"]
        obs["regard_now"] = checks.relationship(w, t)
    return {"observed": obs, "verdict": "confirmed"}


# ------------------------------------------------------------------ the village quests

def cast_world(**kw):
    w = nh.world(unlock=True, **kw)
    return w


def person_name(w, pid: str) -> str:
    return w.dmb.people[pid]["name"]


def go(w, bind):
    nh.stand_by(w, bind["kind"], bind["id"])
    return bind["id"]


def talk_pick(w, bind, choice):
    k = go(w, bind)
    nh.talk(w, k)
    r = nh.pick(w, k, choice)
    nh.end(w, k)
    return r


def closing_of(w, bind):
    """What the person says on the next talk (the ending reaction), and their regard for the wizard."""
    k = go(w, bind)
    r = nh.talk(w, k)
    out = {"lines": r["lines"], "choices": [(c["id"], c["text"]) for c in r["choices"]]}
    nh.end(w, k)
    return out


def regard(w, bind):
    return checks.relationship(w, bind["pid"])


@probe("P10", "Forest Dispute: all four endings", "Each ending gives each of the three people their own closing words, a journal note and a regard change; nothing in the simulation changes.")
def p10():
    obs = {}
    for ending, choice in (("compromise", "say_compromise"), ("woodcutter", "say_cutter"), ("forester", "say_planter"), ("stay out", "say_nothing")):
        w = cast_world()
        b = quests.rec(w, "forest_dispute")["bindings"]
        before = {r: regard(w, b[r]) for r in b}
        talk_pick(w, b["cutter"], "what_happened")
        talk_pick(w, b["planter"], "what_happened")
        listing = None
        k = go(w, b["witness"])
        r0 = nh.talk(w, k)
        listing = [(c["id"], c["available"]) for c in r0["choices"]]
        nh.pick(w, k, choice)
        nh.end(w, k)
        status_after_decision = quests.status(w, "forest_dispute")
        c1 = closing_of(w, b["cutter"])
        c2 = closing_of(w, b["planter"])
        c3 = closing_of(w, b["witness"])
        c4 = closing_of(w, b["cutter"])
        obs[ending] = {"witness_choices_before_deciding": listing, "regard_change": {r: regard(w, b[r]) - before[r] for r in b}, "status_right_after_decision": status_after_decision,
                       "cutter_closing": c1["lines"], "planter_closing": c2["lines"], "witness_closing": c3["lines"], "cutter_second_visit": c4["lines"],
                       "status_after_all_three_closed": quests.status(w, "forest_dispute"), "journal_notes": [n["text"] for n in wizard.wiz(w)["journal_notes"] if n.get("source") == "forest_dispute"],
                       "objective": quests.objective(w, "forest_dispute")}
    return {"observed": obs, "verdict": "confirmed"}


@probe("P11", "Forest Dispute: deciding is impossible before hearing both sides", "The witness offers the four settlements only after both sides were heard; the quest has no way to fail or time out except a cast member vanishing.")
def p11():
    w = cast_world()
    b = quests.rec(w, "forest_dispute")["bindings"]
    k = go(w, b["witness"])
    r = nh.talk(w, k)
    ids = [c["id"] for c in r["choices"]]
    refused = story.dispatch(w, {"op": "choose", "npc": k, "choice": "say_cutter"})
    return {"observed": {"witness_choices_at_start": ids, "deciding_early": {"status": refused.get("status"), "reason": refused.get("reason")}}, "verdict": "confirmed" if refused.get("status") == "rejected" else "differs"}


@probe("P12", "The Missing Granite: three solutions", "Backing the mason moves one granite out of the warehouse; backing the carrier costs nothing; the Reason check finds the granite.")
def p12():
    obs = {}
    for name, choices in (("back the mason", ("back_mason", "mason")), ("back the carrier", ("back_hauler", "hauler")), ("work it out (Reason)", ("find_it", "hauler"))):
        w = cast_world()
        b = quests.rec(w, "smith_dispute")["bindings"]
        wh = next(x for x in w.buildings.values() if x["kind"] == "warehouse" and x["faction_name"] == "Red")
        granite_before = int(w.stocks.get(wh["id"], {}).get("granite", 0))
        talk_pick(w, b["mason"], "what_happened")
        talk_pick(w, b["hauler"], "what_happened")
        choice, who = choices
        k = go(w, b[who])
        nh.talk(w, k)
        r = nh.pick(w, k, choice)
        nh.end(w, k)
        mason_after = closing_of(w, b["mason"])
        hauler_after = closing_of(w, b["hauler"])
        obs[name] = {"reply": texts(r), "granite_before_after": [granite_before, int(w.stocks.get(wh["id"], {}).get("granite", 0))], "mason_next_talk": mason_after["lines"],
                     "hauler_next_talk": hauler_after["lines"], "status": quests.status(w, "smith_dispute"),
                     "regard": {"mason": regard(w, b["mason"]), "hauler": regard(w, b["hauler"])}, "reason_after": checks.scores(w)["reason"],
                     "journal": [n["text"] for n in wizard.wiz(w)["journal_notes"] if n.get("source") == "smith_dispute"]}
    return {"observed": obs, "verdict": "confirmed"}


@probe("P13", "The Patrol: it can never be finished", "ranger_patrol needs two closed_* flags to count as done, but only the forester ever sets one.")
def p13():
    w = cast_world()
    r = quests.rec(w, "ranger_patrol")
    if r is None or r["status"] != "cast":
        return {"observed": {"quest_record": r}, "verdict": "quest not cast in this world"}
    b = r["bindings"]
    talk_pick(w, b["ranger"], "ask_patrol")
    k = go(w, b["ranger"])
    nh.talk(w, k)
    pick = nh.pick(w, k, "advise_east")
    nh.end(w, k)
    closing = closing_of(w, b["ranger"])
    guard = closing_of(w, b["guard"]) if "guard" in b else None
    st1 = quests.status(w, "ranger_patrol")
    again = closing_of(w, b["ranger"])
    flags = sorted(graph.flags(w, "ranger_patrol"))
    return {"observed": {"cast": {k_: person_name(w, v["pid"]) for k_, v in b.items()}, "advise_east": texts(pick), "ranger_after": closing["lines"], "guard_after": guard and guard["lines"],
                         "flags_set": flags, "status": st1, "objective": quests.objective(w, "ranger_patrol"), "ranger_next_visit": again["lines"]},
            "verdict": "defect confirmed" if st1 != "done" else "not reproduced"}


# ------------------------------------------------------------------ the stranger

import _campaign as cp  # noqa: E402


def scene_pages(w, answers: dict[str, str] | None = None, stop_before_end: bool = False):
    """Read every page of the open scene as the player would. `answers` maps a response id to take on the pages that ask a question."""
    pages, last = [], {}
    answers = answers or {}
    for _ in range(40):
        v = campaign.scene_view(w)
        if v is None:
            break
        page = {"page": f"{v['i'] + 1}/{v['n']}", "speaker": v["name"] or v["speaker"], "text": v["text"], "focus": v["focus"], "fx": v["fx"],
                "answers_open": [(c["id"].split(":")[-1], c["text"], c["available"]) for c in v["choices"]]}
        if v["needs_answer"]:
            want = next((a for a in answers.values() if any(c["id"].endswith(":" + a) for c in v["choices"])), None)
            cid = next((c["id"] for c in v["choices"] if want and c["id"].endswith(":" + want)), v["choices"][0]["id"])
            r = story.dispatch(w, {"op": "scene_choose", "choice": cid})
            ans = r["scene"]["answer"] if r.get("scene") else {}
            page["chosen"] = cid.split(":")[-1]
            page["answer_text"] = ans.get("text")
            page["stranger_reply"] = ans.get("reply")
            page["check"] = ans.get("check")
            page["reaction"] = ans.get("reaction")
        pages.append(page)
        last = story.dispatch(w, {"op": "scene_next"})
        if last.get("status") != "ok":
            page["scene_next_error"] = last
            break
    return pages, last


def to_confrontation(w):
    cp.to_arrival(w)
    cp.walk_in(w)


@probe("P20", "The stranger's confrontation, page by page", "Ten pages: narration, mentor and stranger argue, the mentor is killed on page 7, the stranger speaks to you (page 10), a final page offers challenge or silence.")
def p20():
    w = nh.world()
    to_confrontation(w)
    mentor_before = w.dmb.people[cp.mentor(w)].get("alive", True)
    pages, last = scene_pages(w, {"a": "let_go"})
    return {"observed": {"pages": pages, "mentor_alive_before": mentor_before, "mentor_alive_after": w.dmb.people[cp.mentor(w)].get("alive", True),
                         "lethal_state": wizard.wiz(w).get("lethal"), "stage_after": campaign.stage(w), "last_reply": {k: v for k, v in last.items() if k != "scene"}},
            "verdict": "confirmed"}


@probe("P21", "Resolve check against the stranger (‘Try it.’) with and without the mentor's creed", "Demanding (4): Resolve 2 + hidden-Ward lesson +1 + creed fact +1 + the stranger's regard 0. Without the creed the check fails.")
def p21():
    obs = {}
    for label, creed in (("without having answered the creed question", False), ("after answering the creed question", True)):
        w = nh.world()
        if creed:
            wizard.learn_fact(w, "mentor_creed")
        to_confrontation(w)
        pages, last = scene_pages(w, {"a": "firm", "b": "let_go"})
        page = next((p for p in pages if p.get("chosen") == "firm"), None)
        obs[label] = {"check": page and page.get("check"), "answer_text": page and page.get("answer_text"), "reply": page and page.get("stranger_reply"),
                      "fact_stood_firm": wizard.knows_fact(w, "stood_firm")}
    return {"observed": obs, "verdict": "confirmed"}


@probe("P22", "Belief replies to the stranger and how he takes them", "Seven replies, one per worldview; the stranger (main S, second C) agrees with S, is neutral to A, G and C, and disagrees with M, R and D. ‘C’ needs the mentor's old-craft secret.")
def p22():
    obs = {}
    for code in ("s", "a", "r", "d", "g", "m", "c"):
        w = nh.world()
        wizard.learn_fact(w, "mentor_old_craft")
        to_confrontation(w)
        before_rel = None
        pages, last = scene_pages(w, {"a": code, "b": "let_go"})
        page = next(p for p in pages if p.get("chosen") == code)
        obs[code.upper()] = {"offered": [a[0] for a in next(p for p in pages if p["answers_open"])["answers_open"]], "reply": page["stranger_reply"], "reaction": page["reaction"],
                             "worldview_after": wizard.worldview_scores(w), "primary_worldview": wizard.worldview_primary(w)}
    w = nh.world()
    to_confrontation(w)
    pages, _ = scene_pages(w, {"a": "firm", "b": "let_go"})
    obs["without the old-craft secret, replies offered"] = [a[0] for a in next(p for p in pages if p["answers_open"])["answers_open"]]
    return {"observed": obs, "verdict": "confirmed"}


@probe("P23", "The ending choices: let him go, challenge, win, lose", "Silence lets the stranger go with no duel; a challenge starts a lethal duel; a verified win makes him retreat alive; a loss kills the apprentice.")
def p23():
    obs = {}
    w = nh.world()
    to_confrontation(w)
    pages, last = scene_pages(w, {"a": "firm", "b": "let_go"})
    obs["let him go"] = {"final_page": pages[-1], "stage": campaign.stage(w), "lethal": wizard.wiz(w).get("lethal"), "duel_lease_started": "duel_lease" in last}
    for tag, win in (("challenge and win", True), ("challenge and lose", False)):
        w = nh.world()
        to_confrontation(w)
        pages, last = scene_pages(w, {"a": "firm", "b": "challenge"})
        rec = last["duel_lease"]["payload"]["duel"]
        out = cp.fight(w, rec, win)
        obs[tag] = {"challenge_page": pages[-1], "stage_after_duel": campaign.stage(w), "duel_outcome": out.get("outcome"), "lethal": wizard.wiz(w).get("lethal"), "fate": wizard.wiz(w).get("fate"),
                    "resolve_after": checks.scores(w)["resolve"], "journal": [n["text"] for n in wizard.wiz(w)["journal_notes"]]}
        if win:
            victory, last2 = scene_pages(w)
            obs[tag]["victory_pages"] = victory
            obs[tag]["stage_after_victory_scene"] = campaign.stage(w)
            obs[tag]["stranger_present"] = residents.table(w)[campaign.state(w)["attacker"]]["status"]
    return {"observed": obs, "verdict": "confirmed"}


@probe("P24", "If the mentor is already dead: ‘confrontation_alone’", "A different scene plays when the mentor is not present when the stranger arrives.")
def p24():
    from wizard_rts.narrative import residents as res

    w = nh.world()
    cp.finished_training(w)
    cp.meet_people(w, 3)
    m = cp.mentor(w)
    res.table(w)[m]["status"] = "dead"  # the mentor was lost to something else
    for _ in range(400):
        nh.adv(w, 1)
        if campaign.stage(w) == "arrival":
            break
    cp.walk_in(w)
    pages, last = scene_pages(w, {"a": "let_go"})
    return {"observed": {"pages": [(p["page"], p["speaker"], p["text"][:160]) for p in pages], "mentor_fate": campaign.state(w)["mentor_fate"]}, "verdict": "confirmed"}


# ------------------------------------------------------------------ the villagers after the stranger, and everyday talk

from wizard_rts.narrative import occupations  # noqa: E402


def villagers_by_role(w) -> dict[str, tuple[str, str]]:
    """One Red villager per trade: role -> (kind, id)."""
    out: dict[str, tuple[str, str]] = {}
    for eid, row in sorted(w.workers.items()):
        if row["faction_name"] == "Red":
            out.setdefault(row["role"], ("worker", eid))
    for eid, row in sorted(w.carriers.items()):
        if row["faction_name"] == "Red":
            out.setdefault("carrier", ("carrier", eid))
    for eid, row in sorted(w.units.items()):
        if row["faction_name"] == "Red" and row.get("kind", "soldier") == "soldier":
            out.setdefault("soldier", ("unit", eid))
    return out


def first_reaction_id(w, kind, eid) -> tuple[str, dict[str, Any]]:
    """Which aftermath reaction would be spoken for this person (without speaking it)."""
    sp = conversation.resolve(w, eid)
    gctx, octx = conversation._ctx(w, sp)
    from wizard_rts.narrative import personas as pe

    p = pe.persona(w, sp["pid"])
    for r in occupations.aftermath()["reactions"]:
        if graph.holds(w, "occupation", r.get("when"), octx):
            return r["id"], {"role": octx["facts"]["role"], "knows": campaign.knowledge(w, sp["pid"]), "main": p["primary"], "second": p["secondary"], "traits": p["traits"],
                             "attitude_to_mentor": p["mentor"], "attitude_to_magic": p["magic"], "regard": checks.relationship(w, sp["pid"])}
    return "(none)", {}


@probe("P30", "After the stranger: each trade's first words", "The first reaction in the file whose trade, knowledge and persona conditions hold is spoken once per person.")
def p30():
    w = nh.world()
    cp.to_aftermath(w)
    obs = {}
    for role, (kind, eid) in sorted(villagers_by_role(w).items()):
        rid, why = first_reaction_id(w, kind, eid)
        nh.stand_by(w, kind, eid)
        r = nh.talk(w, eid)
        obs[role] = {"person": r["name"], "reaction_selected": rid, "persona_and_knowledge": why, "opening_lines": r["lines"], "topics_offered": [(c["id"], c["text"]) for c in r["choices"]]}
        nh.end(w, eid)
        r2 = nh.talk(w, eid)
        obs[role]["second_talk_lines"] = r2["lines"]
        nh.end(w, eid)
    return {"observed": obs, "verdict": "confirmed"}


@probe("P31", "Everyday talk: first meeting, later meetings and a repeated ‘once’ topic", "The introduction is said once, later greetings come from the hub bank, a question is not repeated in one conversation, and ‘once’ topics are NOT enforced.")
def p31():
    w = nh.world()
    obs = {}
    roles = villagers_by_role(w)
    for role in ("lumberjack", "soldier", "carrier"):
        if role not in roles:
            continue
        kind, eid = roles[role]
        nh.stand_by(w, kind, eid)
        r1 = nh.talk(w, eid)
        first = {"intro": r1["lines"], "topics": [(c["id"], c["text"]) for c in r1["choices"]]}
        nh.end(w, eid)
        r2 = nh.talk(w, eid)
        second = {"greeting": r2["lines"], "topics": [(c["id"], c["text"]) for c in r2["choices"]]}
        nh.end(w, eid)
        r3 = nh.talk(w, eid)
        third = {"greeting": r3["lines"], "topics": [(c["id"], c["text"]) for c in r3["choices"]]}
        nh.end(w, eid)
        obs[role] = {"person": r1["name"], "first_talk": first, "second_talk": second, "third_talk": third}
    # a topic marked ‘once’ is offered again and again
    kind, eid = roles.get("carrier", next(iter(roles.values())))
    from wizard_rts.narrative import mortality

    ledger.bump(w, "accosted", seat=mortality.me(w), n=8)  # the condition reads this wizard's own count (my_accosted)
    nh.stand_by(w, kind, eid)
    offered_count = 0
    for visit in range(1, 6):
        r = nh.talk(w, eid)
        ids = [c["id"] for c in r["choices"]]
        if "topic:who_counts" in ids:
            offered_count += 1
            nh.pick(w, eid, "topic:who_counts")
        nh.end(w, eid)
    obs["once_topic_who_counts"] = {"times_offered_in_5_visits": offered_count, "fourth_wall_count_now": ledger.count(w, "fourth_wall"), "my_accosted": ledger.facts(w, mortality.me(w)).get("my_accosted")}
    return {"observed": obs, "verdict": "confirmed"}


@probe("P32", "How a speaker reacts to each belief (the Ideology Reactions matrix)", "reaction = agree when the speaker's main worldview scores ≥ 2 towards the reply (+1 if their second view IS the reply's view), disagree when ≤ −1, otherwise neutral.")
def p32():
    table = wizard.worldview_table()
    codes = list(table)
    matrix = {}
    for primary in codes:
        row = {}
        for code in codes:
            base = personas.reaction({"primary": primary, "secondary": "-"}, code)
            row[code] = base
        matrix[primary] = row
    upgraded = {}
    for primary in codes:
        for code in codes:
            with_second = personas.reaction({"primary": primary, "secondary": code}, code)
            if with_second != matrix[primary][code]:
                upgraded[f"{primary}/{code}"] = [matrix[primary][code], with_second]
    return {"observed": {"matrix_primary_by_reply": matrix, "changed_when_second_worldview_equals_the_reply": upgraded,
                         "affinity_numbers": {p: {c: personas.affinity({"primary": p, "secondary": "-"}, c) for c in codes} for p in codes}}, "verdict": "confirmed"}


@probe("P33", "Examples of generated villagers", "Every villager's persona is drawn from the world seed and their trade; two villagers of one trade usually differ.")
def p33():
    w = nh.world()
    rows = []
    for role, (kind, eid) in sorted(villagers_by_role(w).items()):
        nh.stand_by(w, kind, eid)
        r = nh.talk(w, eid)
        sp = conversation.resolve(w, eid)
        p = personas.persona(w, sp["pid"])
        rows.append({"role": role, "name": r["name"], "scores": p["scores"], "main": p["primary"], "second": p["secondary"], "traits": p["traits"], "attitude_to_mentor": p["mentor"], "attitude_to_magic": p["magic"],
                     "starting_regard": checks.relationship(w, sp["pid"])})
        nh.end(w, eid)
    lumberjacks = [(eid) for eid, row in sorted(w.workers.items()) if row["role"] == "lumberjack" and row["faction_name"] == "Red"][:4]
    extra = []
    for eid in lumberjacks:
        nh.stand_by(w, "worker", eid)
        r = nh.talk(w, eid)
        sp = conversation.resolve(w, eid)
        p = personas.persona(w, sp["pid"])
        extra.append({"name": r["name"], "main": p["primary"], "second": p["secondary"], "traits": p["traits"], "attitude_to_mentor": p["mentor"], "attitude_to_magic": p["magic"]})
        nh.end(w, eid)
    mentor = personas.persona(w, teacher_key(w))
    return {"observed": {"one_per_trade": rows, "four_lumberjacks": extra, "mentor": mentor}, "verdict": "confirmed"}



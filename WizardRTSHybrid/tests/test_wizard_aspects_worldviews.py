"""Aspects (capability) and worldviews (belief) in the wizard's conversations, and the personas of the people who answer: real scores and rules, repeat-safe
checks, once-only ideological consequences, distinguishable reactions, persistence."""
import json
from pathlib import Path

import pytest

import _campaign as cp
import _nh as nh
from test_narrative_quests import QID, cast_world, decide, go, hear_both
from test_wizard_tutorial import go_to_teacher
from wizard_rts import story
from wizard_rts.narrative import campaign, checks, graph, persist, personas, quests, residents, tutorial, wizard

from sim.dmb.narrative.aspects import AspectService
from sim.dmb.people.registry import PeopleService

HERE = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    cp.quick(monkeypatch)


def set_score(w, aspect, value):
    checks.service(w)
    AspectService(w.dmb)._store()["scores"]["player"][aspect] = value


def mentor_talk(w):
    t = go_to_teacher(w)
    nh.talk(w, t)
    nh.pick(w, t, "learn_colours")
    return t


# ------------------------------------------------------------------ Aspects

def test_a_check_uses_the_real_aspect_score_and_the_rules_of_the_service():
    w = nh.world()
    t = mentor_talk(w)
    r = nh.pick(w, t, "ask_wards")  # Curiosity against "demanding" (4): score 3 + the mentor's warmth (+1)
    c = r["check"]
    assert (c["aspect"], c["score"], c["relationship"], c["total"], c["threshold"], c["passed"]) == ("curiosity", 3, 1, 4, 4, True)
    w2 = nh.world()
    set_score(w2, "curiosity", 1)
    t2 = mentor_talk(w2)
    c2 = nh.pick(w2, t2, "ask_wards")["check"]
    assert (c2["score"], c2["total"], c2["passed"]) == (1, 2, False)  # the same words, a lesser apprentice: a different result


def test_the_speakers_relationship_moves_the_result():
    w = nh.world()
    t = go_to_teacher(w)
    PeopleService(w.dmb).set_relationship(t, "player", -50)  # the mentor is angry with the apprentice
    nh.talk(w, t)
    nh.pick(w, t, "learn_colours")
    c = nh.pick(w, t, "ask_wards")["check"]
    assert c["relationship"] == -1 and c["total"] == 2 and not c["passed"]


def test_evidence_the_apprentice_has_gathered_changes_the_outcome_and_allows_a_retry():
    w = nh.world()
    t = mentor_talk(w)
    fail = nh.pick(w, t, "ask_glow")  # Wonder 2 + warmth 1 = 3 against 4
    assert fail["check"]["passed"] is False and not fail["ends"] and "evening light" in fail["text"]  # an alternative path, not a dead end
    ids = {c["id"]: c for c in fail["choices"]}
    assert ids["ask_glow"]["available"] is False  # asking again with nothing new is not offered
    assert story.dispatch(w, {"op": "choose", "npc": t, "choice": "ask_glow"})["reason"] == "choice_unavailable"
    assert len(AspectService(w.dmb)._store()["failed_fingerprints"]) == 1  # and cannot be ground through
    # the apprentice learns something: now there is evidence and the attempt is a new one
    wizard.learn_fact(w, "ward_lore")
    wizard.complete_lesson(w, "hidden_ward")
    r = nh.pick(w, t, "ask_glow")
    assert r["check"]["passed"] is True and r["check"]["evidence"] == 2 and "older than the schools" in r["text"]
    assert wizard.knows_fact(w, "mentor_old_craft")


def test_a_passed_check_is_not_rolled_again_and_pays_nothing_twice():
    w = nh.world()
    t = mentor_talk(w)
    nh.pick(w, t, "ask_wards")
    first = list(wizard.wiz(w)["facts"])
    again = nh.pick(w, t, "ask_wards")
    assert again["check"]["again"] is True and again["check"]["passed"] is True
    assert wizard.wiz(w)["facts"] == first and first.count("ward_lore") == 1


def test_aspect_changes_are_applied_once():
    w = nh.world()
    assert checks.scores(w)["resolve"] == 2
    assert checks.change_once(w, "resolve", 1, "x")["applied"] is True
    assert checks.change_once(w, "resolve", 1, "x")["applied"] is False
    assert checks.scores(w)["resolve"] == 3
    assert checks.change_once(w, "resolve", 1, "y")["after"] == 4


def test_scores_and_results_survive_save_and_load(tmp_path):
    w = nh.world()
    t = mentor_talk(w)
    nh.pick(w, t, "ask_glow")  # fails
    persist.save_world(w, tmp_path / "s.pkl")
    loaded, _ = persist.load_world(tmp_path / "s.pkl")
    assert checks.scores(loaded) == checks.scores(w)
    assert checks.table(loaded) == checks.table(w)
    t2 = go_to_teacher(loaded)
    r = nh.talk(loaded, t2)
    assert {c["id"]: c for c in r["choices"]}["ask_glow"]["available"] is False  # still blocked after loading: no save-scumming a failed attempt
    assert story.dispatch(loaded, {"op": "choose", "npc": t2, "choice": "ask_glow"})["reason"] == "choice_unavailable"


def test_checks_in_ordinary_conversations_are_per_person():
    w = nh.world()
    cp.finished_training(w)
    wizard.learn_fact(w, "stranger_harrowmere")
    # the same Guile topic with two different villagers keeps two separate results
    results = {}
    for kind, table in (("worker", w.workers), ("carrier", w.carriers)):
        for eid in sorted(table):
            if table[eid]["faction_name"] == "Red" and len(results) < 2:
                results[eid] = (kind, eid)
    assert len(results) == 2
    keys = set()
    for eid, (kind, _e) in results.items():
        nh.stand_by(w, kind, eid)
        nh.talk(w, eid)
        nh.end(w, eid)
        pid = w.narrative["links"][f"{kind}:{eid}"]
        keys.add(checks.key({"template": "occupation", "speaker_pid": pid}, "t:t_guile"))
    assert len(keys) == 2


# ------------------------------------------------------------------ worldviews

def test_the_worldview_table_is_a_faithful_copy_of_the_dialogue_factorys():
    src = json.loads((HERE.parent / "tools" / "dialogue_generation" / "worldviews.json").read_text())["worldviews"]
    mine = wizard.worldview_table()
    assert [w["code"] for w in src] == list(mine) == ["M", "A", "R", "G", "S", "D", "C"]
    for w in src:
        assert mine[w["code"]]["delta"] == w["delta"] and mine[w["code"]]["key"] == w["key"]
    import re

    for f in (HERE / "wizard_rts" / "narrative").glob("*.py"):
        assert not re.search(r"^\s*(from|import) tools\b", f.read_text(), re.M), f  # no runtime path imports tools/


def test_a_worldview_choice_applies_its_established_delta_exactly_once():
    w = nh.world()
    assert wizard.apply_worldview_choice(w, "r1", "D") is True
    assert wizard.apply_worldview_choice(w, "r1", "D") is False
    assert wizard.worldview_scores(w) == {"M": 0, "A": 1, "R": 1, "G": -1, "S": -1, "D": 3, "C": 0}
    assert wizard.worldview_primary(w) == "D"
    wizard.apply_worldview_choice(w, "r2", "S")
    assert wizard.worldview_scores(w)["S"] == 2 and wizard.worldview_scores(w)["D"] == 2


def test_the_mentors_creed_choices_are_distinguishable_and_pay_once():
    outs = {}
    for choice in ("creed_d", "creed_s", "creed_a"):
        w = nh.world()
        t = go_to_teacher(w)
        nh.talk(w, t)
        nh.pick(w, t, "why_not_rule")
        r = nh.pick(w, t, choice)
        outs[choice] = (r["text"], wizard.worldview_scores(w), w.dmb.people[t]["relationship_map"]["player"])
    assert len({o[0] for o in outs.values()}) == 3  # three different answers from the mentor
    assert outs["creed_d"][2] > outs["creed_a"][2] > outs["creed_s"][2]  # the mentor's convictions colour how they take it
    assert outs["creed_d"][1]["D"] == 3 and outs["creed_s"][1]["S"] == 3
    w = nh.world()
    t = go_to_teacher(w)
    nh.talk(w, t)
    nh.pick(w, t, "why_not_rule")
    nh.pick(w, t, "creed_d")
    before = dict(wizard.worldview_scores(w))
    r = nh.talk(w, t)
    assert "why_not_rule" not in nh.ids(r)  # asked once
    assert wizard.worldview_scores(w) == before


def test_an_ideological_answer_is_taken_according_to_the_listeners_own_persona():
    w = nh.world()
    cp.to_aftermath(w)
    reactions = {}
    for kind, table in (("worker", w.workers), ("carrier", w.carriers)):
        for eid in sorted(table):
            row = table[eid]
            if row["faction_name"] != "Red":
                continue
            nh.stand_by(w, kind, eid)
            r = nh.talk(w, eid)
            if "topic:t_meaning" in nh.ids(r):
                out = nh.pick(w, eid, "topic:t_meaning")
                resp = next(c["id"] for c in out["choices"] if c["id"].startswith("resp:topic:t_meaning:s"))
                reply = nh.pick(w, eid, resp)
                pid = w.narrative["links"][f"{kind}:{eid}"]
                p = personas.persona(w, pid)
                reactions[eid] = (personas.reaction(p, "S"), reply["reaction"], reply["text"], p["primary"])
            nh.end(w, eid)
            if len(reactions) >= 12:
                break
    assert reactions
    for expected, got, _text, _prim in reactions.values():
        assert expected == got  # the reply follows the established worldview deltas of the listener's own view
    # not everyone agrees and not everyone disagrees
    assert len({g for _e, g, _t, _p in reactions.values()}) >= 2 or len({p for *_a, p in reactions.values()}) >= 2
    # the apprentice's own leaning moved once, however many people were told
    assert wizard.worldview_scores(w)["S"] == 3


def test_repeating_a_conversation_does_not_repeat_its_rewards():
    w = nh.world()
    cp.to_aftermath(w)
    wid = nh.find_worker(w, "lumberjack")
    nh.stand_by(w, "worker", wid)
    nh.talk(w, wid)
    out = nh.pick(w, wid, "topic:t_meaning")
    resp = next(c["id"] for c in out["choices"] if c["id"].startswith("resp:topic:t_meaning:a"))
    nh.pick(w, wid, resp)
    pid = w.narrative["links"]["worker:" + wid]
    rel, wv = w.dmb.people[pid]["relationship_map"].get("player", 0), dict(wizard.worldview_scores(w))
    nh.end(w, wid)
    r = nh.talk(w, wid)
    assert not [c for c in r["choices"] if c["id"].startswith("resp:topic:t_meaning")]  # one answer per person per topic
    out2 = nh.pick(w, wid, "topic:t_meaning")
    assert not [c for c in out2["choices"] if c["id"].startswith("resp:topic:t_meaning")]
    assert w.dmb.people[pid]["relationship_map"].get("player", 0) == rel and wizard.worldview_scores(w) == wv


def test_the_stranger_takes_the_apprentices_answer_by_his_own_view():
    replies = {}
    for resp in ("s", "d", "a"):
        w = nh.world()
        cp.to_arrival(w)
        cp.walk_in(w)
        for _ in range(20):
            v = campaign.scene_view(w)
            if v["needs_answer"]:
                break
            story.dispatch(w, {"op": "scene_next"})
        cid = next(c["id"] for c in v["choices"] if c["id"].endswith(":" + resp))
        out = story.dispatch(w, {"op": "scene_choose", "choice": cid})
        replies[resp] = (out["scene"]["answer"]["reaction"], out["scene"]["answer"]["reply"], wizard.worldview_scores(w))
    assert replies["s"][0] == "agree" and replies["d"][0] == "disagree" and replies["a"][0] == "neutral"  # a Supremacist's affinity table
    assert len({r[1] for r in replies.values()}) == 3
    assert replies["s"][2]["S"] == 3 and replies["d"][2]["D"] == 3


def test_the_resolve_check_in_the_confrontation_depends_on_what_the_apprentice_has_done():
    results = {}
    for asked in (False, True):
        w = nh.world()
        t = go_to_teacher(w)
        nh.talk(w, t)
        nh.pick(w, t, "learn_colours")
        if asked:
            nh.pick(w, t, "why_not_rule")
            nh.pick(w, t, "creed_leave")
        nh.learn(w)
        nh.adv(w, 2)
        cp.meet_people(w, 3)
        for _ in range(200):
            nh.adv(w, 1)
            if campaign.stage(w) == "arrival":
                break
        cp.walk_in(w)
        for _ in range(20):
            v = campaign.scene_view(w)
            if v["needs_answer"]:
                break
            story.dispatch(w, {"op": "scene_next"})
        cid = next(c["id"] for c in v["choices"] if c["id"].endswith(":firm"))
        results[asked] = story.dispatch(w, {"op": "scene_choose", "choice": cid})["scene"]["answer"]["check"]
    assert results[False]["passed"] is False and results[True]["passed"] is True
    assert results[True]["total"] == results[False]["total"] + 1  # the mentor's lesson was evidence


# ------------------------------------------------------------------ personas and relationships

def test_personas_are_deterministic_stable_and_independent_of_who_is_met_first():
    a = nh.world()
    b = nh.world()
    ids = sorted(i for i, r in a.workers.items() if r["faction_name"] == "Red")[:6]
    first = {}
    for i in ids:
        nh.stand_by(a, "worker", i)
        nh.talk(a, i)
        nh.end(a, i)
        first[i] = personas.persona(a, a.narrative["links"]["worker:" + i])
    for i in reversed(ids):  # the other world meets them in the opposite order
        nh.stand_by(b, "worker", i)
        nh.talk(b, i)
        nh.end(b, i)
        assert personas.persona(b, b.narrative["links"]["worker:" + i]) == first[i]
    for i in ids:
        assert personas.persona(a, a.narrative["links"]["worker:" + i]) == first[i]  # and it does not change


def test_occupations_tilt_personas_without_dictating_them():
    w = nh.world()
    draw = lambda key, role: personas._draw(w, key, role)
    rangers = [draw(f"worker:r{i}", "ranger") for i in range(80)]
    cutters = [draw(f"worker:c{i}", "lumberjack") for i in range(80)]
    soldiers = [draw(f"unit:s{i}", "soldier") for i in range(80)]
    share = lambda xs, code: sum(1 for p in xs if p["primary"] == code) / len(xs)
    assert share(rangers, "D") > share(cutters, "D") and share(cutters, "G") > share(rangers, "G") and share(soldiers, "M") > share(rangers, "M")
    for group in (rangers, cutters, soldiers):
        assert len({p["primary"] for p in group}) >= 4  # no trade is of one mind
        assert len({tuple(p["traits"]) for p in group}) >= 10


def test_people_are_not_all_the_same_before_the_attack_either():
    w = nh.world()
    cp.finished_training(w)
    lines = {}
    for kind, table in (("worker", w.workers), ("carrier", w.carriers)):
        for eid in sorted(table):
            if table[eid]["faction_name"] != "Red" or len(lines) >= 10:
                continue
            nh.stand_by(w, kind, eid)
            r = nh.talk(w, eid)
            ids = nh.ids(r)
            for t in ("topic:opinion_wizards", "topic:opinion_mentor", "topic:opinion_apprentice"):
                if t in ids:
                    lines[(eid, t)] = nh.pick(w, eid, t)["text"]
            nh.end(w, eid)
    assert len({text for (e, t), text in lines.items() if t == "topic:opinion_wizards"}) >= 2 or not [1 for (e, t) in lines if t == "topic:opinion_wizards"]
    assert lines  # at least some of them were asked, and every answer is a finished sentence
    assert all("{" not in text and text for text in lines.values())


def test_helping_someone_earlier_makes_them_more_willing_afterwards():
    w, bind = cast_world()
    hear_both(w, bind)
    decide(w, bind, "say_cutter")
    cutter, planter = bind["cutter"], bind["planter"]
    cpid, ppid = w.narrative["links"]["worker:" + cutter["id"]], w.narrative["links"]["worker:" + planter["id"]]
    assert w.dmb.people[cpid]["relationship_map"]["player"] == 10 and w.dmb.people[ppid]["relationship_map"]["player"] == -4
    # the helped woodcutter is, afterwards, the one who offers to ask around
    cp.finished_training(w)
    w.narrative["campaign"]["stage"] = "aftermath"
    w.narrative["campaign"]["mentor_fate"] = "killed_by_stranger"
    for who, expect in ((cutter, True), (planter, False)):
        go(w, who)
        r = nh.talk(w, who["id"])
        out = nh.pick(w, who["id"], "topic:t_leave") if "topic:t_leave" in nh.ids(r) else None
        assert out is not None
        assert ("ask around" in out["text"]) is expect
        nh.end(w, who["id"])

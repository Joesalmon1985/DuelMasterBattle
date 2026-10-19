"""The world notices the player (plan `docs/PLAN_PLAYER_STRESS_AND_PROGRESSION.md` section 3, after the stress report's findings): neglect, spam, arson,
a new generation, losses, the stale scene, Mira's idle and forfeit lines, the inner voice. Every line here is placeholder prose; what is tested is that
each is reachable by the behaviour it answers, said at most as often as intended, and never fabricated (its facts hold)."""
from __future__ import annotations

import _stress as S
import pytest
from _party import Table
from test_ai_wizard import bring_together
from test_village import fight_pest

from wizard_rts.narrative import campaign, ledger, mortality, party, pests, progression, residents, voice, wizard


def solo(ai: int = 1) -> Table:
    t = Table(humans=1, ai=ai)
    t.advance(1)
    return t


def ai_of(t: Table):
    (ai,) = t.session.ais.values()
    return ai


def burn_people(t: Table, h, n: int) -> int:
    done = 0
    for cls, table in (("carrier", t.world.carriers), ("worker", t.world.workers)):
        for tid in list(sorted(table)):
            if done >= n:
                return done
            if S.burn(t, h, tid).get("status") == "ok":
                done += 1
                t.advance(0.7)
    return done


# ------------------------------------------------------------------ arson

def test_the_village_notices_a_burned_person_the_mentor_the_mother_the_villagers_mira_and_the_inner_voice():
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    bring_together(t, joe, ai)
    assert burn_people(t, joe, 1) == 1
    assert ledger.count(t.world, "burned_people", joe.id) == 1 and ledger.count(t.world, "burned_things", joe.id) == 1
    t.advance(3)
    ns = joe.state()["notices"]  # (a poll clears the notices: read them once)
    lines = [n["line"] for n in ns if n["kind"] == "ai_says"]
    assert "you_burned_someone" in lines, lines
    voices = [n for n in ns if n["kind"] == "inner_voice"]
    assert voices and voices[0]["trigger"] == "first_person_burned" and voices[0]["aspect"] == "Empathy", voices
    r = S.talk_and_leave(t, joe, S.mentor(t))
    assert "carriers came past my door" in S.text_of(r), S.text_of(r)
    r = S.talk_and_leave(t, joe, S.mum(t, joe))
    assert "set alight" in S.text_of(r), S.text_of(r)
    r = S.talk_and_leave(t, joe, S.official(t))
    assert "burns the help" in S.text_of(r), S.text_of(r)
    w = S.red_workers(t)[0]
    r = S.ask(t, joe, w)
    ids = [c[0] for c in S.choices_of(r)]
    assert "topic:seen_burning" in ids, ids
    r2 = joe.op("choose", npc=w, choice="topic:seen_burning")
    assert "Put that down" in S.text_of(r2) or "set a carrier alight" in S.text_of(r2), S.text_of(r2)
    joe.op("end_talk", npc=w)
    # once each: the mother does not say it twice, Mira does not say it twice
    r = S.talk_and_leave(t, joe, S.mum(t, joe))
    assert "set alight" not in S.text_of(r)
    assert burn_people(t, joe, 1) == 1
    t.advance(3)
    assert [n["line"] for n in S.notices(joe, "ai_says")].count("you_burned_someone") == 0, "said once"


def test_ten_trees_wake_curiosity_and_the_lumberjack_complains_through_the_mentor():
    t = solo(ai=0)
    joe = t.people[0]
    S.talk_and_leave(t, joe, S.mentor(t))
    burned = 0
    for tid in list(sorted(t.world.trees)):
        if burned >= 10:
            break
        burned += S.burn(t, joe, tid).get("status") == "ok"
        t.advance(0.7)
    assert ledger.count(t.world, "burned_trees", joe.id) == 10
    t.advance(2)
    voices = S.notices(joe, "inner_voice")
    assert any(v["trigger"] == "tenth_tree" and v["aspect"] == "Curiosity" for v in voices), voices
    r = S.talk_and_leave(t, joe, S.mentor(t))
    assert "lumberjack came to see me" in S.text_of(r), S.text_of(r)


def test_the_burned_warehouse_is_noticed_by_mira_the_mother_and_reason():
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    bring_together(t, joe, ai)
    sid, b = pests.home(t.world)
    assert S.burn(t, joe, b["id"])["status"] == "ok"
    assert ledger.count(t.world, "burned_home_buildings", joe.id) == 1
    t.advance(3)
    ns = joe.state()["notices"]
    assert "you_burned_the_store" in [n["line"] for n in ns if n["kind"] == "ai_says"]
    assert any(v["trigger"] == "warehouse_burned" for v in ns if v["kind"] == "inner_voice")
    r = S.talk_and_leave(t, joe, S.mum(t, joe))
    assert "smell it from here" in S.text_of(r), S.text_of(r)


# ------------------------------------------------------------------ neglect

def test_doing_nothing_is_noticed_by_the_mentor_the_mother_mira_and_resolve():
    t = solo()
    joe = t.people[0]
    S.talk_and_leave(t, joe, S.mentor(t))  # he has met you; now you vanish
    for _ in range(13):
        t.advance(60, step_ms=500)
    ns = joe.state()["notices"]
    v = [n for n in ns if n["kind"] == "inner_voice" and n["trigger"] == "idle_ten"]
    assert v and v[0]["aspect"] == "Resolve", ns
    idle = [n for n in ns if n["kind"] == "ai_says" and n["line"] == "idle"]
    assert 1 <= len(idle) <= 4, idle
    r = S.ask(t, joe, S.mentor(t))
    assert "standing about" in S.text_of(r), S.text_of(r)
    joe.op("end_talk", npc=S.mentor(t))
    r = S.talk_and_leave(t, joe, S.mum(t, joe))
    assert "send the chickens" in S.text_of(r) or "store is empty" in S.text_of(r).lower(), S.text_of(r)  # (thirteen idle minutes empty the store too)
    w = S.red_workers(t)[0]
    r = S.ask(t, joe, w)
    assert "topic:nothing_doing" in [c[0] for c in S.choices_of(r)]
    joe.op("end_talk", npc=w)


def test_a_mentor_never_visited_for_a_quarter_hour_greets_you_accordingly():
    t = solo(ai=0)
    joe = t.people[0]
    progression.state(t.world)["played_ms"] = 16 * 60000
    r = S.talk_and_leave(t, joe, S.mentor(t))
    assert "So you exist" in S.text_of(r), S.text_of(r)
    with joe.seat_state():
        assert wizard.lesson_done(t.world, "meet")


def test_an_empty_store_is_noticed_by_the_keeper_the_mother_and_the_mentor(monkeypatch):
    monkeypatch.setitem(pests.config._file()["pests"], "eat_every_ms", 300)
    t = solo(ai=0)
    joe = t.people[0]
    S.talk_and_leave(t, joe, S.mentor(t))
    for _ in range(40):
        t.advance(10)
        if pests.food_left(t.world) <= 0:
            break
    assert pests.food_left(t.world) <= 0
    progression.state(t.world)["played_ms"] = max(progression.state(t.world)["played_ms"], 6 * 60000)
    r = S.talk_and_leave(t, joe, S.keeper(t))
    assert "nothing left" in S.text_of(r).lower(), S.text_of(r)
    r = S.talk_and_leave(t, joe, S.mum(t, joe))
    assert "store is empty" in S.text_of(r).lower(), S.text_of(r)
    r = S.talk_and_leave(t, joe, S.mentor(t))
    assert "store is empty" in S.text_of(r).lower(), S.text_of(r)


# ------------------------------------------------------------------ spam

def test_the_fifth_visit_gets_you_again_from_villagers_and_the_rollkeeper_counts_the_standing():
    t = solo(ai=0)
    joe = t.people[0]
    w = S.red_workers(t)[0]
    openings = []
    for _ in range(7):
        r = S.ask(t, joe, w)
        openings.append(S.text_of(r)[:60])
        joe.op("end_talk", npc=w)
    from wizard_rts.narrative import occupations

    often = set(occupations.data()["often"]) | {line for tribe in occupations.data()["tribes"].values() for line in tribe.get("often", [])}
    assert any(any(o.startswith(x[:40]) for x in often) for o in openings[5:]), openings  # the generic pool, or the tribe's own
    o = S.official(t)
    texts = [S.text_of(S.talk_and_leave(t, joe, o)) for _ in range(4)]
    assert any("Still here" in x for x in texts) and any("second column" in x for x in texts[3:]), texts


def test_the_contestants_notice_a_second_visit():
    t = solo(ai=0)
    joe = t.people[0]
    from wizard_rts.trial import run as trial

    seen = 0
    for cid, pid in sorted(trial.state(t.world)["contestants"].items()):
        first = S.text_of(S.talk_and_leave(t, joe, pid))
        second = S.text_of(S.talk_and_leave(t, joe, pid))
        if first != second:
            seen += 1
    assert seen >= 4, seen


# ------------------------------------------------------------------ generations

def test_the_second_generation_is_remembered_by_name():
    t = solo()
    joe = t.people[0]
    assert joe.op("new_game")["status"] == "ok" and party.generation(t.world) == 2
    t.advance(2)
    for who, key, phrase in (("mentor", S.mentor(t), "You are not Joe"), ("mother", S.mum(t, joe), "Joe's way of standing"), ("official", S.official(t), "under Joe's")):
        r = S.talk_and_leave(t, joe, key)
        assert phrase in S.text_of(r), (who, S.text_of(r))
    progression.state(t.world)["played_ms"] = 2 * 60000
    t.advance(3)
    assert any(v["trigger"] == "generation" and "Joe" in v["text"] for v in S.notices(joe, "inner_voice"))


# ------------------------------------------------------------------ the stale scene and the forfeit

def test_a_scene_nobody_answered_is_replaced_by_what_you_missed_and_gives_way_to_a_conversation(monkeypatch):
    import _campaign as camp

    camp.quick(monkeypatch, min_ms=20_000, fallback_ms=60_000, aftermath_fallback_ms=40_000)
    t = solo(ai=0)
    joe = t.people[0]
    t.wait_for_stage("arrival")
    with joe.seat_state():
        assert campaign.scene_view(t.world)["id"] == "notice"
    t.wait_for_stage("aftermath", seconds=600)
    with joe.seat_state():
        sc = campaign.scene_view(t.world)
    assert sc is not None and sc["id"] == "confrontation_missed" and "Nobody waited for you" in sc["text"], sc
    assert ledger.count(t.world, "missed_the_stranger", joe.id) == 1
    r = S.talk_and_leave(t, joe, S.mum(t, joe))
    assert r["status"] == "ok", "a page that asks nothing gives way when you talk to somebody"
    with joe.seat_state():
        assert campaign.scene_view(t.world) is None
    t.advance(130)  # (two game-minutes after whatever the inner voice said last)
    assert any(v["trigger"] == "missed" for v in S.notices(joe, "inner_voice"))


def test_walking_out_of_a_duel_you_demanded_is_a_death_mira_names_and_undoes():
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    for _ in range(3):
        bring_together(t, joe, ai)
        joe.op("pvp_challenge", target=ai.link.id)
        t.advance(6)
        if joe.link.duel_id and joe.link.duel_id in t.session.duels:
            break
    assert joe.op("pvp_forfeit")["status"] == "ok"
    t.advance(3)
    joe.op("pvp_leave")
    assert mortality.is_dead(t.world, joe.id) and t.session.ending is None
    for _ in range(60):
        t.advance(1)
        if not mortality.is_dead(t.world, joe.id):
            break
    assert not mortality.is_dead(t.world, joe.id)
    lines = [n["line"] for n in S.notices(joe, "ai_says")]
    assert "you_forfeited" in lines and ("resurrecting" in lines or "resurrected_you" in lines), lines


def test_the_inner_voice_keeps_its_distance_and_its_count():
    t = solo(ai=0)
    joe = t.people[0]
    st = voice.state(t.world)
    # two triggers true at once: only one speaks, the other waits two game-minutes
    burned = 0
    for tid in list(sorted(t.world.trees)):
        if burned >= 10:
            break
        burned += S.burn(t, joe, tid).get("status") == "ok"
        t.advance(0.7)
    assert burn_people(t, joe, 1) == 1
    t.advance(2)
    first = S.notices(joe, "inner_voice")
    assert len(first) == 1, first
    t.advance(130)
    second = S.notices(joe, "inner_voice")
    assert len(second) == 1 and second[0]["trigger"] != first[0]["trigger"]
    assert ledger.count(t.world, "inner_voice", joe.id) == 2
    assert all(n <= 1 for n in st["said"][str(joe.id)].values())

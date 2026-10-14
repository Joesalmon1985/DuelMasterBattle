"""B.4 and the first quest: the opening, the teacher's lessons through the real ops, the unlock rule, the gossip quest (narrative-only), save/load."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_wizard_duel_lease import play
from wizard_rts import narrative, server, story
from wizard_rts.narrative import duel_lease, graph, persist, residents, tutorial, wizard
from wizard_rts.world import HybridWorld

HERE = Path(__file__).resolve().parents[1]


def new_world(seed=507):
    w = HybridWorld(seed, profile="campaign")
    w.ai_enabled = False
    narrative.enable(w)
    tutorial.start(w)
    return w


def advance(w, seconds):
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(seconds):
        w.advance(1000, base + i + 1, snapshot=False)


def stand_by(w, pid):
    t = residents.table(w)[pid]["tile"]
    w.player["tx"], w.player["ty"] = t[0] + 1, t[1]


def talk(w, pid):
    stand_by(w, pid)
    r = story.dispatch(w, {"op": "talk", "npc": pid})
    assert r["status"] == "ok", r
    return r


def pick(w, pid, choice):
    stand_by(w, pid)
    r = story.dispatch(w, {"op": "choose", "npc": pid, "choice": choice})
    assert r["status"] == "ok", r
    return r


def teacher(w):
    return tutorial.state(w)["teacher"]


def finish_duel(w, r, win=True):
    rec = r["duel_lease"]["payload"]["duel"]
    report = play(rec, win=win)
    msg = {"op": "duel_resolve", "duel_id": rec["id"], **report}
    out = story.dispatch(w, msg)
    assert out["status"] == "resolved", out
    return out


def learn_everything(w):
    t = teacher(w)
    talk(w, t)
    pick(w, t, "learn_colours")
    finish_duel(w, pick(w, t, "told_practice"))
    finish_duel(w, pick(w, t, "hidden_duel"))


def test_a_new_campaign_world_opens_with_a_teacher_beside_the_wizard():
    w = new_world()
    t = teacher(w)
    tile = residents.table(w)[t]["tile"]
    assert abs(tile[0] - w.player["tx"]) + abs(tile[1] - w.player["ty"]) <= 6
    assert len(residents.table(w)) == 1 and not w.narrative["tutorial"]["story_cast"]
    advance(w, 2)
    snap = w.snapshot()
    row = next(r for r in snap["entities"] if r["id"] == t)
    assert row["class"] == "npc" and row["has_quest"] and row["hint"].startswith("Lesson:") and row["label"] == w.dmb.people[t]["name"]
    j = snap["story"]["narrative"]["journal"]
    assert len(j["opening"]) == 3 and [l["done"] for l in j["lessons"]] == [False] * 5 and j["quest"]["status"] == "none"
    story.dispatch(w, {"op": "opening_done"})
    assert w.snapshot()["story"]["narrative"]["journal"]["opening"] == []


def test_only_the_campaign_profile_gets_a_teacher():
    w = HybridWorld(507, profile="developer")
    narrative.enable(w)
    tutorial.start(w)
    assert not residents.table(w)


def test_fire_magic_has_to_be_learned_first():
    w = new_world()
    tree = next(iter(w.trees))
    assert server._handle(w, {"op": "fire", "target": tree})["reason"] == "spell_unknown"
    t = teacher(w)
    talk(w, t)
    r = pick(w, t, "learn_colours")
    assert wizard.spells(w) == [0, 1, 6] and wizard.wiz(w)["weave_size"] == 3 and wizard.lesson_done(w, "colours")
    assert "Flame" in r["text"] and [c["id"] for c in r["choices"]][:1] == ["told_practice"]
    row = w.trees[tree]
    w.player["tx"], w.player["ty"] = row["tx"], row["ty"]
    assert server._handle(w, {"op": "fire", "target": tree})["status"] == "ok"


def test_lessons_are_offered_in_order_and_the_first_talk_completes_meet():
    w = new_world()
    t = teacher(w)
    r = talk(w, t)
    assert wizard.lesson_done(w, "meet") and [c["id"] for c in r["choices"]] == ["learn_colours", "farewell"]
    assert talk(w, t)["lines"] == ["What would you like to learn?"]  # the introduction is shown once
    pick(w, t, "learn_colours")
    ids = [c["id"] for c in talk(w, t)["choices"]]
    assert ids == ["told_practice", "farewell"]  # the hidden duel needs the told one, the village question needs the unlock


def test_the_told_ward_duel_has_the_told_ward_and_a_lost_duel_still_completes_the_lesson():
    w = new_world()
    t = teacher(w)
    talk(w, t)
    pick(w, t, "learn_colours")
    r = pick(w, t, "told_practice")
    rec = r["duel_lease"]["payload"]["duel"]
    assert rec["encounter"]["enemy_combatant"]["fixed_ward"] == [1, 6, 1] and r["duel_lease"]["payload"]["public"]["duel_id"] == rec["id"]
    assert w.dmb.clock["pause_tokens"] and rec["speaker"] == t
    assert story.dispatch(w, {"op": "talk", "npc": t})["reason"] == "duel_open"
    out = finish_duel(w, r, win=False)
    assert out["outcome"] in ("lost", "draw") and wizard.lesson_done(w, "told_ward") and not w.dmb.clock["pause_tokens"]
    assert any("did not break it" in l for l in out["follow_up"]["lines"])
    r2 = pick(w, t, "told_practice")  # it can be tried again
    out2 = finish_duel(w, r2, win=True)
    assert out2["outcome"] == "won" and any("You broke my Ward" in l for l in out2["follow_up"]["lines"])


def test_fleeing_a_lesson_duel_does_not_count():
    w = new_world()
    t = teacher(w)
    talk(w, t)
    pick(w, t, "learn_colours")
    r = pick(w, t, "told_practice")
    rec = r["duel_lease"]["payload"]["duel"]
    out = story.dispatch(w, {"op": "duel_resolve", "duel_id": rec["id"], "outcome": "fled"})
    assert not wizard.lesson_done(w, "told_ward") and rec["state"] == "VOIDED" and not w.dmb.clock["pause_tokens"]
    assert out["follow_up"]["lines"] == ["Leaving so soon? Come back when you are ready."]


def test_a_forged_report_is_rejected_and_the_lesson_is_not_credited():
    w = new_world()
    t = teacher(w)
    talk(w, t)
    pick(w, t, "learn_colours")
    r = pick(w, t, "told_practice")
    rec = r["duel_lease"]["payload"]["duel"]
    forged = {"op": "duel_resolve", "duel_id": rec["id"], "outcome": "victory", "player_casts": 1, "enemy_casts": 1, "enemy_ward": [1, 6, 1],
              "history": [{"pattern": [1, 6, 0], "fracture": 3, "echo": 0, "broke": True}]}
    out = story.dispatch(w, forged)
    assert out["status"] == "rejected" and out["detail"] == "feedback_mismatch" and not wizard.lesson_done(w, "told_ward")


def test_the_stories_unlock_after_the_essential_lessons_and_the_villagers_appear():
    w = new_world()
    advance(w, 5)
    assert not graph.unlocked(w) and not w.narrative["tutorial"]["story_cast"]
    learn_everything(w)
    assert graph.unlocked(w)
    advance(w, 3)
    cast = w.narrative["tutorial"]["story_cast"]
    assert sorted(cast) == ["accused", "aggrieved", "neighbour"] and len(residents.table(w)) == 4
    assert [w.dmb.people[cast[s]]["name"] for s in ("aggrieved", "accused", "neighbour")] == ["Brenna", "Orrik", "Ilda"]
    t = teacher(w)
    ids = [c["id"] for c in talk(w, t)["choices"]]
    assert "ask_village" in ids and "hidden_duel" in ids
    pick(w, t, "ask_village")
    assert wizard.lesson_done(w, "world") and w.snapshot()["story"]["narrative"]["journal"]["quest"]["status"] == "offered"


def test_the_stories_unlock_by_time_without_any_lesson(monkeypatch):
    monkeypatch.setenv("HYBRID_NARRATIVE_UNLOCK_MS", "60000")
    w = new_world()
    advance(w, 58)
    assert not w.narrative["tutorial"]["story_cast"]
    advance(w, 6)
    assert graph.unlocked(w) and len(w.narrative["tutorial"]["story_cast"]) == 3


def test_the_gossip_quest_is_played_through_the_talk_and_choose_ops_and_changes_nothing_in_the_world():
    w = new_world()
    twin = new_world()  # the same world with no one ever talking to anyone
    learn_everything(w)
    advance(w, 4)
    advance(twin, 4 + 0)
    cast = w.narrative["tutorial"]["story_cast"]
    a, b, n = cast["aggrieved"], cast["accused"], cast["neighbour"]
    assert tutorial.quest_status(w) == "offered"
    r = talk(w, n)
    assert "Ilda the weaver" in r["lines"][0] and [c["id"] for c in r["choices"]] == ["gossip", "leave"]
    pick(w, n, "gossip")
    assert tutorial.quest_status(w) == "active"
    assert "say_fence" not in [c["id"] for c in talk(w, n)["choices"]]  # not before hearing both sides
    pick(w, a, "what_happened")
    pick(w, b, "what_happened")
    ids = [c["id"] for c in talk(w, n)["choices"]]
    assert {"say_fence", "say_coins", "say_nothing"} <= set(ids)
    pick(w, n, "say_fence")
    assert any("hammer" in l for l in talk(w, a)["lines"]) and graph.has(w, "gossip", "closed_a")
    assert graph.has(w, "gossip", "closed_b") is False
    talk(w, b)
    assert graph.has(w, "gossip", "closed_b")
    r = talk(w, n)
    assert any("Orrik with a hammer" in l for l in r["lines"]) and tutorial.quest_status(w) == "done"
    notes = w.snapshot()["story"]["narrative"]["journal"]["notes"]
    assert len(notes) == 1 and "mend her fence" in notes[0]["text"]
    assert talk(w, n)["lines"][0].startswith("The lane is as it is")
    # a pure story: the simulation did not change (the twin ran the same seconds, so only the clock differs; compare what the factions own)
    advance(twin, int(w.dmb.clock["game_ms"] // 1000) - int(twin.dmb.clock["game_ms"] // 1000))
    raw = lambda x: hashlib.sha1(json.dumps({k: getattr(x, k) for k in ("buildings", "stocks", "workers", "carriers", "units")}, sort_keys=True, default=str).encode()).hexdigest()
    assert raw(w) == raw(twin)


def test_each_outcome_has_its_own_ending():
    for choice, needle in (("say_coins", "Silver for the hens"), ("say_nothing", "You did not interfere")):
        w = new_world()
        learn_everything(w)
        advance(w, 3)
        cast = w.narrative["tutorial"]["story_cast"]
        for who in ("aggrieved", "accused"):
            pick(w, cast[who], "what_happened")
        talk(w, cast["neighbour"])
        pick(w, cast["neighbour"], choice)
        talk(w, cast["aggrieved"])
        talk(w, cast["accused"])
        assert any(needle in l for l in talk(w, cast["neighbour"])["lines"]), choice


def test_residents_move_near_their_post_stop_while_talked_to_and_are_deterministic():
    w = new_world()
    t = teacher(w)
    anchor = residents.table(w)[t]["anchor"]
    seen = set()
    for _ in range(12):
        advance(w, 20)
        tile = tuple(residents.table(w)[t]["tile"])
        seen.add(tile)
        assert max(abs(tile[0] - anchor[0]), abs(tile[1] - anchor[1])) <= residents.ROUTINE_RADIUS
        assert tile not in w.blocked and tile not in w.tree_tiles
    assert len(seen) > 2
    talk(w, t)
    before = list(residents.table(w)[t]["tile"])
    advance(w, 10)  # a conversation holds the beat (an unclosed one for at most CONVERSATION_MS)
    assert residents.table(w)[t]["tile"] == before
    advance(w, 30)
    assert t not in w.narrative["conversations"]  # a conversation nobody closed expires, so a resident is never frozen for ever

    code = ("import sys; sys.path[:0]=[%r, %r]\nimport os; os.environ['HYBRID_AI']='0'\n"
            "from wizard_rts.world import HybridWorld\nfrom wizard_rts import narrative\nfrom wizard_rts.narrative import tutorial, residents\n"
            "w = HybridWorld(507, profile='campaign'); w.ai_enabled = False; narrative.enable(w); tutorial.start(w)\n"
            "out = []\n"
            "for i in range(240):\n    w.advance(1000, i + 1, snapshot=False)\n    if i %% 20 == 19: out.append(residents.table(w)['person:1']['tile'])\n"
            "print(w.dmb.people['person:1']['name'], out)\n")
    outs = [subprocess.run([sys.executable, "-c", code % (str(HERE), str(HERE.parent))], capture_output=True, text=True, cwd=HERE, check=True,
                           env=dict(os.environ, PYTHONHASHSEED=h)).stdout for h in ("0", "1")]
    assert outs[0] == outs[1] and "[" in outs[0]


def test_lessons_and_the_quest_survive_save_and_load_and_an_open_duel_is_voided(tmp_path):
    w = new_world()
    t = teacher(w)
    talk(w, t)
    pick(w, t, "learn_colours")
    r = pick(w, t, "told_practice")
    lid = r["duel_lease"]["payload"]["duel"]["id"]
    assert w.dmb.clock["pause_tokens"]
    persist.save_world(w, tmp_path / "t.pkl")
    loaded, _ = persist.load_world(tmp_path / "t.pkl")
    assert wizard.spells(loaded) == [0, 1, 6] and wizard.lesson_done(loaded, "colours") and wizard.lesson_done(loaded, "meet")
    assert loaded.dmb.leases[lid]["state"] == "VOIDED" and not loaded.dmb.clock["pause_tokens"]
    assert not wizard.lesson_done(loaded, "told_ward")
    assert [c["id"] for c in talk(loaded, t)["choices"]][0] == "told_practice"  # the teacher offers the duel again
    assert tutorial.state(loaded)["teacher"] == t and len(residents.table(loaded)) == 1

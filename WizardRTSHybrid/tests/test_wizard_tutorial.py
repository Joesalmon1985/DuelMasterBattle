"""B.4: the opening, the teacher's lessons through the real ops, the unlock rule, the duels, save/load. (The quest is tested in test_narrative_quests.py.)"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

import _nh as nh
from test_wizard_duel_lease import play
from wizard_rts import narrative, server, story
from wizard_rts.narrative import conversation, graph, persist, quests, residents, tutorial, wizard
from wizard_rts.world import HybridWorld

HERE = Path(__file__).resolve().parents[1]


def teacher(w):
    return tutorial.state(w)["teacher"]


def go_to_teacher(w):
    t = teacher(w)
    tile = residents.table(w)[t]["tile"]
    w.player["tx"], w.player["ty"] = tile[0] + 1, tile[1]
    return t


def finish_duel(w, r, win=True):
    rec = r["duel_lease"]["payload"]["duel"]
    out = story.dispatch(w, {"op": "duel_resolve", "duel_id": rec["id"], **play(rec, win=win)})
    assert out["status"] == "resolved", out
    return out


def learn_everything(w):
    t = go_to_teacher(w)
    nh.talk(w, t)
    nh.pick(w, t, "learn_colours")
    nh.end(w, t)
    nh.talk(w, t)
    finish_duel(w, nh.pick(w, t, "told_practice"))
    nh.end(w, t)
    nh.talk(w, t)
    finish_duel(w, nh.pick(w, t, "hidden_duel"))
    nh.end(w, t)


def test_a_new_campaign_world_opens_with_a_teacher_beside_the_wizard():
    w = nh.world()
    t = teacher(w)
    tile = residents.table(w)[t]["tile"]
    assert abs(tile[0] - w.player["tx"]) + abs(tile[1] - w.player["ty"]) <= 6
    assert len(residents.table(w)) == 1 and quests.rec(w, "forest_dispute") is None
    nh.adv(w, 2)
    snap = w.snapshot()
    row = next(r for r in snap["entities"] if r["id"] == t)
    assert row["class"] == "npc" and row["has_quest"] and row["label"] == w.dmb.people[t]["name"]
    j = snap["story"]["narrative"]["journal"]
    assert len(j["opening"]) == 3 and [l["done"] for l in j["lessons"]] == [False] * 6 and j["quests"] == []
    assert j["objective"].startswith("Talk to your mentor")
    story.dispatch(w, {"op": "opening_done"})
    assert w.snapshot()["story"]["narrative"]["journal"]["opening"] == []


def test_only_the_campaign_profile_gets_a_teacher():
    w = HybridWorld(507, profile="developer")
    narrative.enable(w)
    tutorial.start(w)
    assert not residents.table(w)


def test_fire_magic_has_to_be_learned_first():
    w = nh.world()
    tree = next(iter(w.trees))
    assert server._handle(w, {"op": "fire", "target": tree})["reason"] == "spell_unknown"
    t = go_to_teacher(w)
    nh.talk(w, t)
    r = nh.pick(w, t, "learn_colours")
    assert wizard.spells(w) == [0, 1, 6] and wizard.wiz(w)["weave_size"] == 3 and wizard.lesson_done(w, "colours")
    assert "Flame" in r["text"] and "told_practice" in nh.ids(r)
    row = w.trees[tree]
    w.player["tx"], w.player["ty"] = row["tx"], row["ty"]
    assert server._handle(w, {"op": "fire", "target": tree})["status"] == "ok"


def test_lessons_are_offered_in_order_and_the_first_talk_completes_meet():
    w = nh.world()
    t = go_to_teacher(w)
    r = nh.talk(w, t)
    assert wizard.lesson_done(w, "meet") and nh.ids(r) == ["learn_colours", "why_not_rule", "farewell"]
    nh.end(w, t)
    assert nh.talk(w, t)["lines"] == ["What would you like to learn?"]  # the introduction is shown once
    nh.pick(w, t, "learn_colours")
    nh.end(w, t)
    ids = nh.ids(nh.talk(w, t))
    assert "told_practice" in ids and "hidden_duel" not in ids and "ask_village" not in ids  # the hidden duel needs the told one, the village question the lessons


def test_the_told_ward_duel_has_the_told_ward_and_a_lost_duel_still_completes_the_lesson():
    w = nh.world()
    t = go_to_teacher(w)
    nh.talk(w, t)
    nh.pick(w, t, "learn_colours")
    r = nh.pick(w, t, "told_practice")
    rec = r["duel_lease"]["payload"]["duel"]
    assert rec["encounter"]["enemy_combatant"]["fixed_ward"] == [1, 6, 1] and r["duel_lease"]["payload"]["public"]["duel_id"] == rec["id"]
    assert r["ends"] is True and w.dmb.clock["pause_tokens"] and rec["speaker"] == t
    nh.end(w, t)
    assert story.dispatch(w, {"op": "talk", "npc": t})["reason"] == "duel_open"
    out = finish_duel(w, r, win=False)
    assert out["outcome"] in ("lost", "draw") and wizard.lesson_done(w, "told_ward") and not w.dmb.clock["pause_tokens"]
    assert any("It held" in l for l in out["follow_up"]["lines"])
    nh.end(w, t)
    nh.talk(w, t)
    out2 = finish_duel(w, nh.pick(w, t, "told_practice"), win=True)  # it can be tried again
    assert out2["outcome"] == "won" and any(("Broken" in l or "Three casts" in l) for l in out2["follow_up"]["lines"])


def test_fleeing_a_lesson_duel_does_not_count():
    w = nh.world()
    t = go_to_teacher(w)
    nh.talk(w, t)
    nh.pick(w, t, "learn_colours")
    r = nh.pick(w, t, "told_practice")
    rec = r["duel_lease"]["payload"]["duel"]
    out = story.dispatch(w, {"op": "duel_resolve", "duel_id": rec["id"], "outcome": "fled"})
    assert not wizard.lesson_done(w, "told_ward") and rec["state"] == "VOIDED" and not w.dmb.clock["pause_tokens"]
    assert out["follow_up"]["lines"] == ["Leaving so soon? Come back when you are ready."]


def test_a_forged_report_is_rejected_and_the_lesson_is_not_credited():
    w = nh.world()
    t = go_to_teacher(w)
    nh.talk(w, t)
    nh.pick(w, t, "learn_colours")
    rec = nh.pick(w, t, "told_practice")["duel_lease"]["payload"]["duel"]
    forged = {"op": "duel_resolve", "duel_id": rec["id"], "outcome": "victory", "player_casts": 1, "enemy_casts": 1, "enemy_ward": [1, 6, 1],
              "history": [{"pattern": [1, 6, 0], "fracture": 3, "echo": 0, "broke": True}]}
    out = story.dispatch(w, forged)
    assert out["status"] == "rejected" and out["detail"] == "feedback_mismatch" and not wizard.lesson_done(w, "told_ward")


def test_the_stories_unlock_after_the_essential_lessons():
    w = nh.world()
    nh.adv(w, 5)
    assert not graph.unlocked(w) and quests.rec(w, "forest_dispute") is None
    learn_everything(w)
    assert graph.unlocked(w)
    nh.adv(w, 3)
    r = quests.rec(w, "forest_dispute")
    assert r["status"] == "cast" and sorted(r["bindings"]) == ["cutter", "planter", "witness"]
    assert len(residents.table(w)) == 1  # nobody new appeared: the quest is played by people who were already here
    t = go_to_teacher(w)
    r = nh.talk(w, t)
    assert "ask_village" in nh.ids(r) and "hidden_duel" in nh.ids(r)
    r = nh.pick(w, t, "ask_village")
    names = quests.cast_names(w, "forest_dispute")
    assert wizard.lesson_done(w, "world") and names["cutter"] in r["text"] and names["planter"] in r["text"] and "tiles" in r["text"]


def test_the_stories_unlock_by_time_without_any_lesson(monkeypatch):
    monkeypatch.setenv("HYBRID_NARRATIVE_UNLOCK_MS", "100000")
    w = nh.world()
    nh.adv(w, 50)
    assert quests.rec(w, "forest_dispute") is None
    nh.adv(w, 15)
    assert graph.unlocked(w) and quests.status(w, "forest_dispute") == "offered"


def test_the_teacher_stays_near_their_post_stops_while_talked_to_and_is_deterministic():
    w = nh.world()
    t = teacher(w)
    anchor = residents.table(w)[t]["anchor"]
    seen = set()
    for _ in range(12):
        nh.adv(w, 20)
        tile = tuple(residents.table(w)[t]["tile"])
        seen.add(tile)
        assert max(abs(tile[0] - anchor[0]), abs(tile[1] - anchor[1])) <= residents.ROUTINE_RADIUS
        assert tile not in w.blocked and tile not in w.tree_tiles
    assert len(seen) > 2
    go_to_teacher(w)
    nh.talk(w, t)
    before = list(residents.table(w)[t]["tile"])
    nh.adv(w, 40)  # a conversation holds the beat
    assert residents.table(w)[t]["tile"] == before
    nh.adv(w, conversation.IDLE_MS // 1000)
    assert t not in conversation.table(w)  # and an abandoned one ends, so the teacher is never frozen for ever

    code = ("import sys; sys.path[:0]=[%r, %r]\nimport os; os.environ['HYBRID_AI']='0'\n"
            "from wizard_rts.world import HybridWorld\nfrom wizard_rts import narrative\nfrom wizard_rts.narrative import tutorial, residents\n"
            "w = HybridWorld(507, profile='campaign'); w.ai_enabled = False; narrative.enable(w); tutorial.start(w)\n"
            "out = []\n"
            "for i in range(240):\n    w.advance(1000, i + 1, snapshot=False)\n    if i %% 20 == 19: out.append(residents.table(w)['person:1']['tile'])\n"
            "print(w.dmb.people['person:1']['name'], out)\n")
    outs = [subprocess.run([sys.executable, "-c", code % (str(HERE), str(HERE.parent))], capture_output=True, text=True, cwd=HERE, check=True,
                           env=dict(os.environ, PYTHONHASHSEED=h)).stdout for h in ("0", "1")]
    assert outs[0] == outs[1] and "[" in outs[0]


def test_lessons_survive_save_and_load_and_an_open_duel_is_voided(tmp_path):
    w = nh.world()
    t = go_to_teacher(w)
    nh.talk(w, t)
    nh.pick(w, t, "learn_colours")
    lid = nh.pick(w, t, "told_practice")["duel_lease"]["payload"]["duel"]["id"]
    assert w.dmb.clock["pause_tokens"]
    persist.save_world(w, tmp_path / "t.pkl")
    loaded, _ = persist.load_world(tmp_path / "t.pkl")
    assert wizard.spells(loaded) == [0, 1, 6] and wizard.lesson_done(loaded, "colours") and wizard.lesson_done(loaded, "meet")
    assert loaded.dmb.leases[lid]["state"] == "VOIDED" and not loaded.dmb.clock["pause_tokens"] and not conversation.table(loaded)
    assert not wizard.lesson_done(loaded, "told_ward")
    assert "told_practice" in nh.ids(nh.talk(loaded, t))  # the teacher offers the duel again
    assert tutorial.state(loaded)["teacher"] == t and len(residents.table(loaded)) == 1

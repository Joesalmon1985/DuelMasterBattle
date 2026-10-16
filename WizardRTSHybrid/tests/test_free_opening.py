"""The free opening (plan M3): nothing is mandatory. The apprentices know their colours from the first moment, training ends by lessons or by play,
the stranger's judgement reads what they actually did, the lethal duel is a challenge the apprentice may make or decline, the stranger leaves either way
and the world records where he went, the mentor's lines read the ledger."""
from __future__ import annotations

import _campaign as camp
import pytest
from _party import Table
from test_mortality import beside, duel_to_the_death
from test_wizard_duel_lease import play

from wizard_rts.narrative import campaign, ledger, mortality, mother, party, residents, wizard


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    camp.quick(monkeypatch, min_ms=20_000, fallback_ms=60_000, aftermath_fallback_ms=40_000)


def fight(t, h, rec, win):
    return h.op("duel_resolve", duel_id=rec["id"], **play(rec, win=win))


def to_confrontation(t: Table, humans) -> None:
    t.meet_people(humans[0], 3)
    t.wait_for_stage("arrival")
    for h in humans:
        t.through_scene(h)
    t.wait_for_stage("confrontation")


def test_the_apprentices_know_the_colours_from_the_first_moment_and_fire_works():
    t = Table(humans=2)
    joe, ann = t.people
    for h in (joe, ann):
        with h.seat_state():
            assert wizard.spells(t.world) == [0, 1, 6] and wizard.wiz(t.world)["weave_size"] == 3 and not wizard.wiz(t.world)["lessons"]
    tree = next(iter(t.world.trees))
    r = joe.op("fire", target=tree)
    assert r.get("reason") != "spell_unknown", r


def test_training_ends_by_play_a_duel_between_the_apprentices_with_no_lesson_taken():
    t = Table(humans=2)
    joe, ann = t.people
    assert campaign.stage(t.world) == "training"
    duel_to_the_death(t, joe, ann)
    t.advance(2)
    assert campaign.stage(t.world) == "explore" and campaign.state(t.world)["training_ended_by"] == "play"
    assert campaign.explore_due(t.world)["contacts"] >= 2, "the duel and the death count as contact with the world"


def test_training_ends_by_time_when_nobody_does_anything(monkeypatch):
    t = Table(humans=1)
    monkeypatch.setitem(campaign.config._file()["campaign"], "training_fallback_ms", 60_000)
    t.advance(25)
    assert campaign.stage(t.world) == "explore" and campaign.state(t.world)["training_ended_by"] == "time"


def test_declining_the_challenge_the_stranger_leaves_and_the_world_records_where():
    t = Table(humans=1)
    joe = t.people[0]
    t.learn(joe)
    t.advance(2)
    to_confrontation(t, [joe])
    out = t.through_scene(joe, pick="let_go")
    assert "duel_lease" not in out and campaign.stage(t.world) == "aftermath"
    assert campaign.state(t.world)["outcome"] == "spared" and not mortality.is_dead(t.world, joe.id)
    with joe.seat_state():
        assert wizard.wiz(t.world)["lethal"] == "declined"
    a = campaign.state(t.world)["attacker"]
    assert t.world.dmb.people[a]["alive"] and t.world.dmb.people[t.mentor]["alive"] is False
    for _ in range(90):
        t.advance(1)
        if residents.table(t.world)[a]["status"] == "gone":
            break
    assert residents.table(t.world)[a]["status"] == "gone"
    gone = campaign.state(t.world)["stranger_gone_to"]
    assert gone and gone["direction"] in ("north", "south", "east", "west") and len(gone["tile"]) == 2
    t.meet_people(joe, 2)
    t.advance(50)
    assert campaign.stage(t.world) == "complete"


def test_challenging_the_stranger_opens_the_lethal_duel_and_losing_it_is_a_death_the_friend_can_undo():
    t = Table(humans=2)
    joe, ann = t.people
    for h in (joe, ann):
        t.learn(h)
    t.advance(2)
    to_confrontation(t, [joe, ann])
    out_j = t.through_scene(joe, pick="challenge")
    out_a = t.through_scene(ann, pick="let_go")
    assert "duel_lease" in out_j and "duel_lease" not in out_a and campaign.stage(t.world) == "duel"
    rec = out_j["duel_lease"]["payload"]["duel"]
    assert fight(t, joe, rec, False)["outcome"] in ("lost", "draw")
    assert mortality.is_dead(t.world, joe.id) and mortality.fate_of(t.world, joe.id)["by"] == campaign.state(t.world)["attacker"]
    assert not mortality.is_dead(t.world, ann.id) and t.session.ending is None
    t.advance(2)
    assert campaign.stage(t.world) == "aftermath", "the stranger leaves once the challenge is settled"
    pid = mortality.body_of(t.world, joe.id)
    body = residents.table(t.world)[pid]
    ann.pose["tx"], ann.pose["ty"] = body["tile"][0] + 1, body["tile"][1]
    assert ann.op("resurrect", target=joe.id)["status"] == "started"
    t.advance(mortality.resurrect_ms() / 1000.0 + 1.5)
    assert not mortality.is_dead(t.world, joe.id)
    assert not mother.is_grounded(t.world, ann.id), "nobody killed anybody: the stranger did"


def test_winning_the_challenge_drives_him_off_for_everybody():
    t = Table(humans=2)
    joe, ann = t.people
    for h in (joe, ann):
        t.learn(h)
    t.advance(2)
    to_confrontation(t, [joe, ann])
    rec = t.through_scene(joe, pick="challenge")["duel_lease"]["payload"]["duel"]
    assert fight(t, joe, rec, True)["outcome"] == "won"
    assert campaign.stage(t.world) == "victory"
    t.through_scene(joe)
    t.through_scene(ann)
    assert campaign.stage(t.world) == "aftermath"
    with ann.seat_state():
        assert wizard.wiz(t.world)["lethal"] in ("spared", "declined")


def test_the_strangers_judgement_reads_what_the_apprentices_did():
    t = Table(humans=2)
    joe, ann = t.people
    duel_to_the_death(t, joe, ann)
    pid = mortality.body_of(t.world, ann.id)
    joe.pose["tx"], joe.pose["ty"] = residents.table(t.world)[pid]["tile"][0] + 1, residents.table(t.world)[pid]["tile"][1]
    assert joe.op("resurrect", target=ann.id)["status"] == "started"
    t.advance(mortality.resurrect_ms() / 1000.0 + 1.5)
    t.advance(2)
    to_confrontation(t, [joe, ann])
    seen = {}
    for h in (joe, ann):
        for _ in range(12):
            v = t.scene(h)
            if v is None:
                break
            if v["speaker"] == "attacker" and "The apprentice" in v["text"]:
                seen[h.id] = v["text"]
                break
            if v["needs_answer"]:
                h.op("scene_choose", choice=v["choices"][0]["id"])
            h.op("scene_next")
    assert "killed your friend" in seen[joe.id], seen[joe.id]
    assert "died already" in seen[ann.id], seen[ann.id]


def test_the_mentor_reads_the_ledger():
    t = Table(humans=2)
    joe, ann = t.people
    duel_to_the_death(t, joe, ann)
    joe.stand_by_resident(t.mentor)
    reply = joe.op("talk", npc=t.mentor)
    assert reply["status"] == "ok", reply
    joe.op("end_talk", npc=t.mentor)
    reply = joe.op("talk", npc=t.mentor)
    text = " ".join(reply["lines"])
    assert "killed your friend" in text, text
    assert "skip_theory" in [c["id"] for c in reply["choices"]], "a duellist may skip the theory"
    r = joe.op("choose", npc=t.mentor, choice="skip_theory")
    assert r["status"] == "ok"
    with joe.seat_state():
        assert wizard.lesson_done(t.world, "colours")
    joe.op("end_talk", npc=t.mentor)
    pid = mortality.body_of(t.world, ann.id)
    joe.pose["tx"], joe.pose["ty"] = residents.table(t.world)[pid]["tile"][0] + 1, residents.table(t.world)[pid]["tile"][1]
    assert joe.op("resurrect", target=ann.id)["status"] == "started"
    t.advance(mortality.resurrect_ms() / 1000.0 + 1.5)
    ann.stand_by_resident(t.mentor)
    reply = ann.op("talk", npc=t.mentor)
    ann.op("end_talk", npc=t.mentor)
    reply = ann.op("talk", npc=t.mentor)
    assert "You died" in " ".join(reply["lines"]), reply["lines"]


def test_the_confrontation_happens_while_both_are_away_and_they_learn_of_it_from_people():
    t = Table(humans=2)
    joe, ann = t.people
    for h in (joe, ann):
        t.learn(h)
    t.advance(2)
    t.meet_people(joe, 3)
    joe.drop()
    ann.drop()
    t.wait_for_stage("arrival")
    t.wait_for_stage("confrontation", 200)
    for _ in range(300):
        t.advance(1)
        if campaign.stage(t.world) == "aftermath":
            break
    assert campaign.stage(t.world) == "aftermath" and t.world.dmb.people[t.mentor]["alive"] is False, "nobody waited for the absent"
    joe.reconnect()
    with joe.seat_state():
        assert campaign.scene_view(t.world) is None, "the stranger is gone: nothing to face"
        assert wizard.wiz(t.world)["lethal"] in ("spared", None, "", "declined")
    assert joe.op("talk", npc=t.mentor)["reason"] == "dead"

"""The Wizard World campaign with one human or with two: the same story, completable either way, nobody held back by the other.

Driven through the real `MultiplayerSession` (the same messages a connection sends), with a clock the test advances."""
from __future__ import annotations

import _campaign as camp
import _nh as nh
import pytest
from _party import Table
from test_wizard_duel_lease import play

from wizard_rts import narrative
from wizard_rts.narrative import campaign, conversation, duel_lease, party, residents, wizard


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    camp.quick(monkeypatch, min_ms=20_000, fallback_ms=60_000, aftermath_fallback_ms=40_000)


def lease_of(table, h):
    with party.as_player(table.world, h.id):
        return duel_lease.active(table.world)


def fight(table, h, rec, win):
    report = play(rec, win=win)
    return h.op("duel_resolve", duel_id=rec["id"], **report)


# ------------------------------------------------------------------ one human: the whole campaign through the session

def test_a_single_human_plays_the_whole_campaign_through_the_session():
    t = Table(humans=1)
    joe = t.people[0]
    assert narrative.enabled(t.world) and t.mentor and not party.multi(t.world)
    t.learn(joe)
    t.advance(2)
    assert campaign.stage(t.world) == "explore"
    assert t.meet_people(joe, 3) == 3
    t.wait_for_stage("arrival")
    assert t.scene(joe)["id"] == "notice"
    assert t.through_scene(joe)
    t.wait_for_stage("confrontation")
    out = t.through_scene(joe)
    assert "duel_lease" in out and campaign.stage(t.world) == "duel"
    assert t.world.dmb.clock["pause_tokens"], "alone, the world waits while the stranger is fought (the classic rule)"
    rec = out["duel_lease"]["payload"]["duel"]
    assert fight(t, joe, rec, True)["outcome"] == "won"
    assert campaign.stage(t.world) == "victory"
    t.through_scene(joe)
    assert campaign.stage(t.world) == "aftermath"
    t.meet_people(joe, 2)
    for _ in range(60):
        t.advance(1)
        if campaign.stage(t.world) == "complete":
            break
    assert campaign.stage(t.world) == "complete"
    assert any("greater magical power" in n["text"] for n in wizard.wiz(t.world)["journal_notes"])


def test_a_single_human_who_loses_the_lethal_duel_is_over():
    t = Table(humans=1)
    joe = t.people[0]
    t.learn(joe)
    t.advance(2)
    t.meet_people(joe, 3)
    t.wait_for_stage("arrival")
    t.through_scene(joe)
    t.wait_for_stage("confrontation")
    rec = t.through_scene(joe)["duel_lease"]["payload"]["duel"]
    fight(t, joe, rec, False)
    assert campaign.stage(t.world) == "duel" and campaign.over(t.world), "the stage never records a defeat; the wizard's fate does"
    assert joe.op("talk", npc=t.mentor)["reason"] in ("dead", "ending")
    assert t.session.ending and t.session.ending["kind"] == "human_dead", "alone, death ends the session (the world is saved with the body)"


# ------------------------------------------------------------------ two humans

def test_two_humans_have_their_own_wizards_conversations_and_flags():
    t = Table(humans=2)
    joe, ann = t.people
    assert party.multi(t.world) and party.order(t.world) == [joe.id, ann.id]
    w_joe = party.seats(t.world)[joe.id]
    assert w_joe["host"] and not party.seats(t.world)[ann.id]["host"]
    with joe.seat_state():
        a = wizard.wiz(t.world)
    with ann.seat_state():
        b = wizard.wiz(t.world)
    assert a is not b
    t.learn(joe)
    with ann.seat_state():
        assert wizard.spells(t.world) == [0, 1, 6] and not wizard.lesson_done(t.world, "meet"), "the colours from the first moment; the lessons are hers to take"
    with joe.seat_state():
        assert wizard.spells(t.world) == [0, 1, 6] and wizard.lesson_done(t.world, "meet")
    # both talk to the same person at once; neither conversation closes the other's
    kind, eid = next((k, i) for k, tab in (("worker", t.world.workers), ("carrier", t.world.carriers)) for i, r in sorted(tab.items()) if r["faction_name"] == "Red")
    joe.stand_by(kind, eid)
    ann.stand_by(kind, eid)
    ann.pose["ty"] += 1
    assert joe.op("talk", npc=eid)["status"] == "ok"
    assert ann.op("talk", npc=eid)["status"] == "ok"
    with joe.seat_state():
        assert eid in conversation.table(t.world)
    with ann.seat_state():
        assert eid in conversation.table(t.world)
    ann.op("end_talk", npc=eid)
    with joe.seat_state():
        assert eid in conversation.table(t.world), "Ann closing her conversation did not close Joe's"
    with ann.seat_state():
        assert eid not in conversation.table(t.world)
    # the Aspect actor and the relationships are per wizard
    from wizard_rts.narrative import checks

    with joe.seat_state():
        assert checks.actor(t.world) == "player"
    with ann.seat_state():
        assert checks.actor(t.world) == ann.id
        assert checks.relationship(t.world, t.mentor) == 40


def test_training_waits_for_every_present_human_but_only_for_a_while():
    t = Table(humans=2)
    joe, ann = t.people
    t.learn(joe)
    t.advance(5)
    assert campaign.stage(t.world) == "training", "Ann is present and has not finished: the lessons wait a little"
    t.advance(party.training_grace_ms() / 1000 + 5)
    assert campaign.stage(t.world) == "explore"
    with ann.seat_state():
        assert wizard.spells(t.world) == [0, 1, 6] and wizard.wiz(t.world)["caught_up"], "the slow one is caught up, not stranded"


def test_training_does_not_wait_at_all_for_an_absent_human():
    t = Table(humans=2)
    joe, ann = t.people
    t.session.disconnect(ann.conn, t.now)
    t.learn(joe)
    t.advance(3)
    assert campaign.stage(t.world) == "explore"
    with ann.seat_state():
        assert not party.seats(t.world)[ann.id]["present"]


def test_both_finishing_the_lessons_moves_on_at_once():
    t = Table(humans=2)
    joe, ann = t.people
    t.learn(joe)
    t.learn(ann)
    t.advance(3)
    assert campaign.stage(t.world) == "explore"


def _to_confrontation(t, humans):
    for h in humans:
        t.learn(h)
    t.advance(3)
    assert campaign.stage(t.world) == "explore"
    t.meet_people(humans[0], 2)
    if len(humans) > 1:
        t.meet_people(humans[1], 2)
    t.wait_for_stage("arrival")
    for h in humans:
        assert t.scene(h)["id"] == "notice", "every present wizard sees the stranger arrive"
        t.through_scene(h)
    t.wait_for_stage("confrontation")
    for h in humans:
        assert t.scene(h)["id"] == "confrontation"


def test_two_humans_each_face_the_stranger_and_the_first_victory_repels_him_for_both():
    t = Table(humans=2)
    joe, ann = t.people
    _to_confrontation(t, [joe, ann])
    out_j = t.through_scene(joe)
    out_a = t.through_scene(ann)
    rec_j, rec_a = out_j["duel_lease"]["payload"]["duel"], out_a["duel_lease"]["payload"]["duel"]
    assert rec_j["id"] != rec_a["id"] and campaign.stage(t.world) == "duel"
    assert not t.world.dmb.clock.get("pause_tokens"), "with company the world keeps living while two people fight the stranger"
    assert lease_of(t, joe)["id"] == rec_j["id"] and lease_of(t, ann)["id"] == rec_a["id"]
    # Ann cannot report Joe's duel as her own, nor checkpoint it
    forged = play(rec_j, win=True)
    assert ann.op("duel_resolve", duel_id=rec_j["id"], **forged).get("reason") == "missing_duel"
    assert fight(t, ann, rec_a, True)["outcome"] == "won"
    assert campaign.stage(t.world) == "victory"
    with joe.seat_state():
        assert wizard.wiz(t.world)["lethal"] == "spared" and duel_lease.active(t.world) is None, "Joe's open duel was released without penalty"
        assert not campaign.over(t.world)
        assert campaign.scene_view(t.world)["id"] == "victory"
    # Joe's board may still report: nothing happens to him
    late = play(rec_j, win=False)
    assert joe.op("duel_resolve", duel_id=rec_j["id"], **late).get("status") in ("idempotent",)
    with joe.seat_state():
        assert not campaign.over(t.world)
    t.through_scene(joe)
    t.through_scene(ann)
    assert campaign.stage(t.world) == "aftermath"
    t.meet_people(joe, 2)
    t.advance(60)
    assert campaign.stage(t.world) == "complete"
    for h in (joe, ann):
        with h.seat_state():
            assert wizard.wiz(t.world)["campaign_finished"]


def test_one_wizard_dying_does_not_end_the_world_for_the_other():
    t = Table(humans=2)
    joe, ann = t.people
    _to_confrontation(t, [joe, ann])
    rec_j = t.through_scene(joe)["duel_lease"]["payload"]["duel"]
    rec_a = t.through_scene(ann)["duel_lease"]["payload"]["duel"]
    fight(t, joe, rec_j, False)
    with joe.seat_state():
        assert campaign.over(t.world) and wizard.wiz(t.world)["fate"]["alive"] is False
    assert campaign.stage(t.world) == "duel", "the campaign goes on"
    assert not campaign.over_for_all(t.world)
    assert joe.op("talk", npc=t.mentor).get("status") == "rejected"
    with ann.seat_state():
        assert not campaign.over(t.world)
    assert fight(t, ann, rec_a, True)["outcome"] == "won"
    assert campaign.stage(t.world) == "victory"
    t.through_scene(ann)
    t.meet_people(ann, 2)
    t.advance(60)
    assert campaign.stage(t.world) == "complete"


def test_the_campaign_is_over_when_no_human_is_left():
    t = Table(humans=2)
    joe, ann = t.people
    _to_confrontation(t, [joe, ann])
    rec_j = t.through_scene(joe)["duel_lease"]["payload"]["duel"]
    rec_a = t.through_scene(ann)["duel_lease"]["payload"]["duel"]
    fight(t, joe, rec_j, False)
    assert campaign.stage(t.world) == "duel"
    fight(t, ann, rec_a, False)
    assert campaign.stage(t.world) == "duel" and campaign.over_for_all(t.world)
    assert t.session.ending and t.session.ending["kind"] == "all_dead"


def test_a_wizard_who_goes_away_never_blocks_the_story_and_is_told_what_they_missed():
    t = Table(humans=2)
    joe, ann = t.people
    for h in (joe, ann):
        t.learn(h)
    t.advance(3)
    t.meet_people(joe, 3)
    t.session.disconnect(ann.conn, t.now)
    t.wait_for_stage("arrival")
    assert t.scene(joe)["id"] == "notice"
    with ann.seat_state():
        assert campaign.scene_view(t.world) is None, "an absent wizard has no scene to hold the story"
    t.through_scene(joe)
    t.wait_for_stage("confrontation")
    rec = t.through_scene(joe)["duel_lease"]["payload"]["duel"]
    assert fight(t, joe, rec, True)["outcome"] == "won"
    t.through_scene(joe)
    t.meet_people(joe, 2)
    t.advance(60)
    assert campaign.stage(t.world) == "complete"
    # Ann comes back to a story that went on without her: it is in her journal, and the duel that was won for everybody is not hers to lose
    ann.reconnect()
    with ann.seat_state():
        w = wizard.wiz(t.world)
        text = " ".join(n["text"] for n in w["journal_notes"])
        assert w["lethal"] == "spared" and "driven out" in text and "too late" in text
        assert not campaign.over(t.world)
    assert party.seats(t.world)[ann.id]["present"]


def test_a_wizard_who_joins_late_is_caught_up_and_told_the_story_so_far():
    t = Table(humans=1)
    joe = t.people[0]
    t.learn(joe)
    t.advance(3)
    t.meet_people(joe, 3)
    t.wait_for_stage("arrival")
    t.through_scene(joe)
    t.wait_for_stage("confrontation")
    rec = t.through_scene(joe)["duel_lease"]["payload"]["duel"]
    assert fight(t, joe, rec, True)["outcome"] == "won"
    t.session.max_players = 2
    late = t.add("Cy")
    with late.seat_state():
        w = wizard.wiz(t.world)
        assert wizard.spells(t.world) == [0, 1, 6] and w["lethal"] == "spared" and w["caught_up"]
        notes = " ".join(n["text"] for n in w["journal_notes"])
        assert "too late" in notes and "driven out" in notes
    from wizard_rts.narrative import checks

    with late.seat_state():
        assert checks.relationship(t.world, t.mentor) == 40, "the mentor (or his memory) knows the newcomer as well as the first apprentice"

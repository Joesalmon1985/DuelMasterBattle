"""Mira in the story and the Trial (plan M7): she goes in with the human and keeps up zone by zone, comes out when they do, is refused by her
mother like anyone, people speak of her when she is about (the mentor, the scenes), the fourth wall is noticed rarely and counted, and a hub
that is seen again says it another way."""
from __future__ import annotations

import _campaign as camp
import pytest
from _party import Table

from wizard_rts.narrative import campaign, graph, ledger, mother, party, wizard
from wizard_rts.net import ai_wizard
from wizard_rts.trial import run as trial


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    camp.quick(monkeypatch, min_ms=20_000, fallback_ms=60_000, aftermath_fallback_ms=40_000)


def solo() -> Table:
    t = Table(humans=1, ai=1)
    t.advance(1)
    return t


def ai_of(t: Table):
    (ai,) = t.session.ais.values()
    return ai


def at_gate(t: Table, h) -> None:
    g = trial.gate_tile(t.world)
    h.pose["tx"], h.pose["ty"] = g[0], g[1] + 1
    if (h.pose["tx"], h.pose["ty"]) in t.world.blocked:
        h.pose["tx"], h.pose["ty"] = g[0] + 1, g[1]


def said(h, kind: str) -> list[dict]:
    return [n for n in h.state()["notices"] if n["kind"] == "ai_says" and n.get("line") == kind]


def test_mira_follows_the_human_into_the_trial_keeps_up_and_comes_out_with_them():
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    at_gate(t, joe)
    mira = t.world.players[ai.link.id]
    g = trial.gate_tile(t.world)
    mira["tx"], mira["ty"] = g[0] - 4, g[1] + 2  # she was following at a distance
    assert joe.op("trial_enter")["status"] == "ok"
    t.advance(12)
    assert trial.inside(t.world, ai.link.id), "she walked to the gate and went in"
    assert said(joe, "trial_in"), "and said so, in her own voice"
    assert any(p.get("ai") and p.get("trial", {}).get("zone") == "dd_entrance" for p in joe.state()["snapshot"]["players"]), "the human's picture shows her inside"
    v = joe.op("trial_view")["view"]
    assert [o["seat"] for o in v["others"]] == [ai.link.id], "drawn in the same zone"
    # the human goes up into the fork: she finds the way through the exit on her own
    rec = trial.seat_rec(t.world, joe.id)
    rec.update(zone="dd_fork", x=9, y=10)
    t.advance(30)
    mrec = trial.seat_rec(t.world, ai.link.id)
    assert mrec["zone"] == "dd_fork", mrec
    assert abs(mrec["x"] - 9) + abs(mrec["y"] - 10) <= int(ai.c["follow"]["near"]) + 1, "and stands near, a tile short"
    for line in t.session.command_log:
        if line["player"] == ai.link.id and line["op"].startswith("trial_"):
            assert line["op"] in ("trial_enter", "trial_move"), "she faces nothing and takes nothing: the choices are the human's"
    # out: the human leaves by the door; she walks back to it and leaves too
    rec.update(zone="dd_entrance", x=10, y=11)
    assert joe.op("trial_leave")["status"] == "ok"
    t.advance(45)
    assert not trial.inside(t.world, ai.link.id), trial.seat_rec(t.world, ai.link.id)
    assert said(joe, "trial_out")


def test_a_grounded_mira_stays_outside_and_says_why(monkeypatch):
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    at_gate(t, joe)
    mira = t.world.players[ai.link.id]
    mira["tx"], mira["ty"] = joe.pose["tx"] + 1, joe.pose["ty"]
    real = mother.is_grounded
    monkeypatch.setattr(mother, "is_grounded", lambda world, seat: seat == ai.link.id or real(world, seat))  # her mother had words (the rule itself is tested in test_mortality)
    assert joe.op("trial_enter")["status"] == "ok"
    t.advance(6)
    assert not trial.inside(t.world, ai.link.id)
    assert said(joe, "trial_grounded")


def test_the_mentor_mentions_mira_when_she_is_near_and_the_scene_gives_her_a_line():
    t = solo()
    joe, ai = t.people[0], ai_of(t)
    joe.stand_by_resident(t.mentor)
    mira = t.world.players[ai.link.id]
    mira["tx"], mira["ty"] = joe.pose["tx"] - 30, joe.pose["ty"]  # far away: not a word about her
    r = joe.op("talk", npc=t.mentor)
    assert r["status"] == "ok"
    joe.op("end_talk", npc=t.mentor, reason="closed")
    mira["tx"], mira["ty"] = joe.pose["tx"] + 1, joe.pose["ty"]
    r = joe.op("talk", npc=t.mentor)
    assert any("Mira" in line for line in r["lines"]), r["lines"]
    joe.op("end_talk", npc=t.mentor, reason="closed")
    r = joe.op("talk", npc=t.mentor)
    assert not any("second shadow" in line for line in r["lines"]), "said once"
    with party.as_player(t.world, joe.id):
        assert campaign.scene_ctx(t.world)["facts"]["mira_present"] == 1
    t2 = Table(humans=2)
    with party.as_player(t2.world, t2.people[0].id):
        assert campaign.scene_ctx(t2.world)["facts"]["mira_present"] == 0, "no AI in a two-human world"


def test_the_fourth_wall_is_noticed_rarely_and_counted():
    t = Table(humans=1)
    joe = t.people[0]
    t.learn(joe)
    for _ in range(8):
        ledger.bump(t.world, "talks", seat=joe.id)
    seen = 0
    asked = 0
    for kind, table in (("worker", t.world.workers), ("carrier", t.world.carriers)):
        for eid, row in sorted(table.items()):
            if row["faction_name"] != "Red" or asked >= 6:
                continue
            joe.stand_by(kind, eid)
            r = joe.op("talk", npc=eid)
            if r["status"] != "ok":
                continue
            asked += 1
            if "topic:who_counts" in [c["id"] for c in r["choices"]]:
                r2 = joe.op("choose", npc=eid, choice="topic:who_counts")
                assert "counting" in str(r2.get("text", "")), r2
                seen += 1
            joe.op("end_talk", npc=eid, reason="closed")
    assert asked >= 3
    assert ledger.count(t.world, "fourth_wall") == seen
    assert 1 <= seen <= 2, ("rare: offered while fewer than two have said it, then never again", seen)


def test_a_hub_seen_again_says_it_another_way():
    t = Table(humans=1)
    joe = t.people[0]
    from wizard_rts.narrative import pests

    pests.ensure(t.world)
    sid, b = pests.home(t.world)
    keeper = pests.ensure_keeper(t.world, sid, b)
    for inf in pests.state(t.world)["infestations"].values():  # nothing live and nothing to say about it: the keeper's "quiet" variant
        inf["cleared_ms"] = 0
        inf["complained"] = {}
    joe.stand_by_resident(keeper)
    firsts = []
    for _ in range(3):
        r = joe.op("talk", npc=keeper)
        assert r["status"] == "ok", r
        firsts.append(r["lines"][0])
        joe.op("end_talk", npc=keeper, reason="closed")
    assert len(set(firsts)) >= 2, firsts

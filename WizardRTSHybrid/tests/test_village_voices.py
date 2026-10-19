"""Each tribe speaks in its own voice and knows which village the apprentice is from; the Trial gate can be found (the journal, the status line,
the ranger and the carriers name its direction and distance); the developer's total reset deletes every save and builds from nothing."""
from __future__ import annotations

import pytest
from _party import Table

from wizard_rts.narrative import campaign, occupations, persist
from wizard_rts.net import host as nethost
from wizard_rts.trial import run as trial


@pytest.fixture(autouse=True)
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DMB_RUNS", str(tmp_path))
    return tmp_path


def worker_of(t: Table, faction: str, role: str = "lumberjack") -> str:
    return next(i for i, r in sorted(t.world.workers.items()) if r["faction_name"] == faction and r["role"] == role)


def talk(t: Table, h, wid: str) -> dict:
    h.stand_by("worker", wid)
    r = h.op("talk", npc=wid)
    assert r["status"] == "ok", r
    return r


def test_a_home_villager_and_a_villager_of_another_tribe_greet_you_differently_and_name_the_villages():
    t = Table(humans=1)
    joe = t.people[0]
    home = t.world.faction_info["Red"]["tribe"]
    other_faction = next(f for f, i in sorted(t.world.faction_info.items()) if i["tribe"] != home and f != "Red")
    r_home = talk(t, joe, worker_of(t, "Red"))
    joe.op("end_talk", npc=worker_of(t, "Red"))
    r_away = talk(t, joe, worker_of(t, other_faction))
    home_text, away_text = " ".join(r_home["lines"]), " ".join(r_away["lines"])
    assert home_text != away_text
    assert campaign.village(t.world) in away_text, (away_text, "an outsider greets the apprentice of the wizard's village by its name")
    assert "{" not in home_text + away_text
    ids = [c["id"] for c in r_away["choices"]]
    assert "topic:tribe_wizard_village" in ids or "topic:tribe_village" in ids, ids
    if "topic:tribe_wizard_village" in ids:
        rr = joe.op("choose", npc=worker_of(t, other_faction), choice="topic:tribe_wizard_village")
        assert rr["status"] == "ok" and rr["text"]
    joe.op("end_talk", npc=worker_of(t, other_faction))
    # the facts behind it
    with joe.seat_state():
        from wizard_rts.narrative import conversation

        sp = conversation.resolve(t.world, worker_of(t, other_faction))
        f = occupations.facts_for(t.world, sp)
    assert f["is_home"] == 0 and f["tribe"] == t.world.faction_info[other_faction]["tribe"] and f["home_village"] == campaign.village(t.world)
    assert f["this_village"] != f["home_village"] and f["home_distance"] > 20


def test_every_tribe_has_a_voice_and_every_village_a_name():
    t = Table(humans=1)
    data = occupations.data()["tribes"]
    for faction, info in sorted(t.world.faction_info.items()):
        assert info["tribe"] in data, (faction, info["tribe"])
        for key in ("intro_home", "intro_away", "hub", "often", "topics"):
            assert data[info["tribe"]][key], (info["tribe"], key)
    names = {campaign.settlement_name(t.world, sid) for sid in t.world.dmb.settlements}
    assert len(names) == len(t.world.dmb.settlements) and all(" " in n for n in names)
    assert campaign.village(t.world) == campaign.settlement_name(t.world, next(sid for sid, s in t.world.dmb.settlements.items() if s["faction"] == "Red"))


def test_the_gate_can_be_found_from_the_journal_the_status_line_and_the_people():
    t = Table(humans=1)
    joe = t.people[0]
    g = trial.gate_tile(t.world)
    st = joe.state()
    hint = st["trial_gate"]
    assert hint["tx"] == g[0] and hint["ty"] == g[1] and hint["distance"] >= 1 and hint["compass"] in trial.COMPASS
    with joe.seat_state():
        text = trial.gate_text(t.world)
        from wizard_rts.narrative import tutorial

        j = tutorial.snapshot(t.world)
    assert str(hint["distance"]) in text and hint["compass"] in text and j["trial_gate"] == text
    # stand on the gate: "right here"; inside the Trial the status line says nothing about it
    joe.pose["tx"], joe.pose["ty"] = g[0], g[1] + 1
    assert joe.state()["trial_gate"]["distance"] <= 1
    with joe.seat_state():
        assert "right here" in trial.gate_text(t.world)
    assert joe.op("trial_enter")["status"] == "ok"
    assert joe.state()["trial_gate"] == {}
    assert joe.op("trial_leave")["status"] == "ok"
    # the carriers' rumour names the direction and distance from where they stand
    from wizard_rts.narrative import graph

    topic = next(x for x in occupations.data()["shared_topics"] if x["id"] == "rumour_road")
    assert "{gate_compass}" in topic["lines"][-1] and "{gate_distance}" in topic["lines"][-1]
    ranger = graph.load("ranger_patrol")["speakers"]["ranger"]["nodes"]["hub"]["choices"]
    assert any("{gate_compass}" in " ".join(c.get("lines", [])) for c in ranger if c["id"] == "why_east")
    # the finished campaign's objective says where the gate is
    with joe.seat_state():
        from wizard_rts.narrative import wizard

        wizard.wiz(t.world)["campaign_finished"] = True
        campaign.state(t.world)["stage"] = "complete"
        assert "gate" in tutorial.objective(t.world) and hint["compass"] in tutorial.objective(t.world) or "right here" in tutorial.objective(t.world)


def test_the_total_reset_deletes_every_save_and_builds_from_nothing_with_the_seed_given(tmp_path):
    t = Table(humans=1)
    persist.save_world(t.world, persist.slot_path("campaign", "quit"))
    nethost.archive_saves("campaign")
    persist.save_world(t.world, persist.slot_path("campaign", "quit"))
    folder = persist.saves_dir("campaign")
    assert len(list(folder.glob("*"))) >= 2, "a live save and an archived one"
    world, info = nethost.prepare_world("campaign", 4242, "small", fresh=True)
    assert not info["loaded"] and info["wiped"] and not list(folder.glob("*.pkl")) and not list(folder.glob("*.json"))
    assert world.seed == 4242 and "narrative" not in world.__dict__ or world.dmb.clock.get("game_ms", 0) < 5000, "a world from nothing"
    # the ordinary new world keeps the old aside; a continued host finds nothing to continue after the reset
    world2, info2 = nethost.prepare_world("campaign", 507, "small")
    assert not info2["loaded"] and not info2["archived"]
    args = nethost.parse_args(["--fresh", "--seed", "7", "--code", "1234", "--secret", "x"])
    assert args.fresh and args.seed == 7

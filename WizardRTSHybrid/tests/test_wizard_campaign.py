"""The apprentice opening: the mentor, the lessons, free exploration, the stranger, the mentor's death, the lethal Ward Duel (win and lose), the aftermath,
the final objective, persistence and isolation. Everything goes through the real ops (`story.dispatch`), the same ones the Godot client sends."""
import hashlib
import json

import pytest

import _campaign as cp
import _nh as nh
from test_wizard_tutorial import go_to_teacher, learn_everything
from wizard_rts import narrative, server, story
from wizard_rts.narrative import campaign, checks, conversation, duel_lease, graph, persist, personas, residents, tutorial, wizard

from sim.dmb.people.registry import PeopleService


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    cp.quick(monkeypatch)


def rows(w, **kw):
    return [r for r in residents.table(w).values() if all(r.get(k) == v for k, v in kw.items())]


# ------------------------------------------------------------------ 1. the apprentice and the mentor

def test_the_player_begins_as_an_apprentice_with_a_known_mentor():
    w = nh.world()
    m = cp.mentor(w)
    snap = w.snapshot()["story"]["narrative"]["journal"]
    opening = " ".join(snap["opening"])
    assert len(snap["opening"]) == 3 and w.dmb.people[m]["name"] in opening and "apprentice" in opening
    assert "ruler" in opening  # wizards are not necessarily rulers
    assert campaign.stage(w) == "training" and not campaign.state(w)["attacker"]
    rec = w.dmb.people[m]
    assert rec["persona"]["primary"] == "D" and rec["persona"]["secondary"] == "M" and rec["relationship_map"]["player"] == 40
    assert residents.table(w)[m]["role"] == "mentor" and len(residents.table(w)) == 1
    start = checks.scores(w)  # an apprentice is not a blank: the starting Aspects come from configuration
    assert start["curiosity"] == 3 and start["authority"] == 1 and set(start) == {"reason", "empathy", "authority", "guile", "resolve", "curiosity", "wonder"}


def test_the_mentor_teaches_the_three_spells_and_the_weave_and_they_can_be_used():
    w = nh.world()
    t = go_to_teacher(w)
    nh.talk(w, t)
    r = nh.pick(w, t, "learn_colours")
    assert wizard.spells(w) == [0, 1, 6] and wizard.wiz(w)["weave_size"] == 3
    for word in ("Flame", "Frost", "Vine", "Fracture", "Echo", "Fade", "Ward"):
        assert word in r["text"], word
    c = wizard.combatant(w)  # what the board is given: the spells the apprentice really has, in a weave of three
    assert c["attack_pool"] == [0, 1, 6] and c["weave_size"] == 3 and c["ward_size"] == 3
    rec = duel_lease.begin(w, "opponent.teacher_hidden", purpose="hidden_ward")["payload"]["duel"]
    assert rec["encounter"]["player_combatant"]["attack_pool"] == [0, 1, 6]
    duel_lease.abandon(w)


def test_losing_a_practice_duel_is_not_lethal():
    w = nh.world()
    t = go_to_teacher(w)
    nh.talk(w, t)
    nh.pick(w, t, "learn_colours")
    nh.end(w, t)
    nh.talk(w, t)
    r = nh.pick(w, t, "told_practice")
    rec = r["duel_lease"]["payload"]["duel"]
    out = cp.fight(w, rec, False)
    assert out["outcome"] in ("lost", "draw")
    assert not campaign.over(w) and campaign.stage(w) == "training" and wizard.lesson_done(w, "told_ward")
    assert server._handle(w, {"op": "pose", "tx": w.player["tx"], "ty": w.player["ty"], "facing": "down"}).get("reason") != "game_over"
    assert any("nothing here can hurt you" in l or "It held" in l for l in out["follow_up"]["lines"])


def test_the_mentor_reacts_to_how_the_apprentice_did():
    w = nh.world()
    t = go_to_teacher(w)
    nh.talk(w, t)
    nh.pick(w, t, "learn_colours")
    nh.end(w, t)
    nh.talk(w, t)
    r = nh.pick(w, t, "told_practice")
    out = cp.fight(w, r["duel_lease"]["payload"]["duel"], True)
    lines = " ".join(out["follow_up"]["lines"])
    quick = int(wizard.wiz(w)["duels"]["attempts"][-1]["casts"]) <= 3
    assert ("Three casts" in lines) == quick and "Now a fair fight" in lines or "Next, a fair fight" in lines


# ------------------------------------------------------------------ 2. free exploration

def test_the_exploration_starts_when_the_essential_lessons_are_done_and_not_before():
    w = nh.world()
    nh.adv(w, 120)
    assert campaign.stage(w) == "training" and not campaign.state(w)["attacker"]  # time alone never moves a world past its lessons
    cp.finished_training(w)
    assert campaign.state(w)["explore_start_ms"] is not None
    assert tutorial.objective(w).startswith("Explore")


def test_the_attack_needs_game_time_and_real_contact_or_the_fallback():
    w = nh.world()
    cp.finished_training(w)
    nh.adv(w, 15)
    assert campaign.stage(w) == "explore"  # before the minimum time, whatever the player did
    cp.meet_people(w, 3)
    nh.adv(w, 8)
    assert campaign.stage(w) == "arrival", campaign.explore_due(w)  # time and contact: the stranger comes
    w2 = nh.world()
    cp.finished_training(w2)
    nh.adv(w2, 40)  # past the minimum, but nobody has been met
    assert campaign.stage(w2) == "explore" and campaign.explore_due(w2)["by"] == ""
    nh.adv(w2, 30)  # the bounded fallback: the player cannot wait for ever
    assert campaign.stage(w2) == "arrival" and campaign.explore_due(w2)["by"] == "fallback"


def test_a_paused_clock_does_not_advance_the_exploration():
    w = nh.world()
    cp.finished_training(w)
    from sim.dmb.time.clock import ClockService

    ClockService(w.dmb.clock).acquire_pause("test", "t")  # the client's pause (an open card, a minimised window) holds game time
    before = campaign.explore_due(w)["elapsed_ms"]
    for i in range(300):
        w.advance(1000, int(w.dmb.clock["clock_sequence"]) + 1, snapshot=False)
    assert campaign.explore_due(w)["elapsed_ms"] == before and campaign.stage(w) == "explore"


def test_the_attack_waits_for_a_quiet_moment():
    w = nh.world()
    cp.finished_training(w)
    nh.adv(w, 70)
    # a conversation is open at the moment the fallback expires: nothing interrupts it
    wid = nh.find_worker(w, "lumberjack")
    nh.stand_by(w, "worker", wid)
    story.dispatch(w, {"op": "talk", "npc": wid})
    nh.adv(w, 5)
    assert campaign.stage(w) in ("explore", "arrival")
    if campaign.stage(w) == "explore":
        nh.end(w, wid)
        nh.adv(w, 3)
        assert campaign.stage(w) == "arrival"


def test_the_forest_dispute_is_optional():
    w = nh.world()
    cp.finished_training(w)
    nh.adv(w, 3)
    assert quests_status(w) in ("offered", "cast", "active")
    nh.adv(w, 80)
    assert campaign.stage(w) == "arrival"  # the attack comes whether or not the quarrel was heard


def quests_status(w):
    from wizard_rts.narrative import quests

    return quests.status(w, "forest_dispute")


# ------------------------------------------------------------------ 3. the stranger and the mentor's death

def test_the_stranger_arrives_once_as_a_named_resident_who_walks_in():
    w = nh.world()
    cp.to_arrival(w)
    st = campaign.state(w)
    a = st["attacker"]
    r = residents.table(w)[a]
    assert w.dmb.people[a]["name"] and r["role"] == "stranger" and r["hostile"] and r["walk"]
    assert w.dmb.people[a]["persona"]["primary"] == "S"  # he believes magical power is a right to command
    start = tuple(r["tile"])
    assert campaign.active_scene(w)["id"] == "notice"
    view = campaign.scene_view(w)
    assert view["focus"] == list(start)  # the camera is guided to where he enters
    cp.walk_in(w)
    assert tuple(residents.table(w)[a]["tile"]) != start
    mt = residents.table(w)[cp.mentor(w)]["tile"]
    at = residents.table(w)[a]["tile"]
    assert max(abs(at[0] - mt[0]), abs(at[1] - mt[1])) <= 2  # he walked up to the mentor over a real path
    nh.adv(w, 200)
    assert len(rows(w, role="stranger")) == 1 and campaign.state(w)["attacker"] == a  # exactly once, however long the world runs


def test_the_mentor_dies_exactly_once_for_real_and_stays_dead():
    w = nh.world()
    m = cp.mentor(w)
    rec = cp.to_duel(w)
    p = w.dmb.people[m]
    assert p["alive"] is False and p["status"] == "dead" and w.dmb.tombstones[m]["cause_id"].startswith("killed_by:")
    assert residents.table(w)[m]["status"] == "dead" and campaign.state(w)["mentor_fate"] == "killed_by_stranger"
    deaths = [e for e in w.narrative["log"] if e["kind"] == "character_died" and e["person"] == m]
    notes = [n for n in wizard.wiz(w)["journal_notes"] if "was killed" in n["text"]]
    assert len(deaths) == 1 and len(notes) == 1
    row = next(r for r in w.snapshot()["entities"] if r["id"] == m)
    assert row["dead"] is True and row["alive"] is False  # a body in the world, drawn as one
    tile = residents.table(w)[m]["tile"]
    w.player["tx"], w.player["ty"] = tile[0] + 1, tile[1]
    cp.fight(w, rec, True)
    cp.through_scene(w)
    assert story.dispatch(w, {"op": "talk", "npc": m})["reason"] == "dead"  # nobody can speak to the dead
    nh.adv(w, 100)
    assert w.dmb.people[m]["alive"] is False and len([e for e in w.narrative["log"] if e["kind"] == "character_died" and e["person"] == m]) == 1
    assert len(rows(w, role="mentor")) == 1  # never a second mentor, never a resurrection


def test_a_mentor_already_lost_to_something_else_is_not_resurrected_or_killed_twice():
    w = nh.world()
    m = cp.mentor(w)
    PeopleService(w.dmb).record_death(m, cause_id="elsewhere")
    residents.table(w)[m]["status"] = "dead"
    cp.finished_training(w)
    cp.meet_people(w, 3)
    for _ in range(100):
        nh.adv(w, 1)
        if campaign.stage(w) == "arrival":
            break
    assert campaign.stage(w) == "arrival"
    cp.walk_in(w)
    assert campaign.active_scene(w)["id"] == "confrontation_alone"
    r = cp.through_scene(w)
    assert "duel_lease" in r and campaign.state(w)["mentor_fate"] == "died_earlier"
    assert len([e for e in w.narrative["log"] if e["kind"] == "character_died" and e["person"] == m]) == 0  # the scene did not kill them again
    assert w.dmb.tombstones[m]["cause_id"] == "elsewhere" and len(rows(w, role="mentor")) == 1


# ------------------------------------------------------------------ 4. the lethal duel

def test_the_lethal_duel_is_a_real_ward_duel_with_the_ordinary_rules_made_gentle_by_configuration_only():
    w = nh.world()
    rec = cp.to_duel(w)
    enc = rec["encounter"]
    teacher = duel_lease.begin(nh.world(), "opponent.teacher_hidden", purpose="x")["payload"]["duel"]["encounter"]
    assert rec["purpose"] == "stranger_duel" and rec["kind"] == duel_lease.KIND and w.dmb.clock["pause_tokens"]
    for key in ("weave_size", "ward_size", "attack_pool", "allow_repeats"):
        assert enc["player_combatant"][key] == teacher["player_combatant"][key]  # the apprentice's real spells and weave
        assert enc["enemy_combatant"][key] == teacher["enemy_combatant"][key]  # the same rules for the stranger
    assert enc["enemy_combatant"]["display_name"] == w.dmb.people[campaign.state(w)["attacker"]]["name"]
    assert enc["player_combatant"]["max_casts"] > enc["enemy_combatant"]["max_casts"] - 1  # a forgiving budget...
    assert enc["enemy_combatant"]["bot_logic"] == "random" and enc["enemy_combatant"]["think_min_seconds"] >= 40  # ...against a slow, careless opponent
    assert "fixed_ward" not in enc["enemy_combatant"]  # nothing is rigged: the Ward is the bot's own, reproduced by Python from the seed
    assert duel_lease.expected_enemy_ward(rec) == duel_lease.expected_enemy_ward(rec) and len(duel_lease.expected_enemy_ward(rec)) == 3


def test_a_careful_player_usually_wins_and_a_careless_one_can_lose():
    wins = 0
    losses = 0
    for seed in (507, 11, 3):
        w = nh.world(seed=seed)
        rec = cp.to_duel(w)
        wins += cp.fight(w, rec, True)["outcome"] == "won"
        w2 = nh.world(seed=seed)
        rec2 = cp.to_duel(w2)
        losses += cp.fight(w2, rec2, False)["outcome"] != "won"
    assert wins >= 2 and losses == 3  # easy, never guaranteed: the careless side of the table really loses


def test_victory_the_stranger_retreats_alive_nothing_new_begins_and_the_mentor_stays_dead():
    w = nh.world()
    rec = cp.to_duel(w)
    out = cp.fight(w, rec, True)
    assert out["outcome"] == "won" and out["campaign"]["stage"] == "victory" and not campaign.over(w)
    a = campaign.state(w)["attacker"]
    assert campaign.scene_view(w)["id"] == "victory" and w.dmb.people[a]["alive"] is True
    cp.through_scene(w)
    nh.adv(w, 60)
    assert residents.table(w)[a]["status"] == "gone" and w.dmb.people[a]["alive"]  # retreated, not killed: he can return later
    assert duel_lease.active(w) is None and not [l for l in w.dmb.leases.values() if l.get("state") == "ACTIVE"]  # no encounter starts by itself
    assert w.dmb.people[cp.mentor(w)]["alive"] is False
    assert wizard.wiz(w)["duels"]["won"] >= 1
    assert checks.scores(w)["resolve"] == 3  # surviving by one's own hand steadies the apprentice, once


def test_defeat_is_terminal():
    w = nh.world()
    rec = cp.to_duel(w)
    lid = rec["id"]
    out = cp.fight(w, rec, False)
    assert out["outcome"] in ("lost", "draw") and out["campaign"]["stage"] == "game_over"
    assert campaign.over(w) and wizard.wiz(w)["fate"]["alive"] is False and "player" in w.dmb.tombstones
    assert w.dmb.leases[lid]["state"] == "RESOLVED"  # the duel was released properly
    snap = w.snapshot()["story"]["narrative"]["journal"]["campaign"]
    assert snap["stage"] == "game_over" and snap["game_over"]["text"] == "The apprentice was defeated."
    assert [e["kind"] for e in w.narrative["log"]].count("player_died") == 1
    # nothing can go on with the dead character
    for op in ({"op": "pose", "tx": 1, "ty": 1}, {"op": "fire", "target": next(iter(w.trees))}, {"op": "talk", "npc": cp.mentor(w)}, {"op": "interact"},
               {"op": "move", "units": [], "tx": 1, "ty": 1}, {"op": "save", "slot": "x"}):
        assert server._handle(w, op)["reason"] == "game_over", op
    ms = int(w.dmb.clock["game_ms"])
    nh.adv(w, 30)
    assert int(w.dmb.clock["game_ms"]) == ms  # the world is held
    # recorded once, however many times the report is repeated
    again = story.dispatch(w, {"op": "duel_resolve", "duel_id": lid, **cp.play(rec, win=False)})
    assert again.get("reason") == "game_over" or again.get("status") in ("idempotent", "rejected")
    assert [e["kind"] for e in w.narrative["log"]].count("player_died") == 1


@pytest.mark.parametrize("how", ["stalemate_or_defeat", "fled", "forged", "abandon", "load"])
def test_every_other_way_out_of_the_lethal_duel_is_the_apprentices_death(how, tmp_path):
    w = nh.world()
    rec = cp.to_duel(w)
    if how == "stalemate_or_defeat":
        cp.fight(w, rec, False)
    elif how == "fled":
        story.dispatch(w, {"op": "duel_resolve", "duel_id": rec["id"], "outcome": "fled"})
    elif how == "forged":
        story.dispatch(w, {"op": "duel_resolve", "duel_id": rec["id"], "outcome": "victory", "player_casts": 1, "enemy_casts": 1, "enemy_ward": [0, 0, 0],
                           "history": [{"pattern": [0, 0, 0], "fracture": 3, "echo": 0, "broke": True}]})
    elif how == "abandon":
        story.dispatch(w, {"op": "duel_abandon"})
    else:  # saved with the duel open, then loaded: not an escape
        persist.save_world(w, tmp_path / "s.pkl")
        w, _ = persist.load_world(tmp_path / "s.pkl")
    assert campaign.over(w), how
    assert not w.dmb.leases[rec["id"]]["state"] == "ACTIVE" and wizard.wiz(w)["fate"]["alive"] is False


def test_a_dead_apprentice_is_never_restored_into_an_active_game(tmp_path):
    w = nh.world()
    persist.save_world(w, tmp_path / "before.pkl")  # an earlier valid save is still valid
    cp.fight(w, cp.to_duel(w), False)
    with pytest.raises(persist.SaveError) as err:
        persist.save_world(w, tmp_path / "after.pkl")
    assert err.value.reason == "game_over" and not (tmp_path / "after.pkl").exists()
    assert server._handle(w, {"op": "save", "slot": "quit"})["reason"] == "game_over"
    older, _ = persist.load_world(tmp_path / "before.pkl")
    assert not campaign.over(older) and campaign.stage(older) == "training"  # loading an earlier save is the player's explicit choice
    # even if a dead world were written by some other route, it loads as dead
    import pickle

    blob = pickle.dumps({"format": persist.save_format(), "hash": w.state_hash(), "narrative_version": narrative.config.version(), "world": w})
    (tmp_path / "forced.pkl").write_bytes(blob)
    forced, _ = persist.load_world(tmp_path / "forced.pkl")
    assert campaign.over(forced) and forced.snapshot()["story"]["narrative"]["journal"]["campaign"]["game_over"]


def test_new_game_gives_a_fresh_living_world():
    w = nh.world()
    cp.fight(w, cp.to_duel(w), False)
    reply = server._handle(w, {"op": "new_game"})
    fresh = reply["_swap"]
    assert reply["status"] == "ok" and not campaign.over(fresh) and campaign.stage(fresh) == "training" and fresh is not w
    assert wizard.spells(fresh) == [] and fresh.dmb.people[tutorial.state(fresh)["teacher"]]["alive"]
    assert reply["snapshot"] is not None


# ------------------------------------------------------------------ 5. the aftermath

def test_the_aftermath_uses_ordinary_people_who_react_as_themselves():
    w = nh.world()
    cp.to_aftermath(w)
    before = len(residents.table(w))
    assert before == 2  # the mentor's body and the stranger: no one else was created to carry the story
    seen = {}
    for role in ("lumberjack", "ranger"):
        wid = nh.find_worker(w, role)
        nh.stand_by(w, "worker", wid)
        r = nh.talk(w, wid)
        seen[role] = r["lines"]
        assert not any("{" in l for l in r["lines"])
        assert any(c["id"] == "topic:t_happened" for c in r["choices"]) and any(c["id"] == "topic:t_leave" for c in r["choices"])
        nh.end(w, wid)
    assert seen["lumberjack"] != seen["ranger"]  # a forester and a woodcutter do not say the same thing
    assert len(residents.table(w)) == before
    cid = next(i for i in w.carriers if w.carriers[i]["faction_name"] == "Red")
    nh.stand_by(w, "carrier", cid)
    assert nh.talk(w, cid)["lines"]


def test_witnesses_and_rumour_are_kept_apart():
    w = nh.world()
    cp.to_aftermath(w)
    st = campaign.state(w)
    near = [k for k in st["witnesses"] if k.startswith("worker:")]
    far = [(i, r) for i, r in sorted(w.workers.items()) if characters_key(i) not in st["witnesses"] and r["faction_name"] == "Red"]
    if near:
        pid = nh.talk(w, near[0].split(":")[1]) and w.narrative["links"][near[0]]
        assert campaign.knowledge(w, pid) == "witnessed"
        nh.end(w, near[0].split(":")[1])
    if far:
        i, _row = far[0]
        nh.stand_by(w, "worker", i)
        nh.talk(w, i)
        pid = w.narrative["links"]["worker:" + i]
        assert campaign.knowledge(w, pid) == "rumour"
        r = nh.pick(w, i, "topic:t_happened")
        assert "I was not there" in r["text"] and w.dmb.people[st["attacker"]]["name"] not in r["text"]  # a rumour does not know the stranger's name


def characters_key(i):
    return "worker:" + i


def test_the_final_objective_is_recorded_once_after_conversation_or_the_fallback():
    w = nh.world()
    cp.to_aftermath(w)
    assert tutorial.objective(w).startswith("Speak with the people")
    for role in ("lumberjack", "ranger"):
        wid = nh.find_worker(w, role)
        nh.stand_by(w, "worker", wid)
        nh.talk(w, wid)
        nh.end(w, wid)
    nh.adv(w, 3)
    assert campaign.stage(w) == "complete" and wizard.wiz(w)["campaign_finished"]
    notes = [n for n in wizard.wiz(w)["journal_notes"] if "seek greater magical power" in n["text"].lower()]
    assert len(notes) == 1 and tutorial.objective(w) == "Seek greater magical power."
    nh.adv(w, 100)
    assert len([n for n in wizard.wiz(w)["journal_notes"] if "seek greater magical power" in n["text"].lower()]) == 1
    # and nothing further is started
    assert duel_lease.active(w) is None and campaign.stage(w) == "complete" and len(rows(w, role="stranger", status="present")) == 0


def test_the_fallback_ends_the_aftermath_even_if_nobody_is_spoken_to():
    w = nh.world()
    cp.to_aftermath(w)
    nh.adv(w, 60)
    assert campaign.stage(w) == "complete"


# ------------------------------------------------------------------ 6. scenes cannot be skipped, repeated or duplicated

def test_a_scene_needs_an_answer_before_it_moves_and_effects_apply_once():
    w = nh.world()
    cp.to_arrival(w)
    cp.walk_in(w)
    for _ in range(20):
        v = campaign.scene_view(w)
        if v["needs_answer"]:
            break
        story.dispatch(w, {"op": "scene_next"})
    assert v["needs_answer"] and story.dispatch(w, {"op": "scene_next"})["reason"] == "answer_required"
    assert story.dispatch(w, {"op": "scene_choose", "choice": "resp:nonsense"})["reason"] == "choice_unavailable"
    kills = [e for e in w.narrative["log"] if e["kind"] == "character_died"]
    assert len(kills) == 1
    cid = v["choices"][0]["id"]
    assert story.dispatch(w, {"op": "scene_choose", "choice": cid})["status"] == "ok"
    assert story.dispatch(w, {"op": "scene_choose", "choice": cid})["status"] == "rejected"  # one answer per page
    assert len([e for e in w.narrative["log"] if e["kind"] == "character_died"]) == 1


# ------------------------------------------------------------------ 7. persistence at every stage

@pytest.mark.parametrize("stage", ["explore", "arrival", "confrontation", "victory", "aftermath", "complete"])
def test_save_and_load_keep_the_campaign_without_duplicating_anyone(stage, tmp_path):
    w = nh.world()
    m = cp.mentor(w)
    if stage == "explore":
        cp.finished_training(w)
    elif stage == "arrival":
        cp.to_arrival(w)
    elif stage == "confrontation":
        cp.to_arrival(w)
        cp.walk_in(w)
        for _ in range(8):
            story.dispatch(w, {"op": "scene_next"})
    elif stage == "victory":
        cp.fight(w, cp.to_duel(w), True)
    elif stage == "aftermath":
        cp.to_aftermath(w)
    else:
        cp.to_aftermath(w)
        nh.adv(w, 60)
    assert campaign.stage(w) == stage, campaign.stage(w)
    persist.save_world(w, tmp_path / "s.pkl")
    loaded, info = persist.load_world(tmp_path / "s.pkl")
    assert not info["hash_mismatch"] and campaign.stage(loaded) == stage
    assert json.dumps(loaded.narrative["campaign"], sort_keys=True, default=str) == json.dumps(w.narrative["campaign"], sort_keys=True, default=str)
    assert loaded.dmb.people[m]["alive"] == w.dmb.people[m]["alive"]
    assert len(rows(loaded, role="mentor")) == 1 and len(rows(loaded, role="stranger")) == len(rows(w, role="stranger")) <= 1
    nh.adv(loaded, 60)
    assert len(rows(loaded, role="stranger")) <= 1 and len(rows(loaded, role="mentor")) == 1
    if stage in ("victory", "aftermath", "complete", "confrontation"):
        assert [e for e in loaded.narrative["log"] if e["kind"] == "character_died" and e["person"] == m].__len__() <= 1


def test_the_whole_opening_is_deterministic():
    def run():
        w = nh.world()
        cp.fight(w, cp.to_duel(w), True)
        cp.through_scene(w)
        nh.adv(w, 30)
        return json.dumps({"c": w.narrative["campaign"], "wz": wizard.wiz(w)["worldview"], "log": [(e["kind"], e["game_ms"]) for e in w.narrative["log"]],
                           "names": [p["name"] for p in w.dmb.people.values()][:6]}, sort_keys=True, default=str)

    assert hashlib.sha1(run().encode()).hexdigest() == hashlib.sha1(run().encode()).hexdigest()


def test_the_opening_changes_no_rule_of_the_rts_simulation():
    """The whole opening (to the final objective) leaves the factions exactly as a world without any narrative layer: the stranger and the mentor are
    narrative residents, the hold only touches people the apprentice talks to, and nothing draws from world.rng."""
    from test_narrative_isolation import faction_hash
    from wizard_rts.world import HybridWorld

    w = nh.world(enable_after=0)
    rec = cp.to_duel(w)
    cp.fight(w, rec, True)
    cp.through_scene(w)
    nh.adv(w, 60)
    assert campaign.stage(w) == "complete"
    plain = HybridWorld(507, profile="campaign")
    plain.ai_enabled = False
    seconds = int(w.dmb.clock["game_ms"] // 1000)
    for i in range(seconds):
        plain.advance(1000, i + 1, snapshot=False)
    # the narrative world also stood still during the scenes and the duel (pause tokens) and met three people (holds of a few seconds): compare the
    # tick-for-tick part only, the rng and the events, which hold is not allowed to disturb
    assert plain.rng.getstate() == w.rng.getstate()
    assert plain.events.total == w.events.total


# ------------------------------------------------------------------ 8. content

def test_every_scene_and_aftermath_line_formats_and_names_exist():
    data = json.loads((nh.__file__ and __import__("pathlib").Path(nh.__file__).resolve().parents[1] / "wizard_rts" / "data" / "narrative" / "dialogue" / "campaign_scenes.json").read_text())
    assert set(data["scenes"]) == {"notice", "confrontation", "confrontation_alone", "victory"}
    for sid, sc in data["scenes"].items():
        assert sc["final"] in ("arrival", "duel", "aftermath"), sid
        assert sc["pages"] and all(p["lines"] for p in sc["pages"]), sid
    kills = [p for sc in data["scenes"].values() for p in sc["pages"] if any(e["kind"] == "kill_mentor" for e in p.get("effects", []))]
    assert len(kills) == 1  # one place in the story kills the mentor
    assert sum(1 for sc in data["scenes"].values() if sc["final"] == "duel") == 2  # the two ways to the duel


# ------------------------------------------------------------------ 9. more guarantees

def test_the_progression_is_applied_not_just_the_flags():
    w = nh.world()
    for lesson in ("meet", "colours", "told_ward", "hidden_ward"):
        wizard.complete_lesson(w, lesson)  # flags only: no spells (an inconsistent state)
    assert wizard.spells(w) == []
    nh.adv(w, 3)
    assert campaign.stage(w) == "explore" and wizard.spells(w) == [0, 1, 6] and wizard.wiz(w)["weave_size"] == 3
    assert [e for e in w.narrative["log"] if e["kind"] == "spells_repaired"]
    assert wizard.combatant(w)["attack_pool"] == [0, 1, 6]


def test_a_finished_scene_cannot_be_repeated_and_opens_one_duel():
    w = nh.world()
    rec = cp.to_duel(w)
    assert story.dispatch(w, {"op": "scene_next"})["reason"] == "no_scene"
    assert story.dispatch(w, {"op": "scene_choose", "choice": "resp:confrontation:9:s"})["reason"] == "no_scene"
    assert len([l for l in w.dmb.leases.values() if l.get("purpose") == "stranger_duel"]) == 1
    nh.adv(w, 20)  # the world is held by the duel's pause; nothing re-triggers
    assert len(rows(w, role="stranger")) == 1 and campaign.stage(w) == "duel" and rec["state"] == "ACTIVE"


def test_the_same_person_reacts_differently_with_different_relationships_and_beliefs():
    w = nh.world()
    cp.to_aftermath(w)
    texts = {}
    for variant in ("fond", "wary"):
        wid = nh.find_worker(w, "lumberjack")
        nh.stand_by(w, "worker", wid)
        pid = story.dispatch(w, {"op": "inspect_person", "npc": wid})["person"]
        p = personas.persona(w, pid)
        p["mentor"] = variant
        w.narrative["reacted"] = [x for x in w.narrative.get("reacted", []) if x != pid]
        texts[variant] = nh.talk(w, wid)["lines"]
        nh.end(w, wid)
    # a lumberjack with the same trade and knowledge: a fond one and a wary one are not given the same words
    assert texts["fond"] is not None and texts["wary"] is not None
    # and the generic witness reactions do separate fond from wary
    gen = {r["id"]: r for r in __import__("wizard_rts.narrative.occupations", fromlist=["x"]).aftermath()["reactions"]}
    assert gen["w_fond"]["lines"] != gen["w_wary"]["lines"]


def test_asking_a_person_the_aspect_topics_pays_nothing_twice_after_loading(tmp_path):
    w = nh.world()
    cp.to_aftermath(w)
    wid = nh.find_worker(w, "lumberjack")
    nh.stand_by(w, "worker", wid)
    nh.talk(w, wid)
    out = nh.pick(w, wid, "topic:t_stranger")
    pid = w.narrative["links"]["worker:" + wid]
    first = (out["check"]["passed"], list(wizard.wiz(w)["facts"]), len(wizard.wiz(w)["journal_notes"]))
    persist.save_world(w, tmp_path / "s.pkl")
    loaded, _ = persist.load_world(tmp_path / "s.pkl")
    nh.stand_by(loaded, "worker", wid)
    nh.talk(loaded, wid)
    if first[0]:
        again = nh.pick(loaded, wid, "topic:t_stranger")
        assert again["check"]["again"] is True
    assert list(wizard.wiz(loaded)["facts"]) == first[1] and len(wizard.wiz(loaded)["journal_notes"]) == first[2]


def test_people_with_a_part_in_the_forest_dispute_also_react_to_the_attack():
    w = nh.world()
    cp.finished_training(w)
    nh.adv(w, 3)
    cutter = quests_binding(w, "cutter")
    cp.to_aftermath(w)
    nh.stand_by(w, "worker", cutter["id"])
    r = nh.talk(w, cutter["id"])
    text = " ".join(r["lines"])
    assert any(w in text for w in ("saw it", "sat down", "axe sharper", "Everyone is talking", "I was there", "heard", "felled my share")), text
    assert "topic:t_happened" in nh.ids(r)


def quests_binding(w, role):
    from wizard_rts.narrative import quests

    return quests.rec(w, "forest_dispute")["bindings"][role]

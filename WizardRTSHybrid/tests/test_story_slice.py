"""M3: one live-settlement story on the real world. A shortage that exists in the simulation (a mine whose gallery caved in, D22: sites
never run dry) opens a quest for a real person; the wizard talks, goes underground, solves four puzzles, breaks the warden's code in a
Mastermind duel and a typed effect reopens the gallery once; the mine digs again. Every step goes through the wizard's public ops (story.dispatch)."""
import copy
import os
import pickle
import subprocess
import sys

import pytest

from wizard_rts import ledger, story, story_agent as A, story_fixture
from wizard_rts import construction as con
from wizard_rts.puzzle.dungeon import ENTRY
from wizard_rts.world import HybridWorld

SEED = 507


def fresh():
    w = HybridWorld(SEED, profile="developer")
    w.ai_enabled = False
    ids = story_fixture.prepare(w)
    return w, ids


@pytest.fixture(scope="module")
def prepared():
    w, ids = fresh()
    blob = pickle.dumps(w)  # a pristine copy for the variants (saves round-trip through pickle exactly as HybridEnv.save does)
    return blob, ids


def clone(prepared):
    blob, ids = prepared
    return pickle.loads(blob), copy.deepcopy(ids)  # each test gets its own clock sequence counter


def seq_run(w, ids, seconds):
    for _ in range(seconds):
        ids["seq"] += 1
        w.advance(1000, ids["seq"], snapshot=False)


def learn_and_accept(w, ids, persuade=True):
    npc = ids["npc"]
    A.walk_to_npc(w, npc)
    for c in ("ask_cause", "ask_gallery", "accept_help") + (("persuade",) if persuade else ()):
        r = A.op(w, "choose", npc=npc, choice=c)
        assert r["status"] == "ok", r


def go_down(w, ids):
    entrance = story.state(w)["dungeons"][ids["dungeon"]]["entrance"]["tile"]
    A.place_wizard_near(w, entrance)
    r = A.op(w, "enter", dungeon=ids["dungeon"])
    assert r["status"] == "ok", r
    return r


def reach_reward(w):
    view = story.dungeon_view(w)
    reward = next(e for e in view["entities"] if e["id"].endswith("_reward"))
    return A.go_adjacent(w, view, tuple(reward["pos"])), reward


def walk_out(w):
    view = story.dungeon_view(w)
    exit_pos = tuple(next(e for e in view["entities"] if e["kind"] == "exit")["pos"])
    path = A._bfs(view, None, exit_pos)
    cur = tuple(view["pos"])
    r = {}
    for st in path:
        r = A.op(w, "dungeon_move", dx=st[0] - cur[0], dy=st[1] - cur[1])
        cur = st
    assert r.get("left")


def test_shortage_comes_from_real_state_and_opens_one_quest(prepared):
    w, ids = clone(prepared)
    q = w.dmb.quests[ids["quest"]]
    mine = w.buildings[ids["mine"]]
    assert mine["disrupted"]["cause"] == "collapse" and mine["kind"] == "mine" and mine["operational"]
    assert w.resource_total((mine["tx"], mine["ty"]), 2, "coal") > 0  # the seam is still there (D22): the gallery is what failed
    made = w.stats.get("made_coal", 0)
    seq_run(w, ids, 60)
    assert w.stats.get("made_coal", 0) == made  # a closed mine really produces nothing
    assert q["status"] == "offered" and q["template_id"] == "quest.shortage.gallery_collapse"
    assert q["affected_entity_id"] == ids["mine"] and q["stakeholder_id"] == ids["npc"] and q["site_id"].startswith("settlement:")
    person = w.dmb.people[ids["npc"]]
    assert person["workplace_id"] == ids["mine"] and person["alive"]
    seq_run(w, ids, 60)  # the check repeats every second: still exactly one quest, one cause, one person
    assert len(w.dmb.quests) == 1 and len(w.dmb.people) == 1 and len(story.state(w)["dungeons"]) == 1
    # the person and the entrance are entities of the one world
    rows = {r["kind"]: r for r in story.entity_rows(w)}
    assert rows["npc"]["has_quest"] and rows["dungeon_entrance"]["dungeon"] == ids["dungeon"]


def test_no_quest_without_a_shortage():
    w = HybridWorld(SEED, profile="developer")
    w.ai_enabled = False
    for i in range(300):
        w.advance(1000, i + 1, snapshot=False)
    assert not w.dmb.quests and not story.state(w)["npcs"]


def test_dialogue_facts_come_from_the_live_world(prepared):
    w, ids = clone(prepared)
    A.walk_to_npc(w, ids["npc"])
    r = A.op(w, "talk", npc=ids["npc"])
    f = story.facts(w, story.state(w)["quests"][ids["quest"]])
    assert "caved in" in r["lines"][0] and "%d minutes ago" % f["minutes_since"] in r["lines"][0]
    assert "props on site: %d of %d" % (f["props_have"], f["props_need"]) in r["lines"][1]
    # change the world and the words change: the same person cites the new stock
    wh = con.faction_warehouse(w, "Red")
    from wizard_rts.economy import produce
    mine = w.buildings[ids["mine"]]
    produce(w, mine["id"], "log", 2)  # two props carried in (counted as made so the ledger stays balanced)
    w.stats["made_log"] = w.stats.get("made_log", 0) + 2
    r2 = A.op(w, "talk", npc=ids["npc"])
    assert "props on site: %d of %d" % (story.facts(w, story.state(w)["quests"][ids["quest"]])["props_have"], f["props_need"]) in r2["lines"][1]
    assert r2["lines"][1] != r["lines"][1]
    assert A.op(w, "talk", npc="person:999")["reason"] == "no_such_person"
    w.player["tx"], w.player["ty"] = 5, 5
    assert A.op(w, "talk", npc=ids["npc"])["reason"] == "too_far"  # the wizard has to be standing there


def test_aspect_check_needs_evidence_and_is_not_retried_for_free(prepared):
    w, ids = clone(prepared)
    npc = ids["npc"]
    A.walk_to_npc(w, npc)
    story.state(w)["quests"][ids["quest"]]["sigil_given"] = True  # skip ahead to the check without learning anything first
    r = A.op(w, "choose", npc=npc, choice="persuade")
    assert r["check"]["passed"] is False and r["check"]["total"] == 1  # reason score 1, no evidence, neutral relationship
    again = A.op(w, "choose", npc=npc, choice="persuade")
    assert again["check"]["blocked"] is True  # same fingerprint: nothing changed, so no free retry
    story.state(w)["quests"][ids["quest"]]["evidence"] = 1  # the wizard has learned something since
    third = A.op(w, "choose", npc=npc, choice="persuade")
    assert third["check"]["passed"] is True and story.state(w)["quests"][ids["quest"]]["persuaded"]


def test_full_story_changes_the_world_once(prepared):
    w, ids = clone(prepared)
    mine = w.buildings[ids["mine"]]
    tile = (mine["tx"], mine["ty"])
    init = ledger.snapshot_totals(w)
    reserve0 = w.resource_total(tile, 2, "coal")
    layer = bytes(w.terrain.res_kind)
    assert mine["disrupted"]["cause"] == "collapse"
    learn_and_accept(w, ids)
    assert story.state(w)["inventory"] == [story.state(w)["dungeons"][ids["dungeon"]]["record"]["needs"]["item"]]
    go_down(w, ids)
    log = []
    assert A.solve_dungeon(w, log)
    # the plinth is guarded: the reward cannot be taken until the warden's code is broken
    view, reward = reach_reward(w)
    assert A.op(w, "dungeon_interact", entity=reward["id"])["status"] == "duel_required"
    assert w.dmb.quests[ids["quest"]]["status"] == "active"
    ms = int(w.dmb.clock["game_ms"])
    result = A.break_the_code(w)
    assert result["status"] == "solved" and result["result"]["outcome"] == "full"
    assert len(result["public"]["guesses"]) <= result["public"]["max_casts"] == 12  # persuasion gave two more casts
    assert "secret" not in str(result["public"])  # the public view never leaks the code
    q = w.dmb.quests[ids["quest"]]
    assert q["status"] == "completed" and q["resolution"] == "gallery_full"
    # a typed effect with receipts reopened the real mine, exactly once; the deposit layer is untouched (D22: no new geology)
    assert not w.buildings[ids["mine"]].get("disrupted") and w.resource_total(tile, 2, "coal") == reserve0
    assert bytes(w.terrain.res_kind) == layer
    assert len(q["effect_receipts"]) == 2 and all(r in w.dmb.command_receipts for r in q["effect_receipts"])
    assert sum(1 for e in w.events if e["kind"] == "disruption_cleared" and e["how"] == "wizard") == 1
    # applying the same effects again changes nothing
    again = story.apply_effects(w, ids["quest"], [{"kind": "reopen_gallery", "mode": "full", "mine": ids["mine"]},
                                                  {"kind": "history_fact", "fact": "gallery_reopened:full", "person": ids["npc"]}], prefix="duel1")
    assert [a["status"] for a in again["applied"]] == ["idempotent", "idempotent"]
    walk_out(w)
    assert not story.state(w)["in_dungeon"]
    # production changes: the mine digs again and the warehouse coal stock rises
    wh = con.faction_warehouse(w, "Red")
    coal0, made0 = w.stocks[wh["id"]].get("coal", 0), w.stats.get("made_coal", 0)
    seq_run(w, ids, 400)
    assert w.stats.get("made_coal", 0) > made0 and w.stocks[wh["id"]].get("coal", 0) > coal0
    assert ledger.check(w, init) == []  # the wares balance; mined coal is logged as an inexhaustible-deposit source (D22)
    # the story is closed: no second quest, the person remembers
    assert len(w.dmb.quests) == 1
    A.walk_to_npc(w, ids["npc"])
    talk = A.op(w, "talk", npc=ids["npc"])
    assert "coming up again" in talk["lines"][0] and talk["choices"] == []
    assert any(f["value"] == "gallery_reopened:full" for f in w.dmb.people[ids["npc"]]["known_facts"])


def test_duel_freezes_game_time_and_keeps_entity_ids(prepared):
    w, ids = clone(prepared)
    learn_and_accept(w, ids)
    go_down(w, ids)
    A.solve_dungeon(w)
    reach_reward(w)
    ids_before = w.entity_ids()
    ms = int(w.dmb.clock["game_ms"])
    assert A.op(w, "duel_begin")["status"] == "started"
    assert w.dmb.clock["pause_tokens"]
    ids["seq"] += 1
    r = w.advance(5000, ids["seq"], snapshot=False)
    assert r["quanta"] == 0 and int(w.dmb.clock["game_ms"]) == ms  # world time is frozen while the duel is open
    assert w.entity_ids() == ids_before  # nothing came or went while frozen
    assert A.op(w, "duel_abandon")["status"] == "ok"
    assert not w.dmb.clock["pause_tokens"]
    ids["seq"] += 1
    assert w.advance(2000, ids["seq"], snapshot=False)["quanta"] > 0
    assert w.dmb.quests[ids["quest"]]["status"] == "active"  # abandoning the duel resolves nothing
    alive = set(w.entity_ids())  # once time runs again a hunter may take a deer; nothing else of the scene may vanish
    assert {i for i in ids_before if not i.startswith("animal:")} <= alive


def test_exhausted_casts_give_the_shored_gallery_alternate_ending(prepared):
    w, ids = clone(prepared)
    learn_and_accept(w, ids, persuade=False)
    go_down(w, ids)
    A.solve_dungeon(w)
    reach_reward(w)
    assert A.op(w, "duel_begin")["status"] == "started"
    secret = story.state(w)["duel"]["mm"]["mastermind"]["secret"]  # the test peeks to make every guess wrong
    wrong = [(c + 1) % 6 for c in secret]
    last = {}
    for _ in range(10):
        wrong = [(c + 1) % 6 for c in wrong]
        if wrong == secret:
            wrong = [(c + 2) % 6 for c in wrong]
        last = A.op(w, "duel_guess", guess=wrong)
        if last["status"] in ("solved", "exhausted"):
            break
    assert last["status"] == "exhausted" and last["result"]["outcome"] == "thin"
    assert w.dmb.quests[ids["quest"]]["resolution"] == "gallery_thin"  # a legitimate alternate ending, not a failure
    d = w.buildings[ids["mine"]]["disrupted"]  # the dig-out is shortened to two minutes once the props are there
    assert int(d["repair_ms"]) - int(d["progress_ms"]) <= 120_000


def test_giving_up_fails_with_consequence_and_the_shortage_persists(prepared):
    w, ids = clone(prepared)
    A.walk_to_npc(w, ids["npc"])
    r = A.op(w, "choose", npc=ids["npc"], choice="give_up")
    assert r["status"] == "ok"
    q = w.dmb.quests[ids["quest"]]
    assert q["status"] == "failed_with_consequence" and q["branch"] == "abandoned"
    assert w.buildings[ids["mine"]]["disrupted"]["cause"] == "collapse"
    assert "history.abandoned.%s" % ids["quest"] in w.dmb.people[ids["npc"]]["history_refs"]
    assert w.dmb.people[ids["npc"]]["relationship_map"]["player"] < 0
    seq_run(w, ids, 120)
    assert len(w.dmb.quests) == 1  # the same shortage does not spawn the same quest again
    talk = A.op(w, "talk", npc=ids["npc"])
    assert "remember" in talk["lines"][0]


def test_destroying_the_mine_mid_quest_fails_it_without_a_soft_lock(prepared):
    w, ids = clone(prepared)
    learn_and_accept(w, ids)
    go_down(w, ids)
    A.solve_dungeon(w)
    w.damage_building(ids["mine"], 10 ** 9, ["structure"], {})
    seq_run(w, ids, 30)
    q = w.dmb.quests[ids["quest"]]
    assert q["status"] == "failed_with_consequence" and q["resolution"] == "target_destroyed"
    # still underground: the wizard can walk out; nothing is stuck
    assert story.state(w)["in_dungeon"]
    walk_out(w)
    assert not story.state(w)["in_dungeon"]
    seq_run(w, ids, 200)  # the ruin is purged: the entrance disappears with the building, the person is displaced
    assert not [r for r in story.entity_rows(w) if r["kind"] == "dungeon_entrance"]
    assert w.dmb.people[ids["npc"]]["status"] == "displaced"
    A.walk_to_npc(w, ids["npc"])
    assert "no mine left" in A.op(w, "talk", npc=ids["npc"])["lines"][0]


def test_world_fixes_the_shortage_first(prepared):
    w, ids = clone(prepared)
    mine = w.buildings[ids["mine"]]
    # the faction digs itself out: its props arrive over the roads and the long repair runs (no wizard involved)
    w.disruptions_enabled = True
    w.hazard_tile = None  # the Ward Duel hazard on Red's log road (a separate story) is gone, so logs reach the warehouse again
    for _ in range(20 * 60):
        ids["seq"] += 1
        w.advance(1000, ids["seq"], snapshot=False)
        if not mine.get("disrupted"):
            break
    assert not mine.get("disrupted")
    assert any(e["kind"] == "disruption_cleared" and e["how"] == "repaired" and e["id"] == ids["mine"] for e in w.events)
    seq_run(w, ids, 2)
    q = w.dmb.quests[ids["quest"]]
    assert q["status"] == "resolved_by_world" and q["resolution"] == "world_fix_first"
    A.walk_to_npc(w, ids["npc"])
    assert "already gone" in A.op(w, "talk", npc=ids["npc"])["lines"][0]
    assert not A.op(w, "choose", npc=ids["npc"], choice="accept_help")["status"] == "ok"


def test_save_reload_and_reenter_never_reapply_or_respawn(prepared):
    w, ids = clone(prepared)
    learn_and_accept(w, ids)
    go_down(w, ids)
    A.solve_dungeon(w)
    reach_reward(w)
    A.break_the_code(w)
    walk_out(w)
    stats = dict(w.stats)
    w2 = pickle.loads(pickle.dumps(w))  # save and reload
    assert w2.state_hash() == w.state_hash()
    story.state(w2)  # the story survives the round trip
    assert w2.dmb.quests[ids["quest"]]["status"] == "completed"
    entrance = story.state(w2)["dungeons"][ids["dungeon"]]["entrance"]["tile"]
    A.place_wizard_near(w2, entrance)
    assert A.op(w2, "enter", dungeon=ids["dungeon"])["status"] == "ok"  # re-entering is allowed
    view = story.dungeon_view(w2)
    assert all(view["solved"])  # puzzles stay solved
    assert A.op(w2, "dungeon_interact", entity="x")["status"] == "rejected"
    assert A.op(w2, "duel_begin")["reason"] in ("too_far", "no_open_quest")  # the quest is closed: no second duel, no second reward
    walk_out(w2)
    assert sum(1 for e in w2.events if e["kind"] == "disruption_cleared" and e["how"] == "wizard") == 1
    assert len(w2.dmb.quests) == 1 and len(w2.dmb.people) == 1


def run_hash(pyhashseed):
    code = (
        "import os; os.environ['HYBRID_AI']='0'\n"
        "from wizard_rts.world import HybridWorld\nfrom wizard_rts import story, story_agent as A, story_fixture\n"
        "w=HybridWorld(507, profile='developer'); w.ai_enabled=False\nids=story_fixture.prepare(w)\n"
        "npc=ids['npc']; A.walk_to_npc(w,npc)\n"
        "[A.op(w,'choose',npc=npc,choice=c) for c in ('ask_cause','ask_gallery','accept_help','persuade')]\n"
        "A.place_wizard_near(w, story.state(w)['dungeons'][ids['dungeon']]['entrance']['tile']); A.op(w,'enter',dungeon=ids['dungeon'])\n"
        "A.solve_dungeon(w)\n"
        "view=story.dungeon_view(w); r=[e for e in view['entities'] if e['id'].endswith('_reward')][0]; A.go_adjacent(w,view,tuple(r['pos']))\n"
        "res=A.break_the_code(w)\nprint(res['status'], len(res['public']['guesses']), w.state_hash())\n")
    here = os.path.dirname(__file__)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=os.path.dirname(here),
                       env={**os.environ, "PYTHONHASHSEED": pyhashseed, "PYTHONPATH": here + os.pathsep + os.path.dirname(here)})
    assert r.returncode == 0, r.stderr[-800:]
    return r.stdout.strip()


def test_whole_story_is_deterministic_across_processes():
    assert run_hash("0") == run_hash("4242")

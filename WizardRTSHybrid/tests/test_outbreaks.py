"""M5: the hex-region outbreak overlay (D12, S09) on the unchanged square-grid world."""
import os
import subprocess
import sys

import pytest

from wizard_rts import construction as con
from wizard_rts import regions, story, story_agent as A
from wizard_rts.world import HybridWorld

SEED = 507


def world(profile="developer", enabled=False):
    w = HybridWorld(SEED, profile=profile)
    w.ai_enabled = False
    w.outbreaks_enabled = enabled  # cadence off unless a test wants it: cubes are then placed by hand
    w._seq = 0
    return w


def run(w, seconds):
    for _ in range(int(seconds)):
        w._seq += 1
        w.advance(1000, w._seq, snapshot=False)


def test_every_tile_belongs_to_exactly_one_region_and_the_count_is_s09s():
    w = world()
    rg = regions.state(w)
    assert 19 <= len(rg.axials) <= 37
    assert len(rg.table) == w.terrain.w * w.terrain.h and min(rg.table) == 0 and max(rg.table) == len(rg.axials) - 1
    counts = [0] * len(rg.axials)
    for v in rg.table:
        counts[v] += 1
    assert all(c > 0 for c in counts) and sum(counts) == w.terrain.w * w.terrain.h  # a partition: no gap, no overlap
    for i, ns in enumerate(rg.neighbours):  # adjacency is symmetric and at most six
        assert len(ns) <= 6 and all(i in rg.neighbours[n] for n in ns)
    # the hex centre of a region lies in that region
    import math
    for i, (q, r) in enumerate(rg.axials):
        cx, cy = w.terrain.w / 2 + 1.5 * rg.size * q, w.terrain.h / 2 + math.sqrt(3) * rg.size * (r + q / 2)
        if 0 <= cx < w.terrain.w and 0 <= cy < w.terrain.h:
            assert rg.region_at(int(cx), int(cy)) == i


def test_overlay_never_changes_placement_or_movement():
    a, b = world(), world()
    rg = regions.state(b)
    for i in range(len(rg.cubes)):
        rg.cubes[i] = 3
        rg.kind[i] = "sickness"
    run(a, 3)
    run(b, 3)
    wh = con.faction_warehouse(a, "Red")
    for kind in ("quarry", "producer", "ranger", "farm", "mine"):
        for dx, dy in ((5, 5), (-6, 4), (9, -3), (2, 8), (-10, -10)):
            assert con.check_placement(a, "Red", kind, wh["tx"] + dx, wh["ty"] + dy)[0] == con.check_placement(b, "Red", kind, wh["tx"] + dx, wh["ty"] + dy)[0]
    t = a.terrain
    for x, y in ((10, 10), (100, 100), (300, 200), (wh["tx"], wh["ty"])):
        for loco in ("foot", "tracked", "wheeled"):
            assert a.tile_speed(loco, x, y) == b.tile_speed(loco, x, y)
    from wizard_rts.workers import find_path
    assert find_path(a, (wh["tx"], wh["ty"]), (wh["tx"] + 12, wh["ty"] + 9)) == find_path(b, (wh["tx"], wh["ty"]), (wh["tx"] + 12, wh["ty"] + 9))


def test_cadence_adds_a_cube_every_ten_minutes_deterministically():
    w = world(enabled=True)
    run(w, 9 * 60 + 50)
    assert not any(regions.state(w).cubes)
    run(w, 20)
    rg = regions.state(w)
    assert sum(rg.cubes) == 1 and rg.added == 1
    first = [i for i, n in enumerate(rg.cubes) if n][0]
    assert any(b for b in w.buildings.values() if rg.region_at(b["tx"], b["ty"]) == first)  # an empty wilderness cannot suffer
    run(w, 10 * 60)
    assert rg.added == 2 or sum(rg.cubes) >= 2


def test_spread_pushes_one_cube_from_a_region_with_two_to_its_emptiest_neighbour():
    w = world(enabled=True)
    rg = regions.state(w)
    i = max(range(len(rg.cubes)), key=lambda k: len(rg.neighbours[k]))
    rg.cubes[i] = 2
    rg.kind[i] = "sickness"
    nb = rg.neighbours[i]
    rg.cubes[nb[0]] = 1
    rg.next_cube_ms = 10 ** 12
    rg.next_spread_ms = 1000
    run(w, 3)
    assert rg.cubes[i] == 1
    target = min(nb, key=lambda n: (1 if n == nb[0] else 0, n))
    assert rg.cubes[target] == (2 if target == nb[0] else 1) and sum(rg.cubes) == 3  # conserved: moved, not created


def test_a_cube_in_a_full_region_is_an_outbreak_that_spreads_one_level():
    w = world()
    rg = regions.state(w)
    i = 12
    rg.cubes[i] = 3
    rg.kind[i] = "sickness"
    regions._add_cube(w, rg, i, 0, "test")
    assert rg.outbreaks == 1 and rg.cubes[i] == 3
    assert all(rg.cubes[n] == 1 for n in rg.neighbours[i])
    assert sum(rg.cubes) == 3 + len(rg.neighbours[i])


def test_treatment_needs_presence_time_and_has_a_cooldown():
    w = world()
    rg = regions.state(w)
    mine_region = rg.region_at(w.player["tx"], w.player["ty"])
    rg.cubes[mine_region] = 2
    rg.kind[mine_region] = "sickness"
    other = (mine_region + 1) % len(rg.cubes)
    rg.cubes[other] = 1
    res = A.op(w, "treat")
    assert res["status"] == "started"
    run(w, 4)
    assert rg.cubes[mine_region] == 2  # not done yet: the channel takes 8 s
    run(w, 6)
    assert rg.cubes[mine_region] == 1 and rg.treated == 1
    assert A.op(w, "treat")["reason"] == "recovering"  # limited attention: a cooldown between treatments
    run(w, 20)
    A.op(w, "treat")
    # walking out of the region abandons the treatment
    far_tile = next((x, y) for y in range(0, w.terrain.h, 8) for x in range(0, w.terrain.w, 8) if rg.region_at(x, y) != mine_region and w.terrain.ground(x, y))
    run(w, 2)
    w.player["tx"], w.player["ty"] = far_tile
    run(w, 10)
    assert rg.cubes[mine_region] == 1 and rg.treat is None
    # presence is required to start one at all: no cubes under his feet
    assert A.op(w, "treat")["reason"] in ("nothing_to_treat", "recovering")
    assert rg.region_at(*far_tile) != mine_region and rg.cubes[other] == 1


def _mine_world(cubes):
    import test_industry_mechanics as T

    w = world()
    T.cards(w)
    bid, tile, fp = T._real_mine(w)
    for _ in range(300):  # warm up: the first rations arrive
        run(w, 1)
    rg = regions.state(w)
    i = rg.region_at(w.buildings[bid]["tx"], w.buildings[bid]["ty"])
    rg.cubes[i] = cubes
    rg.kind[i] = "sickness"
    return w, bid, i


def test_an_outbreak_slows_the_workplaces_of_its_region_by_the_stated_factor_and_recovers():
    base_w, bid, _i = _mine_world(0)
    sick_w, sbid, si = _mine_world(3)
    assert regions.production_factor(sick_w, sick_w.buildings[sbid]) == pytest.approx(max(0.4, 0.8 ** 3))  # sickness: 0.8 per cube, floor 0.4
    assert regions.production_factor(base_w, base_w.buildings[bid]) == 1.0
    m0, m1 = base_w.stats.get("made_coal", 0), sick_w.stats.get("made_coal", 0)
    run(base_w, 900)
    run(sick_w, 900)
    healthy, sick = base_w.stats.get("made_coal", 0) - m0, sick_w.stats.get("made_coal", 0) - m1
    assert healthy >= 8 and sick < healthy * 0.8  # visible in conserved production, not decoration
    # the wizard treats the region down to nothing: the pace recovers
    rg = regions.state(sick_w)
    rg.cubes[si] = 0
    assert regions.production_factor(sick_w, sick_w.buildings[sbid]) == 1.0


def test_era_specific_kinds_hit_different_workplaces():
    w = world()
    rg = regions.state(w)
    farm = next(b for b in w.buildings.values() if b["kind"] == "producer")
    w.era_index = 1
    i = rg.region_at(farm["tx"], farm["ty"])
    rg.cubes[i] = 2
    rg.kind[i] = "blight"
    assert regions.production_factor(w, farm) == 1.0  # blight is a food plague: a woodcutter is untouched
    from wizard_rts import construction as c2
    fake = dict(farm, kind="farm")
    assert regions.production_factor(w, fake) == pytest.approx(0.36)
    rg.kind[i] = "toxic_spill"
    assert regions.production_factor(w, dict(farm, kind="mine")) == pytest.approx(0.36) and regions.production_factor(w, fake) == 1.0
    rg.kind[i] = "signal_fault"
    assert regions.production_factor(w, dict(farm, kind="mdy:silicon_smelter")) == pytest.approx(0.25) and regions.production_factor(w, farm) == 1.0
    assert regions.kind_for_era(0)["id"] == "sickness" and regions.kind_for_era(2)["id"] == "toxic_spill" and regions.kind_for_era(3)["id"] == "signal_fault"


def test_unrest_grows_where_cubes_sit_and_feeds_the_split_rule():
    w = world()
    rg = regions.state(w)
    home = next(r for r in w.dmb.settlements.values() if r["faction"] == "Red")
    i = rg.region_at(*home["tile"])
    rg.cubes[i] = 3
    rg.kind[i] = "sickness"
    run(w, 130)  # two game minutes
    assert w.dmb.settlements[home["id"]]["unrest"] >= 0.1
    rg.cubes[i] = 0
    before = w.dmb.settlements[home["id"]]["unrest"]
    run(w, 130)
    assert w.dmb.settlements[home["id"]]["unrest"] < before


def test_visible_clues_one_marker_per_cube_inside_the_region():
    w = world()
    rg = regions.state(w)
    home = next(r for r in w.dmb.settlements.values() if r["faction"] == "Blue")
    i = rg.region_at(*home["tile"])
    rg.cubes[i] = 2
    rg.kind[i] = "sickness"
    rows = [r for r in regions.entity_rows(w) if r["region"] == rg.rid(i)]
    assert len(rows) == 2 and all(r["kind"] == "outbreak_clue" and r["label"] == "withered ground" for r in rows)
    snap = w.snapshot()
    assert any(e["kind"] == "outbreak_clue" for e in snap["entities"]) and snap["regions"]["cubes"][rg.rid(i)] == 2


def test_the_healer_quest_follows_the_cubes_and_completes_when_the_region_is_clean():
    w = world()
    rg = regions.state(w)
    home = next(r for r in w.dmb.settlements.values() if r["faction"] == "Red")
    i = rg.region_at(*home["tile"])
    rg.cubes[i] = 2
    rg.kind[i] = "sickness"
    run(w, 12)
    qs = {qid: q for qid, q in story.state(w)["quests"].items() if q.get("family") == "outbreak"}
    assert len(qs) == 1
    qid, q = next(iter(qs.items()))
    assert w.dmb.quests[qid]["status"] == "offered" and w.dmb.quests[qid]["affected_entity_id"] == rg.rid(i)
    run(w, 30)
    assert len([x for x in story.state(w)["quests"].values() if x.get("family") == "outbreak"]) == 1  # deduped: one quest per region
    A.walk_to_npc(w, q["npc"])
    talk = A.op(w, "talk", npc=q["npc"])
    assert "2 marks" in talk["lines"][0] and "withered ground" in talk["lines"][0]
    assert A.op(w, "choose", npc=q["npc"], choice="accept_treat")["status"] == "ok"
    assert w.dmb.quests[qid]["status"] == "active"
    for _round in range(2):  # treat twice, standing in the region
        w.player["tx"], w.player["ty"] = home["tile"][0] + 2, home["tile"][1] + 2
        assert rg.region_at(w.player["tx"], w.player["ty"]) == i
        assert A.op(w, "treat")["status"] == "started"
        run(w, 10)
        run(w, 21)
    assert rg.cubes[i] == 0 and w.dmb.quests[qid]["status"] == "completed" and w.dmb.quests[qid]["resolution"] == "treated"
    A.walk_to_npc(w, q["npc"])
    assert "work is back" in A.op(w, "talk", npc=q["npc"])["lines"][0].lower()


def test_eight_outbreaks_end_the_cycle_by_the_terminal_rule():
    w = world()
    rg = regions.state(w)
    for k in range(8):
        i = k
        rg.cubes[i] = 3
        rg.kind[i] = "sickness"
        regions._add_cube(w, rg, i, 0, "test")
    assert rg.outbreaks >= 8
    run(w, 2)
    assert rg.lost and w.cycle_pending and any(e["kind"] == "terminal_loss" for e in w.events)
    from wizard_rts import history
    fresh = history.cycle_reset(w)  # the explicit rule: the loss ends the cycle; only the wizard carries over
    assert fresh.dmb.clock["game_ms"] == 0 and not regions.state(fresh).lost


def test_a_wizard_who_treats_where_it_is_worst_keeps_the_count_below_the_loss_line():
    """Recoverable path: with the cadence on and a patient wizard the loss line is not reached; the unattended world drifts toward it."""
    def play(treat):
        w = world(enabled=True)
        rg = regions.state(w)
        for minute in range(60):
            if treat and any(rg.cubes):
                worst = max(range(len(rg.cubes)), key=lambda k: (rg.cubes[k], -k))
                home = next((b for b in sorted(w.buildings.values(), key=lambda b: b["id"]) if rg.region_at(b["tx"], b["ty"]) == worst), None)
                if home is not None:
                    w.player["tx"], w.player["ty"] = home["tx"], home["ty"] + 1
                    if rg.region_at(w.player["tx"], w.player["ty"]) == worst:
                        A.op(w, "treat")
            run(w, 60)
        return rg.outbreaks, sum(rg.cubes), rg.treated

    treated, ignored = play(True), play(False)
    assert treated[0] <= ignored[0] and treated[1] <= ignored[1] and treated[2] > 0
    assert treated[0] < 8


def test_outbreak_state_is_deterministic_across_processes():
    code = (
        "import os; os.environ['HYBRID_AI']='0'\n"
        "from wizard_rts.world import HybridWorld\nfrom wizard_rts import regions\n"
        "w=HybridWorld(507, profile='developer'); w.ai_enabled=False\n"
        "[w.advance(1000,i+1,snapshot=False) for i in range(1900)]\n"
        "print(regions.snapshot(w)['cubes'], w.state_hash())\n")
    here = os.path.dirname(__file__)
    outs = []
    for hs in ("0", "321"):
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=os.path.dirname(here),
                           env={**os.environ, "PYTHONHASHSEED": hs, "PYTHONPATH": os.path.dirname(here)})
        assert r.returncode == 0, r.stderr[-500:]
        outs.append(r.stdout.strip())
    assert outs[0] == outs[1] and "region:" in outs[0]

"""M4: stable settlement identity, the VP ledger (S01-S03), era progress (S04), collapse / decline / split (S12) and the full-cycle reset
(D11, S07), all on the real world."""
import os
import subprocess
import sys

import pytest

from wizard_rts import construction as con
from wizard_rts import history, magic, settlements, tech, territory, vp
from wizard_rts.world import HybridWorld

SEED = 507


def world(profile="test_showcase"):
    w = HybridWorld(SEED, profile=profile)
    w.ai_enabled = False
    w._seq = 0
    return w


def run(w, seconds):
    for _ in range(int(seconds)):
        w._seq += 1
        w.advance(1000, w._seq, snapshot=False)


def free_ground(w, around, min_cheb, max_cheb=140, step=3):
    """A ground tile whose 3x3 footprint is free, at least `min_cheb` (Chebyshev) from every existing command centre."""
    cx, cy = around
    for r in range(min_cheb, max_cheb, step):
        for dy in range(-r, r + 1, step):
            for dx in range(-r, r + 1, step):
                if max(abs(dx), abs(dy)) != r:
                    continue
                x, y = cx + dx, cy + dy
                if not (3 < x < w.terrain.w - 4 and 3 < y < w.terrain.h - 4):
                    continue
                tiles = [(x + a, y + b) for a in (-1, 0, 1) for b in (-2, -1, 0)]
                if all(w.terrain.ground(*t) and t not in w.blocked and t not in w.tree_tiles and t not in w.road_tile_set for t in tiles):
                    if all(territory.cheb((x, y), (c["tx"], c["ty"])) > 40 for c in territory.command_centers(w)):
                        return (x, y)
    raise RuntimeError("no free ground")


def far_sites(w, faction, n, min_home=56):
    """n free sites over the whole map, each beyond `min_home` of the faction's home and more than 40 from every command centre and each other."""
    home = con.faction_warehouse(w, faction)
    chosen: list[tuple[int, int]] = []
    cands = []
    for y in range(8, w.terrain.h - 8, 6):
        for x in range(8, w.terrain.w - 8, 6):
            tiles = [(x + a, y + b) for a in (-1, 0, 1) for b in (-2, -1, 0)]
            if all(w.terrain.ground(*t) and t not in w.blocked and t not in w.tree_tiles and t not in w.road_tile_set for t in tiles):
                if territory.cheb((x, y), (home["tx"], home["ty"])) > min_home and all(territory.cheb((x, y), (c["tx"], c["ty"])) > 40 for c in territory.command_centers(w)):
                    cands.append((territory.cheb((x, y), (home["tx"], home["ty"])), y, x))
    for _d, y, x in sorted(cands):
        if all(territory.cheb((x, y), c) > 40 for c in chosen):
            chosen.append((x, y))
            if len(chosen) == n:
                return chosen
    raise RuntimeError("only %d sites" % len(chosen))


def outpost(w, faction, tile=None, near=None, min_cheb=45):
    """A deployed MCV: a real unit consumed by `territory._create_command_center` (the same call the deploy command ends in)."""
    home = con.faction_warehouse(w, faction)
    tile = tile or free_ground(w, near or (home["tx"], home["ty"]), min_cheb)
    uid = w._unit(w.faction_info[faction]["id"], faction, "mcv", "MCV", territory.MCV_DEFINITION, tile)
    return territory._create_command_center(w, w.units[uid]), tile


def test_every_command_centre_has_a_stable_unique_settlement_id():
    w = world()
    ids = [b["settlement_id"] for b in w.buildings.values() if b["kind"] == "warehouse"]
    assert len(ids) == 6 and len(set(ids)) == 6 and all(i.startswith("settlement:") for i in ids)
    rec = w.dmb.settlements[ids[0]]
    assert rec["state"] == "standing" and rec["home"] and rec["chronicle"][0]["event"] == "founded"
    run(w, 30)
    assert [b["settlement_id"] for b in w.buildings.values() if b["kind"] == "warehouse"] == ids  # ids do not change over time


def test_founding_adds_one_vp_once_and_an_undeployed_mcv_none():
    w = world()
    before = vp.totals(w)
    uid = w._unit(w.faction_info["Red"]["id"], "Red", "mcv", "MCV", territory.MCV_DEFINITION, free_ground(w, (con.faction_warehouse(w, "Red")["tx"], 50), 45))
    run(w, 5)
    assert vp.totals(w) == before  # an MCV that has not deployed is not a settlement
    bid = territory._create_command_center(w, w.units[uid])
    assert vp.faction_vp(w, "Red") == before["Red"] + 1
    sid = w.buildings[bid]["settlement_id"]
    assert w.dmb.settlements[sid]["home"] is False and len(vp.ledger(w)) == 7
    run(w, 3)
    vp.note_founded(w, sid, "Red")  # a repeated event is ignored
    assert len(vp.ledger(w)) == 7 and vp.faction_vp(w, "Red") == before["Red"] + 1


def test_conquest_awards_the_final_blow_exactly_once():
    w = world()
    bid, _ = outpost(w, "Blue")
    attacker = w._unit(w.faction_info["Red"]["id"], "Red", "tank", "Tank", "openra.3tnk", (w.buildings[bid]["tx"] + 3, w.buildings[bid]["ty"]))
    red0, blue0 = vp.faction_vp(w, "Red"), vp.faction_vp(w, "Blue")
    w.damage_building(bid, 10 ** 9, ["structure"], {}, by=attacker)
    assert vp.faction_vp(w, "Red") == red0 + 1  # +1 conquest
    assert vp.faction_vp(w, "Blue") == blue0 - 1  # the standing VP of the destroyed settlement ends
    assert w.dmb.settlements[w.buildings[bid]["settlement_id"]]["state"] == "destroyed"
    again = vp.on_destroyed(w, w.buildings[bid], attacker)
    assert again == {"status": "idempotent"} and vp.faction_vp(w, "Red") == red0 + 1
    run(w, 40)  # the ruin is purged later: nothing is awarded again
    assert vp.faction_vp(w, "Red") == red0 + 1
    assert vp.replay(w) == vp.totals(w)


def test_wizard_destruction_awards_nothing_and_ends_the_owners_vp():
    w = world()
    bid, tile = outpost(w, "Orange")
    w.player["tx"], w.player["ty"] = tile[0] + 2, tile[1] + 1
    totals0 = vp.totals(w)
    res = magic.fire(w, bid)
    assert res["status"] == "ok"
    t = vp.totals(w)
    assert t["Orange"] == totals0["Orange"] - 1
    assert all(t[f] == totals0[f] for f in t if f != "Orange")  # nobody scored
    entry = vp.ledger(w)[w.buildings[bid]["settlement_id"] + ":destroyed"]
    assert entry["cause"] == "wizard" and entry["winner"] == ""
    chron = w.dmb.settlements[w.buildings[bid]["settlement_id"]]["chronicle"][-1]
    assert chron["event"] == "destroyed" and chron["cause"] == "wizard"
    assert vp.replay(w) == vp.totals(w)


def test_a_faction_cannot_score_by_destroying_its_own_settlement():
    w = world()
    bid, _ = outpost(w, "Green")
    own = w._unit(w.faction_info["Green"]["id"], "Green", "tank", "Tank", "openra.3tnk", (w.buildings[bid]["tx"] + 3, w.buildings[bid]["ty"]))
    g0 = vp.faction_vp(w, "Green")
    w.damage_building(bid, 10 ** 9, ["structure"], {}, by=own)
    assert vp.faction_vp(w, "Green") == g0 - 1 and vp.ledger(w)[w.buildings[bid]["settlement_id"] + ":destroyed"]["winner"] == ""


def test_ledger_replay_equals_live_totals_after_a_busy_history_and_a_reload():
    import pickle

    w = world()
    a, _ = outpost(w, "Red")
    b, _ = outpost(w, "Blue")
    c, tc = outpost(w, "Yellow")
    killer = w._unit(w.faction_info["Red"]["id"], "Red", "tank", "Tank", "openra.3tnk", (w.buildings[b]["tx"] + 3, w.buildings[b]["ty"]))
    w.damage_building(b, 10 ** 9, ["structure"], {}, by=killer)
    w.player["tx"], w.player["ty"] = tc[0] + 2, tc[1] + 1
    magic.fire(w, c)
    assert vp.replay(w) == vp.totals(w)
    w2 = pickle.loads(pickle.dumps(w))
    assert vp.replay(w2) == vp.totals(w2) == vp.totals(w) and len(vp.ledger(w2)) == len(vp.ledger(w))
    run(w2, 20)
    assert vp.totals(w2) == vp.totals(w)  # a reloaded world does not count anything twice


def test_nothing_but_settlements_score():
    w = world()
    totals0 = vp.totals(w)
    for b in [b for b in w.buildings.values() if b["kind"] in ("mine", "quarry", "smithy", "barracks")][:6]:
        w.damage_building(b["id"], 10 ** 9, ["structure"], {}, by="wizard")
    run(w, 20)
    assert vp.totals(w) == totals0 and len(vp.ledger(w)) == 6  # only the six founding entries


def test_era_advances_on_the_vp_threshold_keeps_everything_and_opens_cards():
    w = world("developer")
    w.era_vp_threshold = 3
    buildings_before, units_before = set(w.buildings), {u: x["alive"] for u, x in w.units.items()}
    run(w, 2)
    rounds0 = {n: st["round"] for n, st in w.tech.items()}
    assert vp.era_state(w)["index"] == 0
    for _ in range(3):
        outpost(w, "Red")
    assert vp.progress(w) == 3
    run(w, 3)
    st = vp.era_state(w)
    assert st["index"] == 1 and w.era_index == 1 and st["log"][-1]["reason"] == "vp_threshold" and st["base"]["Red"] == 4
    assert buildings_before <= set(w.buildings) and all(w.units[u]["alive"] == a for u, a in units_before.items())  # an ordinary era change destroys nothing
    # S05: the era change gave every faction one extra draft round at once (the 15-minute cadence had not elapsed)
    run(w, 3)
    assert all(w.tech[n]["round"] == rounds0[n] + 1 for n in w.tech)
    assert max(tech.cards()[c]["era"] for c in tech.cards()) >= 1 and tech.draftable(w, "Red")  # era-1 cards are now eligible once their prerequisites hold


def test_era_stall_guard_and_last_era_ends_the_cycle():
    w = world("developer")
    w.era_max_ms = 20_000
    run(w, 25)
    assert vp.era_state(w)["index"] == 1 and vp.era_state(w)["log"][-1]["reason"] == "stall_guard"
    run(w, 50)
    assert vp.era_state(w)["index"] == 3 and not w.cycle_pending
    run(w, 25)
    assert w.cycle_pending and any(e["kind"] == "cycle_due" for e in w.events)  # the Dystopian era is over: the full cycle ends


def test_modern_cards_need_the_modern_era():
    w = world("developer")
    vp.set_era(w, 0)
    from wizard_rts.industry import fixture as F
    assert tech.grant(w, "Red", "dmb.card.automation")["status"] == "ok"  # developer grant ignores era...
    assert "dmb.card.automation" not in tech.draftable(world("developer"), "Red")  # ...but a draft never offers it before the era


def test_faction_without_command_centre_or_mcv_collapses_leaving_ruins():
    w = world()
    red = [b for b in w.buildings.values() if b["faction_name"] == "Red"]
    n_red_units = sum(1 for u in w.units.values() if u["faction_name"] == "Red")
    assert n_red_units > 0
    for b in [b for b in red if b["kind"] == "warehouse"]:
        w.damage_building(b["id"], 10 ** 9, ["structure"], {}, by="wizard")
    run(w, 3)
    fs = history.state(w)["faction"]["Red"]
    assert fs["state"] == "collapsed"
    assert all(u.get("alive") is False for u in w.units.values() if u["faction_name"] == "Red")
    assert all(b.get("destroyed") for b in w.buildings.values() if b["faction_name"] == "Red")  # ruins, then purged by the normal lifecycle
    assert history.state(w)["faction"]["Blue"]["state"] == "active"
    run(w, 30)
    assert not [b for b in w.buildings.values() if b["faction_name"] == "Red"]  # ruins are purged
    assert any(c["event"] == "collapsed" and c["faction"] == "Red" for c in history.state(w)["chronicle"])


def test_a_faction_with_only_an_mcv_left_has_not_collapsed():
    w = world()
    for b in [b for b in w.buildings.values() if b["faction_name"] == "Red" and b["kind"] == "warehouse"]:
        w._unit(w.faction_info["Red"]["id"], "Red", "mcv", "MCV", territory.MCV_DEFINITION, (b["tx"] + 3, b["ty"] + 3))
        w.damage_building(b["id"], 10 ** 9, ["structure"], {}, by="wizard")
    run(w, 3)
    assert history.state(w)["faction"]["Red"]["state"] == "declining"  # capital lost, but it can still found a settlement


def test_decline_when_the_capital_is_lost_or_nothing_has_worked_for_ten_minutes():
    w = world()
    outpost(w, "Blue")
    home = next(r for r in w.dmb.settlements.values() if r["faction"] == "Blue" and r["home"])
    w.damage_building(home["centre"], 10 ** 9, ["structure"], {}, by="wizard")
    run(w, 3)
    assert history.state(w)["faction"]["Blue"]["state"] == "declining"
    w2 = world("campaign")
    for b in w2.buildings.values():
        if b["faction_name"] == "Green":
            b["operational"] = False  # nothing can work
    run(w2, 11 * 60)
    assert history.state(w2)["faction"]["Green"]["state"] == "declining"


def test_split_needs_four_settlements_distance_no_link_and_unrest():
    w = world()
    spots = []
    for tile in far_sites(w, "Red", 3):
        bid, _t = outpost(w, "Red", tile=tile)
        spots.append(bid)
    assert len(settlements.standing(w, "Red")) == 4
    run(w, 3)
    assert history.split_candidates(w, "Red") is None  # no unrest, nothing happens
    far = max((w.buildings[b] for b in spots), key=lambda b: abs(b["tx"] - con.faction_warehouse(w, "Red")["tx"]) + abs(b["ty"] - con.faction_warehouse(w, "Red")["ty"]))
    centre_rec = next(r for r in w.dmb.settlements.values() if r["centre"] == far["id"])
    centre_rec["unrest"] = 0.9
    home = con.faction_warehouse(w, "Red")
    dist = max(abs(far["tx"] - home["tx"]), abs(far["ty"] - home["ty"]))
    cand = history.split_candidates(w, "Red")
    assert dist > history.SPLIT_DISTANCE, dist
    if True:
        assert cand is not None
        vp0 = vp.faction_vp(w, "Red")
        ids_before = set(w.entity_ids())
        history.split(w, "Red", cand[1])
        succ = next(n for n in w.faction_info if n.startswith("Red-"))
        assert w.faction_info[succ]["id"] != w.faction_info["Red"]["id"]
        assert w.buildings[far["id"]]["faction_name"] == succ  # the settlement and what stood in it moved with it
        assert vp.faction_vp(w, succ) >= 1 and vp.faction_vp(w, "Red") == vp0 - vp.faction_vp(w, succ)
        assert set(w.entity_ids()) == ids_before  # nothing was created or lost by the split
        run(w, 10)
        assert w.tech[succ]["cards"] == w.tech["Red"]["cards"]


def test_cycle_reset_keeps_only_the_wizard_and_redeals_homelands_by_peaks():
    from sim.dmb.narrative.aspects import AspectService

    w = world("developer")
    AspectService(w.dmb)._store()["scores"]["player"] = {"reason": 4, "empathy": 3}
    for _ in range(3):
        outpost(w, "Purple")
    run(w, 12)  # the history quantum records Purple's peak: four settlements
    peak = history.state(w)["faction"]["Purple"]["peak"]
    assert peak["settlements"] == 4 and peak["centroid"]
    fresh = history.cycle_reset(w)
    # only the wizard crossed over
    assert fresh is not w and fresh.dmb.clock["game_ms"] == 0
    assert AspectService(fresh.dmb)._store()["scores"]["player"] == {"reason": 4, "empathy": 3}
    assert len(fresh.dmb.settlements) == 6 and all(r["chronicle"][0]["event"] == "founded" and r["founded_ms"] == 0 for r in fresh.dmb.settlements.values())
    assert not fresh.dmb.quests and not fresh.dmb.people and not getattr(fresh, "story", {}).get("npcs")
    assert fresh.past_cycles[-1]["peaks"]["Purple"]["settlements"] == 4 and fresh.past_cycles[-1]["cycle"] == 0
    # S07: the strongest faction (Purple) takes the homeland nearest its old centroid among the three most fertile
    perm = fresh.past_cycles[-1]["homeland_deal"]
    assert sorted(perm) == [0, 1, 2, 3, 4, 5] and perm != [0, 1, 2, 3, 4, 5]
    purple_idx = [n for n in ("Red", "Blue", "Green", "Yellow", "Purple", "Orange")].index("Purple")
    starts = [tuple(s) for s in w.terrain.starts]
    fert = sorted(range(6), key=lambda i: (-history.fertility(w, starts[i]), i))
    assert perm[purple_idx] in fert[:3]
    purple_home = next(r for r in fresh.dmb.settlements.values() if r["faction"] == "Purple")
    assert tuple(purple_home["tile"]) == tuple(fresh.terrain.starts[perm[purple_idx]])  # the new home really stands on the dealt homeland
    # reset is not an era transition: an era change keeps ids and buildings, a reset replaces them
    assert vp.era_state(fresh)["index"] == 0


def test_cycle_reset_is_deterministic_across_processes():
    code = (
        "import os; os.environ['HYBRID_AI']='0'\n"
        "from wizard_rts.world import HybridWorld\nfrom wizard_rts import history\n"
        "w=HybridWorld(507, profile='developer'); w.ai_enabled=False\n"
        "[w.advance(1000,i+1,snapshot=False) for i in range(15)]\n"
        "f=history.cycle_reset(w)\nprint(f.past_cycles[-1]['homeland_deal'], f.state_hash())\n")
    here = os.path.dirname(__file__)
    outs = []
    for hs in ("0", "77"):
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=os.path.dirname(here),
                           env={**os.environ, "PYTHONHASHSEED": hs, "PYTHONPATH": os.path.dirname(here)})
        assert r.returncode == 0, r.stderr[-600:]
        outs.append(r.stdout.strip())
    assert outs[0] == outs[1]

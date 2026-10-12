"""Rules added in the autonomous-civilisation run (12 Oct 2026): inexhaustible mineral sites (D22), workplace disruptions, unrest and
splits, the seven-card draft, the world-VP era rule, settlers, solid trees and rocks for the wizard, and the scripted wizard pilot."""
import random

import pytest

from wizard_rts import construction as con
from wizard_rts import disruption, history, regions, resources, society, tech, territory, vp
from wizard_rts.industry import extraction as X
from wizard_rts.world import HybridWorld


def _mine_site(w, res="coal"):
    t = w.terrain
    for y in range(t.h):
        for x in range(t.w):
            if t.amount(x, y, res) > 0 and t.cls[y * t.w + x] == 1:
                return (x, y)
    raise AssertionError("no %s" % res)


# ------------------------------------------------------------------ D22

def test_two_game_hours_of_coal_and_iron_mining_never_exhaust_the_sites():
    """ActMine runs about every 45-60 s in Widelands; 400 successful digs per mine is far more than two game hours of work."""
    w = HybridWorld(507, profile="campaign")
    for res in ("coal", "iron"):
        site = _mine_site(w, res)
        b = {"id": "test-mine-" + res, "tx": site[0], "ty": site[1], "kind": "mine", "faction_name": "Red"}
        layer = bytes(w.terrain.res_amt)  # nothing else runs here (no advance), so the whole layer must be unchanged
        dug = sum(1 for _ in range(600) if resources.production_mine(w, b, {"resource": res, "radius": 2, "yield": 33.33, "when_empty": 5}))
        assert dug >= 400, dug  # the Widelands weighting fails a roll now and then; it never stops for good
        assert bytes(w.terrain.res_amt) == layer and not b.get("deposit_exhausted")
        assert w.stats["mined_from_inexhaustible_deposit:" + res] == dug


def test_mindustry_drill_on_a_shared_iron_site_never_runs_dry_and_logs_its_source():
    w = HybridWorld(507, profile="campaign")
    site = _mine_site(w, "iron")
    tiles = [(site[0] + dx, site[1] + dy) for dx in (0, 1) for dy in (0, 1)]
    opts = X.options(w, tiles, 2)
    assert opts, "a tier-2 drill on an iron site can make copper or lead"
    item = X.choose_item(opts, None)
    o = opts[item]
    assert X.reserve_left(w, o) == -1  # unlimited
    layer = bytes(w.terrain.res_amt)
    assert all(X.take_reserve(w, o) for _ in range(5000))
    assert bytes(w.terrain.res_amt) == layer
    assert w.stats["mined_from_inexhaustible_deposit:iron"] == 5000


def test_fish_stays_finite():
    from wizard_rts.terrain import is_mineral

    assert not is_mineral("fish") and not is_mineral("water") and is_mineral("stones")


# ------------------------------------------------------------------ disruptions and catastrophes

def _developed(seconds=300, profile="test_showcase"):
    w = HybridWorld(507, profile=profile)
    w.ai_enabled = False
    w.dmb.hazards["catastrophe"]["cubes"][w.hazard_id]["active"] = False
    for i in range(seconds):
        w.advance(1000, i + 1, snapshot=False)
    return w


def test_a_collapsed_mine_stops_and_the_faction_digs_it_out_with_props():
    w = _developed(240)
    mine = next(b for b in w.buildings.values() if b["faction_name"] == "Blue" and b["kind"] == "mine")
    assert disruption.disrupt(w, mine, "collapse", by="test")
    from wizard_rts.economy import produce

    wh = con.faction_warehouse(w, "Blue")
    produce(w, wh["id"], "log", 6)
    w.stats["made_log"] = w.stats.get("made_log", 0) + 6
    n_events = len(w.events)
    seq = int(w.dmb.clock.get("clock_sequence", 0))  # the clock ignores an advance that is not the next in its own sequence
    for _ in range(60):
        seq += 1
        w.advance(1000, seq, snapshot=False)
    assert not [e for e in w.events[n_events:] if e.get("building") == mine["id"] and e["kind"] in ("produced", "mined")], "a closed mine makes nothing"
    assert "Closed: Gallery collapsed" in w.status_text(mine)
    for _ in range(15 * 60):
        seq += 1
        w.advance(1000, seq, snapshot=False)
        if not mine.get("disrupted"):
            break
    assert not mine.get("disrupted") and any(e["kind"] == "disruption_cleared" and e["how"] == "repaired" for e in w.events)


def test_an_outbreak_measurably_slows_the_economy_against_a_paired_world():
    def run(cubes):
        w = HybridWorld(11, profile="test_showcase")
        w.ai_enabled = False
        w.outbreaks_enabled = False
        w.dmb.hazards["catastrophe"]["cubes"][w.hazard_id]["active"] = False
        s = regions.state(w)
        wh = con.faction_warehouse(w, "Green")
        i = s.region_at(wh["tx"], wh["ty"])
        if cubes:
            s.cubes[i] = cubes
            s.kind[i] = "sickness"
        for k in range(20 * 60):
            w.advance(1000, k + 1, snapshot=False)
        made = sum(v for key, v in w.stats.items() if key.startswith("made_"))
        return made, w.stats.get("outbreak_losses", 0), disruption.summary(w)["count"], w
    clean, lost0, _c0, _w0 = run(0)
    sick, lost, closed, w = run(3)
    assert lost > 0 and sick < clean, (clean, sick, lost)
    rec = next(r for r in w.dmb.settlements.values() if r["faction"] == "Green")
    assert rec["unrest"] > 0.1


def test_outbreak_overflow_burns_a_workplace_and_spares_the_command_centre():
    w = _developed(60)
    s = regions.state(w)
    wh = con.faction_warehouse(w, "Red")
    i = s.region_at(wh["tx"], wh["ty"])
    s.cubes[i] = 3
    s.kind[i] = "sickness"
    regions._add_cube(w, s, i, 60_000, "test")
    ev = [e for e in w.events if e["kind"] == "catastrophe_destroyed"]
    assert len(ev) == 1 and ev[0]["building_kind"] != "warehouse" and int(wh["hp"]) > 0


# ------------------------------------------------------------------ unrest, splits

def test_hunger_raises_unrest_and_a_garrison_and_food_calm_it():
    w = _developed(30)
    rec = next(r for r in w.dmb.settlements.values() if r["faction"] == "Yellow")
    wh = w.buildings[rec["centre"]]
    for g in society.FOOD:
        w.stocks[wh["id"]][g] = 0
    p = society.pressures(w, rec)
    assert p.get("hunger") and "plenty" not in p
    w.stocks[wh["id"]]["ration"] = 12
    p2 = society.pressures(w, rec)
    assert "hunger" not in p2 and p2.get("plenty") and p2.get("garrison")  # the start soldier stands at home


def test_unrest_splits_a_distant_unlinked_settlement_into_a_successor():
    w = _developed(30, profile="developer")
    name = "Orange"
    home = con.faction_warehouse(w, name)
    t = w.terrain
    founded = []
    for y in range(8, t.h - 8, 4):
        for x in range(8, t.w - 8, 4):
            if len(founded) >= 2:
                break
            if territory.cheb((x, y), (home["tx"], home["ty"])) < 60 or territory.cheb((x, y), (home["tx"], home["ty"])) > 140:
                continue
            u = {"id": "u", "definition": territory.SETTLER_DEFINITION, "faction_name": name, "alive": True, "tx": x, "ty": y}
            if territory.deploy_check(w, u) is None:
                uid = w._unit(w.faction_info[name]["id"], name, "settlers", "Settlers", territory.SETTLER_DEFINITION, (x, y))
                territory._create_command_center(w, w.units[uid])
                founded.append((x, y))
    assert len(founded) == 2
    recs = settlements_of(w, name)
    for r in recs:
        if not r.get("home"):
            r["unrest"] = 0.9
    w.economy_quanta = 299
    w.advance(1000, int(w.dmb.clock.get("clock_sequence", 0)) + 1, snapshot=False)
    assert any(n.startswith(name + "-") for n in w.faction_info), list(w.faction_info)
    successor = next(n for n in w.faction_info if n.startswith(name + "-"))
    from wizard_rts import ai

    assert ai.policy_of(w, successor) == ai.policy_of(w, name)  # the successor keeps its parent's commander
    assert any(c["event"] == "split" for c in history.state(w)["chronicle"])
    # no cascade: the parent cannot split again for SPLIT_COOLDOWN_MS, the successor not for SUCCESSOR_GRACE_MS
    for r in settlements_of(w, name) + settlements_of(w, successor):
        r["unrest"] = 0.95
    assert history.split_candidates(w, name) is None and history.split_candidates(w, successor) is None


def settlements_of(w, name):
    return [r for r in w.dmb.settlements.values() if r["faction"] == name and r["state"] == "standing"]


# ------------------------------------------------------------------ cards and eras

def test_offers_hold_up_to_seven_eligible_cards_never_padded_and_lapse_when_unpicked():
    w = HybridWorld(507, profile="campaign")
    w.ai_enabled = False
    w.advance(1000, 1, snapshot=False)
    st = w.tech["Red"]
    assert 1 <= len(st["offers"]) <= tech.OFFER_SIZE
    assert set(st["offers"]) <= set(tech.draftable(w, "Red"))
    assert len(st["offers"]) == min(tech.OFFER_SIZE, len(tech.draftable(w, "Red")))
    for i in range(2, 200):
        w.advance(1000, i, snapshot=False)
    assert st["offers"] == [] and st["lapsed"] >= 1  # the three-minute window closed unpicked
    assert any(e["kind"] == "draft_lapsed" and e["faction"] == "Red" for e in w.events)
    cat = tech.catalogue()
    assert all(len(cat[e]) >= 5 for e in tech.ERAS) and sum(len(v) for v in cat.values()) >= 30


def test_deep_mines_need_the_deep_mining_card():
    w = HybridWorld(507, profile="campaign")
    w.tech["Red"]["cards"] = ["dmb.card.mining"]
    assert tech.kind_allowed(w, "Red", "wl:barbarians_coalmine")
    assert not tech.kind_allowed(w, "Red", "wl:barbarians_coalmine_deep")
    w.tech["Red"]["cards"].append("dmb.card.deep_mining")
    assert tech.kind_allowed(w, "Red", "wl:barbarians_coalmine_deeper")


def test_era_advances_on_world_vp_gain_and_reports_the_reason():
    w = HybridWorld(507, profile="campaign")
    assert vp.threshold(w) == vp.ERA_VP_THRESHOLDS[0]
    st = vp.era_state(w)
    for f in list(w.faction_info)[:6]:
        st["base"][f] = vp.totals(w)[f] - 1  # as if every faction had founded one settlement since the era began
    assert vp.progress(w) == 6
    w.economy_quanta = 9
    vp.vp_quantum(w)
    w.economy_quanta = 10
    vp.vp_quantum(w)
    snap = vp.snapshot(w)
    assert snap["era"] == "historic" and snap["last_reason"] == "vp_threshold" and snap["threshold"] == vp.ERA_VP_THRESHOLDS[1]


def test_settlers_found_a_settlement_from_the_warehouse():
    w = HybridWorld(507, profile="developer")
    w.ai_enabled = False
    tech.grant(w, "Purple", "dmb.card.settlers")
    wh = con.faction_warehouse(w, "Purple")
    from wizard_rts.economy import produce

    for g, n in con.RECIPES["warehouse"]["settlers"]["cost"].items():
        produce(w, wh["id"], g, n)
        w.stats["made_" + g] = w.stats.get("made_" + g, 0) + n
    from wizard_rts import ledger

    books = ledger.snapshot_totals(w)
    assert w.queue(wh["id"], "settlers")["status"] == "ok"
    for i in range(80):
        w.advance(1000, i + 1, snapshot=False)
        assert ledger.check(w, books) == [], i  # the cargo is held while the wagon is built and while it travels
    u = next(u for u in w.units.values() if u["faction_name"] == "Purple" and territory.is_founder(u))
    assert u["cargo"] == con.RECIPES["warehouse"]["settlers"]["cargo"]
    from wizard_rts import ai_plus

    site = ai_plus._expansion_site(w, "Purple", u, [], u["definition"])
    assert site is not None
    u["tx"], u["ty"] = site  # the walk itself is tested elsewhere (MCV); here only the founding rule
    before = len(territory.command_centers(w, "Purple"))
    assert territory.deploy(w, u["id"])["status"] == "ok"
    for i in range(80, 90):
        w.advance(1000, i + 1, snapshot=False)
    assert ledger.check(w, books) == []  # the cargo is now the new settlement's store
    assert len(territory.command_centers(w, "Purple")) == before + 1
    assert vp.faction_vp(w, "Purple") == before + 1


# ------------------------------------------------------------------ the wizard

def test_the_wizard_cannot_stand_on_a_tree_or_a_rock():
    w = HybridWorld(507, profile="campaign")
    tree = next(t for t in w.trees.values() if w.tree_solid(t))
    rock = next(iter(w.rocks.values()))
    assert w.set_pose(tree["tx"], tree["ty"], "down", snapshot=False)["reason"] == "obstacle"
    assert w.set_pose(rock["tx"], rock["ty"], "down", snapshot=False)["reason"] == "obstacle"
    sap = next((t for t in w.trees.values() if t["stage"] == "sapling" and (t["tx"], t["ty"]) not in w.blocked), None)
    if sap is not None:
        assert w.set_pose(sap["tx"], sap["ty"], "down", snapshot=False)["status"] == "ok"


def test_the_wizard_pilot_walks_tile_by_tile_and_treats_by_the_public_rule():
    from wizard_rts import wizard_pilot

    w = HybridWorld(507, profile="developer")
    w.ai_enabled = False
    w.outbreaks_enabled = False
    s = regions.state(w)
    rec = next(r for r in w.dmb.settlements.values() if r["faction"] == "Blue")
    i = s.region_at(rec["tile"][0], rec["tile"][1])
    s.cubes[i], s.kind[i] = 2, "sickness"
    p = wizard_pilot.WizardPilot(w)
    last = (w.player["tx"], w.player["ty"])
    for k in range(900):
        w.advance(1000, k + 1, snapshot=False)
        p.step()
        here = (w.player["tx"], w.player["ty"])
        assert abs(here[0] - last[0]) + abs(here[1] - last[1]) <= wizard_pilot.WALK_TILES_PER_S  # never a jump
        last = here
        if s.cubes[i] == 0:
            break
    assert s.cubes[i] == 0 and p.treatments == 2 and p.walked > 10

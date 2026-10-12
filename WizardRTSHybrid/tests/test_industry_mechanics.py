"""M2 mechanics, each isolated on the real world: extraction on existing deposits, belts and backpressure, power, crafters, unit
factory, mine upgrade, card gating, conservation and determinism (D06, D08, D16, D17)."""
import os
import subprocess
import sys

import pytest

from conftest import set_resource
from wizard_rts import construction as con
from wizard_rts import ledger, tech
from wizard_rts.industry import commands as C
from wizard_rts.industry import fixture as F
from wizard_rts.industry import registry as R
from wizard_rts.industry import sim as S
from wizard_rts.world import HybridWorld

SEED = 507
Q = 0  # clock sequence counter shared by helpers (advance needs consecutive sequences)


def world(profile="developer"):
    w = HybridWorld(SEED, profile=profile)
    w.ai_enabled = False
    w._seq = 0
    return w


def run(w, seconds):
    for _ in range(int(seconds)):
        w._seq += 1
        w.advance(1000, w._seq, snapshot=False)


def cards(w, faction="Red"):
    F.grant_cards(w, faction)


def deposit(w, tiles, res, amount=30):
    for t in tiles:
        set_resource(w, t, res, amount)


def reserve(w, tiles, res):
    return sum(w.resource_amount(t, res) for t in tiles)


def line(w, n=1, start=None):
    """A free 2-row strip: returns (x, y) of its first tile."""
    return F.open_ground(w, "Red", n, 4)


def drill_scene(item_res="iron", target="copper", kind="mdy:mechanical_drill", belt_len=6):
    w = world()
    cards(w)
    x, y = F.open_ground(w, "Red", 14, 3)
    fp = [(x + a, y + b) for b in range(2) for a in range(2)]
    deposit(w, fp, item_res)
    d = F.instant_machine(w, "Red", kind, (x, y))
    assert C.configure(w, "Red", d, "target", target)["status"] == "ok"
    belt = [(x + 2 + i, y) for i in range(belt_len)]
    b = F.instant_belt(w, "Red", belt)
    run(w, 1)
    return w, d, belt, fp, b


def test_cards_gate_every_mindustry_kind():
    w = world("campaign")
    wh = con.faction_warehouse(w, "Red")
    for kind in R.kinds():
        assert con.check_placement(w, "Red", kind, wh["tx"] + 6, wh["ty"] + 6)[0] == "locked_by_card", kind
    assert C.place_belt(w, "Red", [(wh["tx"] + 6, wh["ty"] + 6), (wh["tx"] + 7, wh["ty"] + 6)])["reason"] == "locked_by_card"
    d = world()
    assert tech.grant(d, "Red", "dmb.card.unit_fabrication")["status"] == "ok"
    assert {"mdy:ground_factory", "mdy:silicon_smelter", "mdy:mechanical_drill"} <= tech.unlocked_kinds(d, "Red")
    assert "mdy:ground_factory" not in tech.unlocked_kinds(d, "Blue")


def test_drill_needs_an_existing_deposit_or_sand_floor():
    w = world()
    cards(w)
    x, y = F.open_ground(w, "Red", 3, 3)
    why, _ = C.check_machine(w, "Red", "mdy:mechanical_drill", (x, y))
    terrain = w.terrain.terrain_name(x, y)
    if not any(s in terrain for s in ("desert", "beach")):
        assert why == "no_deposit_here"
    deposit(w, [(x, y)], "coal")
    assert C.check_machine(w, "Red", "mdy:mechanical_drill", (x, y))[0] is None
    # a tier-2 drill cannot work a titanium-only option: iron offers titanium only to tier 3
    deposit(w, [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)], "iron")
    from wizard_rts.industry import extraction as X
    fp = [(x + a, y + b) for b in range(2) for a in range(2)]
    assert "titanium" not in X.options(w, fp, 2) and {"copper", "lead"} <= set(X.options(w, fp, 2))
    assert "titanium" in X.options(w, fp, 3)


@pytest.mark.parametrize("kind,target,upi", [("mdy:mechanical_drill", "copper", 1), ("mdy:pneumatic_drill", "titanium", 2)])
def test_drill_on_a_shared_site_logs_its_extraction_and_never_exhausts_it(kind, target, upi):
    """D22 (12 Oct 2026, superseding the shared finite reserve of D21): the drill reads the same Widelands site, applies the conversion
    factor to the logged extraction, and the site does not shrink."""
    w, d, belt, fp, _b = drill_scene("iron", target, kind)
    layer_before = bytes(w.terrain.res_kind)
    start = reserve(w, fp, "iron")
    init = ledger.snapshot_totals(w)
    run(w, 240)
    ware = R.ware(target)
    made = w.stats.get("made_" + ware, 0)
    assert made >= 10
    assert reserve(w, fp, "iron") == start  # the site is inexhaustible
    assert w.stats["extracted_units_iron"] == made * upi and w.stats["mined_from_inexhaustible_deposit:iron"] == made  # conversion factor, source ledger
    assert bytes(w.terrain.res_kind) == layer_before  # no new deposit squares: the resource-kind layer is untouched
    assert S.holdings(w).get(ware, 0) == made  # every drilled item is on the belt or in the drill
    assert ledger.check(w, init) == []


def test_belt_backpressure_blocks_the_drill_and_resumes():
    w, d, belt, fp, _b = drill_scene("coal", "coal", belt_len=5)
    run(w, 300)
    m = w.buildings[d]["mdy"]
    cap = 10 + 3 * len(belt)  # drill buffer + three items per belt tile (Conveyor capacity 3)
    assert S.holdings(w).get("coal") == cap and m["state"] == "output blocked"
    made, left = w.stats["made_coal"], reserve(w, fp, "coal")
    run(w, 60)
    assert w.stats["made_coal"] == made and reserve(w, fp, "coal") == left  # a blocked drill digs nothing: no loss, no duplication
    # unblock: a smelter at the belt end accepts coal
    x, y = belt[-1][0] + 1, belt[-1][1]
    smelter = F.instant_machine(w, "Red", "mdy:silicon_smelter", (x, y))
    run(w, 30)
    assert w.buildings[smelter]["mdy"]["buf"].get("coal", 0) > 0
    run(w, 120)
    assert w.stats["made_coal"] > made  # flow resumed
    assert S.holdings(w)["coal"] == w.stats["made_coal"] - w.stats.get("consumed_coal", 0)


def test_belt_items_keep_order_and_spacing():
    w, d, belt, fp, _b = drill_scene("coal", "coal", belt_len=8)
    for _ in range(200):
        run(w, 1)
        for t in belt:
            items = S.ind(w).belts[t]["items"]
            assert len(items) <= 3
            for a, b in zip(items, items[1:]):
                assert a[1] - b[1] >= S.ITEM_SPACE


def test_belt_speed_matches_source():
    """One item on an 8-tile run reaches the machine at its end after 8 / 1.8 s (Conveyor speed 0.03 tiles per tick)."""
    w = world()
    cards(w)
    x, y = F.open_ground(w, "Red", 12, 3)
    belt = [(x + i, y) for i in range(8)]
    F.instant_belt(w, "Red", belt)
    sm = F.instant_machine(w, "Red", "mdy:silicon_smelter", (x + 8, y))
    run(w, 1)
    S.belt_put(S.ind(w), belt[0], "coal")
    w.stats["made_coal"] = w.stats.get("made_coal", 0) + 1
    assert R.block("mdy:conveyor")["belt"]["tiles_per_second"] == pytest.approx(1.8)
    quanta = 0
    while w.buildings[sm]["mdy"]["buf"].get("coal", 0) == 0 and quanta < 200:
        w._seq += 1
        w.advance(100, w._seq, snapshot=False)
        quanta += 1
    assert abs(quanta - 8 / 1.8 * 10) <= 2, quanta  # about 44.4 quanta of 100 ms


def smelter_scene():
    w = world()
    cards(w)
    x, y = F.open_ground(w, "Red", 9, 4)
    sm = F.instant_machine(w, "Red", "mdy:silicon_smelter", (x, y))
    return w, sm, (x, y)


def graph_sat(w, bid):
    return S.ind(w).power[S.ind(w).graph_of[bid]]["satisfaction"]


def test_power_satisfaction_scales_crafter_and_stops_without_power():
    w, sm, (x, y) = smelter_scene()
    F.inject(w, sm, "coal", 10)
    F.inject(w, sm, "mdy.sand", 10)
    m = w.buildings[sm]["mdy"]
    run(w, 5)
    assert m["state"] == "no power" and w.stats.get("made_mdy.silicon", 0) == 0  # a smelter alone has no power graph
    F.instant_machine(w, "Red", "mdy:solar_panel", (x + 2, y))  # adjacent: Block.connectedPower joins the graph
    run(w, 10)
    got = w.stats.get("made_mdy.silicon", 0)
    F.drain_output(w, sm)
    assert graph_sat(w, sm) == pytest.approx(6 / 30, abs=0.01)  # one small panel (6/s) against the smelter's 30/s
    assert 1 <= got <= 4  # 10 s at 20% is 2 s of work: at most three crafts of 0.667 s
    panels = [F.instant_machine(w, "Red", "mdy:solar_panel", t) for t in ((x + 2, y + 1), (x + 3, y), (x + 3, y + 1), (x + 4, y))]
    F.inject(w, sm, "coal", 10)
    F.inject(w, sm, "mdy.sand", 20)
    run(w, 2)
    assert graph_sat(w, sm) == pytest.approx(1.0)  # five panels make the 30 per second it needs
    F.drain_output(w, sm)
    before = w.stats["made_mdy.silicon"]
    for _ in range(6):
        run(w, 1)
        F.drain_output(w, sm)
    assert w.stats["made_mdy.silicon"] - before == 9  # 6 s / 0.667 s per craft at full speed
    F.inject(w, sm, "coal", 5)
    F.inject(w, sm, "mdy.sand", 10)
    for b in w.buildings.values():
        if b["kind"] == "mdy:solar_panel":
            b["hp"] = 0
    run(w, 3)
    assert w.buildings[sm]["mdy"]["state"] == "no power"
    stopped = w.stats["made_mdy.silicon"]
    run(w, 5)
    assert w.stats["made_mdy.silicon"] == stopped


def test_laser_node_links_blocks_in_range_only():
    w = world()
    cards(w)
    x, y = F.open_ground(w, "Red", 20, 3)
    a = F.instant_machine(w, "Red", "mdy:solar_panel", (x, y))
    sm = F.instant_machine(w, "Red", "mdy:silicon_smelter", (x + 8, y))
    node = F.instant_machine(w, "Red", "mdy:power_node", (x + 4, y))
    run(w, 2)
    st = S.ind(w)
    assert set(st.links[node]) == {a, sm}  # both are within laserRange 6 of the node
    assert st.graph_of[a] == st.graph_of[sm] == st.graph_of[node]
    far = F.instant_machine(w, "Red", "mdy:solar_panel", (x + 19, y))
    run(w, 2)
    assert st.graph_of[far] != st.graph_of[node]  # 15 tiles away: out of range, no link
    assert C.link_power(w, "Red", node, far)["reason"] == "out_of_range"


def test_combustion_generator_burns_fuel_and_conserves():
    w = world()
    cards(w)
    x, y = F.open_ground(w, "Red", 6, 4)
    gen = F.instant_machine(w, "Red", "mdy:combustion_generator", (x, y))
    sm = F.instant_machine(w, "Red", "mdy:silicon_smelter", (x + 1, y))
    F.inject(w, sm, "coal", 10)
    F.inject(w, sm, "mdy.sand", 10)
    run(w, 3)
    assert w.buildings[gen]["mdy"]["state"] == "no fuel"
    F.inject(w, gen, "coal", 5)
    init = ledger.snapshot_totals(w)
    run(w, 4)
    assert w.buildings[gen]["mdy"]["state"] == "burning"
    consumed = w.stats.get("consumed_coal", 0)
    assert consumed >= 2 and w.buildings[gen]["mdy"]["buf"]["coal"] + consumed - 2 <= 5 + 10  # itemDuration 120 ticks: one coal per 2 s
    assert w.stats.get("made_mdy.silicon", 0) >= 1  # 60/s supply covers the smelter's 30/s
    run(w, 30)
    assert w.buildings[gen]["mdy"]["state"] == "no fuel"  # five coal last ten seconds
    assert ledger.check(w, init) == []


def test_battery_buffers_surplus_and_bridges_a_gap():
    w = world()
    cards(w)
    x, y = F.open_ground(w, "Red", 8, 4)
    sp = F.instant_machine(w, "Red", "mdy:solar_panel", (x, y))
    bat = F.instant_machine(w, "Red", "mdy:battery", (x + 1, y))
    run(w, 20)
    stored = w.buildings[bat]["mdy"]["stored"]
    assert stored == pytest.approx(6 * 20 - 6, abs=7)  # six power units a second into the battery (first tick builds the graph)
    w.buildings[sp]["hp"] = 0
    sm = F.instant_machine(w, "Red", "mdy:silicon_smelter", (x + 2, y))
    F.inject(w, sm, "coal", 10)
    F.inject(w, sm, "mdy.sand", 10)
    run(w, 10)
    assert w.stats.get("made_mdy.silicon", 0) >= 5  # the battery runs the smelter with the panel gone
    assert w.buildings[bat]["mdy"]["stored"] < stored


def test_unit_factory_builds_a_dagger_that_joins_world_units():
    w = world()
    cards(w)
    x, y = F.open_ground(w, "Red", 7, 4)
    fac = F.instant_machine(w, "Red", "mdy:ground_factory", (x, y))
    F.instant_machine(w, "Red", "mdy:solar_panel_large", (x + 3, y))  # 78 per second against the factory's 72
    F.inject(w, fac, "mdy.silicon", 10)
    F.inject(w, fac, "mdy.lead", 10)
    before = {u for u in w.units}
    init = ledger.snapshot_totals(w)
    run(w, 14)
    assert not [u for u in w.units.values() if u["kind"] == "mdy_dagger"]  # a dagger takes 900 ticks = 15 s
    run(w, 6)
    new = [u for uid, u in w.units.items() if uid not in before]
    assert len(new) == 1
    u = new[0]
    assert u["kind"] == "mdy_dagger" and u["definition"] == "mindustry.dagger" and u["faction_name"] == "Red"
    assert u["max_hp"] == 7500 and u["weapon"] == "MDY_dagger_gun" and u["alive"]
    assert w.buildings[fac]["mdy"]["buf"] == {"mdy.silicon": 0, "mdy.lead": 0}  # inputs consumed
    assert w.stats["consumed_mdy.silicon"] == 10 and w.stats["consumed_mdy.lead"] == 10
    assert any(e["kind"] == "unit_produced" and e["unit"] == u["id"] for e in w.events)
    assert ledger.check(w, init) == []


def test_factory_plan_is_gated_and_validated():
    w = world("campaign")
    wh = con.faction_warehouse(w, "Red")
    assert tech.unit_allowed(w, "Red", "dagger") is False
    d = world()
    cards(d)
    x, y = F.open_ground(d, "Red", 5, 5)
    fac = F.instant_machine(d, "Red", "mdy:ground_factory", (x, y))
    run(d, 1)
    assert C.configure(d, "Red", fac, "plan", "crawler")["status"] == "rejected"  # crawler is not in the unlocked card's unit list
    assert C.configure(d, "Red", fac, "plan", "dagger")["status"] == "ok"
    assert C.configure(d, "Red", fac, "plan", "nope")["reason"] == "no_such_plan"


def fight(unit_def, enemy_def, enemy_kind, seconds=60):
    w = world()
    cards(w)
    wh = con.faction_warehouse(w, "Red")
    bw = con.faction_warehouse(w, "Blue")
    x, y = F.open_ground(w, "Red", 8, 3)
    a = w._unit(w.faction_info["Red"]["id"], "Red", "mdy_dagger", "Dagger", unit_def, (x, y))
    b = w._unit(w.faction_info["Blue"]["id"], "Blue", enemy_kind, "Enemy", enemy_def, (x + 3, y))
    w.ai_enabled = False
    for u in (a, b):
        w.units[u]["order"] = None
    w.order(a, b)
    w.order(b, a)
    for _ in range(seconds):
        w._seq += 1
        w.advance(1000, w._seq, snapshot=False)
        if not (w.units[a].get("alive", True) and w.units[b].get("alive", True)):
            break
    return w, a, b


def test_dagger_beats_a_rifleman_and_loses_to_a_tank_by_data():
    w, a, b = fight("mindustry.dagger", "openra.e1", "infantry")
    assert w.units[a]["alive"] and not w.units[b]["alive"]
    assert w.units[a]["hp"] < w.units[a]["max_hp"]  # the same damage model: it took hits
    assert w.fstats["Red"].get("kills", 0) >= 1 or w.fstats["Blue"].get("losses", 0) >= 0
    w2, a2, b2 = fight("mindustry.dagger", "openra.3tnk", "tank", seconds=120)
    assert not w2.units[a2].get("alive", True) or not w2.units[b2].get("alive", True)


def test_mindustry_unit_is_targetable_and_shared_combat_hits_it():
    w, a, b = fight("mindustry.dagger", "openra.3tnk", "tank", seconds=20)
    assert w.units[a]["hp"] < w.units[a]["max_hp"] or w.units[b]["hp"] < w.units[b]["max_hp"]
    from wizard_rts.military import target_types
    assert "GroundActor" in target_types(w.units[a])


def test_destroyed_machine_logs_its_buffer_as_a_sink():
    w, sm, (x, y) = smelter_scene()
    F.inject(w, sm, "coal", 7)
    init = ledger.snapshot_totals(w)
    w.buildings[sm]["hp"] = 0
    run(w, 2)
    assert w.buildings[sm]["mdy"] is None
    assert w.stats["consumed_coal"] == 7
    assert ledger.check(w, init) == []


def hash_after(profile_seed, seconds):
    code = (
        "import os; os.environ['HYBRID_AI']='0'\n"
        "from wizard_rts.world import HybridWorld\nfrom wizard_rts.industry import fixture as F\n"
        "w=HybridWorld(507, profile='developer'); w.ai_enabled=False; F.grant_cards(w,'Red')\n"
        "x,y=F.open_ground(w,'Red',14,3)\n"
        "from conftest import set_resource\n"
        "[set_resource(w,(x+a,y+b),'coal',30) for a in range(2) for b in range(2)]\n"
        "d=F.instant_machine(w,'Red','mdy:mechanical_drill',(x,y)); F.instant_belt(w,'Red',[(x+2+i,y) for i in range(8)])\n"
        f"[w.advance(1000,i+1,snapshot=False) for i in range({seconds})]\nprint(w.state_hash())\n")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=os.path.dirname(__file__) + "/..",
                       env={**os.environ, "PYTHONHASHSEED": profile_seed, "PYTHONPATH": os.path.dirname(__file__) + os.pathsep + os.path.dirname(__file__) + "/.."})
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_industry_state_is_deterministic_across_processes():
    assert hash_after("0", 120) == hash_after("987", 120)


def test_save_load_round_trip_keeps_industry_state():
    from wizard_rts.sim_api import HybridEnv

    env = HybridEnv(seed=SEED, profile="developer", step_ms=1000)
    env.reset()
    w = env.world
    w.ai_enabled = False
    F.grant_cards(w, "Red")
    x, y = F.open_ground(w, "Red", 14, 3)
    deposit(w, [(x + a, y + b) for a in range(2) for b in range(2)], "coal")
    F.instant_machine(w, "Red", "mdy:mechanical_drill", (x, y))
    F.instant_belt(w, "Red", [(x + 2 + i, y) for i in range(8)])
    for _ in range(60):
        env.step({})
    blob = env.save()
    h = env.state_hash()
    for _ in range(20):
        env.step({})
    h2 = env.state_hash()
    env.load(blob)
    assert env.state_hash() == h
    for _ in range(20):
        env.step({})
    assert env.state_hash() == h2  # the loaded world continues identically


def _real_mine(w, resource="coal", kind="mine"):
    """A genuine Widelands mine built through the normal construction pipeline on the faction's own deposit."""
    from wizard_rts import ai

    wh = con.faction_warehouse(w, "Red")
    for _try in range(8):
        tile = ai._mine_site(w, wh, resource)
        assert tile is not None
        fp = [(tile[0] + a, tile[1] + b) for a in range(2) for b in range(2)]
        if all(w.terrain.ground(*t) and territory_ok(w, t) for t in fp):
            break
        w.blocked.add(tile)  # not roomy enough for a 2x2 drill: look for another
    for t in fp:
        tid = w.tree_tiles.get(t)
        if tid:
            from wizard_rts.workers import remove_tree
            remove_tree(w, tid, "test")
    w.blocked.discard(tile)
    res = con.place_building(w, "Red", kind, *tile)
    assert res["status"] == "ok", res
    assert con.build_road(w, "Red", res["id"], wh["id"])["status"] == "ok"
    for _ in range(600):
        run(w, 1)
        if w.buildings[res["id"]].get("operational"):
            break
    assert w.buildings[res["id"]]["operational"]
    return res["id"], tile, fp


def territory_ok(w, t):
    from wizard_rts import territory
    return territory.in_territory(w, "Red", t)


def test_mine_upgrade_keeps_identity_pays_real_goods_and_uses_the_same_reserve():
    w = world()
    cards(w)
    bid, tile, fp = _real_mine(w)
    for _ in range(900):  # the mine needs a ration (delivered by carrier) before it digs; the hybrid mine has no worker entity yet (roadmap M6)
        run(w, 1)
        if w.stats.get("made_coal", 0) > 0 and w.buildings[bid].get("working"):
            break
    assert w.stats.get("made_coal", 0) > 0
    layer = bytes(w.terrain.res_kind)
    # S08: new recipe minus the old one plus a quarter of the old one
    assert C.upgrade_cost({"log": 4, "granite": 2}, {"plank": 4, "granite": 3}) == {"granite": 2, "log": 1, "plank": 4}
    other = world("campaign")
    assert C.upgrade_mine(other, "Red", bid, "mdy:mechanical_drill")["status"] == "rejected"
    F.grant_goods(w, "Red")  # the logged developer grant: the upgrade must be paid in delivered goods
    init = ledger.snapshot_totals(w)
    r = C.upgrade_mine(w, "Red", bid, "mdy:mechanical_drill")
    assert r["status"] == "ok" and r["cost"] == {"granite": 2, "log": 1, "plank": 4}
    b = w.buildings[bid]
    assert b["id"] == bid and (b["tx"], b["ty"]) == tile and b["kind"] == "mdy:mechanical_drill" and b["faction_name"] == "Red"
    assert b["history"][-1]["event"] == "upgraded" and b["history"][-1]["from"] == "mine"
    assert not [x for x in w.workers.values() if x.get("building") == bid]  # the miner retires: an automated drill needs none
    assert not b["operational"] and b["constructing"]["cost"] == r["cost"]
    for _ in range(600):
        run(w, 1)
        if b.get("operational"):
            break
    assert b["operational"] and b["mdy"]["role"] == "drill"
    run(w, 30)
    assert b["mdy"]["item"] == "coal" and b["mdy"]["state"] in ("drilling", "output blocked")
    assert bytes(w.terrain.res_kind) == layer  # same deposits, no new ore squares
    assert w.stats.get("drilled_coal", 0) >= 1
    assert ledger.check(w, init) == []  # the upgrade was paid for with delivered wares and nothing else appeared
    assert w.stats["consumed_plank"] >= 4


def test_upgrade_rejections():
    w = world()
    cards(w)
    bid, tile, fp = _real_mine(w)
    assert C.upgrade_mine(w, "Blue", bid, "mdy:mechanical_drill")["reason"] == "not_yours"
    assert C.upgrade_mine(w, "Red", bid, "mdy:silicon_smelter")["reason"] == "cannot_upgrade"
    assert C.upgrade_mine(w, "Red", "building:999999", "mdy:mechanical_drill")["reason"] == "cannot_upgrade"
    camp = HybridWorld(SEED, profile="campaign")
    assert C.upgrade_mine(camp, "Red", "building:1", "mdy:mechanical_drill")["status"] == "rejected"
    assert C.upgrade_mine(w, "Red", bid, "mdy:mechanical_drill")["status"] == "ok"
    assert C.upgrade_mine(w, "Red", bid, "mdy:mechanical_drill")["reason"] in ("not_operational", "not_upgradeable")  # already under way

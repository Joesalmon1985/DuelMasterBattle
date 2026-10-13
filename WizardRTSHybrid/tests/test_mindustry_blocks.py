"""Data-driven checks over every simulated Mindustry block of a role (owner programme 13 Oct 2026): each block is built into a small scene with
the inputs it consumes and must do what its role says. Generated from the registry, so a new block is covered the moment it is added."""
from __future__ import annotations

import pytest

from test_mindustry_engine import C, F, FL, R, S, belt, held_liquid, ledger, put, run, stock, world
from wizard_rts.industry import blocks as B
from wizard_rts.industry import engine as E


def kinds_of(*roles):
    return [k for k in R.kinds() if R.block(k)["role"] in roles and not R.block(k)["sandbox"]]


def stuff(w, bid, spec):
    """Hand the machine what it consumes, as a belt or conduit would have (booked as made so the ledger stays whole)."""
    m = w.buildings[bid]["mdy"]
    for ware, n in spec["consume_items"].items():
        m["buf"][ware] = m["buf"].get(ware, 0) + n * 6
        w.stats["made_" + ware] = w.stats.get("made_" + ware, 0) + n * 6
    for liquid, per in list(spec["consume_liquids"].items()) + list(spec["boost_liquids"].items()):
        qty = max(per * 60 * 400, 5.0)  # 400 s of consumption
        m["liq"][liquid] = m["liq"].get(liquid, 0.0) + qty
        w.stats["liq_made_" + liquid] = w.stats.get("liq_made_" + liquid, 0.0) + qty


def powered_scene(kind, extra=2):
    w = world()
    n = R.block(kind)["size"]
    x, y = F.open_ground(w, "Red", n + 4, n + 2)
    bid = put(w, kind, (x + 1, y + 1))
    ps = put(w, "mdy:power_source", (x + 1 + n, y + 1))
    w.buildings[bid]["mdy"]["tmp"] = 0
    return w, bid, (x, y)


CRAFTERS = [k for k in kinds_of("crafter") if not R.block(k)["attribute"] and R.block(k)["heat_in"] <= 0 and R.block(k)["class"] not in ("Separator",)]


@pytest.mark.parametrize("kind", CRAFTERS)
def test_crafter_turns_its_inputs_into_its_outputs(kind):
    spec = R.block(kind)
    w, bid, _ = powered_scene(kind)
    stuff(w, bid, spec)
    snap = ledger.snapshot_totals(w)
    run(w, 40 if spec["craft_ticks"] < 300 else 120)
    m = w.buildings[bid]["mdy"]
    made = sum(m["out"].values()) + sum(w.stats.get("made_" + o, 0) for o in spec["output_item"])
    out_liq = sum(m["liq"].get(l, 0.0) for l in spec["output_liquid"])
    produced = m.get("count", 0) > 0 or out_liq > 0 or w.stats.get("liq_made_" + next(iter(spec["output_liquid"]), "-"), 0) > 0
    assert produced, (kind, m["state"], m["buf"], m["liq"])
    assert FL.liquid_books(w) == []
    assert not [r for r in ledger.check(w, snap) if r[0].startswith("mdy.") or r[0] == "coal"], ledger.check(w, snap)


# ---- attribute and heat crafters, separators

ATTR = [k for k in kinds_of("crafter") if R.block(k)["attribute"] or R.block(k)["heat_in"] > 0 or R.block(k)["class"] == "Separator"]


@pytest.mark.parametrize("kind", ATTR)
def test_attribute_heat_and_separator_crafters_work_with_their_environment(kind, monkeypatch):
    spec = R.block(kind)
    monkeypatch.setattr(E, "attribute_sum", lambda world, b, attribute: 9.0)  # a site with plenty of spores / steam / heat under it
    w, bid, (x, y) = powered_scene(kind)
    n = spec["size"]
    if spec["heat_in"] > 0:
        put(w, "mdy:heat_source", (x + 1, y + 1 + n))  # a heat producer touching the machine
    stuff(w, bid, spec)
    snap = ledger.snapshot_totals(w)
    run(w, 60 if spec["craft_ticks"] < 300 else 200)
    m = w.buildings[bid]["mdy"]
    out_liq = sum(m["liq"].get(l, 0.0) for l in spec["output_liquid"])
    assert m.get("count", 0) > 0 or out_liq > 0 or w.stats.get("liq_made_" + next(iter(spec["output_liquid"]), "-"), 0) > 0, (kind, m["state"], m["buf"], m["liq"], m.get("heat"))
    if spec["results"]:
        assert set(m["out"]) <= set(spec["results"])
    assert FL.liquid_books(w) == []


def test_separator_draws_only_its_listed_results_and_deterministically():
    w, bid, _ = powered_scene("mdy:separator")
    spec = R.block("mdy:separator")
    stuff(w, bid, spec)
    run(w, 60)
    out1 = dict(w.buildings[bid]["mdy"]["out"])
    assert out1 and set(out1) <= set(spec["results"])
    w2, bid2, _ = powered_scene("mdy:separator")
    stuff(w2, bid2, spec)
    run(w2, 60)
    assert w2.buildings[bid2]["mdy"]["out"] == out1


# ---- pumps

PUMPS = kinds_of("pump")


@pytest.mark.parametrize("kind", PUMPS)
def test_every_pump_makes_its_liquid(kind):
    spec = R.block(kind)
    w = world()
    n = spec["size"]
    from test_mindustry_engine import shore
    liquid = "oil" if spec["class"] == "Fracker" else "water"
    if spec["class"] == "Pump":
        water, anchor, tiles, end_dir = shore(w)
        pb = put(w, kind, water)
        put(w, "mdy:liquid_container", anchor)
        belt(w, tiles, end_dir, kind="mdy:conduit")
        if spec["power_use_per_s"] > 0:
            ring = S.adjacent_tiles(S.footprint(w.buildings[pb]))
            land = next(t for t in ring if w.terrain.ground(*t) and t not in tiles and t not in w.blocked)
            put(w, "mdy:power_source", land, force=True)
        if spec["consume_liquids"]:
            stuff(w, pb, spec)
    else:
        x, y = F.open_ground(w, "Red", n + 5, n + 2)
        pb = put(w, kind, (x + 1, y + 1))
        put(w, "mdy:power_source", (x + 1 + n, y + 1))
        stuff(w, pb, spec)
    run(w, 40)
    assert w.stats.get("liq_made_" + liquid, 0.0) > 0.5, (kind, w.buildings[pb]["mdy"]["state"])
    assert FL.liquid_books(w) == []


# ---- generators, batteries

GENERATORS = [k for k in kinds_of("generator")]


@pytest.mark.parametrize("kind", GENERATORS)
def test_every_generator_charges_a_battery_from_its_fuel(kind, monkeypatch):
    spec = R.block(kind)
    monkeypatch.setattr(E, "attribute_sum", lambda world, b, attribute: 4.0)
    w = world()
    n = spec["size"]
    x, y = F.open_ground(w, "Red", n + 6, n + 3)
    g = put(w, kind, (x + 1, y + 1))
    batt = put(w, "mdy:battery_large", (x + 1 + n, y + 1)) if True else None
    if spec["power_use_per_s"] > 0:  # reactors that need a priming supply
        put(w, "mdy:power_source", (x + 1, y + 1 + n))
    stuff(w, g, spec)
    if not spec["consume_items"] and (spec["flammable"] or spec.get("optional_consumers")):
        fuel = "mdy.spore_pod" if spec["flammable"] else "mdy.thorium"
        m = w.buildings[g]["mdy"]
        m["buf"][fuel] = 8
        w.stats["made_" + fuel] = w.stats.get("made_" + fuel, 0) + 8
    run(w, 20)
    st = S.ind(w)
    gi = st.graph_of.get(g)
    produced = st.power.get(gi, {}).get("supply", 0) > 0 or w.buildings[batt]["mdy"]["stored"] > 0
    assert produced, (kind, w.buildings[g]["mdy"]["state"], w.buildings[g]["mdy"]["buf"], w.buildings[g]["mdy"]["liq"])
    assert FL.liquid_books(w) == []


def test_a_generator_without_fuel_makes_nothing_and_a_consumer_without_power_stops():
    w = world()
    x, y = F.open_ground(w, "Red", 8, 4)
    g = put(w, "mdy:combustion_generator", (x, y + 1))
    sm = put(w, "mdy:silicon_smelter", (x + 1, y + 1))
    stuff(w, sm, R.block("mdy:silicon_smelter"))
    run(w, 20)
    assert w.buildings[g]["mdy"]["state"] != "burning" and w.buildings[sm]["mdy"]["state"] == "no power" and w.buildings[sm]["mdy"].get("count", 0) == 0


def test_a_diode_moves_charge_from_the_fuller_battery_to_the_emptier_one():
    w = world()
    x, y = F.open_ground(w, "Red", 8, 4)
    a = put(w, "mdy:battery", (x, y + 1))
    d = put(w, "mdy:diode", (x + 1, y + 1))
    c = put(w, "mdy:battery", (x + 2, y + 1))
    w.buildings[a]["mdy"]["stored"] = R.block("mdy:battery")["power_buffer"]
    run(w, 20)
    assert w.buildings[c]["mdy"]["stored"] > 0 and w.buildings[a]["mdy"]["stored"] < R.block("mdy:battery")["power_buffer"]


# ---- drills

DRILLS = kinds_of("drill")


@pytest.mark.parametrize("kind", DRILLS)
def test_every_drill_mines_the_best_ore_its_tier_allows(kind):
    from conftest import set_resource
    spec = R.block(kind)
    tier = int(spec["tier"])
    res, expect = ("iron", "copper") if tier < 3 else (("iron", "titanium") if tier < 4 else (("gold", "thorium") if tier < 5 else ("gold", "tungsten")))
    w = world()
    n = spec["size"]
    x, y = F.open_ground(w, "Red", n + 5, n + 2)
    for dx in range(n):
        for dy in range(n):
            set_resource(w, (x + 1 + dx, y + 1 + dy), res, 20)
    d = put(w, kind, (x + 1, y + 1))
    assert C.configure(w, "Red", d, "target", expect)["status"] == "ok", (kind, S.drill_options(w, w.buildings[d]))
    if spec["power_use_per_s"] > 0:
        put(w, "mdy:power_source", (x + 1 + n, y + 1))
    snap = ledger.snapshot_totals(w)
    run(w, 90)
    ware = R.ware(expect)
    m = w.buildings[d]["mdy"]
    assert m["out"].get(ware, 0) + w.stats.get("made_" + ware, 0) >= 1, (kind, m["state"])
    assert not [r for r in ledger.check(w, snap) if r[0] == ware]


def test_water_boosts_a_drill_by_the_liquid_boost_squared():
    from conftest import set_resource
    out = []
    for water in (False, True):
        w = world()
        x, y = F.open_ground(w, "Red", 8, 4)
        for dx in range(2):
            for dy in range(2):
                set_resource(w, (x + 1 + dx, y + 1 + dy), "iron", 20)
        d = put(w, "mdy:pneumatic_drill", (x + 1, y + 1))
        C.configure(w, "Red", d, "target", "copper")
        if water:
            m = w.buildings[d]["mdy"]
            m["liq"]["water"] = 500.0
            w.stats["liq_made_water"] = 500.0
        run(w, 7)
        out.append(w.stats.get("made_mdy.copper", 0))
    assert out[1] >= out[0] * 2 and out[0] >= 1, out


def test_wall_drill_takes_sand_from_the_mountain():
    from wizard_rts import terrain as T
    w = world()
    spec = R.block("mdy:cliff_crusher")
    x, y = F.open_ground(w, "Red", 8, 4)
    for dy in range(2):
        i = (y + 1 + dy) * w.terrain.w + (x + 3)
        w.terrain.cls[i] = T.MINEABLE
    d = put(w, "mdy:cliff_crusher", (x + 1, y + 1))
    put(w, "mdy:power_source", (x + 1, y + 3), force=True)
    run(w, 40)
    assert w.buildings[d]["mdy"]["out"].get("mdy.sand", 0) >= 1


# ---- unit chains

def line_scene(factory, recon_kinds, plan):
    """factory -> reconstructor -> reconstructor ... facing east, each powered by one source, fed by hand-stuffed items."""
    w = world()
    sizes = [R.block(factory)["size"]] + [R.block(k)["size"] for k in recon_kinds]
    x, y = F.open_ground(w, "Red", sum(sizes) + 6, max(sizes) + 3)
    cx = x + 1
    ids = []
    for kind in [factory] + recon_kinds:
        bid = put(w, kind, (cx, y + 1))
        w.buildings[bid]["mdy"]["rot"] = 0
        put(w, "mdy:power_source", (cx, y + 1 + R.block(kind)["size"]))
        stuff(w, bid, R.block(kind))
        if R.block(kind)["role"] == "unit_factory":
            for ware, n in S._plan(R.block(kind), w.buildings[bid]["mdy"] | {"plan": plan})["requirements"].items():
                w.buildings[bid]["mdy"]["buf"][ware] = n * 3
                w.stats["made_" + ware] = w.stats.get("made_" + ware, 0) + n * 3
        ids.append(bid)
        cx += R.block(kind)["size"]
    fm = w.buildings[ids[0]]["mdy"]
    fm["plan"] = plan
    return w, ids


def test_a_unit_walks_through_factory_and_reconstructors_and_comes_out_upgraded():
    w, ids = line_scene("mdy:ground_factory", ["mdy:additive_reconstructor"], "dagger")
    run(w, 90)
    units = [u for u in w.units.values() if u.get("mdy_unit")]
    assert units and {u["mdy_unit"] for u in units} == {"mace"}, [(u["mdy_unit"], u["tx"], u["ty"]) for u in units]
    assert w.stats.get("consumed_mdy.silicon", 0) >= 18 + 40  # the dagger's silicon and the upgrade's silicon were really consumed
    assert units[0]["definition"] == "mindustry.mace" and units[0]["hp"] == units[0]["max_hp"] > 0


def test_a_second_tier_unit_needs_its_card():
    w, ids = line_scene("mdy:ground_factory", ["mdy:additive_reconstructor"], "dagger")
    w.tech["Red"]["cards"] = [c for c in w.tech["Red"]["cards"] if "mace" not in c]
    from wizard_rts.content import graph
    mace_cards = [cid for cid, c in graph.generated_cards().items() if "unit:mace" in c["entities"]]
    w.tech["Red"]["cards"] = [c for c in w.tech["Red"]["cards"] if c not in mace_cards]
    run(w, 90)
    assert {u["mdy_unit"] for u in w.units.values() if u.get("mdy_unit")} == {"dagger"}  # it stays a dagger: the reconstructor refuses a payload it may not upgrade


FACTORY_PLANS = [(k, p["unit"]) for k in kinds_of("unit_factory") if R.block(k).get("game") != "hybrid" for p in (R.block(k)["plans"] or [])]
UPGRADES = [(k, pair[0], pair[1]) for k in kinds_of("reconstructor") for pair in (R.block(k)["upgrades"] or []) if len(pair) > 1]


def _units_of(w, name):
    return [u for u in w.units.values() if u.get("mdy_unit") == name and u.get("alive", True)]


def _place_for(w, kind, unit_loco):
    """A machine that makes units of this movement class: naval units need water in front, so those scenes sit on the shore."""
    spec = R.block(kind)
    n = spec["size"]
    x, y = F.open_ground(w, "Red", n + 6, n + 3)
    return x, y


@pytest.mark.parametrize("factory,unit", FACTORY_PLANS)
def test_every_factory_plan_produces_its_unit(factory, unit):
    from wizard_rts.industry import units as U
    info = U.rules_for(unit)
    if info[0]["locomotor"] == "naval":
        pytest.skip("naval units leave a factory into water: covered by test_naval_unit_leaves_a_shore_factory")
    w = world()
    spec = R.block(factory)
    n = spec["size"]
    x, y = F.open_ground(w, "Red", n + 6, n + 3)
    f = put(w, factory, (x + 1, y + 1))
    w.buildings[f]["mdy"]["rot"] = 0
    put(w, "mdy:power_source", (x + 1, y + 1 + n))
    plan = next(p for p in S._plan_list(spec) if p["unit"] == unit) if hasattr(S, "_plan_list") else next(p for p in spec["plans"] if p["unit"] == unit)
    m = w.buildings[f]["mdy"]
    m["plan"] = unit
    for ware, k in plan["requirements"].items():
        m["buf"][ware] = k * 2
        w.stats["made_" + ware] = w.stats.get("made_" + ware, 0) + k * 2
    snap = ledger.snapshot_totals(w)
    run(w, int(plan["ticks"] / 60) + 15)
    assert _units_of(w, unit), (factory, unit, m["state"], m["buf"])
    for ware, k in plan["requirements"].items():
        assert w.stats.get("consumed_" + ware, 0) >= k
    assert not [r for r in ledger.check(w, snap) if r[0].startswith("mdy.")]


@pytest.mark.parametrize("recon,a,b", UPGRADES)
def test_every_reconstructor_upgrade_consumes_inputs_and_makes_the_next_tier(recon, a, b):
    from wizard_rts.industry import units as U
    if U.rules_for(b)[0]["locomotor"] == "naval":
        pytest.skip("naval payloads need water in front: see test_naval_units_leave_a_shore_reconstructor")
    w = world()
    spec = R.block(recon)
    n = spec["size"]
    x, y = F.open_ground(w, "Red", n + 6, n + 3)
    r = put(w, recon, (x + 1, y + 1))
    put(w, "mdy:power_source", (x + 1, y + 1 + n))
    m = w.buildings[r]["mdy"]
    m["rot"] = 0
    stuff(w, r, spec)
    m["payload"] = {"type": "unit", "unit": a, "faction": "Red", "hp": 1.0}
    snap = ledger.snapshot_totals(w)
    run(w, int(spec["fields"].get("constructTime", 600) / 60) + 12)
    assert _units_of(w, b), (recon, a, b, m["state"], m["buf"], m["liq"])
    for ware, k in spec["consume_items"].items():
        assert w.stats.get("consumed_" + ware, 0) >= k


def shallow_block(w, n):
    """Anchor of an (n+4) x (n+2) pond of shallow water that the test digs into free ground inside Red's territory."""
    from wizard_rts import terrain as T
    x, y = F.open_ground(w, "Red", n + 4, n + 2)
    t = w.terrain
    for a in range(n + 4):
        for b in range(n + 2):
            i = (y + b) * t.w + x + a
            t.cls[i] = T.WATER
            t.depth[i] = 1
    return (x, y)


@pytest.mark.parametrize("factory,unit", [(k, u) for k, u in FACTORY_PLANS if __import__("wizard_rts.industry.units", fromlist=["x"]).rules_for(u)[0]["locomotor"] == "naval"])
def test_naval_units_leave_a_shore_factory_into_the_water(factory, unit):
    w = world()
    spec = R.block(factory)
    n = spec["size"]
    a = shallow_block(w, n)
    if a is None:
        pytest.skip("no shallow water inside Red's territory on this seed")
    f = put(w, factory, (a[0] + 1, a[1] + 1))
    m = w.buildings[f]["mdy"]
    m["rot"] = 0
    put(w, "mdy:power_source", (a[0] + 1, a[1] + 1 + n), force=True)
    plan = next(p for p in spec["plans"] if p["unit"] == unit)
    m["plan"] = unit
    for ware, k in plan["requirements"].items():
        m["buf"][ware] = k * 2
        w.stats["made_" + ware] = w.stats.get("made_" + ware, 0) + k * 2
    run(w, int(plan["ticks"] / 60) + 15)
    made = _units_of(w, unit)
    assert made and all(w.terrain.is_water(u["tx"], u["ty"]) for u in made), (m["state"], m["buf"])


# ---- turrets and walls

TURRETS = [k for k in kinds_of("turret") if R.block(k)["class"] not in ("PointDefenseTurret", "ShockwaveTower")]


def enemy_at(w, tile, name="dagger", hp=10**8):
    fid = w.faction_info["Blue"]["id"]
    uid = w._unit(fid, "Blue", "mdy_" + name, name, "mindustry." + name, tile)
    u = w.units[uid]
    u["hp"] = u["max_hp"] = hp
    return u


@pytest.mark.parametrize("kind", TURRETS)
def test_every_turret_hurts_an_enemy_in_range_and_spends_its_ammunition(kind):
    from wizard_rts.industry import defense
    spec = R.block(kind)
    w = world()
    n = spec["size"]
    x, y = F.open_ground(w, "Red", n + 11, n + 2)
    t = put(w, kind, (x + 1, y + 1))
    m = w.buildings[t]["mdy"]
    if spec["power_use_per_s"] > 0:
        put(w, "mdy:power_source", (x + 1, y + 1 + n))
    stuff(w, t, spec)
    if spec["class"] == "ItemTurret":
        for ware in list(defense.ammo_wares(spec))[:1]:
            for _ in range(6):
                assert defense.turret_take(w, w.buildings[t], ware)
            w.stats["made_" + ware] = w.stats.get("made_" + ware, 0) + 6
    if spec["class"] in ("LiquidTurret", "ContinuousLiquidTurret"):
        liquid = next(iter(spec["ammo"]))
        m["liq"][liquid] = 50.0
        w.stats["liq_made_" + liquid] = 50.0
    targets = defense.turret_targets(spec)
    air = "AirborneActor" in targets and "GroundActor" not in targets
    weapon = defense.turret_weapon(w, w.buildings[t])
    assert weapon is not None, (kind, m["state"])
    dist = max(2, min(int(weapon["range"]) - 1, 7))
    if air:
        e = enemy_at(w, (x + 1 + dist, y + 1), "flare")
    else:
        e = enemy_at(w, (x + 1 + dist, y + 1 + n // 2), "dagger")
    e["order"] = {"kind": "move", "tile": [e["tx"], e["ty"]]}
    hp0 = e["hp"]
    run(w, 25)
    assert e["hp"] < hp0, (kind, m["state"], m.get("ammo"), weapon["range"], dist)
    if spec["class"] == "ItemTurret":
        assert m["shots"] > 0


WALLS = kinds_of("wall", "door")


@pytest.mark.parametrize("kind", WALLS)
def test_walls_and_doors_stand_with_the_health_mindustry_gives_them(kind):
    from wizard_rts.industry import defense
    spec = R.block(kind)
    w = world()
    n = spec["size"]
    x, y = F.open_ground(w, "Red", n + 2, n + 2)
    bid = put(w, kind, (x + 1, y + 1))
    b = w.buildings[bid]
    assert b["max_hp"] == defense.block_hp(spec) and b["max_hp"] >= 50 * 80, (kind, b["max_hp"])
    if spec["role"] == "wall":
        assert b["armor"] == "Concrete"


def test_wall_health_follows_the_item_and_the_size():
    hp = {k: R.block(k)["health"] for k in ("mdy:copper_wall", "mdy:copper_wall_large", "mdy:titanium_wall", "mdy:thorium_wall", "mdy:surge_wall")}
    assert hp["mdy:copper_wall"] == 320 and hp["mdy:copper_wall_large"] == 1280 and hp["mdy:titanium_wall"] == 440 and hp["mdy:thorium_wall"] == 800 and hp["mdy:surge_wall"] == 920


def test_a_mender_heals_a_damaged_neighbour_and_needs_power():
    w = world()
    x, y = F.open_ground(w, "Red", 8, 4)
    wall = put(w, "mdy:copper_wall", (x + 4, y + 1))
    mender = put(w, "mdy:mender", (x + 1, y + 1))
    ps = put(w, "mdy:power_source", (x + 1, y + 2))
    b = w.buildings[wall]
    b["hp"] = b["max_hp"] // 2
    h0 = b["hp"]
    run(w, 10)
    assert b["hp"] > h0
    w.buildings.pop(ps)  # cut the power: no more healing
    S.ind(w).dirty = True


def test_an_overdrive_projector_speeds_up_a_machine_in_range():
    w = world()
    x, y = F.open_ground(w, "Red", 10, 5)
    out = []
    for od in (False, True):
        pass
    w1 = world()
    x, y = F.open_ground(w1, "Red", 10, 5)
    sm = put(w1, "mdy:silicon_smelter", (x + 1, y + 1))
    put(w1, "mdy:power_source", (x + 1, y + 3))
    stuff(w1, sm, R.block("mdy:silicon_smelter"))
    run(w1, 2)
    base = w1.buildings[sm]["mdy"]["count"]
    w2 = world()
    x, y = F.open_ground(w2, "Red", 10, 5)
    sm2 = put(w2, "mdy:silicon_smelter", (x + 1, y + 1))
    put(w2, "mdy:power_source", (x + 3, y + 1))
    od = put(w2, "mdy:overdrive_projector", (x + 4, y + 1))
    stuff(w2, sm2, R.block("mdy:silicon_smelter"))
    stuff(w2, od, R.block("mdy:overdrive_projector"))
    run(w2, 2)
    assert w2.buildings[sm2]["mdy"]["count"] > base


def test_a_force_projector_absorbs_bullets_until_it_breaks():
    w = world()
    x, y = F.open_ground(w, "Red", 14, 7)
    sp = put(w, "mdy:force_projector", (x + 1, y + 1))
    put(w, "mdy:power_source", (x + 1, y + 4))
    wall = put(w, "mdy:copper_wall", (x + 6, y + 2))
    e = enemy_at(w, (x + 10, y + 2), "dagger")
    run(w, 3)
    hp0 = w.buildings[wall]["hp"]
    w.projectiles.append({"left_ms": 300, "target": {"kind": "building", "id": wall}, "warheads": [{"type": "SpreadDamage", "damage": 1000, "spread": 0, "versus": {}, "valid_targets": ["Structure"]}], "shooter": e["id"]})
    run(w, 2)
    assert w.buildings[wall]["hp"] == hp0 and w.stats.get("shield_absorbed", 0) >= 1000


def test_point_defense_shoots_a_bullet_down():
    w = world()
    x, y = F.open_ground(w, "Red", 14, 7)
    seg = put(w, "mdy:segment", (x + 1, y + 1))
    put(w, "mdy:power_source", (x + 1, y + 3))
    wall = put(w, "mdy:copper_wall", (x + 6, y + 2))
    e = enemy_at(w, (x + 10, y + 2), "dagger")
    run(w, 3)
    w.projectiles.append({"left_ms": 900, "target": {"kind": "building", "id": wall}, "warheads": [{"type": "SpreadDamage", "damage": 1000, "spread": 0, "versus": {}, "valid_targets": ["Structure"]}], "shooter": e["id"]})
    run(w, 1)
    assert w.stats.get("bullets_downed", 0) == 1 and not any(p["target"]["id"] == wall for p in w.projectiles)


def test_a_shock_mine_hurts_an_enemy_that_stands_on_it():
    w = world()
    x, y = F.open_ground(w, "Red", 6, 3)
    mine = put(w, "mdy:shock_mine", (x + 2, y + 1))
    e = enemy_at(w, (x + 2, y + 1), "dagger")
    e["order"] = {"kind": "move", "tile": [e["tx"], e["ty"]]}
    hp0 = e["hp"]
    run(w, 3)
    assert e["hp"] < hp0


# ---- transport over distance and payloads

def test_mass_drivers_shoot_items_across_the_map_into_a_store():
    from test_mindustry_engine import feed
    w = world()
    x, y = F.open_ground(w, "Red", 16, 6)
    a = put(w, "mdy:mass_driver", (x + 1, y + 1))
    b2 = put(w, "mdy:mass_driver", (x + 10, y + 1))
    for d in (a, b2):
        put(w, "mdy:power_source", (w.buildings[d]["tx"], w.buildings[d]["ty"] + 3))
    w.buildings[a]["mdy"]["link"] = b2
    cont = put(w, "mdy:container", (x + 13, y + 2))
    snap = ledger.snapshot_totals(w)
    belt(w, [(x, y + 2)], 0)
    run(w, 1)
    feed(w, (x, y + 2), "mdy.copper", 12)
    run(w, 40)
    assert stock(w, cont, "mdy.copper") >= 10
    assert stock(w, cont, "mdy.copper") + w.buildings[a]["mdy"]["item_total"] + sum(1 for _ in S.ind(w).shipments) * 0 == 12
    assert not ledger.check(w, snap)


def test_launch_pad_ships_to_another_store_and_the_books_balance():
    w = world()
    x, y = F.open_ground(w, "Red", 14, 6)
    pad = put(w, "mdy:launch_pad", (x + 1, y + 1))
    put(w, "mdy:power_source", (x + 1, y + 4))
    cont = put(w, "mdy:vault", (x + 8, y + 1))
    m = w.buildings[pad]["mdy"]
    m["link"] = cont
    m["buf"]["mdy.silicon"] = 30
    w.stats["made_mdy.silicon"] = 30
    snap = ledger.snapshot_totals(w)
    run(w, 60)
    assert stock(w, cont, "mdy.silicon") == 30 and sum(m["buf"].values()) == 0
    assert not ledger.check(w, snap)


def test_a_payload_conveyor_carries_a_unit_between_machines():
    w = world()
    x, y = F.open_ground(w, "Red", 14, 6)
    fac = put(w, "mdy:ground_factory", (x + 1, y + 1))
    put(w, "mdy:power_source", (x + 1, y + 4))
    rec = put(w, "mdy:additive_reconstructor", (x + 8, y + 1))
    put(w, "mdy:power_source", (x + 8, y + 4))
    w.buildings[fac]["mdy"]["rot"] = 0
    w.buildings[rec]["mdy"]["rot"] = 0
    # 3-wide machines: the factory front tile is x+4; the conveyor runs from x+4 to x+9 at the middle row
    belt(w, [(x + 4 + i, y + 2) for i in range(4)], 0, kind="mdy:payload_conveyor")
    fm = w.buildings[fac]["mdy"]
    fm["plan"] = "dagger"
    for ware, k in S._plan(R.block("mdy:ground_factory"), fm)["requirements"].items():
        fm["buf"][ware] = k * 2
        w.stats["made_" + ware] = w.stats.get("made_" + ware, 0) + k * 2
    stuff(w, rec, R.block("mdy:additive_reconstructor"))
    run(w, 70)
    names = sorted(u["mdy_unit"] for u in w.units.values() if u.get("mdy_unit"))
    assert "mace" in names, (names, w.buildings[rec]["mdy"]["state"], w.buildings[fac]["mdy"]["state"])


def test_a_constructor_builds_a_wall_payload_and_a_deconstructor_returns_its_materials():
    w = world()
    x, y = F.open_ground(w, "Red", 14, 6)
    con = put(w, "mdy:constructor", (x + 1, y + 1))
    put(w, "mdy:power_source", (x + 1, y + 4))
    decon = put(w, "mdy:small_deconstructor", (x + 8, y + 1))
    put(w, "mdy:power_source", (x + 8, y + 4))
    m = w.buildings[con]["mdy"]
    m["rot"] = 0
    m["block"] = "mdy:berylliun_wall_large".replace("berylliun", "beryllium")
    from wizard_rts.industry import payload as PL
    items = PL._block_items(R.block(m["block"]))
    for ware, n in items.items():
        m["buf"][ware] = n * 2
        w.stats["made_" + ware] = w.stats.get("made_" + ware, 0) + n * 2
    belt(w, [(x + 4 + i, y + 2) for i in range(4)], 0, kind="mdy:payload_conveyor")
    snap = ledger.snapshot_totals(w)
    run(w, 40)
    dm = w.buildings[decon]["mdy"]
    refunded = sum(w.stats.get("made_" + k, 0) for k in items) - sum(n * 2 for n in items.values())
    assert refunded >= 1 or dm["out"] or dm.get("payload"), (m["state"], dm["state"], m["buf"])


def test_a_repair_point_heals_a_friendly_unit_and_a_build_tower_speeds_up_a_site():
    w = world()
    x, y = F.open_ground(w, "Red", 14, 6)
    rp = put(w, "mdy:repair_point", (x + 1, y + 1))
    fid = w.faction_info["Red"]["id"]
    uid = w._unit(fid, "Red", "mdy_dagger", "d", "mindustry.dagger", (x + 4, y + 1))
    w.units[uid]["hp"] = w.units[uid]["max_hp"] // 3
    h0 = w.units[uid]["hp"]
    run(w, 10)
    assert w.units[uid]["hp"] > h0


def test_a_radar_reveals_ground_and_an_incinerator_destroys_what_it_is_given():
    w = world()
    x, y = F.open_ground(w, "Red", 14, 6)
    rd = put(w, "mdy:radar", (x + 1, y + 1))
    put(w, "mdy:power_source", (x + 1, y + 2))
    inc = put(w, "mdy:incinerator", (x + 5, y + 1))
    put(w, "mdy:power_source", (x + 5, y + 2))
    from test_mindustry_engine import feed
    belt(w, [(x + 3, y + 1), (x + 4, y + 1)], 0)
    run(w, 1)
    feed(w, (x + 3, y + 1), "mdy.copper", 3)
    snap = ledger.snapshot_totals(w)
    run(w, 60)
    assert w.__dict__.get("explored", {}).get("Red")
    assert w.stats.get("incinerated_mdy.copper", 0) == 3
    assert not ledger.check(w, snap)


def test_a_processor_runs_its_program_against_linked_blocks():
    w = world()
    x, y = F.open_ground(w, "Red", 10, 6)
    cpu = put(w, "mdy:micro_processor", (x + 1, y + 1))
    cell = put(w, "mdy:memory_cell", (x + 3, y + 1))
    msg = put(w, "mdy:message", (x + 5, y + 1))
    cont = put(w, "mdy:container", (x + 1, y + 3))
    w.stocks[cont]["mdy.copper"] = 7
    w.stats["made_mdy.copper"] = 7
    code = """
sensor n container1 @copper
write n cell1 0
op add k k 1
write k cell1 1
print "copper="
print n
printflush message1
end
"""
    assert C.configure(w, "Red", cpu, "code", code)["status"] == "ok"
    run(w, 3)
    cells = w.buildings[cell]["mdy"]["cells"]
    assert cells[0] == 7.0 and cells[1] >= 2.0
    assert w.buildings[msg]["mdy"]["text"].startswith("copper=7")


def test_a_processor_can_switch_a_block_off_and_a_bad_instruction_is_reported_not_fatal():
    w = world()
    x, y = F.open_ground(w, "Red", 10, 6)
    cpu = put(w, "mdy:micro_processor", (x + 1, y + 1))
    tur = put(w, "mdy:duo", (x + 3, y + 1))
    C.configure(w, "Red", cpu, "code", "control enabled duo1 0\nend")
    run(w, 3)
    assert w.buildings[tur].get("unpowered") is True
    C.configure(w, "Red", cpu, "code", "op bogus a 1 2\nend")
    run(w, 2)
    assert w.buildings[cpu]["mdy"]["error"]


ASSEMBLER_PLANS = [(k, p["unit"]) for k in kinds_of("assembler") for p in (R.block(k)["assembler_plans"] or [])]


@pytest.mark.parametrize("kind,unit", ASSEMBLER_PLANS)
def test_every_assembler_plan_builds_its_unit_from_delivered_payloads(kind, unit):
    spec = R.block(kind)
    w = world()
    n = spec["size"]
    x, y = F.open_ground(w, "Red", n + 5, n + 3)
    a = put(w, kind, (x + 1, y + 1))
    put(w, "mdy:power_source", (x + 1, y + 1 + n))
    m = w.buildings[a]["mdy"]
    m["rot"] = 0
    stuff(w, a, spec)
    plan = next(p for p in spec["assembler_plans"] if p["unit"] == unit)
    m["plan"] = unit
    m["stack"] = dict(plan["payload"])  # the unit and block payloads a conveyor would have delivered
    run(w, int(plan["time_ticks"] / 60) + 15)
    assert _units_of(w, unit), (kind, unit, m["state"], m["stack"])


def test_a_core_is_a_store_for_both_economies_roads_deliver_to_it_and_unloaders_serve_belts():
    from wizard_rts import construction as con
    from wizard_rts.economy import produce
    w = world()
    wh = con.faction_warehouse(w, "Red")
    x, y = F.open_ground(w, "Red", 8, 5)
    core = put(w, "mdy:core_shard", (x + 1, y + 1))
    assert w.buildings[core].get("store")
    w.stocks[core]["mdy.copper"] = 9
    w.stats["made_mdy.copper"] = 9
    # a road from the core to the settlement lets Widelands carriers take and bring wares: the core is listed as a warehouse
    from wizard_rts import logistics
    assert core in [b["id"] for b in logistics._warehouses(w, w.buildings[core]["faction"])]


@pytest.mark.parametrize("kind,unit", ASSEMBLER_PLANS)
def test_an_assembler_accepts_real_payloads_and_builds_its_unit(kind, unit):
    """No faked stack: each payload goes through give_payload, which refuses what the plan does not want and what it already has enough of."""
    from wizard_rts.industry import blocks as B
    from wizard_rts.industry import payload as P

    spec = R.block(kind)
    w = world()
    n = spec["size"]
    x, y = F.open_ground(w, "Red", n + 5, n + 3)
    a = put(w, kind, (x + 1, y + 1))
    put(w, "mdy:power_source", (x + 1, y + 1 + n))
    m = w.buildings[a]["mdy"]
    stuff(w, a, spec)
    plan = next(p for p in spec["assembler_plans"] if p["unit"] == unit)
    m["plan"] = unit
    from wizard_rts.industry import sim as S

    run(w, 1)
    st = S.ind(w)
    tile = (w.buildings[a]["tx"], w.buildings[a]["ty"])
    src = (tile[0] - 5, tile[1])

    def payload_for(java: str) -> dict:
        blk = next((bid for bid, d in B.full()["blocks"].items() if d.get("java_name") == java), None)
        if blk is not None:
            return {"type": "block", "block": blk, "stock": {}, "cap": 10}
        return {"type": "unit", "unit": java, "faction": "Red", "hp": 1.0}

    assert not P.accepts_payload(w, st, w.buildings[a], {"type": "unit", "unit": "dagger", "faction": "Red", "hp": 1.0}, src)  # not in the plan
    for java, need in plan["payload"].items():
        for _ in range(need):
            assert P.accepts_payload(w, st, w.buildings[a], payload_for(java), src), (kind, unit, java)
            assert P.give_payload(w, st, tile, payload_for(java), src)
            run(w, 1)
    assert all(m["stack"].get(k, 0) >= v for k, v in plan["payload"].items()), m["stack"]
    run(w, int(plan["time_ticks"] / 60) + 15)
    assert _units_of(w, unit), (kind, unit, m["state"])

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
        m["liq"][liquid] = m["liq"].get(liquid, 0.0) + max(per * 6 * 60, 5.0)
        w.stats["liq_made_" + liquid] = w.stats.get("liq_made_" + liquid, 0.0) + max(per * 6 * 60, 5.0)


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
        run(w, 14)
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

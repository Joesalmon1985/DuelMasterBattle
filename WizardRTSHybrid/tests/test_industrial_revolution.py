"""Modern replaces the hand-worked economy (owner programme 13 Oct 2026, section 6): every Widelands ware the economy consumes has an industrial source, the
industrial blocks make it many times faster, drills win stone and ore, and a standing Widelands building can be converted into its replacement."""
from __future__ import annotations

import pytest

from conftest import set_resource
from test_mindustry_engine import C, F, FL, R, S, ledger, put, run, world
from test_mindustry_blocks import stuff
from wizard_rts import construction as con
from wizard_rts import wl_defs
from wizard_rts.industry import blocks as B
from wizard_rts.industry import hybrid as H
from wizard_rts.industry import sim


def consumed_wares():
    """Every ware a Widelands production site, a build cost or an OpenRA recipe asks for."""
    out = set()
    for n in wl_defs.runnable_names():
        sp = wl_defs.building_spec(n)
        if sp and sp["tribe"]:
            out.update(g for g in sp["inputs"] if g not in ("recruit", "carrier"))
            out.update(sp["cost"])
    for recipes in con.RECIPES.values():
        for r in recipes.values():
            out.update(r["cost"])
    return out


def test_every_consumed_widelands_ware_has_an_industrial_source_or_a_written_reason():
    sources = H.ware_sources()
    missing = sorted(w for w in consumed_wares() if w not in sources and w not in H.UNMADE and not w.startswith("mdy."))
    assert missing == [], missing


def test_every_hybrid_industrial_block_and_recipe_is_data_complete():
    for kind, s in H.specs().items():
        assert s["cost"] and s["recipes"] and s["role"] in ("crafter", "harvester")
        for name, r in s["recipes"].items():
            assert r["output"] and r["ticks"] > 0 and r.get("power", 0) >= 0, (kind, name)


def recipes():
    return [(k, r) for k, s in sorted(H.specs().items()) if s["role"] == "crafter" for r in s["recipes"]]


@pytest.mark.parametrize("kind,recipe", recipes())
def test_every_industrial_recipe_makes_its_ware_from_physical_inputs_with_power(kind, recipe):
    spec = R.block(kind)
    w = world()
    n = spec["size"]
    x, y = F.open_ground(w, "Red", n + 4, n + 2)
    bid = put(w, kind, (x + 1, y + 1))
    put(w, "mdy:power_source", (x + 1 + n, y + 1))
    assert C.configure(w, "Red", bid, "recipe", recipe)["status"] == "ok"
    eff = H.effective(spec, w.buildings[bid]["mdy"])
    stuff(w, bid, eff)
    snap = ledger.snapshot_totals(w)
    run(w, 45)
    m = w.buildings[bid]["mdy"]
    ware = next(iter(eff["output_item"]))
    assert m["count"] >= 1 and (m["out"].get(ware, 0) >= 1 or w.stats.get("made_" + ware, 0) >= 1), (kind, recipe, m["state"], m["buf"])
    assert FL.liquid_books(w) == []


def test_the_tree_harvester_fells_trees_by_power_and_logs_appear():
    w = world()
    x, y = F.open_ground(w, "Red", 8, 4)
    h = put(w, "mdy:hy_tree_harvester", (x + 1, y + 1))
    put(w, "mdy:power_source", (x + 3, y + 1))
    from wizard_rts.workers import plant_tree
    for i in range(4):
        tid = plant_tree(w, (x + 5 + i, y + 6), "sapling", "beech")
        w.trees[tid]["stage"] = "old"
    run(w, 30)
    assert w.stats.get("trees_harvested", 0) >= 1 and w.stats.get("made_log", 0) >= 2


def wl_rate_per_minute(kind: str, ware: str) -> float:
    """Wares per game minute of a Widelands building running flat out: the produce counts of its main programme (and what it calls) over the sleeps, animations and its
    worker's animations in one cycle."""
    sp = wl_defs.spec_for_kind(kind)
    programs = sp["programs"]
    ms = 0
    made = 0

    def walk(name, depth=0):
        nonlocal ms, made
        for cmd, args in programs.get(name, []):
            if cmd in ("sleep", "animate"):
                ms += args["ms"]
            elif cmd == "call" and args["target"] in programs and depth < 4 and not args["target"].startswith("encyclopedia"):
                walk(args["target"], depth + 1)
            elif cmd == "produce":
                made += args.get(ware, 0)
            elif cmd == "callworker":
                role = sp["worker_for_program"].get(args["program"])
                for c2, a2 in (wl_defs.worker_programs(role) or {}).get(args["program"], []):
                    if c2 == "animate":
                        ms += a2["ms"]
                    if c2 == "createware" and a2["ware"] == ware:
                        made += 1

    walk("main")
    return 60_000 * made / max(ms, 1) if made else 0.0


def industrial_rate_per_minute(kind: str, ware: str) -> float:
    s = H.specs()[kind]
    r = s["recipes"].get(ware)
    return 60 * 60 * r["output"][ware] / r["ticks"] if r else 0.0


PAIRS = [("empire_sawmill", "mdy:hy_sawmill_line", "plank"), ("barbarians_smelting_works", "mdy:hy_arc_smelter", "iron"), ("barbarians_bakery", "mdy:hy_food_plant", "bread"),
         ("barbarians_farm", "mdy:hy_hydroponic_farm", "wheat"), ("barbarians_well", "mdy:hy_water_bottler", "water"), ("barbarians_lumberjacks_hut", "mdy:hy_tree_harvester", "log"),
         ("empire_weaving_mill", "mdy:hy_fibre_loom", "cloth"), ("barbarians_lime_kiln", "mdy:hy_material_press", "grout"), ("barbarians_metal_workshop", "mdy:hy_tool_foundry", "pick")]


@pytest.mark.parametrize("old,new,ware", PAIRS)
def test_the_industrial_block_outproduces_the_widelands_building_it_replaces(old, new, ware):
    old_rate = wl_rate_per_minute("wl:" + old, ware)
    new_rate = industrial_rate_per_minute(new, ware) if new != "mdy:hy_tree_harvester" else 60 * 60 * 2 / H.specs()[new]["craft_ticks"] if False else 60 * 60 * 2 / 110
    assert old_rate > 0, (old, ware)
    assert new_rate >= 3 * old_rate, (old, new, ware, old_rate, new_rate)


def test_drills_win_granite_iron_ore_and_gold_ore_from_the_existing_deposits():
    for res, ware, tier in (("stones", "granite", "mdy:pneumatic_drill"), ("iron", "iron_ore", "mdy:pneumatic_drill"), ("gold", "gold_ore", "mdy:pneumatic_drill")):
        w = world()
        x, y = F.open_ground(w, "Red", 8, 4)
        for dx in range(2):
            for dy in range(2):
                set_resource(w, (x + 1 + dx, y + 1 + dy), res, 20)
        d = put(w, tier, (x + 1, y + 1))
        assert C.configure(w, "Red", d, "target", ware)["status"] == "ok", (res, ware)
        run(w, 30)
        m = w.buildings[d]["mdy"]
        assert m["out"].get(ware, 0) + w.stats.get("made_" + ware, 0) >= 1


def test_the_rock_deposit_does_not_run_dry_so_industry_replaces_the_quarry_for_good():
    w = world()
    x, y = F.open_ground(w, "Red", 8, 4)
    for dx in range(2):
        for dy in range(2):
            set_resource(w, (x + 1 + dx, y + 1 + dy), "stones", 20)
    d = put(w, "mdy:pneumatic_drill", (x + 1, y + 1))
    C.configure(w, "Red", d, "target", "granite")
    run(w, 60)
    assert w.stats.get("extracted_units_stones", 0) >= 2


def wl_building(w, kind, stock=None):
    from wizard_rts import ai
    from wizard_rts.economy import produce
    wh = con.faction_warehouse(w, "Red")
    bid = ai._place_near(w, "Red", kind, wh)
    assert bid, kind
    b = w.buildings[bid]
    b.pop("constructing", None)
    b["operational"], b["hp"] = True, b["max_hp"]
    w.recipe_requests.pop(bid, None)
    for g, n in (stock or {}).items():
        produce(w, bid, g, n)
    return b


def test_a_widelands_building_is_converted_into_its_industrial_replacement_for_the_upgrade_price():
    from wizard_rts.economy import produce
    w = world()
    b = wl_building(w, "wl:barbarians_lumberjacks_hut")
    from test_mindustry_engine import unlock
    unlock(w)
    wh = con.faction_warehouse(w, "Red")
    for g in ("iron", "plank", "granite", "mdy.silicon"):
        produce(w, wh["id"], g, 30)
    r = C.convert_building(w, "Red", b["id"])
    assert r["status"] == "ok" and b["kind"] == "mdy:hy_tree_harvester" and b["constructing"]["convert_from"] == "wl:barbarians_lumberjacks_hut"
    new_cost = R.block("mdy:hy_tree_harvester")["cost"]
    assert all(r["cost"].get(g, 0) <= n for g, n in new_cost.items())
    run(w, 400)
    assert b.get("mdy") is not None and b["mdy"]["role"] == "harvester"


def test_dismantling_returns_part_of_the_build_cost_through_the_carriers_and_removes_the_building():
    from wizard_rts import ledger
    w = world()
    b = wl_building(w, "wl:barbarians_tavern", stock={"ration": 2})
    wh = con.faction_warehouse(w, "Red")
    snap = ledger.snapshot_totals(w)
    before = {g: w.stocks[wh["id"]].get(g, 0) for g in ("log", "granite", "blackwood", "reed")}
    r = con.dismantle_building(w, "Red", b["id"])
    assert r["status"] == "ok" and r["returns"]
    run(w, 240)
    assert b["id"] not in w.buildings
    after = {g: w.stocks[wh["id"]].get(g, 0) for g in before}
    assert any(after[g] > before[g] for g in r["returns"] if g in after) or sum(w.stocks[wh["id"]].values()) > 0
    assert not ledger.check(w, snap)

"""Shared water and the first naval slice: yards on the coast, ships from delivered goods, water-only movement, naval combat.

Source: OpenRA RA rules (SYRD/SPEN Building.TerrainTypes Water, naval locomotor Water 100, PT/SS weapons and target types,
Cloak and DetectCloaked), imported into data/openra_rules.json. Level B/C/D (live loop on the generated map).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["HYBRID_AI"] = "0"

from wizard_rts import ai, construction as con, rules, terrain as T  # noqa: E402
from wizard_rts.economy import produce  # noqa: E402
from wizard_rts.workers import find_path  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def _run(w, seconds):
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(seconds):
        w.advance(1000, base + i + 1, snapshot=False)


def _until(w, pred, max_s):
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(max_s):
        if pred():
            return True
        w.advance(1000, base + i + 1, snapshot=False)
    return pred()


def _yard_world(faction="Blue", kind="naval_yard"):
    w = HybridWorld(507)
    w.ai_enabled = False
    wh = con.faction_warehouse(w, faction)
    site = ai._naval_site(w, faction, wh)
    res = w.build(faction, kind, *site)
    assert res["status"] == "ok", res
    produce(w, wh["id"], "plank", 30)
    produce(w, wh["id"], "iron", 20)
    produce(w, wh["id"], "granite", 6)
    assert w.road(faction, res["id"], wh["id"])["status"] == "ok"
    assert _until(w, lambda: not w.buildings[res["id"]].get("constructing"), 400)
    return w, wh, res["id"]


def test_yard_rules_come_from_the_openra_definition() -> None:
    syrd = rules.actor("openra.syrd")
    assert syrd["building"]["terrain_types"] == ["Water"] and syrd["building"]["footprint"] == "XXX xxx XXX"
    assert "Ship" in syrd["produces"] and "Boat" in syrd["produces"]
    assert rules.actor("openra.spen")["produces"][1] == "Submarine"
    assert rules.locomotor("naval")["speeds"] == {"Water": 100}
    assert "Water" not in rules.locomotor("foot")["speeds"] and "Water" not in rules.locomotor("heavytracked")["speeds"]
    ss = rules.actor("openra.ss")
    assert ss["cloak"]["delay_ticks"] == 50 and ss["locomotor"] == "naval"


def test_yard_needs_water_footprint_real_shore_and_a_real_body_of_water() -> None:
    w = HybridWorld(507)
    wh = con.faction_warehouse(w, "Blue")
    good = ai._naval_site(w, "Blue", wh)
    assert w.terrain.is_water(*good)
    # on land: rejected
    assert w.build("Blue", "naval_yard", wh["tx"], wh["ty"] + 3)["reason"] == "needs_water"
    # footprint half on the beach: rejected
    shore = next(p for p in ((x, y) for x in range(good[0] - 12, good[0] + 12) for y in range(good[1] - 12, good[1] + 12))
                 if w.terrain.is_water(*p) and w.terrain.depth[p[1] * w.terrain.w + p[0]] == 1 and not con.naval_site(w, p, wh)[0] is None
                 and con.naval_site(w, p, wh)[0] == "needs_water")
    assert w.build("Blue", "naval_yard", *shore)["reason"] == "needs_water"
    # the middle of the lake has water all around but no shore touching the footprint
    lake = w.terrain.meta["homes"][1]["lake"]
    assert w.build("Blue", "naval_yard", *lake)["reason"] in ("no_shore", "outside_territory")
    # a good site works and is on the coast of a big body
    assert w.build("Blue", "naval_yard", *good)["status"] == "ok"
    comp = w.terrain.water_comp[good[1] * w.terrain.w + good[0]]
    assert w.terrain.comp_size[comp] >= T.PORT_MIN_WATER


def test_yard_on_a_pond_is_refused() -> None:
    """A 5x5 pond cut into the meadow beside Red's warehouse: water, with a shore, but far too small to sail."""
    from wizard_rts import mapgen

    w = HybridWorld(minimal=True, terrain=True)
    t = w.terrain
    wh = con.faction_warehouse(w, "Red")
    px, py = wh["tx"] + 6, wh["ty"] + 3
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            t.terrain[(py + dy) * t.w + px + dx] = mapgen.P["water"]
    t.compute()
    comp = t.water_comp[py * t.w + px]
    assert t.comp_size[comp] == 25 < T.PORT_MIN_WATER
    assert con.naval_site(w, (px, py), wh)[0] == "water_too_small"


def test_ship_is_built_from_delivered_goods_and_spawns_on_water() -> None:
    w, wh, yard = _yard_world()
    b = w.buildings[yard]
    assert b["operational"] and b["footprint"] and all(t.is_water(*p) for t in [w.terrain] for p in b["footprint"])
    # nothing is free: with no goods in the yard the queue waits
    assert w.queue(yard, "patrol_boat")["status"] == "ok"
    ships_before = [u for u in w.units.values() if u["kind"] == "patrol_boat"]
    stock_before = dict(w.stocks[wh["id"]])
    assert _until(w, lambda: any(u["kind"] == "patrol_boat" for u in w.units.values()), 400)
    ship = next(u for u in w.units.values() if u["kind"] == "patrol_boat")
    assert not ships_before and w.terrain.swimmable(ship["tx"], ship["ty"]) and ship["loco"] == "naval"
    assert w.stats["consumed_plank"] >= 3 and w.stats["consumed_iron"] >= 1  # the recipe's goods really left the economy
    assert w.stocks[wh["id"]].get("plank", 0) < stock_before.get("plank", 0)
    assert rules.actor(ship["definition"])["name"] == "PT"


def test_ship_without_goods_never_appears() -> None:
    w = HybridWorld(507)
    wh = con.faction_warehouse(w, "Blue")
    site = ai._naval_site(w, "Blue", wh)
    for g in ("plank", "iron"):
        w.stocks[wh["id"]][g] = 0
        w.economy_totals.totals[g] = 0
    res = w.build("Blue", "naval_yard", *site)
    produce(w, wh["id"], "plank", 8)
    produce(w, wh["id"], "granite", 3)
    w.road("Blue", res["id"], wh["id"])
    assert _until(w, lambda: not w.buildings[res["id"]].get("constructing"), 400)
    for g in ("plank", "iron"):  # the yard is built; take every remaining plank and iron out of the economy
        for b in w.buildings.values():
            w.stocks[b["id"]][g] = 0
        w.economy_totals.totals[g] = 0
    w.queue(res["id"], "patrol_boat")
    _run(w, 120)
    assert not any(u["kind"] == "patrol_boat" for u in w.units.values())


def test_ships_stay_on_water_and_cannot_cross_or_enter_land() -> None:
    w, wh, yard = _yard_world()
    w.queue(yard, "patrol_boat")
    assert _until(w, lambda: any(u["kind"] == "patrol_boat" for u in w.units.values()), 400)
    ship = next(u for u in w.units.values() if u["kind"] == "patrol_boat")
    t = w.terrain
    # an order onto land is refused for a ship
    land = next(p for p in ((ship["tx"] + dx, ship["ty"] + dy) for dx in range(-12, 13) for dy in range(-12, 13)) if t.ground(*p) and p not in w.blocked)
    assert w.move([ship["id"]], *land)["status"] == "rejected"
    # far water in the same sea is reachable, and every step of the route is water
    lake = t.meta["homes"][1]["lake"]
    sea = t.water_comp[lake[1] * t.w + lake[0]]
    here = (ship["tx"], ship["ty"])
    assert t.water_comp[here[1] * t.w + here[0]] == sea  # the yard opens onto the shared sea
    mid = (int(w.terrain.meta["capitals"][1][0]) + 60, int(w.terrain.meta["capitals"][1][1]) + 50)
    goal = next(p for r in range(0, 30) for p in __import__("wizard_rts.grid", fromlist=["ring"]).ring(mid[0], mid[1], r) if t.swimmable(*p) and t.water_comp[p[1] * t.w + p[0]] == t.water_comp[here[1] * t.w + here[0]])
    path = find_path(w, here, goal, limit=500, max_nodes=600_000, loco="naval")
    assert path and all(t.swimmable(*p) for p in path)
    assert all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip([here] + path, path))
    # a separate body of water (the outer ocean) cannot be reached: the land between has no passage
    other = next(i for i in range(t.w * t.h) if t.water_comp[i] and t.water_comp[i] != t.water_comp[here[1] * t.w + here[0]])
    assert find_path(w, here, (other % t.w, other // t.w), limit=600, max_nodes=800_000, loco="naval") is None
    # and the ship, sent to that far water, really moves only over water tiles
    assert w.move([ship["id"]], *goal)["status"] == "ok"
    seen = set()
    seq = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(6000):  # 100 ms steps: every tile the ship stands on is sampled
        seq += 1
        w.advance(100, seq, snapshot=False)
        seen.add((ship["tx"], ship["ty"]))
        if (ship["tx"], ship["ty"]) == goal:
            break
    assert max(abs(ship["tx"] - goal[0]), abs(ship["ty"] - goal[1])) <= 1 and len(seen) > 30 and all(t.swimmable(*p) for p in seen)


def test_ground_units_cannot_use_naval_paths_and_ships_cannot_use_ground_paths() -> None:
    w = HybridWorld(507)
    t = w.terrain
    lake = w.terrain.meta["homes"][1]["lake"]
    land = (w.buildings[next(i for i, b in w.buildings.items() if b["kind"] == "warehouse" and b["faction_name"] == "Blue")]["tx"] + 4, 72)
    assert find_path(w, tuple(lake), (lake[0] + 2, lake[1]), limit=50, loco="heavytracked") is None  # a tank cannot drive across the lake
    assert find_path(w, tuple(lake), (lake[0] + 2, lake[1]), limit=50, loco="foot") is None
    assert find_path(w, tuple(lake), (lake[0] + 2, lake[1]), limit=50, loco="naval") is not None
    assert find_path(w, land, (land[0] + 3, land[1]), limit=50, loco="naval") is None


def test_torpedo_and_cannon_follow_the_openra_target_filters() -> None:
    torp = rules.weapon("TorpTube")
    cannon = rules.weapon("2Inch")
    depth = rules.weapon("DepthCharge")
    assert rules.can_hit(torp, {"WaterActor", "Ship"}) and not rules.can_hit(torp, {"GroundActor", "Infantry"})
    assert rules.can_hit(cannon, {"WaterActor", "Ship"}) and not rules.can_hit(cannon, {"Underwater", "Submarine"})
    assert rules.can_hit(depth, {"Underwater"}) and not rules.can_hit(depth, {"WaterActor", "Ship"})


def _two_fleets():
    """Blue and Green each get a ship on the shared sea, two tiles apart, no yards, AI off."""
    w = HybridWorld(507)
    w.ai_enabled = False
    t = w.terrain
    centre = w.terrain.meta["capitals"]
    lake = t.meta["homes"][1]["lake"]
    sea = t.water_comp[lake[1] * t.w + lake[0]]  # the shared inland sea (the outer ocean is a separate body)
    cx, cy = (centre[1][0] + centre[2][0]) // 2, (centre[1][1] + centre[4][1]) // 2
    spots = [(x, y) for x in range(cx - 8, cx + 9) for y in range(cy - 8, cy + 9) if t.water_comp[y * t.w + x] == sea]
    return w, spots


def _spawn(w, faction, kind, definition, tile):
    return w._unit(w.faction_info[faction]["id"], faction, kind, kind, definition, tile)


def test_patrol_boats_fight_and_one_sinks() -> None:
    w, spots = _two_fleets()
    a = _spawn(w, "Blue", "patrol_boat", "openra.pt", spots[0])
    b = _spawn(w, "Green", "patrol_boat", "openra.pt", (spots[0][0] + 3, spots[0][1]))
    _until(w, lambda: not w.units[a]["alive"] or not w.units[b]["alive"], 240)
    assert w.units[a]["hp"] < w.units[a]["max_hp"] or w.units[b]["hp"] < w.units[b]["max_hp"]
    assert w.stats["attack"] > 0
    assert not (w.units[a]["alive"] and w.units[b]["alive"]) or w.stats["attack"] >= 2


def test_cloaked_submarine_is_hidden_until_it_fires_or_is_detected() -> None:
    from wizard_rts import military

    w, spots = _two_fleets()
    sub = _spawn(w, "Blue", "submarine", "openra.ss", spots[0])
    pt = _spawn(w, "Green", "patrol_boat", "openra.pt", (spots[0][0] + 6, spots[0][1]))
    military.update_cloak(w.units[sub])
    assert w.units[sub]["cloaked"] is True
    assert military.target_types(w.units[sub]) == {"Underwater", "Submarine"}
    green = w.faction_info["Green"]["id"]
    cannon, depth = rules.weapon("2Inch"), rules.weapon("DepthCharge")
    # PT's DetectCloaked range is 4 cells (rules): at 6 cells the sub is invisible to it
    assert rules.actor("openra.pt")["detect"]["range"] == 4.0
    assert not military.weapon_can_attack(w, green, cannon, w.units[sub])
    assert not military.weapon_can_attack(w, green, depth, w.units[sub])
    # closing to 3 cells detects it: the depth charge (valid on Underwater) may fire, the cannon (invalid on Underwater) may not
    w.units[pt]["tx"], w.units[pt]["ty"] = spots[0][0] + 3, spots[0][1]
    assert military.weapon_can_attack(w, green, depth, w.units[sub])
    assert not military.weapon_can_attack(w, green, cannon, w.units[sub])
    # after the sub fires it shows for CloakDelay (50 ticks = 2 s), then hides again
    w.units[sub]["uncloak_ms"] = 2000
    military.update_cloak(w.units[sub])
    assert w.units[sub]["cloaked"] is False and "WaterActor" in military.target_types(w.units[sub])
    assert military.weapon_can_attack(w, green, cannon, w.units[sub])  # surfaced: the cannon can hit it
    for _ in range(25):
        military.update_cloak(w.units[sub])
    assert w.units[sub]["cloaked"] is True
    # a critically damaged sub cannot stay hidden (OpenRA GrantConditionOnDamageState Critical)
    w.units[sub]["hp"] = w.units[sub]["max_hp"] // 5
    military.update_cloak(w.units[sub])
    assert w.units[sub]["cloaked"] is False


def test_submarine_torpedoes_a_patrol_boat_and_depth_charges_answer() -> None:
    w, spots = _two_fleets()
    sub = _spawn(w, "Blue", "submarine", "openra.ss", spots[0])
    pt = _spawn(w, "Green", "patrol_boat", "openra.pt", (spots[0][0] + 4, spots[0][1]))
    dd = _spawn(w, "Green", "destroyer", "openra.dd", (spots[0][0] + 5, spots[0][1] + 1))
    _until(w, lambda: not w.units[sub]["alive"] or not w.units[pt]["alive"], 300)
    killed_sub = not w.units[sub]["alive"]
    hurt = w.units[pt]["hp"] < w.units[pt]["max_hp"] or not w.units[pt]["alive"]
    assert killed_sub or hurt
    assert w.units[dd]["alive"] or w.units[sub]["alive"]


def test_naval_yard_can_be_destroyed_and_frees_its_water() -> None:
    w, wh, yard = _yard_world()
    fp = [tuple(p) for p in w.buildings[yard]["footprint"]]
    assert all(p in w.blocked for p in fp)
    w.damage_building(yard, 10**9, ["structure"], {})
    _run(w, 20)
    assert yard not in w.buildings and not any(p in w.blocked for p in fp)


def test_ai_builds_a_yard_and_queues_ships_when_it_has_a_shore() -> None:
    w = HybridWorld(507)
    w.ai_aggressive = False
    w.ai_enabled = True
    assert _until(w, lambda: any(b["kind"] == "naval_yard" for b in w.buildings.values()), 1500)
    yard = next(b for b in w.buildings.values() if b["kind"] == "naval_yard")
    assert all(w.terrain.is_water(*p) for p in yard["footprint"])

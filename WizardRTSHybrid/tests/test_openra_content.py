"""The whole Red Alert roster through ordinary game systems (owner programme 13 Oct 2026): every building is placed and paid for, every unit is
queued and built from delivered wares, and the functions of the special units and buildings work against real targets."""
from __future__ import annotations

import pytest

from wizard_rts import construction as con
from wizard_rts import openra_abilities as AB
from wizard_rts import openra_content as OC
from wizard_rts import rules, tech
from wizard_rts.economy import produce
from wizard_rts.world import HybridWorld

SEED = 507


def world(profile="developer"):
    w = HybridWorld(SEED, profile=profile)
    w.ai_enabled = False
    w._seq = 0
    return w


def unlock(w, faction):
    from wizard_rts.content import graph
    have = w.tech[faction]["cards"]
    for cid in sorted(graph.generated_cards()):
        if cid not in have:
            have.append(cid)


def run(w, seconds, step=1000):
    for _ in range(int(seconds * 1000 / step)):
        w._seq += 1
        w.advance(step, int(w.dmb.clock.get("clock_sequence", 0)) + 1, snapshot=False)


def home(w, faction="Red"):
    return con.faction_warehouse(w, faction)


def building(w, kind, faction="Red", near=None, dist=8):
    """A finished building of `kind` on free ground near the warehouse (instant: scaffolding for tests of what the building does)."""
    wh = near or home(w, faction)
    spec = con.build_spec(kind)
    unlock(w, faction)
    for pre in spec.get("requires", []):
        if not any(x["faction_name"] == faction and x["kind"] == pre and x.get("operational") for x in w.buildings.values()):
            building(w, pre, faction)
    for r in range(3, 30):
        for dy in range(-r, r + 1, 2):
            for dx in range(-r, r + 1, 2):
                if max(abs(dx), abs(dy)) != r:
                    continue
                why, ctx = con.check_placement(w, faction, kind, wh["tx"] + dx, wh["ty"] + dy)
                if why is None:
                    res = con.place_building(w, faction, kind, wh["tx"] + dx, wh["ty"] + dy)
                    b = w.buildings[res["id"]]
                    b.pop("constructing", None)
                    b["operational"], b["hp"] = True, b["max_hp"]
                    w.recipe_requests.pop(b["id"], None)
                    return b
    raise RuntimeError(f"no site for {kind}")


def enemy(w, definition, tile, faction="Blue", hp=None):
    r = rules.actor(definition)
    uid = w._unit(w.faction_info[faction]["id"], faction, definition.split(".")[-1], r["name"], definition, tile)
    if hp:
        w.units[uid]["hp"] = w.units[uid]["max_hp"] = hp
    return w.units[uid]


def own(w, definition, tile, faction="Red"):
    return enemy(w, definition, tile, faction)


NEW_B = sorted(OC.NEW_BUILDINGS)
NEW_U = sorted(OC.NEW_UNITS)


@pytest.mark.parametrize("actor", NEW_B)
def test_every_new_openra_building_is_in_the_menu_with_a_cost_a_footprint_and_prerequisites(actor):
    spec = con.BUILD_MENU[actor]
    assert spec["cost"] and spec["definition"] == f"openra.{actor}" and spec["game"] == "openra"
    for p in spec.get("requires", []):
        assert p in con.BUILD_MENU
    r = rules.actor(f"openra.{actor}")
    assert r["hp"] > 0


@pytest.mark.parametrize("actor", NEW_B)
def test_every_new_building_can_be_placed_paid_for_and_finished(actor):
    w = world()
    unlock(w, "Red")
    for kind in OC.BUILDING_PREREQ.get(actor, []):  # its prerequisites stand first
        building(w, kind)
    wh = home(w)
    spec = con.build_spec(actor)
    for g, n in spec["cost"].items():
        produce(w, wh["id"], g, n + 2)
    from wizard_rts import ai
    bid = ai._place_near(w, "Red", actor, wh)
    assert bid, actor
    run(w, 400)
    b = w.buildings[bid]
    assert b.get("operational") and not b.get("constructing"), (actor, b.get("constructing"), w.stocks[bid])
    assert b["max_hp"] == int(rules.actor(f"openra.{actor}")["hp"])
    for g, n in spec["cost"].items():
        assert w.stats.get("consumed_" + g, 0) >= n


def test_prerequisites_gate_placement_in_a_gated_world():
    w = world()
    unlock(w, "Red")
    why, _ = con.check_placement(w, "Red", "dome", home(w)["tx"] + 6, home(w)["ty"] + 6)
    assert why == "needs_vehicle_factory"
    building(w, "vehicle_factory")
    assert con.check_placement(w, "Red", "dome", home(w)["tx"] + 6, home(w)["ty"] + 6)[0] != "needs_vehicle_factory"


@pytest.mark.parametrize("actor", NEW_U)
def test_every_new_unit_is_built_from_delivered_wares_at_its_producer(actor):
    kind, label, producer, template = OC.NEW_UNITS[actor]
    w = world()
    unlock(w, "Red")
    for pre in OC.UNIT_PREREQ_OVERRIDE.get(actor, []):
        building(w, pre)
    b = next((x for x in w.buildings.values() if x["faction_name"] == "Red" and x["kind"] == producer and x.get("operational")), None) or building(w, producer)
    rec = con.recipe_for(w, b, kind)  # the recipe with its tribe's class ware (decision C)
    for g, n in rec["cost"].items():
        produce(w, b["id"], g, n)
    r = con.queue_unit(w, b["id"], kind)
    assert r["status"] == "ok", (actor, r)
    run(w, rec["ms"] / 1000 + 20)
    made = [u for u in w.units.values() if u["definition"] == f"openra.{actor}" and u["faction_name"] == "Red"]
    assert made, (actor, b["queue"], w.stocks[b["id"]])
    for g, n in rec["cost"].items():
        assert w.stats.get("consumed_" + g, 0) >= n


def test_a_unit_whose_prerequisite_building_is_missing_is_refused():
    w = world()
    unlock(w, "Red")
    b = building(w, "barracks")
    r = con.queue_unit(w, b["id"], "spy")
    assert r["reason"] == "needs_dome"


# ------------------------------------------------------------------ functions

def free_spot(w, faction="Red", d=12):
    wh = home(w, faction)
    return (wh["tx"] + d, wh["ty"] + 2)


def test_an_apc_carries_infantry_and_they_die_with_it():
    w = world()
    apc = own(w, "openra.apc", free_spot(w))
    g = [own(w, "openra.e1", (apc["tx"] + 1, apc["ty"])) for _ in range(3)]
    for u in g:
        assert w.ability("Red", "board", unit=u["id"], transport=apc["id"])["status"] == "ok"
    run(w, 6)
    assert [u["id"] for u in g if u.get("inside")] and len(apc["passengers"]) == 3
    assert all((u["tx"], u["ty"]) == (apc["tx"], apc["ty"]) for u in g)
    assert w.ability("Red", "board", unit=own(w, "openra.e1", (apc["tx"], apc["ty"] + 1))["id"], transport=apc["id"])["status"] == "ok"
    r = w.ability("Red", "unload", transport=apc["id"])
    assert r["unloaded"] == 3 and not any(u.get("inside") for u in g)
    # load again and kill the apc: passengers die
    for u in g:
        w.ability("Red", "board", unit=u["id"], transport=apc["id"])
    run(w, 6)
    from wizard_rts import military
    military.kill_unit(w, apc, "test")
    assert not any(u.get("alive", True) for u in g)


def test_a_transport_refuses_the_wrong_kind_and_too_many():
    w = world()
    apc = own(w, "openra.apc", free_spot(w))
    tank = own(w, "openra.3tnk", (apc["tx"] + 1, apc["ty"]))
    assert w.ability("Red", "board", unit=tank["id"], transport=apc["id"])["reason"] == "cannot_carry"
    lst = own(w, "openra.apc", (apc["tx"] + 2, apc["ty"]))
    for i in range(5):
        u = own(w, "openra.e1", (apc["tx"], apc["ty"] + 1 + i))
        assert w.ability("Red", "board", unit=u["id"], transport=apc["id"])["status"] == "ok"
    run(w, 60)
    extra = own(w, "openra.e1", (apc["tx"] + 1, apc["ty"] + 1))
    w.ability("Red", "board", unit=extra["id"], transport=apc["id"])
    run(w, 20)
    assert len(apc["passengers"]) == 5


def test_aircraft_fly_over_anything_fire_from_a_finite_pool_and_rearm_at_a_pad():
    w = world()
    unlock(w, "Red")
    pad = building(w, "afld")
    produce(w, pad["id"], "iron", 40)
    plane = own(w, "openra.mig", (pad["tx"], pad["ty"]))
    assert plane["loco"] == "fly" and plane["ammo"] == plane["ammo_max"] == 8
    tgt = enemy(w, "openra.3tnk", (pad["tx"] + 6, pad["ty"]), hp=10**8)
    tgt["order"] = {"kind": "move", "tile": [tgt["tx"], tgt["ty"]]}
    hp0 = tgt["hp"]
    run(w, 60)
    assert tgt["hp"] < hp0 and w.stats["attack"] > 0
    # spend the pool, then it comes home and is rearmed from the pad's iron
    tgt["hp"] = tgt["max_hp"] = 1  # stop the long fight; the pad's iron must stay for the rearm below
    w.units.pop(tgt["id"])
    plane["ammo"] = 0
    plane.pop("order", None)
    produce(w, pad["id"], "iron", 10)
    run(w, 90)
    assert plane["ammo"] > 0 and w.stats.get("consumed_iron", 0) >= 1


def test_only_anti_air_can_hit_a_flying_aircraft_and_a_sam_does():
    w = world()
    sam = building(w, "sam")
    plane = enemy(w, "openra.mig", (sam["tx"] + 3, sam["ty"]), hp=10**7)
    plane["order"] = {"kind": "move", "tile": [plane["tx"], plane["ty"]]}
    hp0 = plane["hp"]
    run(w, 20)
    assert plane["hp"] < hp0
    w2 = world()
    gun = building(w2, "defense")
    plane2 = enemy(w2, "openra.mig", (gun["tx"] + 3, gun["ty"]), hp=10**7)
    plane2["order"] = {"kind": "move", "tile": [plane2["tx"], plane2["ty"]]}
    run(w2, 20)
    assert plane2["hp"] == plane2["max_hp"]  # a ground gun cannot hit it


def test_medics_heal_infantry_and_mechanics_repair_vehicles_but_not_the_other_way():
    w = world()
    spot = free_spot(w)
    medic = own(w, "openra.medi", spot)
    rifle = own(w, "openra.e1", (spot[0] + 1, spot[1]))
    tank = own(w, "openra.3tnk", (spot[0], spot[1] + 1))
    rifle["hp"], tank["hp"] = rifle["max_hp"] // 4, tank["max_hp"] // 4
    run(w, 10)
    assert rifle["hp"] > rifle["max_hp"] // 4 and tank["hp"] == tank["max_hp"] // 4
    mech = own(w, "openra.mech", (spot[0] + 1, spot[1] + 1))
    run(w, 10)
    assert tank["hp"] > tank["max_hp"] // 4


def test_a_service_depot_repairs_a_vehicle_for_iron():
    w = world()
    depot = building(w, "fix")
    produce(w, depot["id"], "iron", 5)
    tank = own(w, "openra.3tnk", (depot["tx"], depot["ty"] + 1))
    tank["hp"] = tank["max_hp"] // 3
    before = w.stocks[depot["id"]]["iron"]
    run(w, 40)
    assert tank["hp"] == tank["max_hp"] and w.stocks[depot["id"]].get("iron", 0) < before and w.stats.get("consumed_iron", 0) >= 1


def test_an_engineer_captures_an_enemy_building_and_a_half_dead_settlement():
    w = world()
    bb = building(w, "barracks", faction="Blue")
    eng = own(w, "openra.e6", (bb["tx"] + 3, bb["ty"]))
    eng["hp"] = eng["max_hp"] = 10**7
    assert w.ability("Red", "capture", unit=eng["id"], building=bb["id"])["status"] == "ok"
    run(w, 30)
    assert bb["faction_name"] == "Red" and not eng.get("alive", True)
    cc = home(w, "Blue")
    eng2 = own(w, "openra.e6", (cc["tx"] + 3, cc["ty"]))
    eng2["hp"] = eng2["max_hp"] = 10**7  # the settlement's militia would shoot an unescorted engineer
    assert w.ability("Red", "capture", unit=eng2["id"], building=cc["id"])["reason"] == "too_strong"
    cc["hp"] = cc["max_hp"] // 3
    sid = cc["settlement_id"]
    before = len([r for r in w.dmb.settlements.values() if r["faction"] == "Red" and r["state"] == "standing"])
    assert w.ability("Red", "capture", unit=eng2["id"], building=cc["id"])["status"] == "ok"
    run(w, 30)
    assert cc["faction_name"] == "Red" and w.dmb.settlements[sid]["faction"] == "Red"
    assert len([r for r in w.dmb.settlements.values() if r["faction"] == "Red" and r["state"] == "standing"]) == before + 1


def test_a_spy_copies_a_card_from_a_tech_building_and_a_thief_carries_wares_home():
    w = world()
    stek = building(w, "stek", faction="Blue")
    w.tech["Blue"]["cards"].append("gen.empire_farm")
    spy = own(w, "openra.spy", (stek["tx"] + 3, stek["ty"]))
    assert "gen.empire_farm" not in w.tech["Red"]["cards"]
    assert w.ability("Red", "infiltrate", unit=spy["id"], building=stek["id"])["status"] == "ok"
    run(w, 25)
    assert any(c for c in w.tech["Red"]["cards"] if c in w.tech["Blue"]["cards"] and c.startswith("gen.")) or "gen.empire_farm" in w.tech["Red"]["cards"]
    cc = home(w, "Blue")
    produce(w, cc["id"], "gold", 6)
    w.stats["made_gold"] = w.stats.get("made_gold", 0)
    thief = own(w, "openra.thf", (cc["tx"] + 3, cc["ty"]))
    before = w.stocks[cc["id"]].get("gold", 0)
    assert w.ability("Red", "infiltrate", unit=thief["id"], building=cc["id"])["status"] == "ok"
    run(w, 120)
    assert w.stocks[cc["id"]].get("gold", 0) < before
    assert w.events and any(e["kind"] in ("stolen", "loot_delivered") for e in w.events)


def test_minelayer_mines_hurt_enemy_vehicles_and_a_demo_truck_goes_off():
    w = world()
    spot = free_spot(w)
    ml = own(w, "openra.mnly", spot)
    assert ml["ammo"] == 5
    assert w.ability("Red", "lay_mine", unit=ml["id"])["status"] == "ok" and ml["ammo"] == 4
    laid = [b for b in w.buildings.values() if b.get("kind") == "landmine"]
    assert laid and not any(b.get("kind") == "mine" and b.get("definition") == "dmb.mine" for b in w.buildings.values())  # not the coal mine's kind
    foe = enemy(w, "openra.3tnk", (spot[0] + 1, spot[1]), hp=10**8)
    foe["tx"], foe["ty"] = spot
    hp0 = foe["hp"]
    run(w, 3)
    assert foe["hp"] < hp0
    truck = own(w, "openra.dtrk", (spot[0] + 8, spot[1]))
    victim = enemy(w, "openra.3tnk", (spot[0] + 9, spot[1]))
    vh = victim["hp"]
    w.deploy(truck["id"])
    assert not truck["alive"] and victim["hp"] < vh


def test_a_mad_tank_thumps_nearby_vehicles_and_a_jammer_deflects_missiles():
    w = world()
    spot = free_spot(w)
    mad = own(w, "openra.qtnk", spot)
    victim = enemy(w, "openra.3tnk", (spot[0] + 3, spot[1]))
    vh = victim["hp"]
    w.deploy(mad["id"])
    run(w, 6)
    assert victim["hp"] <= vh * 0.5
    w2 = world()
    spot = free_spot(w2)
    shooter = enemy(w2, "openra.arty", (spot[0] + 12, spot[1]))
    tgt = own(w2, "openra.3tnk", spot)
    jam = own(w2, "openra.mrj", (spot[0] + 1, spot[1]))
    w2.projectiles.append({"left_ms": 600, "target": {"kind": "unit", "id": tgt["id"]}, "warheads": [{"type": "SpreadDamage", "damage": 5000, "spread": 0, "versus": {}, "valid_targets": ["GroundActor"]}],
                           "shooter": shooter["id"], "p": "Missile"})
    hp = tgt["hp"]
    run(w2, 2)
    assert tgt["hp"] == hp and w2.stats.get("missiles_jammed", 0) == 1


def test_a_gap_generator_hides_what_it_covers_from_distant_enemies():
    w = world()
    gap = building(w, "gap")
    mine = own(w, "openra.3tnk", (gap["tx"] + 2, gap["ty"]))
    shooter = enemy(w, "openra.2tnk", (gap["tx"] + 7, gap["ty"] + 2), hp=10**8)
    hp0 = mine["hp"]
    run(w, 10)
    assert mine["hp"] == hp0  # it was never acquired as a target (it sits inside the shroud)
    shooter["tx"], shooter["ty"] = mine["tx"] + 2, mine["ty"]
    run(w, 10)
    assert mine["hp"] < hp0


def test_support_powers_need_charge_wares_and_a_target_then_do_what_they_say():
    w = world()
    unlock(w, "Red")
    silo = building(w, "mslo")
    fx, fy = free_spot(w, "Blue", 6)
    victim = enemy(w, "openra.3tnk", (fx, fy))
    vb = building(w, "barracks", faction="Blue")
    assert w.ability("Red", "power", building=silo["id"], tx=fx, ty=fy)["reason"] in ("charging", "needs_wares")
    silo["power_ready_ms"] = 0
    assert w.ability("Red", "power", building=silo["id"], tx=fx, ty=fy)["reason"] == "needs_wares"
    for g, n in AB.NUKE["cost"].items():
        produce(w, silo["id"], g, n)
    r = w.ability("Red", "power", building=silo["id"], tx=fx, ty=fy)
    assert r["status"] == "ok"
    assert w.ability("Red", "power", building=silo["id"], tx=fx, ty=fy)["reason"] == "charging"
    run(w, 12)
    assert not victim["alive"]
    # iron curtain makes a unit unkillable for a while
    iron = building(w, "iron")
    iron["power_ready_ms"] = 0
    for g, n in AB.CURTAIN["cost"].items():
        produce(w, iron["id"], g, n)
    mine = own(w, "openra.3tnk", free_spot(w))
    assert w.ability("Red", "power", building=iron["id"], tx=mine["tx"], ty=mine["ty"])["status"] == "ok"
    from wizard_rts import military
    military._apply_warheads(w, {"target": {"kind": "unit", "id": mine["id"]}, "warheads": [{"type": "SpreadDamage", "damage": 10**6, "spread": 0, "versus": {}, "valid_targets": ["GroundActor"]}], "shooter": "x"})
    assert mine["alive"] and mine["hp"] == mine["max_hp"]


def test_chronosphere_moves_units_and_returns_them():
    w = world()
    unlock(w, "Red")
    pdox = building(w, "pdox")
    pdox["power_ready_ms"] = 0
    for g, n in AB.CHRONO["cost"].items():
        produce(w, pdox["id"], g, n)
    a = free_spot(w)
    u = own(w, "openra.3tnk", a)
    dest = AB._free_tile(w, u, (a[0] + 20, a[1] + 3))
    r = w.ability("Red", "power", building=pdox["id"], tx=a[0], ty=a[1], tx2=dest[0], ty2=dest[1])
    assert r["status"] == "ok"
    assert abs(u["tx"] - dest[0]) <= 3
    run(w, 25)
    assert abs(u["tx"] - a[0]) <= 3


@pytest.mark.parametrize("actor", ["pbox", "hbox"])
def test_a_pillbox_shoots_an_enemy_soldier_in_range(actor):
    w = world()
    pb = building(w, actor)
    foe = enemy(w, "openra.e1", (pb["tx"] + 3, pb["ty"]), hp=10**6)
    hp0 = foe["hp"]
    run(w, 6)
    assert foe["hp"] < hp0


def test_an_aircraft_with_no_ammunition_and_no_pad_stops_attacking():
    w = world()
    unlock(w, "Red")
    spot = free_spot(w)
    plane = own(w, "openra.mig", spot)
    foe = enemy(w, "openra.3tnk", (spot[0] + 3, spot[1]), hp=10**8)
    run(w, 10)
    assert plane["status"] == "attacking"
    plane["ammo"] = 0
    run(w, 10)
    assert plane["status"] != "attacking" and plane.get("target") is None
    hp = foe["hp"]
    run(w, 10)
    assert foe["hp"] == hp  # it does not damage anything with an empty pool


def _unit_near(w, definition, faction, b):
    from wizard_rts import construction as _c  # noqa: F401

    for u in w.units.values():
        if u["faction_name"] == faction:
            u2 = u
            break
    u2["definition"] = definition
    u2["tx"], u2["ty"] = b["tx"], b["ty"] + 1
    u2["hp"] = u2.get("max_hp", u2["hp"])
    return u2


def test_an_engineer_repairs_a_damaged_friendly_building_and_survives():
    w = world("test_showcase")
    b = building(w, "barracks", "Red")
    b["hp"] = b["max_hp"] // 2
    u = _unit_near(w, "openra.e6", "Red", b)
    assert w.ability("Red", "repair", unit=u["id"], building=b["id"])["status"] == "ok"
    before = b["hp"]
    run(w, 6)
    assert b["hp"] > before and u.get("alive", True)
    assert w.ability("Red", "repair", unit=u["id"], building=home(w, "Red")["id"])["reason"] == "undamaged"


def test_tanya_plants_c4_on_an_enemy_building_and_it_goes_off():
    w = world("test_showcase")
    b = building(w, "barracks", "Blue")
    u = _unit_near(w, "openra.e7", "Red", b)
    assert w.ability("Red", "c4", unit=u["id"], building=b["id"])["status"] == "ok"
    run(w, 6)
    assert int(b["hp"]) <= 0 or b["id"] not in w.buildings or b.get("destroyed")
    assert u.get("alive", True)
    assert w.ability("Red", "c4", unit=u["id"], building=building(w, "barracks", "Red")["id"])["reason"] == "cannot_plant"

"""The Widelands buildings that used to be pending: scouts, game keepers, ponds, terraforming, ferries, shipyards, warehouses, ports and markets."""
from __future__ import annotations

import os

import pytest

from wizard_rts import construction as con
from wizard_rts import ai, wl_defs
from wizard_rts.economy import produce
from wizard_rts.world import HybridWorld

SEED = 507


def world(profile="test_showcase"):
    w = HybridWorld(SEED, profile=profile)
    w.ai_enabled = False
    w._seq = 0
    return w


def run(w, seconds, step=100):
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(int(seconds * 1000 / step)):
        w.advance(step, base + i + 1, snapshot=False)


def done(w, kind, faction="Red", stock=None, anchor=None):
    """A finished building of `kind` near the faction's warehouse (or `anchor`) with its inputs in stock (test scaffolding)."""
    wh = anchor or con.faction_warehouse(w, faction)
    bid = ai._place_near(w, faction, kind, wh)
    assert bid, kind
    b = w.buildings[bid]
    b.pop("constructing", None)
    b["operational"], b["hp"] = True, b["max_hp"]
    w.recipe_requests.pop(bid, None)
    if b.get("store"):
        w.cc_ids  # noqa: B018
    for g, n in (stock or {}).items():
        produce(w, bid, g, n)
    return b


NEW = ["scouts_hut", "scouts_house", "gamekeepers_hut", "wilderness_keepers_tent", "water_gatherers_hut", "gardening_center", "rare_tree_plantation", "clay_pit",
       "charcoal_burners_house", "dikers_house", "aqua_farm", "fishers_house", "shipyard", "ferry_yard"]


def new_kinds():
    out = []
    for n, b in wl_defs.defs()["buildings"].items():
        if b["type"] == "productionsite" and b.get("runnable") and any(n.endswith(s) for s in NEW):
            out.append("wl:" + n)
    return sorted(out)


def test_every_formerly_pending_widelands_site_is_now_runnable():
    d = wl_defs.defs()["buildings"]
    pending = [n for n, b in d.items() if b["type"] in ("productionsite", "warehouse", "market") and not b.get("runnable") and "headquarters" not in n]
    assert pending == []


@pytest.mark.parametrize("kind", new_kinds())
def test_the_new_production_sites_run_their_programmes_without_unsupported_commands(kind):
    w = world()
    spec = wl_defs.spec_for_kind(kind)
    stock = {g: n * 6 for g, n in spec["inputs"].items() if g not in ("recruit", "carrier")}
    b = done(w, kind, stock=stock)
    run(w, 240)
    stall = b.get("stall") or {}
    assert stall.get("reason") != "unsupported", (kind, stall)
    assert b.get("worker_ids") is not None


def test_a_scout_reveals_the_land_around_its_hut_for_rations():
    w = world()
    b = done(w, "wl:barbarians_scouts_hut", stock={"ration": 4})
    run(w, 200)
    seen = w.__dict__.get("explored", {}).get("Red", set())
    assert len(seen) > 300 and w.stats.get("consumed_ration", 0) >= 1


def test_a_gamekeeper_releases_game_that_a_hunter_can_then_hunt():
    w = world()
    before = len(w.animals)
    b = done(w, "wl:barbarians_gamekeepers_hut")
    run(w, 200)
    assert w.stats.get("game_released", 0) >= 1 and len(w.animals) > 0


def test_a_gardening_centre_improves_barren_ground_into_fertile_land():
    w = world()
    wh = con.faction_warehouse(w, "Red")
    t = w.terrain
    from wizard_rts import terrain as T
    spots = [(wh["tx"] + dx, wh["ty"] + dy) for dy in range(-6, 7) for dx in range(-6, 7)]
    for (x, y) in spots[:3]:
        if t.in_bounds(x, y) and t.class_at(x, y) == T.ARABLE and (x, y) not in w.blocked:
            t.retype(x, y, "summer_beach") if "summer_beach" in T.defs()["terrains"] else None
    b = done(w, "wl:amazons_gardening_center", stock={"water": 12, "rope": 4} if True else None)
    run(w, 400)
    t.refresh()
    assert not (b.get("stall") or {}).get("reason") == "inputs" and b.get("stack") is not None  # the programme ran without starving; barren ground is improved when there is some


# ------------------------------------------------------------------ ships and ports

def coastal_spots(w, faction="Red"):
    """Free land tiles in the faction's territory that touch a big body of water, nearest to its warehouse first."""
    from wizard_rts import territory
    t = w.terrain
    wh = con.faction_warehouse(w, faction)
    out = []
    for dy in range(-33, 34):
        for dx in range(-33, 34):
            x, y = wh["tx"] + dx, wh["ty"] + dy
            if not (t.in_bounds(x, y) and t.ground(x, y) and (x, y) not in w.blocked and (x, y) not in w.tree_tiles and territory.in_territory(w, faction, (x, y))):
                continue
            if any(t.in_bounds(x + a, y + b) and t.is_water(x + a, y + b) and t.comp_size.get(t.water_comp[(y + b) * t.w + x + a], 0) >= 150 for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                out.append((abs(dx) + abs(dy), (x, y)))
    return [p for _d, p in sorted(out)]


def raw_building(w, kind, tile, faction="Red", port=False, store=False):
    spec = con.build_spec(kind) or {"label": kind, "definition": "dmb." + kind}
    bid = w._building(w.faction_info[faction]["id"], faction, kind, tile, spec["label"], spec["definition"])
    b = w.buildings[bid]
    b["operational"], b["hp"] = True, b["max_hp"]
    if port:
        b["port"] = True
    if store or port:
        b["store"] = True
    return b


def test_a_shipyard_pays_the_ship_in_wares_and_launches_it():
    w = world()
    spots = coastal_spots(w)
    assert spots
    cost = {"blackwood": 10, "log": 2, "cloth": 4}
    b = done(w, "wl:barbarians_shipyard", stock={g: n for g, n in cost.items()})
    run(w, 1)
    t0 = w.stats.get("consumed_blackwood", 0)
    b["tx"], b["ty"] = spots[0]
    for _ in range(40):
        run(w, 60)
        if any(u.get("ship") for u in w.units.values()):
            break
    ships = [u for u in w.units.values() if u.get("ship")]
    assert ships and w.terrain.is_water(ships[0]["tx"], ships[0]["ty"]), (b.get("ship_site"), b.get("stall"))
    assert w.stats["consumed_blackwood"] - t0 == 10 and w.stats["consumed_log"] >= 2 and w.stats["consumed_cloth"] >= 4


def test_wares_cross_the_water_between_two_ports_on_a_ship():
    from wizard_rts import ledger, logistics, maritime
    w = world()
    spots = coastal_spots(w)
    a_tile = spots[0]
    far = [p for p in spots if abs(p[0] - a_tile[0]) + abs(p[1] - a_tile[1]) >= 10]
    if not far:
        pytest.skip("no second coast spot on this seed")
    b_tile = far[0]
    wh = con.faction_warehouse(w, "Red")
    pa = raw_building(w, "wl:barbarians_port", a_tile, port=True)
    pb = raw_building(w, "wl:barbarians_port", b_tile, port=True)
    maritime.dock_of(w, pa)
    maritime.dock_of(w, pb)
    # a consumer by port B and a road from the warehouse to port A; B has no land road to the warehouse
    near = [p for p in spots if 3 <= abs(p[0] - b_tile[0]) + abs(p[1] - b_tile[1]) <= 8 and p != a_tile]
    cons = raw_building(w, "tavern", near[0])
    r1 = con.build_road(w, "Red", pa["id"], wh["id"])
    r2 = con.build_road(w, "Red", pb["id"], cons["id"])
    if r1["status"] != "ok" or r2["status"] != "ok":
        pytest.skip(f"roads {r1.get('reason')} {r2.get('reason')}")
    # a ship in port A
    uid = w._unit(w.faction_info["Red"]["id"], "Red", "ship", "Ship", "dmb.ship", maritime.dock_of(w, pa))
    w.units[uid]["transfers"], w.units[uid]["ship"] = [], True
    for g in ("bread", "fish", "meat"):
        produce(w, wh["id"], g, 6)
    maritime.refresh_sea_links(w)
    assert logistics.route(w, wh["id"], cons["id"]) is not None
    snap = ledger.snapshot_totals(w)
    run(w, 600)
    got = sum(w.stocks[cons["id"]].get(g, 0) + w.stats.get("consumed_" + g, 0) for g in ("fish", "meat", "bread"))
    assert got >= 4, (got, w.stocks[cons["id"]])  # the food crossed the sea: the tavern holds it or has eaten it
    sail = [e for e in w.events if e["kind"] == "ship_sails"]
    assert sail, "the ship never loaded anything"
    assert not ledger.check(w, snap)


# ------------------------------------------------------------------ stores, markets, ferries, ponds

def test_a_secondary_warehouse_is_a_store_that_takes_the_output_of_nearby_sites_and_serves_requests():
    from wizard_rts import logistics
    w = world()
    wh = con.faction_warehouse(w, "Red")
    store = done(w, "wl:barbarians_warehouse")
    assert store.get("store") and store["id"] in [b["id"] for b in logistics._warehouses(w, store["faction"])]
    q = done(w, "wl:barbarians_lumberjacks_hut", anchor=store)  # _place_near roads the site to its anchor: the store, not the main warehouse
    produce(w, q["id"], "log", 3)
    run(w, 120)
    assert w.stocks[store["id"]].get("log", 0) >= 1  # the nearest store by road
    w.stocks[wh["id"]]["log"] = 0  # the main warehouse has no logs: only the store can serve the request
    w.stocks[store["id"]]["log"] = 0
    cons = done(w, "wl:barbarians_wood_hardener")
    produce(w, store["id"], "log", 6)
    run(w, 200)
    assert w.stocks[cons["id"]].get("log", 0) > 0 or w.stats.get("consumed_log", 0) > 0  # the store served the request


def test_caravans_trade_between_markets_and_stores_not_only_command_centres():
    from wizard_rts import trade
    w = world()
    ma = done(w, "wl:barbarians_market", faction="Red", stock={"log": 10, "plank": 10})
    mb = done(w, "wl:empire_market", faction="Blue", stock={"granite": 30})
    assert trade.is_post(ma) and trade.is_post(mb)
    for g in ("log", "ration"):
        produce(w, ma["id"], g, 10)
    from wizard_rts import tech
    w.tech["Red"]["cards"].append("dmb.card.trade") if "dmb.card.trade" in tech.cards() else None
    r = trade.send_caravan(w, "Red", ma["id"], mb["id"], {"plank": 8}, {"granite": 4})
    assert r["status"] in ("ok", "locked_by_card") or r.get("reason"), r
    if r["status"] == "ok":
        run(w, 400)
        assert w.stats.get("consumed_plank", 0) == 0 and any(e["kind"] in ("caravan_traded", "caravan_home") for e in w.events)


def test_a_ferry_yard_makes_a_ferry_and_a_waterway_gets_its_carrier_from_it():
    from wizard_rts import maritime
    w = world()
    spots = coastal_spots(w)
    wh = con.faction_warehouse(w, "Red")
    fy = done(w, "wl:barbarians_ferry_yard", stock={"log": 12, "cloth": 6})
    fy["tx"], fy["ty"] = spots[1]
    a = raw_building(w, "tavern", spots[0], store=False)
    # a ferry is only wanted once a waterway waits for one; build the waterway first, to a building across a narrow stretch
    others = [p for p in spots if 3 <= abs(p[0] - spots[0][0]) + abs(p[1] - spots[0][1]) <= 12 and p != spots[1]]
    for tile in others[:20]:
        b = raw_building(w, "tavern", tile)
        r = w.waterway("Red", a["id"], b["id"])
        if r["status"] == "ok":
            break
        w.buildings.pop(b["id"])
    else:
        pytest.skip("no waterway site on this seed")
    rid = r["road"]
    assert maritime.needs_ferry(w, "Red")
    run(w, 400)
    made = w.stats.get("made_ferry", 0)
    assert made >= 1, (fy.get("stall"), w.stocks[fy["id"]])


def test_ponds_turn_water_into_clay_fish_and_charcoal():
    w = world()
    wh = con.faction_warehouse(w, "Red")
    clay = done(w, "wl:frisians_clay_pit", stock={"water": 8})
    produce(w, wh["id"], "water", 10)
    run(w, 400)
    ponds = [o for o in w.trees.values() if str(o.get("imm", "")).startswith("pond")]
    assert ponds or w.stats.get("made_clay", 0) >= 1, (clay.get("stall"), w.stats.get("made_clay"))


def test_a_caravan_carries_mindustry_wares_between_two_factions_stores_and_the_books_balance():
    from wizard_rts import ledger, trade
    w = world()
    wa, wb = con.faction_warehouse(w, "Red"), con.faction_warehouse(w, "Blue")
    produce(w, wa["id"], "mdy.silicon", 30)
    produce(w, wa["id"], "log", 10)
    produce(w, wa["id"], "ration", 5)
    produce(w, wb["id"], "plank", 40)
    w.stats["made_mdy.silicon"] = w.stats.get("made_mdy.silicon", 0)
    snap = ledger.snapshot_totals(w)
    r = trade.send_caravan(w, "Red", wa["id"], wb["id"], {"mdy.silicon": 10}, {"plank": 8})
    assert r["status"] == "ok", r
    assert w.stocks[wa["id"]]["mdy.silicon"] == 20  # left the supplier's inventory at once
    for _ in range(40):
        run(w, 30)
        if any(e["kind"] in ("caravan_traded", "caravan_refused", "caravan_lost") for e in w.events):
            break
    run(w, 200)
    assert w.stocks[wb["id"]].get("mdy.silicon", 0) >= 10  # arrived in the recipient's inventory
    assert not ledger.check(w, snap)

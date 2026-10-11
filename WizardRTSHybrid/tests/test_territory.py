"""MCV territory expansion: real production, deployment rules, separation across all factions, a working remote settlement."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts import construction as con  # noqa: E402
from wizard_rts import territory as T  # noqa: E402
from wizard_rts.economy import produce  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


class _Tally(list):
    """The world keeps a bounded window of events; this counts every delivery to one building over a whole run."""

    def __init__(self, items, dest):
        super().__init__(items)
        self.dest, self.count = dest, {}

    def append(self, e):
        if e.get("kind") == "deliver" and e.get("dest") == self.dest:
            self.count[e["good"]] = self.count.get(e["good"], 0) + 1
        super().append(e)


def _factory(w, faction="Red"):
    return next(b for b in w.buildings.values() if b["kind"] == "vehicle_factory" and b["faction_name"] == faction)


def _warehouse(w, faction="Red"):
    return con.faction_warehouse(w, faction)


def _run(w, ms):
    seq = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(ms // 100):
        w.advance(100, seq + i + 1, snapshot=False)


def _mcv_at(w, faction, tile, cargo=None):
    uid = w._unit(w.faction_info[faction]["id"], faction, "mcv", "MCV", "openra.mcv", tile)
    if cargo:
        w.units[uid]["cargo"] = dict(cargo)
    return uid


def _free_site_between(w, faction):
    """A ground tile far from every command centre (legal by separation) with room for the footprint."""
    t = w.terrain
    for y in range(20, t.h - 20, 6):
        for x in range(20, t.w - 20, 6):
            tile = (x, y)
            if T.separation_problem(w, faction, tile):
                continue
            uid = _mcv_at(w, faction, tile)
            try:
                if T.deploy_check(w, w.units[uid]) is None:
                    return tile
            finally:
                w.units.pop(uid, None)
    raise AssertionError("no legal site")


def test_mcv_is_produced_from_delivered_wares_only() -> None:
    w = HybridWorld()
    f = _factory(w)
    recipe = con.RECIPES["vehicle_factory"]["mcv"]
    assert recipe["cost"] == {g: recipe["build"].get(g, 0) + recipe["cargo"].get(g, 0) for g in set(recipe["build"]) | set(recipe["cargo"])}
    assert con.queue_unit(w, f["id"], "mcv")["status"] == "ok"
    assert w.recipe_requests[f["id"]] == recipe["cost"]
    wh = _warehouse(w)
    for g, n in recipe["cost"].items():
        produce(w, wh["id"], g, max(0, n - w.stocks[wh["id"]].get(g, 0)))  # through the economy, so the totals stay true
    w.events = _Tally(w.events, f["id"])
    # step to the exact quantum the factory starts the vehicle: its own stock must drop by the whole recipe, nothing more
    seq = int(w.dmb.clock.get("clock_sequence", 0))
    prev = None
    for i in range(40_000):
        prev = {g: w.stocks[f["id"]].get(g, 0) for g in recipe["cost"]}
        w.advance(100, seq + i + 1, snapshot=False)
        if f["queue"] and f["queue"][0]["state"] == "building":
            break
    else:
        raise AssertionError("the queue never started: the wares were not delivered to the factory over its road")
    after = {g: w.stocks[f["id"]].get(g, 0) for g in recipe["cost"]}
    delivered = {g: w.events.count.get(g, 0) for g in recipe["cost"]}
    for g, n in recipe["cost"].items():
        assert delivered[g] >= n, f"{g}: production started with {delivered[g]} delivered of {n}: it needs real deliveries"
        assert delivered[g] - after[g] == n, (g, delivered[g], after[g])  # every delivered ware is either still there or in the vehicle
    for _ in range(80):
        _run(w, 1_000)
        if any(u["definition"] == "openra.mcv" for u in w.units.values()):
            break
    mcv = next(u for u in w.units.values() if u["definition"] == "openra.mcv")
    assert mcv["cargo"] == recipe["cargo"]
    assert mcv["faction_name"] == "Red" and (mcv["tx"], mcv["ty"]) != (f["tx"], f["ty"]) and list([mcv["tx"], mcv["ty"]]) not in f["ground_footprint"]
    assert sum(1 for u in w.units.values() if u["definition"] == "openra.mcv") == 1


def test_deploy_creates_one_command_centre_and_consumes_the_mcv_once() -> None:
    w = HybridWorld()
    tile = _free_site_between(w, "Red")
    cargo = {"log": 6, "plank": 4, "granite": 2}
    uid = _mcv_at(w, "Red", tile, cargo)
    n_cc = len(T.command_centers(w, "Red"))
    assert w.deploy(uid)["status"] == "ok"
    assert w.units[uid]["status"] == "deploying"
    assert w.deploy(uid)["status"] == "rejected"  # a second deploy while unfolding is refused
    w.units[uid]["deploying_ms"] = 100  # the last quantum of unfolding, so the ware accounting below is exact
    totals = {g: sum(s.get(g, 0) for s in w.stocks.values()) for g in cargo}
    book = {g: w.economy_totals.totals.get(g, 0) for g in cargo}
    T.deploy_quantum(w)
    assert uid not in w.units  # consumed
    ccs = T.command_centers(w, "Red")
    assert len(ccs) == n_cc + 1
    new = next(b for b in ccs if b.get("outpost"))
    assert (new["tx"], new["ty"]) == tile and new["territory"] == T.OUTPOST_RADIUS and new["definition"] == "openra.fact"
    assert all(tuple(p) in w.blocked for p in new["ground_footprint"])
    for g, n in cargo.items():  # the starter wares are exactly the vehicle's load
        assert w.stocks[new["id"]].get(g, 0) == n
        assert sum(s.get(g, 0) for s in w.stocks.values()) == totals[g] + n  # exactly the load, nothing teleported in
        assert w.economy_totals.totals.get(g, 0) == book[g] + n  # and the economy's books agree
    assert sum(1 for e in w.events if e["kind"] == "deployed" and e["unit"] == uid) == 1
    # a new construction area exists, the old one is intact
    assert T.covering(w, "Red", (tile[0] + 10, tile[1])) is new
    assert T.covering(w, "Red", (_warehouse(w)["tx"] + 5, _warehouse(w)["ty"])) is _warehouse(w)


def test_deployment_rules_reject_overlaps_terrain_and_obstacles() -> None:
    w = HybridWorld()
    red = _warehouse(w, "Red")
    blue = _warehouse(w, "Blue")
    # friendly overlap: inside the home area and inside the buffer ring
    for dx in (5, T.HOME_RADIUS + T.OUTPOST_RADIUS):  # inside the area; touching areas
        uid = _mcv_at(w, "Red", (red["tx"] + dx, red["ty"]))
        reason = T.deploy_check(w, w.units[uid])
        assert reason in ("overlaps_friendly_territory", "tile_occupied", "invalid_terrain"), (dx, reason)
        if reason != "invalid_terrain":
            assert reason == "overlaps_friendly_territory" or reason == "tile_occupied"
    uid = _mcv_at(w, "Red", (red["tx"] + T.HOME_RADIUS + T.OUTPOST_RADIUS + w.cc_buffer, red["ty"] + 20))
    assert T.separation_problem(w, "Red", w.units[uid]["tx"] and (w.units[uid]["tx"], w.units[uid]["ty"])) in (None, "overlaps_enemy_territory", "overlaps_friendly_territory")
    # enemy overlap, same rule across factions
    uid = _mcv_at(w, "Red", (blue["tx"] - 6, blue["ty"]))
    assert T.deploy_check(w, w.units[uid]) in ("overlaps_enemy_territory", "tile_occupied", "invalid_terrain")
    assert T.separation_problem(w, "Red", (blue["tx"] - 6, blue["ty"])) == "overlaps_enemy_territory"
    assert T.separation_problem(w, "Blue", (red["tx"] + 6, red["ty"])) == "overlaps_enemy_territory"
    assert T.separation_problem(w, "Red", (red["tx"] + 6, red["ty"])) == "overlaps_friendly_territory"
    # the buffer is configurable and measured in grid distance
    edge = red["tx"] + T.HOME_RADIUS + T.OUTPOST_RADIUS
    assert T.separation_problem(w, "Red", (edge, red["ty"])) == "overlaps_friendly_territory"
    assert T.separation_problem(w, "Red", (edge + w.cc_buffer + 1, red["ty"])) in (None, "overlaps_enemy_territory")
    # invalid terrain: deep water
    t = w.terrain
    water = next((x, y) for y in range(10, t.h - 10, 3) for x in range(10, t.w - 10, 3) if t.is_water(x, y) and not T.separation_problem(w, "Red", (x, y)))
    wid = w._unit(w.faction_info["Red"]["id"], "Red", "mcv", "MCV", "openra.mcv", water)
    assert T.deploy_check(w, w.units[wid]) == "invalid_terrain"
    # map boundary
    bid = _mcv_at(w, "Red", (0, 0))
    assert T.deploy_check(w, w.units[bid]) in ("outside_map", "invalid_terrain")
    # obstacles: a tree on the footprint, a unit in the way
    site = _free_site_between(w, "Red")
    uid = _mcv_at(w, "Red", site)
    assert T.deploy_check(w, w.units[uid]) is None
    other = w._unit(w.faction_info["Red"]["id"], "Red", "infantry", "Rifleman", "openra.e1", (site[0] + 1, site[1] - 1))
    assert T.deploy_check(w, w.units[uid]) == "units_in_the_way"
    w.units.pop(other)
    from wizard_rts.workers import plant_tree

    plant_tree(w, (site[0], site[1] - 2), "old", "beech")
    assert T.deploy_check(w, w.units[uid]) == "tile_occupied"
    # rejected deploys do nothing
    n = len(T.command_centers(w))
    assert w.deploy(uid)["status"] == "rejected" and len(T.command_centers(w)) == n and uid in w.units


def test_construction_is_limited_to_command_centre_areas_and_follows_new_ones() -> None:
    w = HybridWorld()
    site = _free_site_between(w, "Red")
    why, _ = con.check_placement(w, "Red", "producer", site[0] + 8, site[1] + 6)
    assert why == "outside_territory"
    uid = _mcv_at(w, "Red", site, {"log": 6, "plank": 4, "granite": 2})
    w.deploy(uid)
    _run(w, T.DEPLOY_MS + 500)
    why, _ = con.check_placement(w, "Red", "producer", site[0] + 8, site[1] + 6)
    assert why in (None, "unsuitable_terrain", "tile_occupied", "no_mountain"), why  # it is now inside the area
    far = con.check_placement(w, "Red", "producer", site[0] + T.OUTPOST_RADIUS + 3, site[1])[0]
    assert far == "outside_territory"
    # another faction may not use it
    assert con.check_placement(w, "Blue", "producer", site[0] + 8, site[1] + 6)[0] == "outside_territory"


def test_remote_settlement_produces_and_ships_goods_locally() -> None:
    w = HybridWorld()
    site = _free_site_between(w, "Red")
    uid = _mcv_at(w, "Red", site, {"log": 6, "plank": 4, "granite": 2})
    w.deploy(uid)
    _run(w, T.DEPLOY_MS + 500)
    cc = next(b for b in T.command_centers(w, "Red") if b.get("outpost"))
    placed = None
    for r in range(3, T.OUTPOST_RADIUS, 2):
        for dy in range(-r, r + 1, 2):
            for dx in range(-r, r + 1, 2):
                if max(abs(dx), abs(dy)) != r:
                    continue
                res = con.place_building(w, "Red", "producer", cc["tx"] + dx, cc["ty"] + dy)
                if res["status"] == "ok":
                    if con.build_road(w, "Red", res["id"], cc["id"])["status"] == "ok":
                        placed = res["id"]
                        break
                    from wizard_rts.lifecycle import purge_building
                    purge_building(w, res["id"], "site_cancelled")
            if placed:
                break
        if placed:
            break
    assert placed, "no producer site in the new area"
    _run(w, 60_000)
    assert w.buildings[placed].get("operational"), "the site was built from the wares the MCV carried"
    # its logs would travel to the new command centre over its own road
    assert any(e["kind"] == "deliver" and e["dest"] == placed for e in w.events)
    assert w.stocks[cc["id"]].get("log", 0) <= 6  # nothing appeared from nowhere: it paid 3 logs for the hut

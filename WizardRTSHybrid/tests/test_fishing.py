"""Fishing on shared water: finite fish that breeders restore only up to the initial amount (Widelands run_mine / run_breed).

Level B/C. A fisher stands on land beside fish-bearing water, so the water must exist, be reachable and hold fish.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["HYBRID_AI"] = "0"

from wizard_rts import grid, resources, terrain as T  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def _shore_site(w: HybridWorld, dist_lo: int = 4):
    lx, ly = w.terrain.meta["homes"][0]["lake"]
    return next(p for r in range(8, 20) for p in grid.ring(lx, ly, r) if w.terrain.can_build(p[0], p[1], "small")
                and w.terrain.cells(p[0], p[1], 8, "fish"))


def _run(w, seconds):
    base = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(seconds):
        w.advance(1000, base + i + 1, snapshot=False)


def _world_with_fisher(kind="wl:barbarians_fishers_hut"):
    w = HybridWorld(minimal=True, terrain=True)
    w.ai_enabled = False
    wh = next(b for b in w.buildings.values() if b["kind"] == "warehouse")
    site = _shore_site(w)
    w.faction_info["Red"]["tribe"] = "barbarians"
    fid = w.faction_info["Red"]["id"]
    from wizard_rts import wl_defs

    spec = wl_defs.spec_for_kind(kind)
    bid = w._building(fid, "Red", kind, site, spec["label"], spec["definition"])
    return w, bid, site


def _fish(w, centre, radius=8):
    return w.terrain.total(centre[0], centre[1], radius, "fish")


def test_fisher_catches_real_fish_from_the_water_beside_it() -> None:
    w, bid, site = _world_with_fisher()
    before = _fish(w, site)
    _run(w, 240)
    caught = w.stats.get("fish_caught", 0)
    assert caught >= 3 and w.stats.get("made_fish", 0) >= 1
    assert _fish(w, site) == before - caught  # every fish that left the water was counted
    worker = next(x for x in w.workers.values() if x["building"] == bid)
    assert w.terrain.ground(worker["tx"], worker["ty"])  # the fisher stands on land, never in the water


def test_fisher_needs_fish_within_reach_and_stops_when_the_water_is_empty() -> None:
    w, bid, site = _world_with_fisher()
    for dy in range(-10, 11):
        for dx in range(-10, 11):
            x, y = site[0] + dx, site[1] + dy
            if w.terrain.in_bounds(x, y) and w.terrain.res_kind[y * w.terrain.w + x] == T.RES_FISH:
                w.terrain.res_amt[y * w.terrain.w + x] = 0
    _run(w, 120)
    assert w.stats.get("fish_caught", 0) == 0 and w.stats.get("made_fish", 0) == 0
    # a hut cannot be placed where there is no fish in reach
    w2 = HybridWorld(terrain=True)
    home = next(b for b in w2.buildings.values() if b["kind"] == "warehouse" and b["faction_name"] == "Red")
    far = next(p for p in w2.terrain_free_sites("small", lambda p: abs(p[0] - home["tx"]) < 25 and abs(p[1] - home["ty"]) < 25)
               if not w2.terrain.cells(p[0], p[1], 8, "fish"))
    assert w2.build("Red", "wl:barbarians_fishers_hut", *far)["reason"] == "no_fish"
    near = next(p for p in w2.terrain_free_sites("small", lambda p: abs(p[0] - home["tx"]) < 30 and abs(p[1] - home["ty"]) < 30)
                if w2.terrain.cells(p[0], p[1], 8, "fish"))
    assert w2.build("Red", "wl:barbarians_fishers_hut", *near)["status"] == "ok"


def test_breeding_restores_fish_but_never_above_the_initial_amount() -> None:
    w = HybridWorld(minimal=True, terrain=True)
    site = _shore_site(w)
    cells = w.terrain.cells(site[0], site[1], 1, "fish")
    # find a standing spot with water cells around it
    spot = next(p for p in grid.area(site[0], site[1], 8) if w.terrain.ground(*p) and w.terrain.cells(p[0], p[1], 1, "fish"))
    cells = w.terrain.cells(spot[0], spot[1], 1, "fish")
    for x, y, _a, init in cells:
        w.terrain.res_amt[y * w.terrain.w + x] = max(0, init // 3)
    low = sum(a for _x, _y, a, _i in w.terrain.cells(spot[0], spot[1], 1, "fish"))
    init_total = sum(i for _x, _y, _a, i in w.terrain.cells(spot[0], spot[1], 1, "fish"))
    for _ in range(4000):
        resources.worker_breed(w, spot, "fish", 1)
    now = sum(a for _x, _y, a, _i in w.terrain.cells(spot[0], spot[1], 1, "fish"))
    assert low < now <= init_total
    assert now == init_total  # given enough breeding the grounds fill to exactly their initial amount
    assert resources.worker_breed(w, spot, "fish", 1) is False  # full: nothing to breed


def test_fishing_down_then_breeding_is_a_cycle() -> None:
    w = HybridWorld(minimal=True, terrain=True)
    site = _shore_site(w)
    spot = next(p for p in grid.area(site[0], site[1], 8) if w.terrain.ground(*p) and w.terrain.cells(p[0], p[1], 1, "fish"))
    start = sum(a for _x, _y, a, _i in w.terrain.cells(spot[0], spot[1], 1, "fish"))
    taken = 0
    for _ in range(300):
        taken += resources.worker_mine(w, spot, "fish", 1)
    mid = sum(a for _x, _y, a, _i in w.terrain.cells(spot[0], spot[1], 1, "fish"))
    assert taken > 0 and mid == start - taken
    for _ in range(3000):
        resources.worker_breed(w, spot, "fish", 1)
    assert sum(a for _x, _y, a, _i in w.terrain.cells(spot[0], spot[1], 1, "fish")) == start

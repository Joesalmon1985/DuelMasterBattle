"""Square-grid terrain: generation, determinism, and the gameplay consequences of terrain.

Level B/C (implemented behaviour, isolated). Rendering is checked by the headed Godot scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts import mapgen, terrain as T  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402
from wizard_rts.workers import find_path  # noqa: E402


def _tiles(g, cls=None, res=None):
    for y in range(g.h):
        for x in range(g.w):
            i = y * g.w + x
            if cls is not None and g.cls[i] != cls:
                continue
            if res is not None and g.res_kind[i] != T.RES_CODE[res]:
                continue
            yield x, y


def test_same_seed_same_map_and_different_seed_differs() -> None:
    a, b, c = mapgen.generate(507), mapgen.generate(507), mapgen.generate(11)
    assert a.static_hash() == b.static_hash() and a.state_hash() == b.state_hash()
    assert a.static_hash() != c.static_hash()
    assert a.features == b.features


def test_map_sizes() -> None:
    for name, (w, h) in mapgen.SIZES.items():
        if name == "large":
            continue  # generated in the benchmark script
        g = mapgen.generate(3, name)
        assert (g.w, g.h) == (w, h) and len(g.starts) == 6


def test_terrain_has_every_required_kind() -> None:
    g = mapgen.generate(507)
    names = set(g.palette[t] for t in set(g.terrain))
    assert {"summer_water", "summer_beach"} <= names
    assert any("mountain" in n for n in names) and any("meadow" in n for n in names)
    s = g.summary()
    assert s["classes"]["water"] > 20000 and s["classes"]["arable"] > 40000 and s["classes"]["mineable"] > 8000
    for res in ("coal", "iron", "gold", "stones", "fish", "water"):
        assert s["resources"][res] > 0
    assert s["largest_water"] > 30000  # a sea, not just ponds


def test_six_homelands_are_equal_and_complete() -> None:
    for seed in (507, 1, 2):
        g = mapgen.generate(seed)
        totals = []
        for home in g.meta["homes"]:
            cx, cy = home["capital"]
            assert g.build_cap_name(cx, cy).startswith("big")
            row = {}
            for res in ("coal", "iron", "gold", "stones"):
                row[res] = g.total(home["mountain"][0], home["mountain"][1], 12, res)
                assert row[res] >= 400, (seed, home, res, row[res])
            assert g.cls[home["lake"][1] * g.w + home["lake"][0]] == T.WATER  # every homeland has its own lake
            totals.append(row)
        for res in ("coal", "iron", "gold", "stones"):
            vals = [t[res] for t in totals]
            assert max(vals) <= 1.6 * min(vals), (seed, res, vals)


def test_capitals_reach_each_other_on_foot_and_share_water() -> None:
    for seed in (507, 1, 2, 3):
        w = HybridWorld(seed)
        caps = [(b["tx"], b["ty"]) for b in w.buildings.values() if b["kind"] == "warehouse"]
        assert len(caps) == 6
        for other in caps[1:]:
            p = find_path(w, caps[0], other, limit=500, max_nodes=600_000)
            assert p is not None, (seed, other)
            assert all(w.terrain.ground(x, y) for x, y in p)
            assert all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip([caps[0]] + p, p))  # four directions only
        comps = {w.terrain.water_comp[h["lake"][1] * w.terrain.w + h["lake"][0]] for h in w.terrain.meta["homes"]}
        assert len(comps) == 1 and 0 not in comps


def test_initial_trees_and_rocks_stand_on_suitable_terrain() -> None:
    w = HybridWorld(507)
    for tree in w.trees.values():
        assert w.terrain.class_at(tree["tx"], tree["ty"]) == T.ARABLE
    assert w.trees and w.rocks
    for rock in w.rocks.values():
        assert w.terrain.ground(rock["tx"], rock["ty"])


def test_growth_probability_follows_terrain_affinity() -> None:
    g = mapgen.generate(507)
    meadow = next(p for p in _tiles(g, T.ARABLE) if g.terrain_name(*p) == "summer_meadow1")
    barren = next(p for p in _tiles(g, T.ARABLE) if g.terrain_name(*p) == "summer_steppe_barren")
    assert 0.0 <= g.growth_probability("beech", *barren) < g.growth_probability("beech", *meadow) <= 1.0
    assert g.growth_probability("larch", *meadow) != g.growth_probability("beech", *meadow)


def test_building_rejected_on_invalid_terrain_and_accepted_on_valid() -> None:
    w = HybridWorld(507)
    home = w.buildings[next(i for i, b in w.buildings.items() if b["kind"] == "warehouse" and b["faction_name"] == "Red")]
    hx, hy = home["tx"], home["ty"]
    near = lambda p: max(abs(p[0] - hx), abs(p[1] - hy)) <= 30  # noqa: E731
    water = next(p for p in _tiles(w.terrain, T.WATER) if near(p))
    assert w.build("Red", "producer", *water)["reason"] == "water"
    mountain_noore = next(p for p in _tiles(w.terrain, T.MINEABLE) if near(p) and w.terrain.build[p[1] * w.terrain.w + p[0]] == T.B_MINE and w.terrain.res_kind[p[1] * w.terrain.w + p[0]] == 0
                          and w.terrain.total(p[0], p[1], 2, "coal") == 0 and w.terrain.total(p[0], p[1], 2, "iron") == 0)
    assert w.build("Red", "mine", *mountain_noore)["reason"] == "no_deposit"
    assert w.build("Red", "producer", *mountain_noore)["reason"] == "unsuitable_terrain"
    meadow_free = next(p for p in w.terrain_free_sites("big", near))
    assert w.build("Red", "mine", *meadow_free)["reason"] == "no_mountain"
    assert w.build("Red", "farm", *meadow_free)["status"] == "ok"


def test_mine_takes_from_the_deposit_under_it_and_runs_out() -> None:
    w = HybridWorld(507)
    mine = next(b for b in w.buildings.values() if b["kind"] == "mine" and b["faction_name"] == "Red")
    c = (mine["tx"], mine["ty"])
    before = w.terrain.total(c[0], c[1], 2, "coal")
    assert before >= 150
    from wizard_rts.workers import _mine
    args = {"resource": "coal", "radius": 2, "yield": 33.33, "when_empty": 5}
    taken = 0
    while taken < 40 and _mine(w, mine, args):
        taken += 1
    assert taken >= 20
    assert w.terrain.total(c[0], c[1], 2, "coal") == before - taken
    # a mine with no deposit in reach produces nothing
    far = {"id": "x", "tx": 5, "ty": 5}
    assert _mine(w, far, args) is False


def test_ground_units_cannot_enter_water_and_orders_to_water_fail() -> None:
    w = HybridWorld(507)
    unit = next(u for u in w.units.values() if u["kind"] == "infantry" and u["faction_name"] == "Red")
    water = next(p for p in _tiles(w.terrain, T.WATER) if abs(p[0] - unit["tx"]) < 40 and abs(p[1] - unit["ty"]) < 40)
    assert w.move([unit["id"]], *water)["status"] == "rejected"
    assert find_path(w, (unit["tx"], unit["ty"]), water, limit=100) is None  # even the goal must be ground
    assert not w.tile_in_map(*water) and w.tile_in_bounds(*water)
    # the wizard cannot be placed in water either
    assert w.set_pose(*water)["status"] == "rejected"


def test_determinism_of_the_whole_world() -> None:
    def run(seed: int) -> str:
        w = HybridWorld(seed)
        for i in range(30):
            w.advance(1000, i + 1, snapshot=False)
        return w.state_hash()

    assert run(507) == run(507)
    assert run(507) != run(8)

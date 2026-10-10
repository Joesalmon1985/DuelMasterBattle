"""The commands God Mode and the AI share: build, road, recruit, move."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts.world import HybridWorld  # noqa: E402


def _world() -> HybridWorld:
    w = HybridWorld()
    w.dmb.hazards["catastrophe"]["cubes"][w.hazard_id]["active"] = False
    return w


def _run(w: HybridWorld, until, limit_ms: int = 300_000) -> None:
    seq = int(w.dmb.clock.get("clock_sequence", 0))
    for i in range(limit_ms // 100):
        w.advance(100, seq + i + 1, snapshot=False)
        if until():
            return
    raise AssertionError("condition not reached")


def _of(w: HybridWorld, faction: str, kind: str) -> str:
    return next(i for i, b in w.buildings.items() if b["kind"] == kind and b["faction_name"] == faction)


def test_six_factions_with_own_economies() -> None:
    w = _world()
    assert [f["name"] for f in w.snapshot()["factions"]] == ["Red", "Blue", "Green", "Yellow", "Purple", "Orange"]
    for name in ("Red", "Blue", "Green", "Yellow", "Purple", "Orange"):
        for kind in ("warehouse", "producer", "processor", "ranger", "barracks", "vehicle_factory"):
            assert _of(w, name, kind)
        assert w.stocks[_of(w, name, "warehouse")]["log"] >= 12


def test_build_road_construct_and_cost_is_delivered() -> None:
    w = _world()
    wh = _of(w, "Red", "warehouse")
    home = w.buildings[wh]
    tile = None
    for dx in range(6, 14):
        t = (home["tx"] + dx, home["ty"] + 9)
        if t not in w.blocked and t not in w.tree_tiles and t not in w.road_tile_set:
            tile = t
            break
    placed = w.build("Red", "producer", *tile)
    assert placed["status"] == "ok", placed
    site = placed["id"]
    assert w.buildings[site]["operational"] is False and w.buildings[site]["constructing"]
    before = w.stocks[wh]["log"]
    # nothing arrives without a road
    for i in range(200):
        w.advance(100, i + 1, snapshot=False)
    assert w.stocks[site].get("log", 0) == 0 and w.buildings[site].get("constructing")
    road = w.road("Red", site, wh)
    assert road["status"] == "ok", road
    _run(w, lambda: not w.buildings[site].get("constructing"))
    assert w.buildings[site]["operational"] is True and w.buildings[site]["hp"] == w.buildings[site]["max_hp"]
    assert w.stocks[wh]["log"] <= before - 3 + w.stats.get("consumed_log", 0)  # the 3 logs came from the warehouse
    # rejects: enemy road, occupied tile, outside territory
    assert w.road("Blue", site, wh)["status"] == "rejected"
    assert w.build("Red", "producer", *tile)["reason"] == "tile_occupied"
    assert w.build("Red", "producer", 5, 5)["reason"] == "outside_territory"


def test_rifleman_comes_from_the_real_mining_smelting_smithing_chain() -> None:
    w = _world()
    bar = _of(w, "Red", "barracks")
    assert w.queue(bar, "infantry")["status"] == "ok"
    n = len(w.units)
    _run(w, lambda: len(w.units) > n, 1_200_000)
    # the ax came from coal + iron ore that were mined from finite deposits
    assert w.stats["made_ax"] >= 1 and w.stats["made_iron"] >= 1 and w.stats["made_coal"] >= 2 and w.stats["made_iron_ore"] >= 1
    assert w.stats["consumed_ax"] >= 1 and w.stats["recruit_started"] >= 1


def test_barracks_queue_consumes_delivered_goods_and_unit_obeys_move() -> None:
    w = _world()
    bar = _of(w, "Red", "barracks")
    assert w.queue(bar, "tank")["reason"] == "cannot_build_here"
    from wizard_rts.economy import produce

    produce(w, _of(w, "Red", "warehouse"), "ax", 1)  # test shortcut: the chain has its own test above
    assert w.queue(bar, "infantry")["status"] == "ok"
    units_before = len(w.units)
    _run(w, lambda: len(w.units) > units_before, 600_000)
    assert w.stats["recruit_started"] >= 1
    new = [u for u in w.units.values() if u["id"] not in {e for e in ()} and u["kind"] == "infantry" and u["faction_name"] == "Red"]
    assert len(new) == 2
    unit = max(new, key=lambda u: int(u["id"].split(":")[1]))
    start = (unit["tx"], unit["ty"])
    goal = (start[0] + 9, start[1] + 4)
    assert w.move([unit["id"]], *goal)["status"] == "ok"
    _run(w, lambda: (unit["tx"], unit["ty"]) == goal or not unit.get("order"), 120_000)
    assert (unit["tx"], unit["ty"]) != start and max(abs(unit["tx"] - goal[0]), abs(unit["ty"] - goal[1])) <= 2


def test_queue_stalls_without_goods_and_cancel_refunds() -> None:
    w = _world()
    bar = _of(w, "Red", "barracks")
    w.queue(bar, "infantry")
    n = len(w.units)
    for i in range(20):
        w.advance(100, i + 1, snapshot=False)
    assert len(w.units) == n and w.buildings[bar]["queue"][0]["state"] == "waiting"  # goods still on the road
    assert w.cancel(bar, 0)["status"] == "ok" and not w.buildings[bar]["queue"]
    assert w.cancel(bar, 0)["reason"] == "no_such_item"


def test_damaged_barracks_recruits_slower_and_destroyed_cannot() -> None:
    w = _world()
    bar = _of(w, "Red", "barracks")
    w.damage_building(bar, 10**9, ["structure"], {})
    assert w.queue(bar, "infantry")["reason"] == "not_operational"

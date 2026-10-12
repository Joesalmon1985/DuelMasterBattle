"""Regressions for the first manual playtest (docs/PLAYTEST_FIXES.md): destruction lifecycle, footprints, snapshot fields."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts import lifecycle  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def _step(world: HybridWorld, ms: int, seq: list) -> None:
    for _ in range(ms // 100):
        seq[0] += 1
        world.advance(100, seq[0], snapshot=False)


def _find(world, faction, kind):
    return next(i for i, b in world.buildings.items() if b["kind"] == kind and b["faction_name"] == faction)


def test_destruction_lifecycle_four_seconds() -> None:
    world = HybridWorld()
    bid = _find(world, "Red", "vehicle_factory")
    b = world.buildings[bid]
    footprint = [tuple(p) for p in b["ground_footprint"]]
    assert all(p in world.blocked for p in footprint)
    world.queue(bid, "tank")
    assert b["queue"]
    world.damage_building(bid, 10**9, ["structure"], {})
    # 1-4: production and orders stop at once; the building is marked destroyed, not yet removed
    assert b["destroyed"] and b["operational"] is False and b["queue"] == [] and b["ruin_ms"] == lifecycle.RUIN_MS
    assert world.queue(bid, "tank")["status"] == "rejected"
    row = next(e for e in world.snapshot()["entities"] if e["id"] == bid)
    assert row["destroyed"] is True and 0 < row["ruin_ms"] <= 4000
    # 5-7: ruin burns 3-5 s of game time, then collision, roads and logistics are released
    assert 3000 <= lifecycle.RUIN_MS <= 5000
    seq = [world.dmb.clock.get("clock_sequence", 0)]
    _step(world, lifecycle.RUIN_MS - 500, seq)
    assert bid in world.buildings and all(p in world.blocked for p in footprint)
    _step(world, 1000, seq)
    assert bid not in world.buildings
    assert not any(p in world.blocked for p in footprint)
    assert not any(bid in edge for edge in world.road_edges.values())
    assert any(e["kind"] == "building_removed" and e["id"] == bid for e in world.events)


def test_war_factory_and_barracks_have_real_footprints() -> None:
    world = HybridWorld()
    for faction in ("Red", "Blue", "Green", "Yellow", "Purple", "Orange"):
        wf = world.buildings[_find(world, faction, "vehicle_factory")]
        assert len(wf["ground_footprint"]) == 6  # 3 wide, 2 deep, the door tile is the bottom middle
        xs = {p[0] for p in wf["ground_footprint"]}
        ys = {p[1] for p in wf["ground_footprint"]}
        assert max(xs) - min(xs) == 2 and max(ys) - min(ys) == 1 and [wf["tx"], wf["ty"]] in wf["ground_footprint"]
        assert wf["ty"] == max(ys)
        bk = world.buildings[_find(world, faction, "barracks")]
        assert len(bk["ground_footprint"]) == 4


def test_units_leave_the_factory_through_the_front_not_the_walls() -> None:
    from wizard_rts import construction as con

    world = HybridWorld()
    bid = _find(world, "Red", "vehicle_factory")
    b = world.buildings[bid]
    tile = con._exit_tile(world, b)
    assert tile is not None and tile[1] == b["ty"] + 1
    assert list(tile) not in b["ground_footprint"]

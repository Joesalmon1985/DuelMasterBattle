"""A unit order lowers building health through damage_building and stops production."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts.world import HybridWorld  # noqa: E402


def _pick(world: HybridWorld, faction: str, kind: str) -> str:
    return next(i for i, b in world.buildings.items() if b["kind"] == kind and b["faction_name"] == faction)


def _tank(world: HybridWorld, faction: str) -> str:
    return next(i for i, u in world.units.items() if u["kind"] == "tank" and u["faction_name"] == faction)


def test_order_rejections() -> None:
    world = HybridWorld()
    tank = _tank(world, "Red")
    assert world.order(tank, _pick(world, "Red", "producer"))["reason"] == "friendly"
    assert world.order("nope", _pick(world, "Blue", "producer"))["reason"] == "no_unit"
    tree = next(iter(world.rocks))
    assert world.order(tank, tree)["reason"] == "no_target"


def test_tank_destroys_producer_and_production_stops() -> None:
    world = HybridWorld()
    tank = _tank(world, "Red")
    target = _pick(world, "Blue", "producer")
    assert world.order(tank, target)["status"] == "ok"
    seq = 0
    for _ in range(4000):
        seq += 1
        world.advance(100, seq)
        if world.buildings[target]["hp"] <= 0:
            break
    building = world.buildings[target]
    assert building["hp"] == 0 and building["operational"] is False
    assert "order" not in world.units[tank]
    assert world.units[tank]["weapon"] == "105mm"
    assert any(e["kind"] == "building_destroyed" for e in world.events) or world.stats["destroyed"] >= 1
    before = world.stocks[target].get("log", 0)
    for _ in range(100):  # the ruin burns for 15 s before it is removed
        seq += 1
        world.advance(100, seq)
        now = world.stocks[target].get("log", 0)
        assert now <= before  # leftovers may be hauled away; nothing new is made
        before = now
    red_producer = _pick(world, "Red", "producer")
    assert world.buildings[red_producer]["operational"] is True

"""Wares are conserved and move only by carrier."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wizard_rts.economy import produce  # noqa: E402
from wizard_rts.logistics import in_flight  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def _log_total(world: HybridWorld, good: str) -> int:
    return sum(int(s.get(good, 0)) for s in world.stocks.values()) + in_flight(world, good)


def test_every_ware_is_conserved_over_ten_minutes() -> None:
    world = HybridWorld()
    world.dmb.hazards["catastrophe"]["cubes"][world.hazard_id]["active"] = False
    goods = ("log", "plank", "coal", "iron_ore", "iron", "ax", "granite")
    initial = {g: _log_total(world, g) for g in goods}
    for i in range(6_000):
        world.advance(100, i + 1)
    carried = {g: sum(1 for w in world.workers.values() if w["carrying"] == g) for g in goods}
    for g in goods:
        made = world.stats.get("made_" + g, 0)
        held = _log_total(world, g)
        gone = world.stats.get("consumed_" + g, 0)
        # a ware is made, then held (stock / flag / carrier), or consumed. Wares on a worker's back are not yet made.
        assert held + gone == made + initial[g], (g, held, gone, made, initial[g], carried[g])
    assert world.stats["made_log"] > 0 and world.stats["made_coal"] > 0 and world.stats["made_granite"] > 0


def test_wares_never_teleport() -> None:
    world = HybridWorld()
    world.dmb.hazards["catastrophe"]["cubes"][world.hazard_id]["active"] = False
    wh = next(i for i, b in world.buildings.items() if b["kind"] == "warehouse" and b["faction_name"] == "Red")
    last = world.stocks[wh].get("log", 0) + world.stocks[wh].get("plank", 0)
    last_delivered = world.stats["deliver"]
    for i in range(3_000):
        world.advance(100, i + 1)
        now = world.stocks[wh].get("log", 0) + world.stocks[wh].get("plank", 0)
        # a warehouse can only gain a ware on a tick when a carrier delivered one
        if now > last:
            assert world.stats["deliver"] > last_delivered
        last, last_delivered = now, world.stats["deliver"]


def test_request_pulls_from_warehouse_by_road() -> None:
    world = HybridWorld()
    world.dmb.hazards["catastrophe"]["cubes"][world.hazard_id]["active"] = False
    wh = next(i for i, b in world.buildings.items() if b["kind"] == "warehouse" and b["faction_name"] == "Red")
    saw = next(i for i, b in world.buildings.items() if b["kind"] == "processor" and b["faction_name"] == "Red")
    produce(world, wh, "log", 3)
    for i in range(400):
        world.advance(100, i + 1)
    assert world.stocks[saw].get("log", 0) + world.stats.get("consumed_log", 0) > 0  # hauled to the sawmill by road

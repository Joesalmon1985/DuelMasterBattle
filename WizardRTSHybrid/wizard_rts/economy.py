"""Economic tick for the hybrid world.

Stock changes go through the source-derived Widelands warehouse list.
Carrier route choice and the production schedule are still provisional.
DuelMasterBattle carts are not invoked here.
"""

from __future__ import annotations

from typing import Any

from wizard_rts.widelands_stock import SOURCE as WIDELANDS_STOCK_SOURCE
from wizard_rts.widelands_stock import WarehouseSupply

PROVENANCE = WIDELANDS_STOCK_SOURCE["status"]
SCHEDULE_PROVENANCE = "provisional-scaffolding"


def _supply(world: Any, entity_id: str) -> WarehouseSupply:
    store = world.stocks.setdefault(entity_id, {})
    return WarehouseSupply(store, world.economy_totals)


def move_good(world: Any, source: str, dest: str, good: str, amount: int = 1) -> bool:
    """Move goods using WarehouseSupply remove-then-add. Short stock does not move."""
    if int(amount) <= 0:
        return False
    if int(world.stocks.get(source, {}).get(good, 0)) < int(amount):
        return False
    _supply(world, source).remove_wares(good, amount)
    _supply(world, dest).add_wares(good, amount)
    return True


def produce(world: Any, building_id: str, good: str, amount: int = 1) -> None:
    _supply(world, building_id).add_wares(good, amount)


def economy_quantum(world: Any) -> None:
    """One game-time quantum of processing. Hauling is logistics.py; production is forestry.py."""
    world.economy_quanta += 1
    n = world.economy_quanta
    if n % 10 == 0:
        for building_id, building in world.buildings.items():
            if building["kind"] != "processor" or not building.get("operational", True):
                continue
            if int(world.stocks.get(building_id, {}).get("log", 0)) > 0:
                _supply(world, building_id).remove_wares("log", 1)
                world.stats["consumed_log"] = world.stats.get("consumed_log", 0) + 1
                produce(world, building_id, "plank", 1)
                world.events.append({"kind": "consume", "id": building_id, "good": "log"})
            else:
                world.events.append({"kind": "shortage", "id": building_id, "faction": building["faction"]})
    if len(world.events) > 200:
        del world.events[:-200]


def _facing(dx: int, dy: int) -> str:
    """Six Widelands directions. Pure north and south use the nearest diagonal sheet."""
    if dx > 0 and dy == 0:
        return "e"
    if dx < 0 and dy == 0:
        return "w"
    if dy > 0:
        return "se" if dx >= 0 else "sw"
    if dy < 0:
        return "ne" if dx >= 0 else "nw"
    return "e"

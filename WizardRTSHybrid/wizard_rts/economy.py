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


EVENT_CAP = 6000
EVENT_KEEP = 3000


def economy_quantum(world: Any) -> None:
    """Tick counter and event trimming. Hauling is logistics.py; production is workers.py."""
    world.economy_quanta += 1
    if world.economy_quanta % 300 == 0:
        # Widelands warehouses create workers on demand; recruits and carriers are the two the hybrid models as wares.
        for b in world.buildings.values():
            if b["kind"] == "warehouse" and b.get("operational", True):
                for worker_ware in ("recruit", "carrier"):
                    have = int(world.stocks.get(b["id"], {}).get(worker_ware, 0))
                    if have < 8:
                        _supply(world, b["id"]).add_wares(worker_ware, 8 - have)
                        world.stats["made_" + worker_ware] = world.stats.get("made_" + worker_ware, 0) + 8 - have  # a source: the ledger counts it
    if len(world.events) > EVENT_CAP:
        del world.events[:-EVENT_KEEP]  # the log is a bounded window: long headless runs must not grow without limit


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

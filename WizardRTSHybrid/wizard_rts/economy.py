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


INPUT_CAPACITY = 4


def _wants(world: Any, dest_id: str, good: str) -> bool:
    dest = world.buildings.get(dest_id, {})
    if dest.get("kind") == "warehouse":
        return bool(dest.get("operational", True))
    if not dest.get("operational", True):
        return False
    return int(world.stocks.get(dest_id, {}).get(good, 0)) < INPUT_CAPACITY


def economy_quantum(world: Any) -> None:
    """One game-time quantum of hauling and processing.

    Producers make nothing here: workers (forestry.py) bring wares to the
    workplace output. Carriers move them along a road to the next building.
    """
    world.economy_quanta += 1
    n = world.economy_quanta
    if n % 5 == 0:
        for carrier in world.carriers.values():
            _step_carrier(world, carrier)
    if n % 10 == 0:
        for building_id, building in world.buildings.items():
            if building["kind"] != "processor" or not building.get("operational", True):
                continue
            if int(world.stocks.get(building_id, {}).get("log", 0)) > 0:
                world.stocks[building_id]["log"] -= 1
                produce(world, building_id, "plank", 1)
                world.events.append({"kind": "consume", "id": building_id, "good": "log"})
            else:
                world.events.append({"kind": "shortage", "id": building_id, "faction": building["faction"]})
    if len(world.events) > 200:
        del world.events[:-200]


def _step_carrier(world: Any, carrier: dict) -> None:
    road: list[tuple[int, int]] = world.roads[carrier["road_id"]]
    idx = int(carrier["index"])
    tx, ty = road[idx]
    source, dest, good = carrier["source_id"], carrier["dest_id"], carrier["good"]
    if not carrier["cargo"] and idx == 0 and int(world.stocks.get(source, {}).get(good, 0)) > 0:
        if _wants(world, dest, good) and move_good(world, source, carrier["id"], good, 1):
            carrier["cargo"] = good
            carrier["status"] = "carrying"
            world.events.append({"kind": "pickup", "id": carrier["id"], "from": source, "good": good})
        return
    if carrier["cargo"] and idx == len(road) - 1:
        if move_good(world, carrier["id"], dest, good, 1):
            carrier["cargo"] = None
            carrier["status"] = "idle"
            if world.buildings.get(dest, {}).get("kind") == "warehouse":
                world.stats["deliver"] += 1
            world.events.append({"kind": "deliver", "id": carrier["id"], "dest": dest, "faction": carrier["faction"], "good": good})
        return
    if carrier["cargo"]:
        nxt = idx + 1
    else:
        nxt = idx - 1 if idx > 0 else idx
    if nxt == idx:
        return
    step = road[nxt]
    if world.tile_blocked_for_carrier(step):
        carrier["status"] = "blocked"
        world.stats["blocked"] += 1
        world.events.append({"kind": "carrier_blocked", "id": carrier["id"], "tile": list(step), "faction": carrier["faction"]})
        return
    carrier["status"] = "carrying" if carrier["cargo"] else "moving"
    carrier["facing"] = _facing(step[0] - tx, step[1] - ty)
    carrier["index"] = nxt
    carrier["tx"], carrier["ty"] = step


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

"""Building placement, construction sites, road building and recruitment queues.

Everything here is a command that God Mode and the AI both call. A new building
is a construction site: it requests its build cost through the logistics
network, and only completes after every ware has been delivered and the build
time has run. Costs come from the Widelands tribe data where the building
exists there (lumberjack's hut, ranger's hut). OpenRA buildings, and anything
whose Widelands cost needs wares this hybrid does not make yet (granite,
grout), use a documented hybrid cost.
"""

from __future__ import annotations

import heapq
from typing import Any

from wizard_rts.coords import tile_to_hex
from wizard_rts import wl_defs
from wizard_rts.economy import _supply
from wizard_rts.logistics import add_road

QUANTUM_MS = 100
TERRITORY_RADIUS = 34  # tiles from the faction's warehouse
BUILD_MS = 20_000

BUILD_MENU: dict[str, dict[str, Any]] = {
    "producer": {
        "label": "Lumberjack's hut", "definition": "widelands.lumberjack", "game": "widelands",
        "cost": {"log": 3}, "cost_source": "barbarians/lumberjacks_hut buildcost",
    },
    "ranger": {
        "label": "Ranger's hut", "definition": "widelands.rangers_hut", "game": "widelands",
        "cost": {"log": 4}, "cost_source": "barbarians/rangers_hut buildcost",
    },
    "processor": {
        "label": "Sawmill", "definition": "widelands.sawmill", "game": "widelands",
        "cost": {"log": 2, "plank": 1}, "cost_source": "empire/sawmill buildcost minus granite (not produced yet)",
    },
    "farm": {
        "label": "Farm", "definition": "widelands.farm", "game": "widelands",
        "cost": {"log": 4, "plank": 1, "granite": 3}, "cost_source": "barbarians/farm buildcost with planks for blackwood",
    },
    "hunter": {
        "label": "Hunter's hut", "definition": "widelands.hunters_hut", "game": "widelands",
        "cost": {"log": 4, "granite": 1}, "cost_source": "barbarians/hunters_hut buildcost",
    },
    "well": {
        "label": "Well", "definition": "widelands.well", "game": "widelands",
        "cost": {"log": 4}, "cost_source": "barbarians/well buildcost",
    },
    "tavern": {
        "label": "Tavern", "definition": "widelands.tavern", "game": "widelands",
        "cost": {"log": 3, "plank": 2, "granite": 1}, "cost_source": "barbarians/tavern buildcost with planks for blackwood, no reed",
    },
    "bakery": {
        "label": "Bakery", "definition": "widelands.bakery", "game": "widelands",
        "cost": {"log": 2, "plank": 2, "granite": 2}, "cost_source": "barbarians/bakery buildcost with planks for blackwood, no reed",
    },
    "mine": {
        "label": "Coal mine", "definition": "widelands.coalmine", "game": "widelands",
        "cost": {"log": 4, "granite": 2}, "cost_source": "barbarians/coalmine buildcost",
    },
    "ironmine": {
        "label": "Iron mine", "definition": "widelands.ironmine", "game": "widelands",
        "cost": {"log": 4, "granite": 2}, "cost_source": "barbarians/ironmine buildcost",
    },
    "quarry": {
        "label": "Quarry", "definition": "widelands.quarry", "game": "widelands",
        "cost": {"log": 4}, "cost_source": "barbarians/quarry buildcost",
    },
    "smelter": {
        "label": "Smelting works", "definition": "widelands.smelting_works", "game": "widelands",
        "cost": {"log": 3, "plank": 1, "granite": 1}, "cost_source": "barbarians/smelting_works buildcost with planks for blackwood, no grout or reed",
    },
    "smithy": {
        "label": "Ax workshop", "definition": "widelands.ax_workshop", "game": "widelands",
        "cost": {"log": 3, "plank": 2, "granite": 1}, "cost_source": "hybrid-defined from barbarians/ax_workshop",
    },
    "barracks": {
        "label": "Barracks", "definition": "openra.barracks", "game": "openra",
        "cost": {"log": 2, "plank": 4}, "cost_source": "hybrid-defined; OpenRA credits and power removed by design",
    },
    "vehicle_factory": {
        "label": "War factory", "definition": "openra.weap", "game": "openra",
        "cost": {"log": 4, "plank": 6}, "cost_source": "hybrid-defined; OpenRA credits and power removed by design",
    },
    "defense": {
        "label": "Gun turret", "definition": "openra.gun", "game": "openra",
        "cost": {"plank": 3}, "cost_source": "hybrid-defined; OpenRA power removed by design",
    },
}

# Hybrid recipes: a rifleman takes one ax (barbarians/barracks consume=ax, 30 s); a tank takes granite and a plank. See docs/DECISIONS.md.
RECIPES: dict[str, dict[str, dict[str, Any]]] = {
    "barracks": {
        "infantry": {"label": "Rifleman", "definition": "openra.e1", "cost": {"ax": 1}, "ms": 30_000},
    },
    "vehicle_factory": {
        "tank": {"label": "Tank", "definition": "openra.3tnk", "cost": {"granite": 2, "plank": 1}, "ms": 30_000},
    },
}


# ------------------------------------------------------------------ placement

def faction_warehouse(world: Any, faction_name: str) -> dict | None:
    for b in world.buildings.values():
        if b["kind"] == "warehouse" and b["faction_name"] == faction_name:
            return b
    return None


def build_spec(kind: str) -> dict[str, Any] | None:
    """A menu entry for a hybrid kind, or for any runnable Widelands building ("wl:<name>")."""
    if kind in BUILD_MENU:
        return BUILD_MENU[kind]
    spec = wl_defs.spec_for_kind(kind)
    if spec is None:
        return None
    return {
        "label": spec["label"], "definition": spec["definition"], "game": "widelands", "tribe": spec["tribe"],
        "cost": dict(spec["cost"]), "cost_source": f"{spec['tribe']}/{spec['name']} buildcost (imported)",
    }


def full_menu() -> dict[str, dict[str, Any]]:
    out = dict(BUILD_MENU)
    for name in wl_defs.runnable_names():
        spec = build_spec(wl_defs.PREFIX + name)
        if spec is not None:
            out[wl_defs.PREFIX + name] = spec
    return out


def place_building(world: Any, faction_name: str, kind: str, tx: int, ty: int) -> dict[str, Any]:
    spec = build_spec(kind)
    if spec is None:
        return {"status": "rejected", "reason": "unknown_kind"}
    info = world.faction_info.get(faction_name)
    if info is None:
        return {"status": "rejected", "reason": "unknown_faction"}
    tile = (int(tx), int(ty))
    home = faction_warehouse(world, faction_name)
    if not world.tile_in_map(*tile):
        return {"status": "rejected", "reason": "outside_map"}
    if home is not None and max(abs(tile[0] - home["tx"]), abs(tile[1] - home["ty"])) > TERRITORY_RADIUS:
        return {"status": "rejected", "reason": "outside_territory"}
    if tile in world.blocked or tile in world.tree_tiles or tile in world.road_tile_set or tile in world.reserved_tiles:
        return {"status": "rejected", "reason": "tile_occupied"}
    if any((u["tx"], u["ty"]) == tile for u in world.units.values() if u.get("alive", True)):
        return {"status": "rejected", "reason": "tile_occupied"}
    bid = world._building(info["id"], faction_name, kind, tile, spec["label"], spec["definition"])
    building = world.buildings[bid]
    building["operational"] = False
    building["constructing"] = {"cost": dict(spec["cost"]), "progress_ms": 0}
    building["hp"] = max(1, building["max_hp"] // 10)
    world.recipe_requests[bid] = dict(spec["cost"])
    world.events.append({"kind": "construction_started", "id": bid, "building_kind": kind, "faction": faction_name})
    return {"status": "ok", "id": bid}


def construction_quantum(world: Any) -> None:
    for bid, b in list(world.buildings.items()):
        site = b.get("constructing")
        if not site:
            continue
        stock = world.stocks.get(bid, {})
        if not all(int(stock.get(g, 0)) >= n for g, n in site["cost"].items()):
            continue
        site["progress_ms"] += QUANTUM_MS
        b["hp"] = min(b["max_hp"], max(b["hp"], int(b["max_hp"] * (0.1 + 0.9 * site["progress_ms"] / BUILD_MS))))
        if site["progress_ms"] >= BUILD_MS:
            for good, n in site["cost"].items():
                _supply(world, bid).remove_wares(good, n)
                world.stats["consumed_" + good] = world.stats.get("consumed_" + good, 0) + n
            b.pop("constructing")
            b["operational"] = True
            b["hp"] = b["max_hp"]
            world.recipe_requests.pop(bid, None)
            world.events.append({"kind": "construction_done", "id": bid, "building_kind": b["kind"]})


# ------------------------------------------------------------------ roads

def _road_path(world: Any, start: tuple[int, int], goal: tuple[int, int], ends: tuple[str, str] = ("", ""), limit: int = 70) -> list[tuple[int, int]] | None:
    avoid = world.blocked | world.road_tile_set | set(world.tree_tiles)
    # Roads that already reach an endpoint share its flag: they may be joined there.
    for end in ends:
        for _nxt, rid in world.adjacency.get(end, []):
            avoid -= set(world.roads[rid])
    heap: list[tuple[int, int, tuple[int, int]]] = [(0, 0, start)]
    came: dict[tuple[int, int], tuple[int, int]] = {}
    cost = {start: 0}
    n = 0
    while heap:
        _f, _c, cur = heapq.heappop(heap)
        if cur == goal:
            path = [cur]
            while cur != start:
                cur = came[cur]
                path.append(cur)
            path.reverse()
            return path
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt != goal and (nxt in avoid or not world.tile_in_map(*nxt)):
                continue
            if abs(nxt[0] - start[0]) > limit or abs(nxt[1] - start[1]) > limit:
                continue
            c = cost[cur] + 1
            if nxt not in cost or c < cost[nxt]:
                cost[nxt] = c
                came[nxt] = cur
                n += 1
                heapq.heappush(heap, (c + abs(goal[0] - nxt[0]) + abs(goal[1] - nxt[1]), n, nxt))
    return None


def build_road(world: Any, faction_name: str, a: str, b: str) -> dict[str, Any]:
    ba, bb = world.buildings.get(a), world.buildings.get(b)
    if ba is None or bb is None or "hp" not in ba or "hp" not in bb:
        return {"status": "rejected", "reason": "no_building"}
    if ba["faction_name"] != faction_name or bb["faction_name"] != faction_name:
        return {"status": "rejected", "reason": "not_your_building"}
    if a == b or any(n == b for n, _r in world.adjacency.get(a, [])):
        return {"status": "rejected", "reason": "already_connected"}
    path = _road_path(world, (ba["tx"], ba["ty"]), (bb["tx"], bb["ty"]), (a, b))
    if path is None or len(path) < 2:
        return {"status": "rejected", "reason": "no_path"}
    rid = add_road(world, world.faction_info[faction_name]["id"], faction_name, a, b, path)
    return {"status": "ok", "road": rid, "length": len(path)}


# ------------------------------------------------------------------ recruitment

def queue_unit(world: Any, building_id: str, unit_kind: str) -> dict[str, Any]:
    b = world.buildings.get(building_id)
    if b is None or not b.get("operational", True) or b.get("constructing"):
        return {"status": "rejected", "reason": "not_operational"}
    recipe = RECIPES.get(b["kind"], {}).get(unit_kind)
    if recipe is None:
        return {"status": "rejected", "reason": "cannot_build_here"}
    queue = b.setdefault("queue", [])
    if len(queue) >= 5:
        return {"status": "rejected", "reason": "queue_full"}
    queue.append({"unit": unit_kind, "state": "waiting", "progress_ms": 0})
    _sync_requests(world, b)
    world.events.append({"kind": "queued", "building": building_id, "unit": unit_kind})
    return {"status": "ok", "length": len(queue)}


def cancel_queue(world: Any, building_id: str, index: int) -> dict[str, Any]:
    b = world.buildings.get(building_id)
    if b is None or not b.get("queue") or not (0 <= int(index) < len(b["queue"])):
        return {"status": "rejected", "reason": "no_such_item"}
    item = b["queue"].pop(int(index))
    if item["state"] == "building":  # goods were consumed at start; refund them to the building stock
        for good, n in RECIPES[b["kind"]][item["unit"]]["cost"].items():
            from wizard_rts.economy import produce

            produce(world, building_id, good, n)
    _sync_requests(world, b)
    world.events.append({"kind": "queue_cancelled", "building": building_id, "unit": item["unit"]})
    return {"status": "ok"}


def _sync_requests(world: Any, b: dict) -> None:
    """The barracks asks for the goods of its next queued unit (one batch ahead)."""
    queue = b.get("queue", [])
    waiting = [i for i in queue if i["state"] == "waiting"]
    if not waiting:
        world.recipe_requests.pop(b["id"], None)
        return
    need: dict[str, int] = {}
    for good, n in RECIPES[b["kind"]][waiting[0]["unit"]]["cost"].items():
        need[good] = n
    world.recipe_requests[b["id"]] = need


def _exit_tile(world: Any, b: dict) -> tuple[int, int] | None:
    occupied = {(u["tx"], u["ty"]) for u in world.units.values() if u.get("alive", True)}
    for r in range(1, 6):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                t = (b["tx"] + dx, b["ty"] + dy)
                if max(abs(dx), abs(dy)) != r:
                    continue
                if world.tile_in_map(*t) and t not in world.blocked and t not in occupied and t not in world.road_tile_set:
                    return t
    return None


def recruitment_quantum(world: Any) -> None:
    for bid, b in list(world.buildings.items()):
        queue = b.get("queue")
        if not queue or not b.get("operational", True):
            continue
        head = queue[0]
        recipe = RECIPES[b["kind"]][head["unit"]]
        if head["state"] == "waiting":
            stock = world.stocks.get(bid, {})
            if all(int(stock.get(g, 0)) >= n for g, n in recipe["cost"].items()):
                for g, n in recipe["cost"].items():
                    _supply(world, bid).remove_wares(g, n)
                    world.stats["consumed_" + g] = world.stats.get("consumed_" + g, 0) + n
                head["state"] = "building"
                world.stats["recruit_started"] = world.stats.get("recruit_started", 0) + 1
                world.events.append({"kind": "recruit_started", "building": bid, "unit": head["unit"]})
                _sync_requests(world, b)
            continue
        # a damaged building works more slowly
        slow = max(0.25, b["hp"] / max(b["max_hp"], 1))
        head["progress_ms"] += int(QUANTUM_MS * slow)
        if head["progress_ms"] >= recipe["ms"]:
            tile = _exit_tile(world, b)
            if tile is None:
                continue
            uid = world._unit(b["faction"], b["faction_name"], head["unit"], recipe["label"], recipe["definition"], tile)
            rally = b.get("rally")
            if rally:
                world.units[uid]["order"] = {"kind": "move", "tile": list(rally)}
            queue.pop(0)
            world.stats["recruited"] = world.stats.get("recruited", 0) + 1
            world.events.append({"kind": "unit_produced", "building": bid, "unit": uid, "unit_kind": head["unit"]})
            _sync_requests(world, b)

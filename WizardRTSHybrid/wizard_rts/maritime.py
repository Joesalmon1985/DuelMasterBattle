"""Widelands maritime logistics (owner programme 13 Oct 2026): shipyards, ships, ports, ferries and waterways.

* A shipyard keeps one ship under construction on a shallow-water node near the coast. Every `construct` step of its programme consumes ONE ware of the
  ship's build cost from the yard's own stock (Widelands shipconstruction: blackwood 10, log 2, cloth 4 = 16 steps); when the last is paid the ship
  appears as a unit (`dmb.ship`, naval, capacity 30 wares).
* A port is a store on a port space with a dock tile on the water. Two ports of one faction on the same water body are joined by a sea edge in the
  logistics graph while the faction owns a ship: a ware whose route crosses it waits at the port, a ship loads it (up to its capacity), sails to the other
  dock and hands it back to the road network. Wares on ships are held by the ship (the ledger counts them as in flight); a sunk ship loses them.
* A ferry yard makes ferries (a `ferry` ware). A waterway is a road over shallow water; its carrier is a ferry taken from a warehouse.
"""

from __future__ import annotations

import math
from typing import Any

from wizard_rts import wl_defs

SHIP_CAPACITY = 30
SEA_CHECK = 50  # quanta between sea-link refreshes
MAX_WATERWAY_WATER = 6
SHIP_DEFINITION = "dmb.ship"


def _now(world: Any) -> int:
    return int(world.dmb.clock.get("game_ms", 0))


# ------------------------------------------------------------------ shipyards

def ship_cost(tribe: str) -> dict[str, int]:
    imm = wl_defs.defs()["immovables"].get(f"{tribe}_shipconstruction") or {}
    cost = imm.get("buildcost")
    if cost:
        return dict(cost)
    return {"blackwood": 10, "log": 2, "cloth": 4}


def _site_tile(world: Any, b: dict, radius: int = 6) -> tuple[int, int] | None:
    t = world.terrain
    best = None
    occupied = {(u["tx"], u["ty"]) for u in world.units.values() if u.get("alive", True)}
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            x, y = b["tx"] + dx, b["ty"] + dy
            if not t.in_bounds(x, y) or not t.is_shallow(x, y) or (x, y) in occupied or (x, y) in world.blocked:
                continue
            if t.comp_size.get(t.water_comp[y * t.w + x], 0) < 150:
                continue
            key = (abs(dx) + abs(dy), y, x)
            if best is None or key < best[0]:
                best = (key, (x, y))
    return best[1] if best else None


def construct_step(world: Any, b: dict) -> str | None:
    """One `construct` command of a shipyard. None on success, else the reason it failed (the programme retries)."""
    from wizard_rts.economy import _supply

    if world.terrain is None:
        return "no_terrain"
    tribe = world.faction_info[b["faction_name"]]["tribe"]
    site = b.get("ship_site")
    if site is None:
        tile = _site_tile(world, b)
        if tile is None:
            return "no_coast"
        site = b["ship_site"] = {"tile": list(tile), "need": ship_cost(tribe), "steps": 0, "total": sum(ship_cost(tribe).values())}
        world.events.append({"kind": "ship_site", "building": b["id"], "tile": list(tile)})
    stock = world.stocks.setdefault(b["id"], {})
    ware = next((w for w in sorted(site["need"]) if site["need"][w] > 0 and int(stock.get(w, 0)) >= 1), None)
    if ware is None:
        return "inputs"
    _supply(world, b["id"]).remove_wares(ware, 1)
    world.stats["consumed_" + ware] = world.stats.get("consumed_" + ware, 0) + 1
    site["need"][ware] -= 1
    site["steps"] += 1
    if all(n <= 0 for n in site["need"].values()):
        tile = tuple(site["tile"])
        uid = world._unit(b["faction"], b["faction_name"], "ship", "Ship", "dmb.ship", tile)
        world.units[uid]["transfers"] = []
        world.units[uid]["ship"] = True
        b["ship_site"] = None
        world.fstat(b["faction_name"], "ships_built")
        world.events.append({"kind": "ship_built", "unit": uid, "building": b["id"], "faction": b["faction_name"]})
    return None


def ship_progress(b: dict) -> float:
    s = b.get("ship_site")
    return 0.0 if not s else s["steps"] / max(1, s["total"])


# ------------------------------------------------------------------ ferries and waterways

def needs_ferry(world: Any, faction: str) -> bool:
    """`return=skipped unless fleet needs ferry`: some waterway of the faction waits for its ferry and none is in stock."""
    waiting = [rid for rid in world.__dict__.get("waterways", {}) if rid in world.roads and world.waterways[rid]["faction"] == faction
               and not any(c["road_id"] == rid for c in world.carriers.values())]
    if not waiting:
        return False
    return sum(int(world.stocks.get(b["id"], {}).get("ferry", 0)) for b in world.buildings.values()
               if b["faction_name"] == faction and (b["kind"] == "warehouse" or b.get("store"))) == 0


def claim_ferry(world: Any, faction: str, near: str) -> bool:
    from wizard_rts.economy import _supply
    from wizard_rts.logistics import route

    best = None
    for b in world.buildings.values():
        if b["faction_name"] == faction and (b["kind"] == "warehouse" or b.get("store")) and int(world.stocks.get(b["id"], {}).get("ferry", 0)) > 0:
            path = route(world, near, b["id"])
            if path is not None and (best is None or len(path) < best[0]):
                best = (len(path), b["id"])
    if best is None:
        return False
    _supply(world, best[1]).remove_wares("ferry", 1)
    return True


def build_waterway(world: Any, faction: str, a: str, b: str) -> dict[str, Any]:
    """A road over shallow water between two buildings of the faction that stand on a shore (at most MAX_WATERWAY_WATER water nodes)."""
    from collections import deque
    from wizard_rts.logistics import add_road

    ba, bb = world.buildings.get(a), world.buildings.get(b)
    t = world.terrain
    if ba is None or bb is None or t is None or ba["faction_name"] != faction or bb["faction_name"] != faction:
        return {"status": "rejected", "reason": "not_yours"}
    start, goal = (ba["tx"], ba["ty"]), (bb["tx"], bb["ty"])
    prev: dict[tuple[int, int], tuple[tuple[int, int], int]] = {start: (start, 0)}
    q = deque([start])
    found = False
    while q:
        cur = q.popleft()
        wet = prev[cur][1]
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            n = (cur[0] + dx, cur[1] + dy)
            if n in prev or not t.in_bounds(*n) or abs(n[0] - start[0]) + abs(n[1] - start[1]) > 40:
                continue
            if n == goal:
                prev[n] = (cur, wet)
                found = True
                break
            water = t.is_shallow(n[0], n[1]) and n not in world.blocked
            land = t.ground(*n) and n not in world.blocked and n not in world.tree_tiles and n not in world.road_tile_set
            if not (water or land):
                continue
            w2 = wet + (1 if water else 0)
            if w2 > MAX_WATERWAY_WATER:
                continue
            prev[n] = (cur, w2)
            q.append(n)
        if found:
            break
    if not found or prev[goal][1] == 0:
        return {"status": "rejected", "reason": "no_waterway"}
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]][0])
    path.reverse()
    rid = add_road(world, ba["faction"], faction, a, b, path)
    for cid in [c for c, car in world.carriers.items() if car["road_id"] == rid]:
        world.carriers.pop(cid)  # a waterway has no walking carrier: it waits for a ferry
    world.carrier_respawn[rid] = 0
    world.__dict__.setdefault("waterways", {})[rid] = {"faction": faction, "since_ms": _now(world)}
    world.events.append({"kind": "waterway_built", "road": rid, "faction": faction, "water": prev[goal][1]})
    return {"status": "ok", "road": rid, "water_nodes": prev[goal][1]}


# ------------------------------------------------------------------ ports and ships

def ports_of(world: Any, faction: str) -> list[dict]:
    return [b for b in world.buildings.values() if b["faction_name"] == faction and b.get("port") and b.get("operational") and not b.get("constructing") and int(b.get("hp", 1)) > 0]


def ships_of(world: Any, faction: str) -> list[dict]:
    return [u for u in world.units.values() if u.get("ship") and u["faction_name"] == faction and u.get("alive", True)]


def dock_of(world: Any, port: dict) -> tuple[int, int] | None:
    d = port.get("dock")
    if d is not None and world.terrain.is_water(*d):
        return tuple(d)
    t = world.terrain
    best = None
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            x, y = port["tx"] + dx, port["ty"] + dy
            if t.in_bounds(x, y) and t.is_water(x, y) and t.comp_size.get(t.water_comp[y * t.w + x], 0) >= 150:
                key = (abs(dx) + abs(dy), y, x)
                if best is None or key < best[0]:
                    best = (key, (x, y))
    if best:
        port["dock"] = list(best[1])
        return best[1]
    return None


def _comp(world: Any, tile: tuple[int, int]) -> int:
    return world.terrain.water_comp[tile[1] * world.terrain.w + tile[0]]


def refresh_sea_links(world: Any) -> None:
    """Sea edges between the ports of each faction that share a water body, while the faction has a ship."""
    old = world.__dict__.get("_sea_edges", [])
    for a, c, rid in old:
        world.adjacency[a] = [(n, r) for n, r in world.adjacency.get(a, []) if r != rid]
        world.adjacency[c] = [(n, r) for n, r in world.adjacency.get(c, []) if r != rid]
    new = []
    for faction in world.faction_info:
        ports = [p for p in ports_of(world, faction) if dock_of(world, p) is not None]
        if len(ports) < 2 or not ships_of(world, faction):
            continue
        for i, pa in enumerate(ports):
            for pb in ports[i + 1:]:
                if _comp(world, tuple(pa["dock"])) == _comp(world, tuple(pb["dock"])):
                    rid = f"sea:{pa['id']}-{pb['id']}"
                    world.adjacency.setdefault(pa["id"], []).append((pb["id"], rid))
                    world.adjacency.setdefault(pb["id"], []).append((pa["id"], rid))
                    new.append((pa["id"], pb["id"], rid))
    world._sea_edges = new


def _sea_next(transfer: dict) -> str | None:
    p, i = transfer["path"], transfer["i"]
    return p[i + 1] if i + 1 < len(p) else None


def maritime_quantum(world: Any) -> None:
    if world.terrain is None or world.economy_quanta % 5:
        return
    if world.economy_quanta % SEA_CHECK == 0:
        refresh_sea_links(world)
    from wizard_rts import logistics
    from wizard_rts import military

    for u in list(world.units.values()):
        if not u.get("ship") or not u.get("alive", True):
            continue
        port = u.get("at_port")
        dest = u.get("sail_to")
        if dest is not None:
            dp = world.buildings.get(dest)
            if dp is None or int(dp.get("hp", 1)) <= 0:
                u["sail_to"] = None
                continue
            dock = dock_of(world, dp)
            if dock is None:
                u["sail_to"] = None
                continue
            if math.hypot(u["tx"] - dock[0], u["ty"] - dock[1]) <= 1.6:
                fake = {"id": u["id"], "faction": u["faction"]}
                for tr in u["transfers"]:
                    logistics._arrive(world, fake, tr, tr["path"][tr["i"] + 1])  # the same step a carrier takes at the end of a road
                u["transfers"] = []
                u["at_port"], u["sail_to"] = dest, None
                u["order"] = None
                u.pop("order", None)
            elif not u.get("order"):
                military.order_move(world, [u["id"]], dock[0], dock[1])
            continue
        # idle at (or near) a port: take what waits there for another port
        here = port or _nearest_port(world, u)
        if here is None:
            continue
        hp_ = world.buildings.get(here)
        if hp_ is None:
            u["at_port"] = None
            continue
        dock = dock_of(world, hp_)
        if dock is not None and math.hypot(u["tx"] - dock[0], u["ty"] - dock[1]) > 1.6:
            if not u.get("order"):
                military.order_move(world, [u["id"]], dock[0], dock[1])
            continue
        u["at_port"] = here
        waiting = [t for t in world.node_wares.get(here, []) if _sea_next(t) and str(_edge_to(world, here, _sea_next(t))).startswith("sea:")]
        if waiting:
            target = _sea_next(waiting[0])
            load = [t for t in waiting if _sea_next(t) == target][:SHIP_CAPACITY - len(u["transfers"])]
            for t in load:
                world.node_wares[here].remove(t)
                t["state"] = "sailing"
                u["transfers"].append(t)
            if load:
                u["sail_to"] = target
                u["at_port"] = None
                world.events.append({"kind": "ship_sails", "unit": u["id"], "from": here, "to": target, "wares": len(load)})


def _edge_to(world: Any, a: str, b: str) -> str | None:
    for n, rid in world.adjacency.get(a, []):
        if n == b:
            return rid
    return None


def _nearest_port(world: Any, u: dict) -> str | None:
    best = None
    for p in ports_of(world, u["faction_name"]):
        d = abs(p["tx"] - u["tx"]) + abs(p["ty"] - u["ty"])
        if best is None or d < best[0]:
            best = (d, p["id"])
    return best[1] if best else None


def in_flight(world: Any, good: str | None = None, dest: str | None = None) -> int:
    n = 0
    for u in world.units.values():
        if u.get("ship") and u.get("alive", True):
            for t in u.get("transfers", []):
                if (good is None or t["good"] == good) and (dest is None or t["path"][-1] == dest):
                    n += 1
    return n


def sink(world: Any, ship: dict) -> None:
    from wizard_rts.lifecycle import lose

    for t in ship.get("transfers", []):
        lose(world, t["good"], 1)
        world.events.append({"kind": "ware_lost", "good": t["good"], "at": "sea"})
    ship["transfers"] = []

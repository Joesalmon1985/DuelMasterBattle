"""Removal of destroyed things.

A building at 0 HP burns for RUIN_MS and is then purged: its tile frees, its
roads and their carriers go, wares waiting at its flag or in its stock are lost,
and workers have already been cancelled by workers.py. Dead units stay for
CORPSE_MS so the death can be seen, then go.
"""

from __future__ import annotations

from typing import Any

RUIN_MS = 15_000
CORPSE_MS = 2_000


def purge_building(world: Any, bid: str, reason: str) -> None:
    b = world.buildings.pop(bid, None)
    if b is None:
        return
    world.blocked.discard((b["tx"], b["ty"]))
    for p in b.get("footprint", []):
        world.blocked.discard((int(p[0]), int(p[1])))
    lost = sum(int(n) for n in world.stocks.pop(bid, {}).values())
    for rid in [r for r, (a, c) in world.road_edges.items() if bid in (a, c)]:
        _remove_road(world, rid)
    for t in world.node_wares.pop(bid, []):
        lost += 1
    world.recipe_requests.pop(bid, None)
    world.adjacency.pop(bid, None)
    w = world.workers.pop(b.get("worker_id", ""), None)
    if w is not None:
        lost += 1 if w["carrying"] else 0
    if lost:
        world.stats["lost"] = world.stats.get("lost", 0) + lost
    world.events.append({"kind": "building_removed", "id": bid, "reason": reason, "lost": lost})


def _remove_road(world: Any, rid: str) -> None:
    a, c = world.road_edges.pop(rid)
    world.adjacency[a] = [(n, r) for n, r in world.adjacency.get(a, []) if r != rid]
    world.adjacency[c] = [(n, r) for n, r in world.adjacency.get(c, []) if r != rid]
    world.roads.pop(rid, None)
    for cid in [i for i, car in world.carriers.items() if car["road_id"] == rid]:
        car = world.carriers.pop(cid)
        if car["cargo"]:
            world.stats["lost"] = world.stats.get("lost", 0) + 1
    # wares waiting for this road at either end lose their route; send them on toward a warehouse or drop them
    for node in (a, c):
        queue = world.node_wares.get(node, [])
        keep = []
        for t in queue:
            nxt = t["path"][t["i"] + 1] if t["i"] + 1 < len(t["path"]) else None
            if nxt is not None and not any(n == nxt for n, _r in world.adjacency.get(node, [])):
                world.stats["lost"] = world.stats.get("lost", 0) + 1
                world.events.append({"kind": "ware_lost", "good": t["good"], "at": node})
            else:
                keep.append(t)
        world.node_wares[node] = keep
    world.road_tile_set = {tile for tiles in world.roads.values() for tile in tiles}


def lifecycle_quantum(world: Any) -> None:
    for bid, b in list(world.buildings.items()):
        if "hp" in b and int(b["hp"]) <= 0:
            b["ruin_ms"] = int(b.get("ruin_ms", RUIN_MS)) - 100
            if b["ruin_ms"] <= 0:
                purge_building(world, bid, "destroyed")
    for uid, u in list(world.units.items()):
        if not u.get("alive", True):
            u["corpse_ms"] = int(u.get("corpse_ms", CORPSE_MS)) - 100
            if u["corpse_ms"] <= 0:
                world.units.pop(uid, None)

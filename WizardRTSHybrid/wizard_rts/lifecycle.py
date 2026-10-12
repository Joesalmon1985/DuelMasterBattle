"""Removal of destroyed things.

A building at 0 HP burns for RUIN_MS and is then purged: its tile frees, its
roads and their carriers go, wares waiting at its flag or in its stock are lost,
and workers have already been cancelled by workers.py. Dead units stay for
CORPSE_MS so the death can be seen, then go.
"""

from __future__ import annotations

from typing import Any

RUIN_MS = 4_000  # the Widelands burning-building animation plays this long; playtest: 15 s was far too long
CORPSE_MS = 2_000


def begin_destruction(world: Any, b: dict) -> None:
    """The moment a building reaches 0 HP: production, orders and deliveries stop now; the burning sequence starts.

    Collision, roads, territory and the AI's view change when the ruin is purged RUIN_MS later (purge_building)."""
    b["operational"] = False
    b["destroyed"] = True
    b["ruin_ms"] = RUIN_MS
    lost = len(b.get("queue") or [])
    for item in b.get("queue") or []:  # a founder being built dies with the load already taken from the store
        if item.get("state") == "building":
            from wizard_rts import construction as con

            for good, n in sorted(((con.recipe_for(world, b, item["unit"]) or {}).get("cargo") or {}).items()):
                lose(world, good, int(n))
    b["queue"] = []
    b["working"] = False
    world.recipe_requests.pop(b["id"], None)
    from wizard_rts import society

    society.note_loss(world, b)
    world.events.append({"kind": "destruction_started", "id": b["id"], "faction": b.get("faction_name", ""), "queued_orders_cancelled": lost})


def lose(world: Any, good: str, n: int = 1) -> None:
    """Wares destroyed with a building, a road or a vehicle: booked as consumed, so the ware ledger still balances
    (ARCHITECTURE_CONTRACT section 5); `stats['lost']` keeps the count of everything destroyed this way."""
    if n <= 0:
        return
    world.stats["lost"] = world.stats.get("lost", 0) + n
    world.stats["consumed_" + good] = world.stats.get("consumed_" + good, 0) + n
    world.stats["destroyed_" + good] = world.stats.get("destroyed_" + good, 0) + n


def purge_building(world: Any, bid: str, reason: str) -> None:
    b = world.buildings.pop(bid, None)
    if b is None:
        return
    if b.get("kind") == "warehouse" and b.get("destroyed"):
        from wizard_rts import settlements

        settlements.mark_destroyed(world, b, cause=reason)
    world.cc_ids.pop(bid, None)
    world.blocked.discard((b["tx"], b["ty"]))
    for p in list(b.get("footprint", [])) + list(b.get("ground_footprint", [])):
        world.blocked.discard((int(p[0]), int(p[1])))
    lost = 0
    for good, n in sorted(world.stocks.pop(bid, {}).items()):
        lose(world, good, int(n))
        lost += max(0, int(n))
    for rid in [r for r, (a, c) in world.road_edges.items() if bid in (a, c)]:
        _remove_road(world, rid)
    for t in world.node_wares.pop(bid, []):
        lose(world, t["good"], 1)
        lost += 1
    world.recipe_requests.pop(bid, None)
    world.adjacency.pop(bid, None)
    w = world.workers.pop(b.get("worker_id", ""), None)
    if w is not None and w["carrying"]:
        world.stats["lost"] = world.stats.get("lost", 0) + 1  # not yet produced, so not in the ledger
        lost += 1
    world.events.append({"kind": "building_removed", "id": bid, "reason": reason, "lost": lost})


def _remove_road(world: Any, rid: str) -> None:
    a, c = world.road_edges.pop(rid)
    world.adjacency[a] = [(n, r) for n, r in world.adjacency.get(a, []) if r != rid]
    world.adjacency[c] = [(n, r) for n, r in world.adjacency.get(c, []) if r != rid]
    world.roads.pop(rid, None)
    for cid in [i for i, car in world.carriers.items() if car["road_id"] == rid]:
        car = world.carriers.pop(cid)
        if car["cargo"]:
            lose(world, car["cargo"]["good"], 1)
    # wares waiting for this road at either end lose their route; send them on toward a warehouse or drop them
    for node in (a, c):
        queue = world.node_wares.get(node, [])
        keep = []
        for t in queue:
            nxt = t["path"][t["i"] + 1] if t["i"] + 1 < len(t["path"]) else None
            if nxt is not None and not any(n == nxt for n, _r in world.adjacency.get(node, [])):
                lose(world, t["good"], 1)
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

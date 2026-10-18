"""Wizard fire magic: destroy a nearby world entity by its stable id, through the same lifecycles combat uses.

The wizard (the Overworld player) can burn anything he stands close to: buildings (friendly or enemy, the home warehouse too),
military units and ships, workers, carriers, trees, rocks and animals. The simulation checks the range itself, from the wizard's
authoritative tile to the nearest tile of the target, so a client cannot burn what is far away. Nothing is deleted from a picture:

- a building takes lethal damage through `HybridWorld.damage_building`, so it stops at once, burns for `lifecycle.RUIN_MS`, then its
  roads, carriers, workers, stock and footprint are released by `purge_building`;
- a unit dies through `military.kill_unit` (corpse for CORPSE_MS, kill and loss counters);
- a worker aborts through `workers.worker_abort` (the ware in its hands is lost, its tree is released, its hut gets a replacement
  after a delay); a carrier is killed by `logistics.kill_carrier` (its ware is lost, the road gets a new carrier after 20 s);
- a tree is burned by `workers.remove_tree` (a lumberjack that reserved it is told the tree is gone), a rock is removed and its tile
  freed, an animal is removed from the ecology.
"""

from __future__ import annotations

from typing import Any

FIRE_RANGE = 3  # tiles (Chebyshev) from the wizard to the nearest tile of the target
COOLDOWN_MS = 600  # game time between two spells


def _tiles(world: Any, row: dict) -> list[tuple[int, int]]:
    out = [(int(p[0]), int(p[1])) for p in list(row.get("ground_footprint", [])) + list(row.get("footprint", []))]
    return out or [(int(row["tx"]), int(row["ty"]))]


def find(world: Any, target_id: str) -> tuple[str, dict] | None:
    """(class, row) of the entity with this stable id, or None."""
    for cls, table in (("building", world.buildings), ("unit", world.units), ("worker", world.workers), ("carrier", world.carriers),
                       ("tree", world.trees), ("rock", world.rocks), ("animal", world.animals)):
        row = table.get(target_id)
        if row is not None:
            return cls, row
    return None


def distance(world: Any, row: dict) -> int:
    px, py = world.player["tx"], world.player["ty"]
    return min(max(abs(px - x), abs(py - y)) for x, y in _tiles(world, row))


def in_range(world: Any, target_id: str) -> bool:
    found = find(world, target_id)
    return found is not None and distance(world, found[1]) <= FIRE_RANGE


def _release_reserver(world: Any, row: dict, reason: str) -> None:
    """A worker that reserved this object (a lumberjack walking to a tree) is told it is gone and gives up the job."""
    from wizard_rts.workers import _fail_program

    worker = world.workers.get(row.get("reserved_by", ""))
    if worker is not None:
        _fail_program(world, worker, reason)


def _pest_target(world: Any, target_id: str) -> dict | None:
    """The villagers' rats (narrative residents, not roster entities) burn like anything else the wizard stands near."""
    if "narrative" not in world.__dict__:
        return None
    from wizard_rts.narrative import pests, residents

    if not pests.is_pest(world, target_id):
        return None
    r = residents.table(world)[target_id]
    return {"tx": int(r["tile"][0]), "ty": int(r["tile"][1])}


def fire(world: Any, target_id: str) -> dict[str, Any]:
    found = find(world, str(target_id))
    if found is None:
        pest = _pest_target(world, str(target_id))
        if pest is not None:
            found = ("pest", pest)
    if found is None:
        return {"status": "rejected", "reason": "no_target"}
    cls, row = found
    if cls == "unit" and not row.get("alive", True):
        return {"status": "rejected", "reason": "already_dead"}
    if cls == "building" and (row.get("destroyed") or int(row.get("hp", 1)) <= 0):
        return {"status": "rejected", "reason": "already_destroyed"}
    d = distance(world, row)
    if d > FIRE_RANGE:
        return {"status": "rejected", "reason": "too_far", "distance": d, "range": FIRE_RANGE}
    now = int(world.dmb.clock.get("game_ms", 0))
    if getattr(world, "players", None):  # LAN: each wizard recharges on his own (the record world.player is bound to the acting player)
        if now < int(world.player.get("fire_ready_ms", 0)):
            return {"status": "rejected", "reason": "recharging"}
        world.player["fire_ready_ms"] = now + COOLDOWN_MS
    else:
        if now < getattr(world, "_fire_ready_ms", 0):
            return {"status": "rejected", "reason": "recharging"}
        world._fire_ready_ms = now + COOLDOWN_MS
    px, py = world.player["tx"], world.player["ty"]
    tx, ty = int(row["tx"]), int(row["ty"])
    world.effects.append({"t": "bolt", "x1": px, "y1": py, "x2": tx, "y2": ty, "ttl_ms": 400, "keep": 3, "p": "Missile"})
    world.events.append({"kind": "fire_magic", "target": target_id, "class": cls, "distance": d})
    if cls == "building":
        world.damage_building(target_id, 10**9, ["structure"], {}, by="wizard")
    elif cls == "unit":
        from wizard_rts.military import kill_unit

        kill_unit(world, row, "wizard")
    elif cls == "worker":
        from wizard_rts.workers import worker_abort

        if row["carrying"]:
            world.stats["lost"] = world.stats.get("lost", 0) + 1
        worker_abort(world, row, "killed_by_fire_magic")
        world.effects.append({"t": "explosion", "x1": tx, "y1": ty, "x2": tx, "y2": ty, "ttl_ms": 800, "keep": 3, "p": ""})
    elif cls == "carrier":
        from wizard_rts.logistics import kill_carrier

        kill_carrier(world, target_id, "killed_by_fire_magic")
        world.effects.append({"t": "explosion", "x1": tx, "y1": ty, "x2": tx, "y2": ty, "ttl_ms": 800, "keep": 3, "p": ""})
    elif cls == "tree":
        from wizard_rts.workers import remove_tree

        _release_reserver(world, row, "tree_burned")
        remove_tree(world, target_id, "burned")
        world.effects.append({"t": "explosion", "x1": tx, "y1": ty, "x2": tx, "y2": ty, "ttl_ms": 1200, "keep": 4, "p": ""})
    elif cls == "rock":
        _release_reserver(world, row, "rock_burned")
        world.rocks.pop(target_id, None)
        world.events.append({"kind": "rock_removed", "id": target_id, "reason": "burned"})
        world.effects.append({"t": "explosion", "x1": tx, "y1": ty, "x2": tx, "y2": ty, "ttl_ms": 1200, "keep": 4, "p": ""})
    elif cls == "animal":
        _release_reserver(world, row, "game_burned")
        world.animals.pop(target_id, None)
        world.events.append({"kind": "animal_killed", "id": target_id, "by": "wizard"})
        world.effects.append({"t": "explosion", "x1": tx, "y1": ty, "x2": tx, "y2": ty, "ttl_ms": 800, "keep": 3, "p": ""})
    elif cls == "pest":
        from wizard_rts.narrative import pests

        out = pests.burn(world, target_id)
        world.effects.append({"t": "explosion", "x1": tx, "y1": ty, "x2": tx, "y2": ty, "ttl_ms": 800, "keep": 3, "p": ""})
        return {"status": "ok", "class": cls, "target": target_id, **{k: v for k, v in out.items() if k != "status"}}
    return {"status": "ok", "class": cls, "target": target_id}

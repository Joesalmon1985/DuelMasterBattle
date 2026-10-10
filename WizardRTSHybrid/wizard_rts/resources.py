"""Resource extraction and breeding on the terrain grid, following Widelands.

Source (pinned commit in sources/manifest.json):
- ProductionProgram::ActMine::execute (src/logic/map_objects/tribes/production_program.cc):
  a mine digs until `yield` percent of the deposit in its work area is gone; after that it
  only produces with `when_empty` chance and no longer removes anything.
- Worker::run_mine and Worker::run_breed (src/logic/map_objects/tribes/worker_programs/):
  a node is picked with weight 8 * amount plus a small bonus for small amounts; breeding
  weights by how far a node is below its initial amount and never exceeds it.
GPL-2.0-or-later, Widelands Development Team.
"""

from __future__ import annotations

from typing import Any


def _bonus(amount: int) -> int:
    if amount == 0:
        return 0
    if amount <= 2:
        return 6
    if amount <= 4:
        return 4
    if amount <= 6:
        return 2
    return 0


def production_mine(world: Any, building: dict, args: dict) -> bool:
    """ActMine. True if the programme step succeeds (a unit was dug, or the when_empty roll passed)."""
    res, radius = args["resource"], int(args["radius"])
    cells = world.terrain.cells(building["tx"], building["ty"], radius, res)
    total = sum(a for _x, _y, a, _i in cells)
    start = sum(i for _x, _y, _a, i in cells)
    dug = 100.0 if (total == 0 or start == 0) else (start - total) * 100.0 / start
    if dug < float(args["yield"]):
        if total == 0:
            building["deposit_exhausted"] = True
            return False
        chance = sum(8 * a + _bonus(a) for _x, _y, a, _i in cells)
        pick = world.rng.randrange(chance)
        for x, y, a, _i in cells:
            pick -= 8 * a
            if pick < 0:
                world.terrain.take(x, y, res, 1)
                world.events.append({"kind": "mined", "building": building["id"], "resource": res, "node": [x, y]})
                return True
        return False  # the bonus part of the roll: not successful this time
    building["deposit_exhausted"] = True
    return world.rng.random() * 100.0 < float(args["when_empty"])


def worker_mine(world: Any, centre: tuple[int, int], res: str, radius: int) -> bool:
    """Worker::run_mine: take one unit from a weighted node (fishing nets use this with fish)."""
    cells = world.terrain.cells(centre[0], centre[1], radius, res)
    chance = sum(8 * a + _bonus(a) for _x, _y, a, _i in cells)
    if sum(a for _x, _y, a, _i in cells) == 0:
        return False
    pick = world.rng.randrange(chance)
    for x, y, a, _i in cells:
        pick -= 8 * a
        if pick < 0:
            world.terrain.take(x, y, res, 1)
            world.events.append({"kind": "fished" if res == "fish" else "mined", "node": [x, y], "resource": res})
            return True
    return False


def worker_breed(world: Any, centre: tuple[int, int], res: str, radius: int) -> bool:
    """Worker::run_breed: raise one node back toward its initial amount, weighted by the shortfall."""
    cells = world.terrain.cells(centre[0], centre[1], radius, res)
    shortfall = [(x, y, i - a) for x, y, a, i in cells]
    if sum(s for _x, _y, s in shortfall) == 0:
        return False  # the fishing grounds are full
    chance = 0
    for _x, _y, s in shortfall:
        chance += 8 * s
        chance += 1 if s == 0 else 6 if s <= 2 else 4 if s <= 4 else 2 if s <= 6 else 0
    pick = world.rng.randrange(chance)
    for x, y, s in shortfall:
        if s == 0:
            continue
        pick -= 8 * s
        if pick < 0:
            world.terrain.add(x, y, res, 1)
            world.events.append({"kind": "bred", "node": [x, y], "resource": res})
            return True
    return False

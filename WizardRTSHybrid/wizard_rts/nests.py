"""Blight nests: an outbreak as an immobile, hostile military actor (owner decision, 12 Oct 2026).

Every hex region with outbreak cubes holds one nest, a factionless building near the region's busiest workplace (`kind` "blight_nest",
definition "dmb.blight_nest"). Its cubes are its health bars: max_hp = cubes x hp_per_cube of the current era (data/outbreaks.json
`nests`). Any faction's units can attack it through the ordinary combat code (it is "not their faction"); it shoots back with the era's
nest weapon, which hits units only. Every health bar destroyed removes one cube from the region (so the production penalty and the
unrest it feeds fall with it); when the last cube goes the nest is destroyed and the region is clean. Cubes added by the cadence or by
spreading raise its health; the wizard's treatment (regions._treatment) removes a cube and the nest loses that bar.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from typing import Any

from wizard_rts import regions

SYNC_EVERY = 10  # economy quanta: once a game second
KIND = "blight_nest"
DEFINITION = "dmb.blight_nest"


@lru_cache(maxsize=1)
def table() -> list[dict[str, Any]]:
    return json.loads(regions.DATA.read_text())["nests"]["eras"]


def cfg(world: Any) -> dict[str, Any]:
    era = int(getattr(world, "era_index", 0))
    t = table()
    return t[min(era, len(t) - 1)]


def per_cube(world: Any) -> int:
    return int(cfg(world)["hp_per_cube"])


def is_nest(b: dict | None) -> bool:
    return bool(b) and b.get("kind") == KIND


def weapon_name(world: Any) -> str:
    return "DMB_Nest%d" % int(cfg(world)["era"])


def _spawn_tile(world: Any, s: Any, i: int) -> tuple[int, int] | None:
    cands = [b for b in sorted(world.buildings.values(), key=lambda x: x["id"]) if "hp" in b and int(b["hp"]) > 0 and not is_nest(b)
             and s.region_at(b["tx"], b["ty"]) == i and not b.get("destroyed")]
    if cands:
        anchor = sorted(cands, key=lambda b: (not b.get("working"), not b.get("working_once"), b["id"]))[0]
        centre = (anchor["tx"], anchor["ty"])
    else:
        q, r = s.axials[i]
        centre = (int(s.w / 2 + 1.5 * s.size * q), int(s.h / 2 + math.sqrt(3.0) * s.size * (r + q / 2)))
    occupied = {(int(u["tx"]), int(u["ty"])) for u in world.units.values() if u.get("alive", True)}
    for rad in range(3, 14):
        for dy in range(-rad, rad + 1):
            for dx in range(-rad, rad + 1):
                if max(abs(dx), abs(dy)) != rad:
                    continue
                t = (centre[0] + dx, centre[1] + dy)
                if (world.tile_in_map(*t) and t not in world.blocked and t not in world.tree_tiles and t not in world.road_tile_set
                        and t not in world.reserved_tiles and t not in occupied and s.region_at(*t) == i):
                    return t
    return None


def _spawn(world: Any, s: Any, i: int) -> str | None:
    tile = _spawn_tile(world, s, i)
    if tile is None:
        return None
    k = regions.config()["kinds"]
    label = next((x["label"] for x in k if x["id"] == s.kind[i]), "Blight")
    bid = world._building("", "", KIND, tile, "%s nest" % label, DEFINITION)
    b = world.buildings[bid]
    b["nest"] = s.rid(i)
    b["nest_cubes"] = s.cubes[i]
    b["armor"] = cfg(world)["armor"]
    b["hp"] = b["max_hp"] = s.cubes[i] * per_cube(world)
    b["label"] = "%s nest" % label
    world.events.append({"kind": "nest_spawned", "id": bid, "region": s.rid(i), "cubes": s.cubes[i], "hazard": s.kind[i], "tile": list(tile)})
    return bid


def _credit(world: Any, b: dict, cleared: int) -> None:
    by = b.get("last_hit_by", "")
    shooter = world.units.get(by) or world.buildings.get(by)
    who = shooter["faction_name"] if shooter is not None else ("wizard" if by == "wizard" else "")
    if who and who != "wizard":
        world.fstat(who, "nest_cubes_cleared", cleared)
    world.stats["nest_cubes_cleared"] = world.stats.get("nest_cubes_cleared", 0) + cleared
    world.events.append({"kind": "nest_cube_cleared", "id": b["id"], "region": b.get("nest", ""), "cubes": cleared, "by": who})


def nest_quantum(world: Any) -> None:
    if world.economy_quanta % SYNC_EVERY or not hasattr(world, "buildings") or world.terrain is None:
        return
    s = regions.state(world)
    if s is None or s.lost:
        return
    of = world.__dict__.setdefault("_nests", {})  # region index -> nest building id
    per = per_cube(world)
    for i in list(of):
        b = world.buildings.get(of[i])
        if b is None:
            of.pop(i)
            continue
        if int(b.get("hp", 0)) <= 0 or b.get("destroyed"):  # destroyed by an army: the region is clean
            if s.cubes[i] > 0:
                _credit(world, b, s.cubes[i])
                s.cubes[i] = 0
            world.events.append({"kind": "nest_destroyed", "id": b["id"], "region": s.rid(i)})
            of.pop(i)
            continue
        if s.cubes[i] <= 0:  # treated away by the wizard (or the cycle reset): the nest withers
            from wizard_rts.lifecycle import purge_building

            purge_building(world, b["id"], "withered")
            of.pop(i)
            continue
        last = int(b.get("nest_cubes", s.cubes[i]))
        if s.cubes[i] > last:  # the outbreak grew: so does the nest
            b["hp"] = int(b["hp"]) + per * (s.cubes[i] - last)
        b["max_hp"] = per * s.cubes[i]
        b["armor"] = cfg(world)["armor"]
        b["hp"] = min(int(b["hp"]), b["max_hp"])  # a treatment removed a bar; an era change rescales the bars
        left = max(1, math.ceil(int(b["hp"]) / per))
        if left < s.cubes[i]:  # bars shot away: cubes removed, the region's penalty and unrest fall with them
            _credit(world, b, s.cubes[i] - left)
            s.cubes[i] = left
            b["max_hp"] = per * left
        b["nest_cubes"] = s.cubes[i]
    for i, n in enumerate(s.cubes):
        if n > 0 and i not in of:
            bid = _spawn(world, s, i)
            if bid:
                of[i] = bid


def strength(world: Any) -> dict[str, Any]:
    c = cfg(world)
    return {"era": c["era"], "hp_per_cube": c["hp_per_cube"], "damage": c["damage"], "range": c["range"], "armor": c["armor"]}

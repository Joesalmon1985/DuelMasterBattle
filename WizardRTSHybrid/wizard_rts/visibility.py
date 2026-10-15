"""A minimal per-faction visibility layer (owner decision D, 13 Oct 2026).

What a faction sees is what lies within sight of its own things: a unit sees SIGHT_UNIT tiles (flying units a few more), a building SIGHT_BUILDING,
a command centre its whole territory. `visible` answers "can this faction see that tile now"; `explored` remembers every coarse cell a faction
has ever seen, so a capital once discovered stays known. Observations built for an agent list only what is visible or explored, never the whole
world. God Mode and the simulation itself still see everything; this layer filters what an agent is told.

Enemy buildings are also remembered (`memory_of`): an entry is written when the building is in sight (or revealed by a scout or a spy), keeps its
last seen position, kind, hit points and time, and is dropped only when the faction looks at the place again and the building is gone. The memory
is therefore allowed to be stale, which is the point: a controller must scout to refresh it. Nothing here reads a faction's own memory on behalf
of another; controllers reach all of it through neuro/vision.py.
"""

from __future__ import annotations

from typing import Any

SIGHT_UNIT = 7
SIGHT_AIR = 10
SIGHT_BUILDING = 8
CELL = 4  # explored memory is kept in coarse cells
QUANTA = 20  # explored memory refreshes every this many economy quanta (two game seconds)
GRID = 8  # buildings are bucketed in GRID x GRID tile cells for the per-quantum sight scan


def _flying(u: dict) -> bool:
    from wizard_rts import rules

    r = rules.actor(u.get("definition", ""))
    return bool(r and r.get("flying"))


def sources(world: Any, faction: str) -> list[tuple[int, int, int]]:
    """(x, y, radius) of everything of the faction that sees."""
    from wizard_rts import territory

    out: list[tuple[int, int, int]] = []
    for b in world.buildings.values():
        if b.get("faction_name") != faction or int(b.get("hp", 0)) <= 0 or b.get("destroyed"):
            continue
        r = territory.radius_of(b) if b.get("command_center") or b["kind"] == "warehouse" else SIGHT_BUILDING
        out.append((b["tx"], b["ty"], max(SIGHT_BUILDING, r)))
    for u in world.units.values():
        if u.get("faction_name") == faction and u.get("alive", True) and not u.get("inside"):
            out.append((u["tx"], u["ty"], SIGHT_AIR if _flying(u) else SIGHT_UNIT))
    return out


def visible(world: Any, faction: str, tx: int, ty: int, srcs: list[tuple[int, int, int]] | None = None) -> bool:
    for x, y, r in (srcs if srcs is not None else sources(world, faction)):
        if max(abs(tx - x), abs(ty - y)) <= r:
            return True
    return False


def explored_of(world: Any, faction: str) -> set[tuple[int, int]]:
    return world.__dict__.setdefault("vis_explored", {}).setdefault(faction, set())


def memory_of(world: Any, faction: str) -> dict[str, dict[str, Any]]:
    """{enemy building id: {"tile", "kind", "faction_name", "hp", "last_seen_ms"}} for buildings of other factions this faction has seen."""
    return world.__dict__.setdefault("vis_memory", {}).setdefault(faction, {})


def _is_enemy_building(b: dict, faction: str) -> bool:
    """A building of another faction (blight nests, which belong to nobody, are handled by the nest code and not remembered here)."""
    return b.get("faction_name") not in (faction, None, "") and "hp" in b and int(b["hp"]) > 0 and not b.get("destroyed")


def _row(b: dict, now_ms: int) -> dict[str, Any]:
    return {"tile": [b["tx"], b["ty"]], "kind": b["kind"], "faction_name": b["faction_name"],
            "hp": round(int(b["hp"]) / max(1, int(b.get("max_hp", b["hp"]))), 2), "last_seen_ms": now_ms}


def _now(world: Any) -> int:
    return int(world.dmb.clock.get("game_ms", 0))


def remember(world: Any, faction: str, building: dict) -> None:
    """Put one enemy building into the faction's memory (a sighting, a reveal, or the heuristic AI's own scouting rule)."""
    if _is_enemy_building(building, faction):
        memory_of(world, faction)[building["id"]] = _row(building, _now(world))


def building_grid(world: Any) -> dict[tuple[int, int], list[dict]]:
    grid: dict[tuple[int, int], list[dict]] = {}
    for b in world.buildings.values():
        grid.setdefault((b["tx"] // GRID, b["ty"] // GRID), []).append(b)
    return grid


def refresh(world: Any, faction: str, grid: dict[tuple[int, int], list[dict]] | None = None) -> None:
    """Update the faction's explored cells and its memory of enemy buildings from everything it sees now."""
    ex = explored_of(world, faction)
    srcs = sources(world, faction)
    for x, y, r in srcs:
        for cy in range((y - r) // CELL, (y + r) // CELL + 1):
            for cx in range((x - r) // CELL, (x + r) // CELL + 1):
                ex.add((cx, cy))
    mem = memory_of(world, faction)
    grid = building_grid(world) if grid is None else grid
    mem_cells: dict[tuple[int, int], list[str]] = {}
    for bid, e in mem.items():
        mem_cells.setdefault((e["tile"][0] // GRID, e["tile"][1] // GRID), []).append(bid)
    seen: dict[str, dict] = {}
    looked_at: set[str] = set()
    for x, y, r in srcs:
        for cy in range((y - r) // GRID, (y + r) // GRID + 1):
            for cx in range((x - r) // GRID, (x + r) // GRID + 1):
                for b in grid.get((cx, cy), ()):
                    if max(abs(b["tx"] - x), abs(b["ty"] - y)) <= r:
                        seen[b["id"]] = b
                for bid in mem_cells.get((cx, cy), ()):
                    tx, ty = mem[bid]["tile"]
                    if max(abs(tx - x), abs(ty - y)) <= r:
                        looked_at.add(bid)
    for bid in sorted(looked_at):  # the place is in sight again: a building that is not there any more (or is ours now) is forgotten
        b = seen.get(bid)
        if b is None or not _is_enemy_building(b, faction):
            del mem[bid]
    now = _now(world)
    for bid in sorted(seen):
        if _is_enemy_building(seen[bid], faction):
            mem[bid] = _row(seen[bid], now)


def reveal(world: Any, faction: str, tiles: Any) -> None:
    """Tiles shown to the faction by a scout or a spy: the enemy buildings standing on them right now enter its memory."""
    shown = tiles if isinstance(tiles, (set, frozenset)) else set(tiles)
    for b in world.buildings.values():
        if (b["tx"], b["ty"]) in shown:
            remember(world, faction, b)


def visibility_quantum(world: Any) -> None:
    if world.economy_quanta % QUANTA:
        return
    grid = building_grid(world)
    for name in world.faction_info:
        refresh(world, name, grid)


def known(world: Any, faction: str, tx: int, ty: int) -> bool:
    """Has the faction ever seen this tile?"""
    if (tx // CELL, ty // CELL) in explored_of(world, faction):
        return True
    return (tx, ty) in world.__dict__.get("explored", {}).get(faction, ())  # tiles a scout or a spy revealed (workers.py, openra_abilities.py)


def _in_sight(srcs: list[tuple[int, int, int]], xs: list[int], ys: list[int]) -> list[bool]:
    """For each point: is it within some source's Chebyshev radius? (numpy over points x sources; identical to calling `visible` per point)"""
    import numpy as np

    if not srcs or not xs:
        return [False] * len(xs)
    sa = np.asarray(srcs, dtype=np.int64)
    px, py = np.asarray(xs, dtype=np.int64)[:, None], np.asarray(ys, dtype=np.int64)[:, None]
    return ((np.abs(px - sa[None, :, 0]) <= sa[None, :, 2]) & (np.abs(py - sa[None, :, 1]) <= sa[None, :, 2])).any(axis=1).tolist()


def seen_enemies(world: Any, faction: str) -> dict[str, list[dict[str, Any]]]:
    """Other factions' buildings and units that are in sight right now."""
    srcs = sources(world, faction)
    bl = [b for b in world.buildings.values() if b.get("faction_name") not in (faction, None) and "hp" in b and int(b["hp"]) > 0 and not b.get("destroyed")]
    ul = [u for u in world.units.values() if u.get("faction_name") not in (faction, None) and u.get("alive", True) and not u.get("inside") and not u.get("cloaked")]
    bv = _in_sight(srcs, [b["tx"] for b in bl], [b["ty"] for b in bl])
    uv = _in_sight(srcs, [u["tx"] for u in ul], [u["ty"] for u in ul])
    bs = [{"id": b["id"], "faction": b["faction_name"], "kind": b["kind"], "tile": [b["tx"], b["ty"]], "hp": round(int(b["hp"]) / max(1, int(b.get("max_hp", b["hp"]))), 2)}
          for b, v in zip(bl, bv) if v]
    us = [{"id": u["id"], "faction": u["faction_name"], "kind": u["kind"], "tile": [u["tx"], u["ty"]], "hp": round(int(u["hp"]) / max(1, int(u["max_hp"])), 2)}
          for u, v in zip(ul, uv) if v]
    return {"buildings": bs, "units": us}


def visible_units(world: Any, faction: str) -> list[dict[str, Any]]:
    """Other factions' units in sight now (alive, not cloaked, not inside a transport), sorted by id."""
    return sorted(seen_enemies(world, faction)["units"], key=lambda r: r["id"])


def known_enemy_buildings(world: Any, faction: str) -> list[dict[str, Any]]:
    """The faction's memory of enemy buildings as rows sorted by id; may be stale."""
    return [dict(e, id=bid) for bid, e in sorted(memory_of(world, faction).items())]


def visible_regions(world: Any, faction: str) -> set[int]:
    """Catastrophe regions that hold a tile in sight: each source is sampled at its centre, its four edges and its four corners."""
    from wizard_rts import regions

    s = regions.state(world)
    if s is None:
        return set()
    out: set[int] = set()
    for x, y, r in sources(world, faction):
        for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r), (r, r), (r, -r), (-r, r), (-r, -r)):
            px, py = x + dx, y + dy
            if 0 <= px < s.w and 0 <= py < s.h:
                out.add(s.region_at(px, py))
    return out

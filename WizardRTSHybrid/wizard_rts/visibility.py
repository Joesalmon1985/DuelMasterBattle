"""A minimal per-faction visibility layer (owner decision D, 13 Oct 2026).

What a faction sees is what lies within sight of its own things: a unit sees SIGHT_UNIT tiles (flying units a few more), a building SIGHT_BUILDING,
a command centre its whole territory. `visible` answers "can this faction see that tile now"; `explored` remembers every coarse cell a faction
has ever seen, so a capital once discovered stays known. Observations built for an agent list only what is visible or explored, never the whole
world. God Mode and the simulation itself still see everything; this layer filters what an agent is told.
"""

from __future__ import annotations

from typing import Any

SIGHT_UNIT = 7
SIGHT_AIR = 10
SIGHT_BUILDING = 8
CELL = 4  # explored memory is kept in coarse cells
QUANTA = 20  # explored memory refreshes every this many economy quanta (two game seconds)


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
    return world.__dict__.setdefault("explored", {}).setdefault(faction, set())


def refresh(world: Any, faction: str) -> None:
    ex = explored_of(world, faction)
    for x, y, r in sources(world, faction):
        for cy in range((y - r) // CELL, (y + r) // CELL + 1):
            for cx in range((x - r) // CELL, (x + r) // CELL + 1):
                ex.add((cx, cy))


def visibility_quantum(world: Any) -> None:
    if world.economy_quanta % QUANTA:
        return
    for name in world.faction_info:
        refresh(world, name)


def known(world: Any, faction: str, tx: int, ty: int) -> bool:
    """Has the faction ever seen this tile?"""
    return (tx // CELL, ty // CELL) in explored_of(world, faction)


def seen_enemies(world: Any, faction: str) -> dict[str, list[dict[str, Any]]]:
    """Other factions' buildings and units that are in sight right now."""
    srcs = sources(world, faction)
    bs = [{"id": b["id"], "faction": b["faction_name"], "kind": b["kind"], "tile": [b["tx"], b["ty"]], "hp": round(int(b["hp"]) / max(1, int(b.get("max_hp", b["hp"]))), 2)}
          for b in world.buildings.values() if b.get("faction_name") not in (faction, None) and "hp" in b and int(b["hp"]) > 0 and not b.get("destroyed")
          and visible(world, faction, b["tx"], b["ty"], srcs)]
    us = [{"id": u["id"], "faction": u["faction_name"], "kind": u["kind"], "tile": [u["tx"], u["ty"]], "hp": round(int(u["hp"]) / max(1, int(u["max_hp"])), 2)}
          for u in world.units.values() if u.get("faction_name") not in (faction, None) and u.get("alive", True) and not u.get("inside") and not u.get("cloaked")
          and visible(world, faction, u["tx"], u["ty"], srcs)]
    return {"buildings": bs, "units": us}

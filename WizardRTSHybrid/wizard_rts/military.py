"""Military tick.

Damage uses the source-derived OpenRA warhead chain in openra_damage.py.
Movement is still a one-tile step toward the enemy. OpenRA's PathFinder is
not executing: it requires OpenRA's cell world, locomotor, and actor map.
A DuelMasterBattle formation step is not used.
"""

from __future__ import annotations

from typing import Any

from wizard_rts.openra_damage import SOURCE as OPENRA_DAMAGE_SOURCE
from wizard_rts.openra_damage import inflict_damage, warhead_damage

PROVENANCE = OPENRA_DAMAGE_SOURCE["status"]
MOVEMENT_PROVENANCE = "provisional-scaffolding"


def apply_hit(hp: int, max_hp: int = 12) -> int:
    """One adjacent attack: raw damage 4, no extra modifiers, versus 100."""
    applied = warhead_damage(4, [], 100)
    return inflict_damage(hp, max_hp, applied)


def military_quantum(world: Any) -> None:
    world.military_quanta += 1
    units = [u for u in world.units.values() if u.get("alive", True)]
    if len(units) < 2:
        return
    if world.military_quanta % 20 == 0:
        world.events.append({"kind": "ai_military", "units": [u["id"] for u in units]})
    if world.military_quanta % 2 != 0:
        return
    by_faction: dict[str, dict] = {}
    for unit in units:
        by_faction[unit["faction"]] = unit
    factions = list(by_faction)
    if len(factions) < 2:
        return
    a = by_faction[factions[0]]
    b = by_faction[factions[1]]
    if _adjacent(a, b):
        a["hp"] = apply_hit(a["hp"])
        b["hp"] = apply_hit(b["hp"])
        world.stats["attack"] += 1
        world.events.append({"kind": "attack", "a": a["id"], "b": b["id"], "hp": [a["hp"], b["hp"]]})
        for unit in (a, b):
            if unit["hp"] <= 0:
                unit["alive"] = False
                world.stats["destroyed"] += 1
                world.events.append({"kind": "destroyed", "id": unit["id"]})
        return
    _step_toward(world, a, b)
    _step_toward(world, b, a)


def _facing(dx: int, dy: int) -> str:
    if dx == 0 and dy == 0:
        return "s"
    if abs(dx) >= abs(dy) and abs(dy) * 2 < abs(dx):
        return "e" if dx > 0 else "w"
    if abs(dy) > abs(dx) and abs(dx) * 2 < abs(dy):
        return "s" if dy > 0 else "n"
    if dx > 0:
        return "se" if dy > 0 else "ne"
    return "sw" if dy > 0 else "nw"


def _adjacent(a: dict, b: dict) -> bool:
    return abs(int(a["tx"]) - int(b["tx"])) + abs(int(a["ty"]) - int(b["ty"])) == 1


def _step_toward(world: Any, unit: dict, other: dict) -> None:
    dx = int(other["tx"]) - int(unit["tx"])
    dy = int(other["ty"]) - int(unit["ty"])
    if abs(dx) >= abs(dy) and dx != 0:
        step = (int(unit["tx"]) + (1 if dx > 0 else -1), int(unit["ty"]))
    elif dy != 0:
        step = (int(unit["tx"]), int(unit["ty"]) + (1 if dy > 0 else -1))
    else:
        return
    if step in world.blocked or not world.tile_in_map(*step):
        return
    if step == (int(other["tx"]), int(other["ty"])):
        return
    unit["facing"] = _facing(step[0] - int(unit["tx"]), step[1] - int(unit["ty"]))
    unit["status"] = "moving"
    unit["tx"], unit["ty"] = step
    world.stats["move"] += 1
    world.events.append({"kind": "move", "id": unit["id"], "tile": [unit["tx"], unit["ty"]]})

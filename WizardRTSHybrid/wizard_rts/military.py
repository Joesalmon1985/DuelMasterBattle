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


# Provisional weapon table in OpenRA terms: raw damage, tile range, versus armor.
# Values are scaffolding, not read from the OpenRA rules yaml.
WEAPONS: dict[str, dict[str, Any]] = {
    "tank": {"damage": 40, "range": 3, "versus": {"wood": 100, "concrete": 60}},
    "infantry": {"damage": 8, "range": 2, "versus": {"wood": 50, "concrete": 25}},
    "soldier": {"damage": 6, "range": 1, "versus": {"wood": 50, "concrete": 25}},
}
FIRE_EVERY = 4  # military quanta between shots


def order_attack(world: Any, unit_id: str, building_id: str) -> dict[str, Any]:
    unit = world.units.get(unit_id)
    building = world.buildings.get(building_id)
    if unit is None or not unit.get("alive", True):
        return {"status": "rejected", "reason": "no_unit"}
    if building is None or "hp" not in building:
        return {"status": "rejected", "reason": "no_target"}
    if unit["faction"] == building["faction"]:
        return {"status": "rejected", "reason": "friendly"}
    if unit["kind"] not in WEAPONS:
        return {"status": "rejected", "reason": "no_weapon"}
    if int(building["hp"]) <= 0:
        return {"status": "rejected", "reason": "already_destroyed"}
    unit["order"] = {"kind": "attack", "target": building_id}
    unit["status"] = "ordered"
    world.events.append({"kind": "order_attack", "unit": unit_id, "target": building_id})
    return {"status": "ok"}


def _order_step(world: Any, unit: dict) -> None:
    order = unit["order"]
    building = world.buildings.get(order["target"])
    if building is None or int(building.get("hp", 0)) <= 0:
        unit.pop("order", None)
        unit["status"] = "idle"
        return
    weapon = WEAPONS[unit["kind"]]
    dist = abs(int(unit["tx"]) - int(building["tx"])) + abs(int(unit["ty"]) - int(building["ty"]))
    if dist <= weapon["range"]:
        unit["status"] = "attacking"
        if world.military_quanta % FIRE_EVERY == 0:
            dealt = world.damage_building(order["target"], weapon["damage"], ["structure"], weapon["versus"])
            world.stats["attack"] += 1
            world.events.append(
                {"kind": "building_hit", "unit": unit["id"], "target": order["target"], "dealt": dealt, "hp": building["hp"]}
            )
            if int(building["hp"]) <= 0:
                unit.pop("order", None)
                unit["status"] = "idle"
        return
    goal = (int(building["tx"]), int(building["ty"]))
    dx, dy = goal[0] - int(unit["tx"]), goal[1] - int(unit["ty"])
    options = []
    if dx:
        options.append((int(unit["tx"]) + (1 if dx > 0 else -1), int(unit["ty"])))
    if dy:
        options.append((int(unit["tx"]), int(unit["ty"]) + (1 if dy > 0 else -1)))
    if abs(dy) > abs(dx):
        options.reverse()
    for step in options:
        if step in world.blocked or not world.tile_in_map(*step):
            continue
        unit["facing"] = _facing(step[0] - int(unit["tx"]), step[1] - int(unit["ty"]))
        unit["status"] = "moving"
        unit["tx"], unit["ty"] = step
        world.stats["move"] += 1
        return
    unit["status"] = "stuck"


def military_quantum(world: Any) -> None:
    world.military_quanta += 1
    for unit in list(world.units.values()):
        if unit.get("alive", True) and unit.get("order"):
            _order_step(world, unit)
    units = [u for u in world.units.values() if u.get("alive", True) and not u.get("order")]
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

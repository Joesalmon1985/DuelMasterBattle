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


MOVE_MS = {"tank": 570, "infantry": 760, "soldier": 760}  # OpenRA Speed 72 / 54 per cell at 25 ticks/s


def _occupied(world: Any, me: dict) -> set[tuple[int, int]]:
    return {(u["tx"], u["ty"]) for u in world.units.values() if u.get("alive", True) and u is not me}


def _walk(world: Any, unit: dict, goal: tuple[int, int], stop_at_range: int = 0) -> str:
    """Advance one quantum toward goal. Returns 'moving', 'arrived' or 'stuck'."""
    from wizard_rts.forestry import find_path

    here = (int(unit["tx"]), int(unit["ty"]))
    if max(abs(goal[0] - here[0]), abs(goal[1] - here[1])) <= stop_at_range or here == goal:
        unit["path"] = []
        return "arrived"
    others = _occupied(world, unit)
    if not unit.get("path") or unit.get("path_goal") != list(goal):
        path = find_path(world, here, goal, limit=400, avoid=others)
        if path is None:
            unit["status"] = "stuck"
            return "stuck"
        unit["path"], unit["path_goal"] = path, list(goal)
        unit["progress_ms"] = 0
    nxt = unit["path"][0]
    if nxt in others:
        unit["blocked_ms"] = unit.get("blocked_ms", 0) + 100
        unit["status"] = "blocked"
        if unit["blocked_ms"] >= 1000:  # someone is standing in the way: route around
            unit["path"] = []
            unit["blocked_ms"] = 0
        return "moving"
    unit["blocked_ms"] = 0
    unit["progress_ms"] = unit.get("progress_ms", 0) + 100
    unit["status"] = "moving"
    if unit["progress_ms"] >= MOVE_MS.get(unit["kind"], 760):
        unit["facing"] = _facing(nxt[0] - here[0], nxt[1] - here[1])
        unit["tx"], unit["ty"] = nxt
        unit["path"].pop(0)
        unit["progress_ms"] = 0
        world.stats["move"] += 1
    return "moving"


def _order_step(world: Any, unit: dict) -> None:
    order = unit["order"]
    if order["kind"] == "move":
        if _walk(world, unit, tuple(order["tile"])) in ("arrived", "stuck"):
            unit.pop("order", None)
            unit["status"] = "idle"
        return
    building = world.buildings.get(order["target"])
    if building is None or int(building.get("hp", 0)) <= 0:
        unit.pop("order", None)
        unit["status"] = "idle"
        return
    weapon = WEAPONS[unit["kind"]]
    dist = abs(int(unit["tx"]) - int(building["tx"])) + abs(int(unit["ty"]) - int(building["ty"]))
    if dist <= weapon["range"]:
        unit["path"] = []
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
    result = _walk(world, unit, (int(building["tx"]), int(building["ty"])), stop_at_range=max(weapon["range"] - 2, 0))
    if result == "stuck":
        unit.pop("order", None)
        unit["status"] = "idle"
        world.events.append({"kind": "order_failed", "unit": unit["id"], "reason": "no_path"})


def order_move(world: Any, unit_ids: list[str], tx: int, ty: int) -> dict[str, Any]:
    if not world.tile_in_map(int(tx), int(ty)):
        return {"status": "rejected", "reason": "outside_map"}
    moved = 0
    for k, uid in enumerate(unit_ids):
        unit = world.units.get(uid)
        if unit is None or not unit.get("alive", True):
            continue
        # spread a group into a loose block instead of stacking on one tile
        ox, oy = k % 3 - 1, k // 3 - 1
        goal = [int(tx) + ox, int(ty) + oy]
        if not world.tile_in_map(*goal) or tuple(goal) in world.blocked:
            goal = [int(tx), int(ty)]
        unit["order"] = {"kind": "move", "tile": goal}
        unit["path"] = []
        moved += 1
    world.events.append({"kind": "order_move", "units": list(unit_ids), "tile": [int(tx), int(ty)]})
    return {"status": "ok" if moved else "rejected", "moved": moved}


def order_stop(world: Any, unit_ids: list[str]) -> dict[str, Any]:
    for uid in unit_ids:
        unit = world.units.get(uid)
        if unit is not None:
            unit.pop("order", None)
            unit["path"] = []
            unit["status"] = "idle"
    return {"status": "ok"}


def military_quantum(world: Any) -> None:
    world.military_quanta += 1
    for unit in list(world.units.values()):
        if unit.get("alive", True) and unit.get("order"):
            _order_step(world, unit)
    units = [
        u for u in world.units.values()
        if u.get("alive", True) and not u.get("order") and u["faction_name"] != world.controlled_faction
    ]
    if len(units) < 2:
        return
    if world.military_quanta % 20 == 0:
        world.events.append({"kind": "ai_military", "units": [u["id"] for u in units]})
    if world.military_quanta % 2 != 0:
        return
    by_faction: dict[str, dict] = {}
    for unit in units:
        by_faction[unit["faction"]] = unit
    if len(by_faction) < 2:
        return
    reps = list(by_faction.values())
    for unit in reps:
        enemies = [o for o in reps if o["faction"] != unit["faction"] and o.get("alive", True)]
        if not enemies or not unit.get("alive", True):
            continue
        other = min(enemies, key=lambda o: abs(int(o["tx"]) - int(unit["tx"])) + abs(int(o["ty"]) - int(unit["ty"])))
        if _adjacent(unit, other):
            other["hp"] = apply_hit(other["hp"])
            world.stats["attack"] += 1
            world.events.append({"kind": "attack", "a": unit["id"], "b": other["id"], "hp": [unit["hp"], other["hp"]]})
            if other["hp"] <= 0:
                other["alive"] = False
                world.stats["destroyed"] += 1
                world.events.append({"kind": "destroyed", "id": other["id"]})
        else:
            _step_toward(world, unit, other)


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

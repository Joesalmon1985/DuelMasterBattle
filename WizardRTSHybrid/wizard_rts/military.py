"""Military simulation: orders, movement, target acquisition, weapons, projectiles.

Adapted from OpenRA's trait model with the numbers taken from its rules: health,
armor, speed, weapon range / reload / burst / projectile speed and the warhead
Versus table (see rules.py). Damage goes through the OpenRA warhead chain in
openra_damage.py for units and for buildings alike.

Not OpenRA: pathfinding is A* over tiles with occupancy (not the hierarchical
PathFinder and locomotors), there are no formations, spread damage hits only
the primary target, and sub-cell positions do not exist.
"""

from __future__ import annotations

import math
from typing import Any

from wizard_rts import rules
from wizard_rts.openra_damage import SOURCE as OPENRA_DAMAGE_SOURCE
from wizard_rts.openra_damage import damage_versus, inflict_damage, warhead_damage

PROVENANCE = OPENRA_DAMAGE_SOURCE["status"]
MOVEMENT_PROVENANCE = "astar-with-occupancy (not OpenRA PathFinder)"
SCAN_EVERY = 5  # quanta between target scans (OpenRA AutoTarget scans about every 0.5 s)
CHASE_LEASH = 3.0  # extra cells an idle unit will chase beyond its weapon range
EFFECT_MS = 400


def apply_hit(hp: int, max_hp: int = 12) -> int:
    """Kept for the original damage test: one 4-point hit through the warhead chain."""
    return inflict_damage(hp, max_hp, warhead_damage(4, [], 100))


# ------------------------------------------------------------------ setup

def init_unit(unit: dict) -> None:
    r = rules.actor(unit["definition"])
    if r is None:
        unit.update(hp=12, max_hp=12, armor="None", move_ms=760, weapon=None, cooldown_ms=0, target=None)
        return
    unit["hp"] = unit["max_hp"] = int(r["hp"])
    unit["armor"] = r["armor"] or "None"
    unit["move_ms"] = rules.ms_per_cell(int(r["speed"])) if r["speed"] else 760
    w = rules.weapon(r["armaments"][0]) if r["armaments"] else None
    unit["weapon"] = r["armaments"][0] if w else None
    unit["cooldown_ms"] = 0
    unit["target"] = None


def building_weapon(b: dict) -> dict | None:
    definition = b.get("definition", "")
    r = rules.actor(definition) if definition.startswith("openra.") else None
    if r and r["armaments"] and b.get("operational", True):
        return rules.weapon(r["armaments"][0])
    return None


# ------------------------------------------------------------------ geometry

def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def _occupied(world: Any, me: dict) -> set[tuple[int, int]]:
    return {(u["tx"], u["ty"]) for u in world.units.values() if u.get("alive", True) and u is not me}


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


def _walk(world: Any, unit: dict, goal: tuple[int, int], stop_within: float = 0.0) -> str:
    """Advance one quantum toward goal. Returns 'moving', 'arrived' or 'stuck'."""
    from wizard_rts.workers import find_path

    here = (int(unit["tx"]), int(unit["ty"]))
    if here == goal or _dist(here[0], here[1], goal[0], goal[1]) <= stop_within:
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
    if unit["progress_ms"] >= unit.get("move_ms", 760):
        unit["facing"] = _facing(nxt[0] - here[0], nxt[1] - here[1])
        unit["tx"], unit["ty"] = nxt
        unit["path"].pop(0)
        unit["progress_ms"] = 0
        world.stats["move"] += 1
    return "moving"


# ------------------------------------------------------------------ targets

def _target_pos(world: Any, target: dict) -> tuple[float, float, dict] | None:
    if target["kind"] == "unit":
        u = world.units.get(target["id"])
        if u is None or not u.get("alive", True):
            return None
        return u["tx"], u["ty"], u
    b = world.buildings.get(target["id"])
    if b is None or "hp" not in b or int(b["hp"]) <= 0:
        return None
    return b["tx"], b["ty"], b


CELL = 16


def _build_grid(world: Any) -> None:
    grid: dict[tuple[int, int], tuple[list, list]] = {}
    for u in world.units.values():
        if u.get("alive", True):
            grid.setdefault((u["tx"] // CELL, u["ty"] // CELL), ([], []))[0].append(u)
    for b in world.buildings.values():
        if "hp" in b and int(b["hp"]) > 0:
            grid.setdefault((b["tx"] // CELL, b["ty"] // CELL), ([], []))[1].append(b)
    world._grid = grid


def _scan(world: Any, faction: str, pos: tuple[float, float], radius: float) -> dict | None:
    """Nearest enemy unit, or building if no unit, within radius (cells). Uses the per-scan grid."""
    grid = getattr(world, "_grid", None)
    if grid is None:
        _build_grid(world)
        grid = world._grid
    cx0, cx1 = int((pos[0] - radius) // CELL), int((pos[0] + radius) // CELL)
    cy0, cy1 = int((pos[1] - radius) // CELL), int((pos[1] + radius) // CELL)
    best_u: tuple[float, dict] | None = None
    best_b: tuple[float, dict] | None = None
    for cy in range(cy0, cy1 + 1):
        for cx in range(cx0, cx1 + 1):
            cell = grid.get((cx, cy))
            if cell is None:
                continue
            for u in cell[0]:
                if u["faction"] == faction or not u.get("alive", True):
                    continue
                d = _dist(pos[0], pos[1], u["tx"], u["ty"])
                if d <= radius and (best_u is None or d < best_u[0]):
                    best_u = (d, u)
            if best_u is None:
                for b in cell[1]:
                    if b["faction"] == faction or int(b["hp"]) <= 0:
                        continue
                    d = _dist(pos[0], pos[1], b["tx"], b["ty"])
                    if d <= radius and (best_b is None or d < best_b[0]):
                        best_b = (d, b)
    if best_u is not None:
        return {"kind": "unit", "id": best_u[1]["id"]}
    if best_b is not None:
        return {"kind": "building", "id": best_b[1]["id"]}
    return None


def _fire(world: Any, shooter: dict, w: dict, target: dict, entity: dict, dist: float) -> None:
    """One volley. Damage lands after the projectile's flight time."""
    speed = int(w.get("projectile_speed") or 0)
    flight_ms = int(dist * 1024 / speed * 40) if speed else 0
    for k in range(int(w.get("burst", 1))):
        delay = flight_ms + k * int(w.get("burst_delay", 5)) * 40
        world.projectiles.append(
            {"left_ms": delay, "target": dict(target), "warheads": w["warheads"], "shooter": shooter["id"]}
        )
        world.effects.append(
            {"t": "shot", "x1": shooter["tx"], "y1": shooter["ty"], "x2": entity["tx"], "y2": entity["ty"],
             "ttl_ms": EFFECT_MS + delay, "keep": 3, "p": w.get("projectile", "")}
        )
    world.stats["attack"] += 1
    if len(world.effects) > 120:
        del world.effects[:-120]


def _apply_warheads(world: Any, p: dict) -> None:
    pos = _target_pos(world, p["target"])
    if pos is None:
        return
    entity = pos[2]
    for wh in p["warheads"]:
        if p["target"]["kind"] == "building":
            world.damage_building(p["target"]["id"], int(wh["damage"]), ["structure"], wh.get("versus", {}) or {})
            continue
        versus = damage_versus(wh.get("versus", {}), [str(entity.get("armor", "None"))])
        applied = warhead_damage(int(wh["damage"]), [], versus)
        before = int(entity["hp"])
        entity["hp"] = inflict_damage(before, int(entity["max_hp"]), applied)
        world.events.append({"kind": "unit_hit", "unit": entity["id"], "by": p["shooter"], "dealt": before - entity["hp"], "hp": entity["hp"]})
        if before > 0 and entity["hp"] <= 0:
            entity["alive"] = False
            entity["status"] = "dead"
            entity.pop("order", None)
            entity["path"] = []
            world.stats["destroyed"] += 1
            world.stats["units_lost"] = world.stats.get("units_lost", 0) + 1
            world.effects.append({"t": "explosion", "x1": entity["tx"], "y1": entity["ty"], "x2": entity["tx"], "y2": entity["ty"], "ttl_ms": 800, "keep": 3, "p": ""})
            world.events.append({"kind": "destroyed", "id": entity["id"], "by": p["shooter"]})


def projectile_quantum(world: Any) -> None:
    keep = []
    for p in world.projectiles:
        p["left_ms"] -= 100
        if p["left_ms"] <= 0:
            _apply_warheads(world, p)
        else:
            keep.append(p)
    world.projectiles = keep
    for e in world.effects:
        e["ttl_ms"] -= 100
    world.effects[:] = [e for e in world.effects if e["ttl_ms"] > 0 or e.get("keep", 0) > 0]


# ------------------------------------------------------------------ orders

def order_attack(world: Any, unit_id: str, building_id: str) -> dict[str, Any]:
    unit = world.units.get(unit_id)
    building = world.buildings.get(building_id)
    if unit is None or not unit.get("alive", True):
        return {"status": "rejected", "reason": "no_unit"}
    if building is None or "hp" not in building:
        return {"status": "rejected", "reason": "no_target"}
    if unit["faction"] == building["faction"]:
        return {"status": "rejected", "reason": "friendly"}
    if not unit.get("weapon"):
        return {"status": "rejected", "reason": "no_weapon"}
    if int(building["hp"]) <= 0:
        return {"status": "rejected", "reason": "already_destroyed"}
    unit["order"] = {"kind": "attack", "target": building_id}
    unit["target"] = None
    unit["status"] = "ordered"
    world.events.append({"kind": "order_attack", "unit": unit_id, "target": building_id})
    return {"status": "ok"}


def order_move(world: Any, unit_ids: list[str], tx: int, ty: int, attack_move: bool = False) -> dict[str, Any]:
    if not world.tile_in_map(int(tx), int(ty)):
        return {"status": "rejected", "reason": "outside_map"}
    moved = 0
    for k, uid in enumerate(unit_ids):
        unit = world.units.get(uid)
        if unit is None or not unit.get("alive", True):
            continue
        ox, oy = k % 3 - 1, k // 3 - 1  # spread a group into a loose block
        goal = [int(tx) + ox, int(ty) + oy]
        if not world.tile_in_map(*goal) or tuple(goal) in world.blocked:
            goal = [int(tx), int(ty)]
        unit["order"] = {"kind": "attack_move" if attack_move else "move", "tile": goal}
        unit["path"] = []
        unit["target"] = None
        moved += 1
    world.events.append({"kind": "order_attack_move" if attack_move else "order_move", "units": list(unit_ids), "tile": [int(tx), int(ty)]})
    return {"status": "ok" if moved else "rejected", "moved": moved}


def order_stop(world: Any, unit_ids: list[str]) -> dict[str, Any]:
    for uid in unit_ids:
        unit = world.units.get(uid)
        if unit is not None:
            unit.pop("order", None)
            unit["path"] = []
            unit["target"] = None
            unit["status"] = "idle"
    return {"status": "ok"}


# ------------------------------------------------------------------ per-unit tick

def _engage(world: Any, unit: dict, w: dict, chase: bool, leash: float) -> bool:
    """Acquire, chase and shoot. True if the unit used its turn."""
    pos = (unit["tx"], unit["ty"])
    target = unit.get("target")
    if target is not None and _target_pos(world, target) is None:
        target = unit["target"] = None
    if world.military_quanta % SCAN_EVERY == 0 or target is None:
        found = _scan(world, unit["faction"], pos, w["range"] + (leash if chase else 0.0))
        if found is not None:
            target = unit["target"] = found
    if target is None:
        return False
    tpos = _target_pos(world, target)
    if tpos is None:
        unit["target"] = None
        return False
    dist = _dist(pos[0], pos[1], tpos[0], tpos[1])
    if dist <= w["range"]:
        unit["path"] = []
        unit["status"] = "attacking"
        unit["facing"] = _facing(int(tpos[0]) - pos[0], int(tpos[1]) - pos[1])
        if unit["cooldown_ms"] <= 0 and dist >= w.get("min_range", 0):
            _fire(world, unit, w, target, tpos[2], dist)
            unit["cooldown_ms"] = rules.reload_ms(w)
        return True
    if chase:
        _walk(world, unit, (int(tpos[0]), int(tpos[1])), stop_within=max(w["range"] - 0.5, 0.5))
        return True
    return False


def _unit_step(world: Any, unit: dict) -> None:
    unit["cooldown_ms"] = max(0, int(unit.get("cooldown_ms", 0)) - 100)
    w = rules.weapon(unit["weapon"]) if unit.get("weapon") else None
    order = unit.get("order")
    if order is None:
        if w is not None:
            chase = unit["faction_name"] != world.controlled_faction
            if not _engage(world, unit, w, chase=chase, leash=CHASE_LEASH if chase else 0.0):
                unit["status"] = "idle"
        return
    kind = order["kind"]
    if kind == "move":
        if _walk(world, unit, tuple(order["tile"])) in ("arrived", "stuck"):
            unit.pop("order", None)
            unit["status"] = "idle"
        return
    if kind == "attack_move":
        if w is not None and _engage(world, unit, w, chase=False, leash=0.0):
            return
        if _walk(world, unit, tuple(order["tile"])) in ("arrived", "stuck"):
            unit.pop("order", None)
            unit["status"] = "idle"
        return
    building = world.buildings.get(order["target"])
    if building is None or int(building.get("hp", 0)) <= 0 or w is None:
        unit.pop("order", None)
        unit["status"] = "idle"
        return
    dist = _dist(unit["tx"], unit["ty"], building["tx"], building["ty"])
    if dist <= w["range"]:
        unit["path"] = []
        unit["status"] = "attacking"
        if unit["cooldown_ms"] <= 0:
            _fire(world, unit, w, {"kind": "building", "id": building["id"]}, building, dist)
            unit["cooldown_ms"] = rules.reload_ms(w)
        return
    if _walk(world, unit, (building["tx"], building["ty"]), stop_within=max(w["range"] - 0.5, 0.5)) == "stuck":
        unit.pop("order", None)
        unit["status"] = "idle"
        world.events.append({"kind": "order_failed", "unit": unit["id"], "reason": "no_path"})


def _building_step(world: Any, b: dict) -> None:
    w = building_weapon(b)
    if w is None or b.get("constructing"):
        return
    b["cooldown_ms"] = max(0, int(b.get("cooldown_ms", 0)) - 100)
    target = b.get("target")
    if target is not None and _target_pos(world, target) is None:
        target = b["target"] = None
    if world.military_quanta % SCAN_EVERY == 0 or target is None:
        b["target"] = target = _scan(world, b["faction"], (b["tx"], b["ty"]), w["range"])
    if target is None:
        return
    tpos = _target_pos(world, target)
    if tpos is None:
        return
    dist = _dist(b["tx"], b["ty"], tpos[0], tpos[1])
    if dist <= w["range"] and b["cooldown_ms"] <= 0:
        _fire(world, b, w, target, tpos[2], dist)
        b["cooldown_ms"] = rules.reload_ms(w)


def military_quantum(world: Any) -> None:
    world.military_quanta += 1
    if world.military_quanta % SCAN_EVERY == 0:
        _build_grid(world)
    projectile_quantum(world)
    for unit in list(world.units.values()):
        if unit.get("alive", True):
            _unit_step(world, unit)
    for b in list(world.buildings.values()):
        if "hp" in b and int(b["hp"]) > 0 and b.get("definition", "").startswith("openra."):
            _building_step(world, b)
    if world.military_quanta % 20 == 0:
        alive = [u["id"] for u in world.units.values() if u.get("alive", True)]
        if len(alive) >= 2:
            world.events.append({"kind": "ai_military", "units": alive[:20]})

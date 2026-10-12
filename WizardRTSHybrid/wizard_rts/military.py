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
PATH_SEARCHES_PER_QUANTUM = 1
JOIN_SEARCHES_PER_QUANTUM = 4  # short searches that join a shared route
CHASE_LEASH = 3.0  # extra cells an idle unit will chase beyond its weapon range
EFFECT_MS = 400


def apply_hit(hp: int, max_hp: int = 12) -> int:
    """Kept for the original damage test: one 4-point hit through the warhead chain."""
    return inflict_damage(hp, max_hp, warhead_damage(4, [], 100))


# ------------------------------------------------------------------ setup

def init_unit(unit: dict) -> None:
    r = rules.actor(unit["definition"])
    if r is None:
        unit.update(hp=12, max_hp=12, armor="None", move_ms=760, weapon=None, weapons=[], cds={}, loco="foot", cooldown_ms=0, target=None)
        return
    unit["hp"] = unit["max_hp"] = int(r["hp"])
    unit["armor"] = r["armor"] or "None"
    unit["move_ms"] = rules.ms_per_cell(int(r["speed"])) if r["speed"] else 760
    unit["loco"] = r.get("locomotor") or "foot"
    unit["weapons"] = [n for n in r["armaments"] if rules.weapon(n)]
    unit["cds"] = {n: 0 for n in unit["weapons"]}
    unit["weapon"] = unit["weapons"][0] if unit["weapons"] else None
    unit["cooldown_ms"] = 0
    unit["target"] = None
    if r.get("cloak"):
        unit["cloaked"] = True  # OpenRA Cloak with InitialDelay 0
        unit["uncloak_ms"] = 0


def building_weapon(b: dict) -> dict | None:
    definition = b.get("definition", "")
    r = rules.actor(definition) if definition.startswith("openra.") else None
    if r and r["armaments"] and b.get("operational", True):
        return rules.weapon(r["armaments"][0])
    if b.get("kind") == "blight_nest" and not b.get("destroyed"):
        from wizard_rts import nests

        return rules.weapon(nests.weapon_name(_world_ref[0])) if _world_ref else rules.weapon("DMB_Nest0")
    if b.get("command_center") and b.get("operational", True) and not b.get("destroyed") and not b.get("constructing"):
        # a settlement's militia (a Widelands headquarters holds soldiers): a small raid cannot simply walk in (12 Oct 2026)
        return rules.weapon("DMB_Militia")
    return None


# ------------------------------------------------------------------ target types, cloaking, detection

def _conditions(entity: dict) -> set[str]:
    out = set()
    if entity.get("cloaked"):
        out.add("underwater")
    if int(entity.get("hp", 1)) < int(entity.get("max_hp", 1)):
        out.add("damaged")
    return out


def _requires_ok(expr: str, conds: set[str]) -> bool:
    if not expr:
        return True
    for part in expr.split("&&"):
        part = part.strip()
        if part.startswith("!"):
            if part[1:] in conds:
                return False
        elif part not in conds:
            return False
    return True


def target_types(entity: dict) -> set[str]:
    """OpenRA Targetable.TargetTypes of an entity right now (conditions such as a cloaked submarine apply)."""
    definition = entity.get("definition", "")
    r = rules.actor(definition) if (definition.startswith(("openra.", "mindustry.")) or definition in ("widelands.soldier", "dmb.blight_nest")) else None
    if r is None:
        return {"GroundActor", "Structure"} if "target_type" in entity else {"GroundActor"}  # Widelands buildings and units
    targ = r.get("targetable")
    if not targ:
        return set(r.get("target_types", []))
    conds = _conditions(entity)
    out: set[str] = set()
    for spec in targ.values():
        if _requires_ok(spec.get("requires", ""), conds):
            out.update(spec["types"])
    return out


def update_cloak(unit: dict) -> None:
    """Cloak: hidden unless it fired in the last CloakDelay or is critically damaged (GrantConditionOnDamageState Critical)."""
    r = rules.actor(unit["definition"])
    if not r or not r.get("cloak"):
        return
    unit["uncloak_ms"] = max(0, int(unit.get("uncloak_ms", 0)) - 100)
    critical = int(unit["hp"]) * 4 <= int(unit["max_hp"])
    unit["cloaked"] = unit["uncloak_ms"] <= 0 and not critical


def detected_by(world: Any, faction: str, target: dict) -> bool:
    """A cloaked target can only be attacked while a friendly DetectCloaked actor of a matching type is in range."""
    if not target.get("cloaked"):
        return True
    r = rules.actor(target["definition"]) or {}
    kinds = set((r.get("cloak") or {}).get("detection_types", []))
    for pool in (world.units.values(), world.buildings.values()):
        for e in pool:
            if e["faction"] != faction or not e.get("alive", True) or ("hp" in e and int(e["hp"]) <= 0) or e.get("constructing"):
                continue
            er = rules.actor(e.get("definition", "")) if e.get("definition", "").startswith("openra.") else None
            det = (er or {}).get("detect")
            if det and kinds & set(det["types"]) and _dist(e["tx"], e["ty"], target["tx"], target["ty"]) <= float(det["range"]):
                return True
    return False


def weapon_can_attack(world: Any, faction: str, w: dict, entity: dict) -> bool:
    return rules.can_hit(w, target_types(entity)) and detected_by(world, faction, entity)


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


_NO_BUDGET: list = []  # sentinel: this quantum's route searches are spent


def _shared_route(world: Any, here: tuple[int, int], goal: tuple[int, int], others: set, loco: str | None, fresh: bool = False) -> list | None:
    """A route for one unit. Units heading to the same goal share a cached route: a unit standing on it just follows, any other
    searches only as far as the route and joins it. Only a full search costs budget (PATH_SEARCHES_PER_QUANTUM per quantum)."""
    from wizard_rts.workers import find_path

    cache = world.__dict__.setdefault("_route_cache", {})
    failed = world.__dict__.setdefault("_route_failed", {})
    key = (loco, goal)
    cell = (here[0] // 12, here[1] // 12)
    if world.military_quanta - failed.get((key, cell), -10**9) < 100:
        return None  # nobody near here could get there a few seconds ago; do not repeat a failing wide search every quantum
    hit = None if fresh else cache.get(key)
    if hit is not None and world.military_quanta - hit["q"] > 600:
        cache.pop(key, None)
        hit = None
    if hit is not None:
        index = hit["index"]
        if here in index:
            return list(hit["path"][index[here] + 1:])
        if world.join_searches >= JOIN_SEARCHES_PER_QUANTUM:
            return _NO_BUDGET
        world.join_searches += 1
        part = find_path(world, here, goal, limit=400, avoid=others, max_nodes=8_000, loco=loco, join=index)
        if part is not None and part:
            tail = part[-1]
            if tail == goal:
                return part
            if tail in index:
                return part + list(hit["path"][index[tail] + 1:])
    if world.path_searches >= PATH_SEARCHES_PER_QUANTUM:
        return _NO_BUDGET
    world.path_searches += 1
    path = find_path(world, here, goal, limit=400, avoid=others, max_nodes=150_000, loco=loco)
    if path is None and loco in ("naval", "lcraft"):
        path = _path_toward(world, here, goal, others, loco)  # a ship goes as near as the water allows
    if path is None:
        failed[(key, cell)] = world.military_quanta
        if len(failed) > 2000:
            failed.clear()
    if path:
        full = [here] + list(path)
        cache[key] = {"path": full, "index": {t: i for i, t in enumerate(full)}, "q": world.military_quanta}
        if len(cache) > 200:
            for k in sorted(cache, key=lambda k: cache[k]["q"])[:100]:
                cache.pop(k)
    return path


def _walk(world: Any, unit: dict, goal: tuple[int, int], stop_within: float = 0.0) -> str:
    """Advance one quantum toward goal. Returns 'moving', 'arrived' or 'stuck'."""
    from wizard_rts.workers import find_path

    here = (int(unit["tx"]), int(unit["ty"]))
    if here == goal or _dist(here[0], here[1], goal[0], goal[1]) <= stop_within:
        unit["path"] = []
        return "arrived"
    others = _occupied(world, unit)
    loco = unit.get("loco")
    if goal in others and _dist(here[0], here[1], goal[0], goal[1]) <= 2.0:
        unit["path"] = []  # somebody already stands on the destination tile: this close is there (a guard post, a rally point)
        return "arrived"
    if not unit.get("path") or unit.get("path_goal") != list(goal):
        # A long march by a whole army is dozens of wide A* searches. Spread them over quanta (a count, so replays stay deterministic):
        # once this quantum's searches are spent the unit waits a quantum, visibly, rather than freezing the world for seconds.
        path = _shared_route(world, here, goal, others, loco, bool(unit.pop("fresh_route", False)))
        if path is _NO_BUDGET:
            unit["status"] = "waiting_route"
            return "moving"
        if path is None and loco in ("naval", "lcraft"):
            path = _path_toward(world, here, goal, others, loco)  # a ship goes as near as the water allows
        if path is None:
            unit["status"] = "stuck"
            return "stuck"
        unit["path"], unit["path_goal"] = path, list(goal)
        unit["progress_ms"] = 0
    if not unit["path"]:
        return "arrived"
    nxt = unit["path"][0]
    if nxt in others:
        unit["blocked_ms"] = unit.get("blocked_ms", 0) + 100
        unit["status"] = "blocked"
        if unit["blocked_ms"] >= 1000:  # someone is standing in the way: route around (not along a shared route that is jammed)
            unit["path"] = []
            unit["blocked_ms"] = 0
            unit["fresh_route"] = True
        return "moving"
    unit["blocked_ms"] = 0
    unit["progress_ms"] = unit.get("progress_ms", 0) + 100
    unit["status"] = "moving"
    # OpenRA Locomotor.TerrainSpeeds: the percent speed of the terrain being entered (roads are faster)
    pct = world.tile_speed(loco, nxt[0], nxt[1]) if loco else 100
    if pct <= 0:
        unit["path"] = []
        return "moving"
    if unit["progress_ms"] * pct >= unit.get("move_ms", 760) * 100:
        unit["facing"] = _facing(nxt[0] - here[0], nxt[1] - here[1])
        unit["tx"], unit["ty"] = nxt
        unit["path"].pop(0)
        unit["progress_ms"] = 0
        world.stats["move"] += 1
    return "moving"


def _path_toward(world: Any, here: tuple[int, int], goal: tuple[int, int], others: set, loco: str) -> list[tuple[int, int]] | None:
    """When the goal itself cannot be entered (a ship ordered to a shore tile), path to the nearest enterable tile."""
    best = None
    for r in range(1, 12):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                t = (goal[0] + dx, goal[1] + dy)
                if world.tile_speed(loco, t[0], t[1]) > 0 and t not in others:
                    d = abs(dx) + abs(dy)
                    if best is None or d < best[0]:
                        best = (d, t)
        if best is not None:
            break
    if best is None:
        return None
    from wizard_rts.workers import find_path

    return find_path(world, here, best[1], limit=400, avoid=others, max_nodes=400_000, loco=loco)


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


def _scan(world: Any, faction: str, pos: tuple[float, float], radius: float, weapon: dict | None = None) -> dict | None:
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
                if weapon is not None and not weapon_can_attack(world, faction, weapon, u):
                    continue
                d = _dist(pos[0], pos[1], u["tx"], u["ty"])
                if d <= radius and (best_u is None or d < best_u[0]):
                    best_u = (d, u)
            if best_u is None:
                for b in cell[1]:
                    if b["faction"] == faction or int(b["hp"]) <= 0:
                        continue
                    if weapon is not None and not rules.can_hit(weapon, target_types(b)):
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
    sr = rules.actor(shooter.get("definition", "")) if shooter.get("definition", "").startswith(("openra.", "mindustry.")) else None
    if sr and sr.get("cloak"):
        shooter["uncloak_ms"] = int(sr["cloak"]["delay_ticks"]) * rules.TICK_MS  # Cloak UncloakOn Attack
        shooter["cloaked"] = False
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
    types = target_types(entity)
    for wh in p["warheads"]:
        if not rules.warhead_hits(wh, types):
            continue
        if p["target"]["kind"] == "building":
            world.damage_building(p["target"]["id"], int(wh["damage"]), ["structure"], wh.get("versus", {}) or {}, by=p["shooter"])
            continue
        versus = damage_versus(wh.get("versus", {}), [str(entity.get("armor", "None"))])
        applied = warhead_damage(int(wh["damage"]), [], versus)
        before = int(entity["hp"])
        entity["hp"] = inflict_damage(before, int(entity["max_hp"]), applied)
        world.events.append({"kind": "unit_hit", "unit": entity["id"], "by": p["shooter"], "dealt": before - entity["hp"], "hp": entity["hp"]})
        if before > 0 and entity["hp"] <= 0:
            kill_unit(world, entity, p["shooter"])


def kill_unit(world: Any, entity: dict, by: str = "") -> None:
    """The one place a unit dies (combat, fire magic): it is marked dead, loses its orders, and stays as a corpse for CORPSE_MS."""
    if not entity.get("alive", True):
        return
    entity["hp"] = 0
    entity["alive"] = False
    entity["status"] = "dead"
    entity.pop("order", None)
    entity.pop("deploying_ms", None)
    entity["path"] = []
    world.stats["destroyed"] += 1
    world.stats["units_lost"] = world.stats.get("units_lost", 0) + 1
    if entity.get("cargo"):  # an MCV or settlers' wagon dies with the starter kit it carried
        from wizard_rts.lifecycle import lose

        for good, n in sorted(entity.pop("cargo").items()):
            lose(world, good, int(n))
    vr = rules.actor(entity.get("definition", "")) or {}
    value = int(vr.get("cost", 0))
    world.fstat(entity["faction_name"], "loss_value", value)
    shooter = world.units.get(by) or world.buildings.get(by)
    if shooter is not None:
        from wizard_rts import trade

        trade.note_hostility(world, shooter.get("faction_name", ""), entity.get("faction_name", ""))
        world.fstat(shooter["faction_name"], "kill_value", value)
        world.fstat(shooter["faction_name"], "unit_kills")
    world.effects.append({"t": "explosion", "x1": entity["tx"], "y1": entity["ty"], "x2": entity["tx"], "y2": entity["ty"], "ttl_ms": 800, "keep": 3, "p": ""})
    world.events.append({"kind": "destroyed", "id": entity["id"], "by": by})


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
    if not world.tile_in_bounds(int(tx), int(ty)):
        return {"status": "rejected", "reason": "outside_map"}
    moved = 0
    for k, uid in enumerate(unit_ids):
        unit = world.units.get(uid)
        if unit is None or not unit.get("alive", True):
            continue
        loco = unit.get("loco")
        ox, oy = (k % 3 - 1, k // 3 - 1) if len(unit_ids) > 1 else (0, 0)  # spread a group into a loose block; one unit goes exactly there
        goal = [int(tx) + ox, int(ty) + oy]
        if world.tile_speed(loco, *goal) <= 0 or tuple(goal) in world.blocked:
            goal = [int(tx), int(ty)]
        if world.tile_speed(loco, *goal) <= 0:
            continue  # this locomotor cannot enter that terrain (a tank into the sea, a ship onto land)
        unit["order"] = {"kind": "attack_move" if attack_move else "move", "tile": goal}
        unit["path"] = []
        unit["target"] = None
        moved += 1
    world.events.append({"kind": "order_attack_move" if attack_move else "order_move", "units": list(unit_ids), "tile": [int(tx), int(ty)]})
    if not moved:
        return {"status": "rejected", "reason": "cannot_enter", "moved": 0}
    return {"status": "ok", "moved": moved}


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

def _weapon_order(unit: dict) -> list[str]:
    return unit.get("weapons") or ([unit["weapon"]] if unit.get("weapon") else [])


def _engage(world: Any, unit: dict, w: dict | None, chase: bool, leash: float) -> bool:
    """Acquire, chase and shoot with whichever armament can hit something. True if the unit used its turn."""
    pos = (unit["tx"], unit["ty"])
    names = _weapon_order(unit)
    if not names:
        return False
    target = unit.get("target")
    if target is not None and _target_pos(world, target) is None:
        target = unit["target"] = None
    if target is not None:  # a cloaked submarine that is no longer detected is lost
        tp = _target_pos(world, target)
        if tp is not None and target["kind"] == "unit" and not detected_by(world, unit["faction"], tp[2]):
            target = unit["target"] = None
    if world.military_quanta % SCAN_EVERY == 0 or target is None:
        for name in names:
            wi = rules.weapon(name)
            found = _scan(world, unit["faction"], pos, wi["range"] + (leash if chase else 0.0), wi)
            if found is not None:
                target = unit["target"] = found
                unit["target_weapon"] = name
                break
    if target is None:
        return False
    tpos = _target_pos(world, target)
    if tpos is None:
        unit["target"] = None
        return False
    dist = _dist(pos[0], pos[1], tpos[0], tpos[1])
    types = target_types(tpos[2])
    in_range = None
    for name in names:
        wi = rules.weapon(name)
        if rules.can_hit(wi, types) and dist <= wi["range"]:
            in_range = (name, wi)
            break
    if in_range is not None:
        name, wi = in_range
        unit["path"] = []
        unit["status"] = "attacking"
        unit["facing"] = _facing(int(tpos[0]) - pos[0], int(tpos[1]) - pos[1])
        if unit["cds"].get(name, 0) <= 0 and dist >= wi.get("min_range", 0):
            _fire(world, unit, wi, target, tpos[2], dist)
            unit["cds"][name] = rules.reload_ms(wi)
            unit["cooldown_ms"] = unit["cds"][unit["weapon"]] if unit.get("weapon") else 0
        return True
    if chase:
        wi = rules.weapon(unit.get("target_weapon") or names[0]) or rules.weapon(names[0])
        _walk(world, unit, (int(tpos[0]), int(tpos[1])), stop_within=max(wi["range"] - 0.5, 0.5))
        return True
    return False


def _unit_step(world: Any, unit: dict) -> None:
    for n in unit.get("cds", {}):
        unit["cds"][n] = max(0, int(unit["cds"][n]) - 100)
    unit["cooldown_ms"] = unit["cds"].get(unit.get("weapon"), 0) if unit.get("weapon") else max(0, int(unit.get("cooldown_ms", 0)) - 100)
    update_cloak(unit)
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
    types = target_types(building)
    use = next(((n, rules.weapon(n)) for n in _weapon_order(unit) if rules.can_hit(rules.weapon(n), types)), None)
    if use is None:
        unit.pop("order", None)
        unit["status"] = "idle"
        world.events.append({"kind": "order_failed", "unit": unit["id"], "reason": "cannot_hit_target"})
        return
    name, wi = use
    if dist <= wi["range"]:
        unit["path"] = []
        unit["status"] = "attacking"
        if unit["cds"].get(name, 0) <= 0:
            _fire(world, unit, wi, {"kind": "building", "id": building["id"]}, building, dist)
            unit["cds"][name] = rules.reload_ms(wi)
        return
    if _walk(world, unit, (building["tx"], building["ty"]), stop_within=max(wi["range"] - 0.5, 0.5)) == "stuck":
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
        b["target"] = target = _scan(world, b["faction"], (b["tx"], b["ty"]), w["range"], w)
    if target is None:
        return
    tpos = _target_pos(world, target)
    if tpos is None:
        return
    dist = _dist(b["tx"], b["ty"], tpos[0], tpos[1])
    if dist <= w["range"] and b["cooldown_ms"] <= 0:
        _fire(world, b, w, target, tpos[2], dist)
        b["cooldown_ms"] = rules.reload_ms(w)


_world_ref: list = []  # the world being stepped (building_weapon has no world argument; the nest weapon depends on the era)


def military_quantum(world: Any) -> None:
    _world_ref[:] = [world]
    world.military_quanta += 1
    world.path_searches = 0  # route searches started this quantum (military._walk spends PATH_SEARCHES_PER_QUANTUM of them)
    world.join_searches = 0
    if world.military_quanta % SCAN_EVERY == 0:
        _build_grid(world)
    projectile_quantum(world)
    units = list(world.units.values())
    if units:  # route budget is spent in this order: rotate the start so the same units do not always win it
        k = world.military_quanta % len(units)
        units = units[k:] + units[:k]
    for unit in units:
        if unit.get("alive", True):
            _unit_step(world, unit)
    for b in list(world.buildings.values()):
        if "hp" in b and int(b["hp"]) > 0 and (b.get("definition", "").startswith("openra.") or b.get("command_center") or b.get("kind") == "blight_nest"):
            _building_step(world, b)  # OpenRA defences, every settlement's militia and the blight nests (building_weapon)
    if world.military_quanta % 20 == 0:
        alive = [u["id"] for u in world.units.values() if u.get("alive", True)]
        if len(alive) >= 2:
            world.events.append({"kind": "ai_military", "units": alive[:20]})

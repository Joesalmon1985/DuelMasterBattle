"""Faction commanders. They use the same commands as God Mode, and nothing else.

An AI faction never gets free wares or units. It assesses what its economy
lacks, places construction sites near its warehouse (paid for with warehouse
stock, delivered over roads), connects them, queues recruits (paid in axes,
granite and planks that its own industry made), gathers idle units, and sends
them against an enemy, defending its base first.

Shaped after Widelands' DefaultAI (build priorities driven by economy needs and
space) and OpenRA's HackyAI/SquadManager (assemble a squad, pick an enemy
target, attack-move). It is far smaller than either; see docs/feature_catalogue.json.
"""

from __future__ import annotations

import math
from typing import Any

from wizard_rts import construction as con

DECIDE_EVERY = 50  # quanta (5 s) between decisions per faction
BASE_PLAN = {
    "producer": 3, "ranger": 3, "quarry": 2, "mine": 2, "ironmine": 2,
    "smelter": 1, "smithy": 1, "processor": 1, "barracks": 1, "vehicle_factory": 1, "defense": 1,
    "farm": 2, "hunter": 2, "well": 1, "tavern": 2, "bakery": 1, "fisher": 1,
}
# Plan kinds that are an imported building of the faction's own tribe: fish is a ration ingredient. Frisians catch fish in
# ponds (not implemented), so they have none here; the Amazon hunter-gatherer brings fish as well as game.
FISHER_OF = {
    "barbarians": "wl:barbarians_fishers_hut", "empire": "wl:empire_fishers_house", "atlanteans": "wl:atlanteans_fishers_house",
    "amazons": "wl:amazons_hunter_gatherers_hut",
}
# Personality: extra buildings, squad size before attacking, target preference.
PERSONALITY = {
    "Red": {"plan": {"barracks": 2, "smithy": 2}, "squad": 6, "targets": ["barracks", "vehicle_factory", "warehouse"]},
    "Blue": {"plan": {"producer": 3, "ranger": 3, "processor": 2}, "squad": 8, "targets": ["warehouse", "processor", "barracks"]},
    "Green": {"plan": {"quarry": 2, "vehicle_factory": 2}, "squad": 7, "targets": ["vehicle_factory", "barracks", "warehouse"]},
    "Yellow": {"plan": {"mine": 2, "ironmine": 2, "smithy": 2}, "squad": 7, "targets": ["smithy", "mine", "warehouse"]},
    "Purple": {"plan": {"defense": 3, "barracks": 2}, "squad": 9, "targets": ["defense", "barracks", "warehouse"]},
    "Orange": {"plan": {"vehicle_factory": 2, "barracks": 2, "quarry": 2}, "squad": 7, "targets": ["warehouse", "vehicle_factory", "barracks"]},
}
MAX_ARMY = 30
MAX_NAVY = 6
BUILD_WL_BARRACKS = False
NAVAL_AFTER_MS = 8 * 60_000  # the land economy comes first
NAVAL = ("naval", "lcraft")
NAVAL_BUILDINGS = ("naval_yard", "sub_pen")
ATTACK_AFTER_MS = 20 * 60_000  # factions build up for 20 game minutes before they march


def _plan(name: str) -> dict[str, int]:
    plan = dict(BASE_PLAN)
    for k, v in PERSONALITY.get(name, {}).get("plan", {}).items():
        plan[k] = max(plan.get(k, 0), v)
    return plan


def _mine(world: Any, name: str) -> list[dict]:
    return [b for b in world.buildings.values() if b["faction_name"] == name and "hp" in b and int(b["hp"]) > 0]


def _stock(world: Any, name: str, good: str) -> int:
    return sum(
        int(world.stocks.get(b["id"], {}).get(good, 0))
        for b in world.buildings.values()
        if b["faction_name"] == name and b["kind"] == "warehouse" and int(b.get("hp", 1)) > 0
    )


FLOWING = ("log", "plank", "granite")  # base wares the faction's own producers keep making: a site may wait for them


def _can_pay(world: Any, name: str, cost: dict[str, int]) -> bool:
    """Widelands construction sites request their wares and wait. The AI therefore places a site when the warehouse has the
    cost, or when the only shortfall is a base ware its own working producers make (the sawmill eats logs as fast as they
    arrive, so the stock is almost always 0 even in a healthy economy)."""
    for g, n in cost.items():
        if _stock(world, name, g) >= n:
            continue
        if g in FLOWING and _makes(world, name, g):
            continue
        return False
    return True


def _affordable(world: Any, name: str, kind: str) -> bool:
    return _can_pay(world, name, con.build_spec(kind)["cost"])


def _policy(kind: str) -> str:
    """Where a building wants to stand: woodcutters beside trees, foresters beside woodcutters, the rest near the warehouse."""
    from wizard_rts import wl_defs

    if kind == "producer":
        return "woodcutter"
    if kind == "ranger":
        return "forester"
    spec = wl_defs.spec_for_kind(kind)
    if spec:
        for role in set(spec["worker_for_program"].values()):
            for steps in (wl_defs.worker_programs(role) or {}).values():
                for cmd, args in steps:
                    if cmd == "findobject" and args.get("attrib") == "tree":
                        return "woodcutter"
                    if cmd == "plant" and args.get("attrib") == "tree_sapling":
                        return "forester"
    return "near"


def _trees_near(world: Any, tile: tuple[int, int], radius: int = 10) -> int:
    n = 0
    tt = world.tree_tiles
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            tid = tt.get((tile[0] + dx, tile[1] + dy))
            if tid is not None:
                tree = world.trees.get(tid)
                if tree is not None and tree.get("species") != "wheat" and tree.get("stage") in ("old", "mature", "pole"):
                    n += 1
    return n


def _place_ranked(world: Any, name: str, kind: str, anchor: dict, score) -> str | None:
    """Try legal sites around the warehouse, best score first, until one can be reached by a road."""
    cx, cy = anchor["tx"], anchor["ty"]
    cands = []
    for r in range(3, 30, 2):
        for dy in range(-r, r + 1, 2):
            for dx in range(-r, r + 1, 2):
                if max(abs(dx), abs(dy)) != r:
                    continue
                why, _ctx = con.check_placement(world, name, kind, cx + dx, cy + dy)
                if why is None:
                    s = score((cx + dx, cy + dy))
                    if s > 0:
                        cands.append((-s, r, cx + dx, cy + dy))
    cands.sort()
    for _neg, _r, x, y in cands[:6]:
        res = con.place_building(world, name, kind, x, y)
        if res["status"] != "ok":
            continue
        road = con.build_road(world, name, res["id"], anchor["id"])
        if road["status"] == "ok":
            return res["id"]
        _cancel_site(world, res["id"])
    return None


def _place_near(world: Any, name: str, kind: str, anchor: dict) -> str | None:
    """A legal site that a road can reach: by the trees for a woodcutter, by a woodcutter for a forester, else near the warehouse."""
    policy = _policy(kind)
    if policy == "woodcutter":
        site = _place_ranked(world, name, kind, anchor, lambda t: _trees_near(world, t))
        if site:
            return site
    elif policy == "forester":
        cutters = [b for b in world.buildings.values() if b["faction_name"] == name and _policy(b["kind"]) == "woodcutter" and "constructing" not in b]
        if cutters:
            def near_cutter(t: tuple[int, int]) -> float:
                d = min(abs(t[0] - c["tx"]) + abs(t[1] - c["ty"]) for c in cutters)
                return 40.0 - d if d <= 12 else 0.0
            site = _place_ranked(world, name, kind, anchor, near_cutter)
            if site:
                return site
    cx, cy = anchor["tx"], anchor["ty"]
    for r in range(4, 26, 2):
        for dy in range(-r, r + 1, 3):
            for dx in range(-r, r + 1, 3):
                if max(abs(dx), abs(dy)) != r:
                    continue
                res = con.place_building(world, name, kind, cx + dx, cy + dy)
                if res["status"] != "ok":
                    continue
                road = con.build_road(world, name, res["id"], anchor["id"])
                if road["status"] == "ok":
                    return res["id"]
                _cancel_site(world, res["id"])
    return None


def _cancel_site(world: Any, bid: str) -> None:
    from wizard_rts.lifecycle import purge_building

    purge_building(world, bid, "site_cancelled")


def economy_step(world: Any, name: str) -> None:
    wh = con.faction_warehouse(world, name)
    if wh is None or int(wh["hp"]) <= 0:
        return
    mine = _mine(world, name)
    have: dict[str, int] = {}
    for b in mine:
        if b.get("deposit_exhausted") and b["kind"] in ("mine", "ironmine"):
            continue  # a worked-out mine does not count: the faction needs another where the deposit remains
        have[b["kind"]] = have.get(b["kind"], 0) + 1  # sites count: they are on their way
    # repair the road network: a building with no road gets one
    for b in mine:
        if b["kind"] != "warehouse" and b["kind"] not in ("ranger",) and not world.adjacency.get(b["id"]):
            con.build_road(world, name, b["id"], wh["id"])
    # one new site at a time
    if any(b.get("constructing") for b in mine):
        return
    plan = _plan(name)
    logs = _stock(world, name, "log")
    order = ["producer", "ranger", "processor", "quarry", "hunter", "fisher", "farm", "well", "tavern", "bakery", "mine", "ironmine", "smelter", "smithy", "barracks", "vehicle_factory", "defense"]
    if logs < 6:  # wood first when it runs short
        order = ["producer", "ranger"] + [k for k in order if k not in ("producer", "ranger")]
    for plan_kind in order:
        kind = plan_kind
        if plan_kind == "fisher":
            kind = FISHER_OF.get(world.faction_info.get(name, {}).get("tribe", ""), "")
            if not kind:
                continue
        if have.get(kind, 0) >= plan.get(plan_kind, 0):
            continue
        if kind in ("mine", "ironmine") and not _deposit_site(world, name, kind):
            continue
        if not _affordable(world, name, kind):
            continue
        site = _place_near(world, name, kind, wh) if kind not in ("mine", "ironmine") else _build_mine(world, name, kind, wh)
        if site:
            world.events.append({"kind": "ai_build", "faction": name, "building": kind, "id": site})
            return
    if naval_economy_step(world, name, wh, mine):
        return
    tribe_step(world, name, wh)


# ------------------------------------------------------------------ navy

def naval_economy_step(world: Any, name: str, wh: dict, mine: list[dict]) -> bool:
    """A faction with a navigable shore near its warehouse builds a naval yard, then (once it is working) a submarine pen."""
    if world.terrain is None or int(world.dmb.clock.get("game_ms", 0)) < NAVAL_AFTER_MS:
        return False
    have = {b["kind"] for b in mine}
    want = "naval_yard" if "naval_yard" not in have else ("sub_pen" if "sub_pen" not in have and "barracks" in have else None)
    if want is None or not _affordable(world, name, want):
        return False
    if want == "sub_pen" and not any(b["kind"] == "naval_yard" and b.get("operational") for b in mine):
        return False
    site = _naval_site(world, name, wh)
    if site is None:
        return False
    res = con.place_building(world, name, want, site[0], site[1])
    if res["status"] != "ok":
        return False
    road = con.build_road(world, name, res["id"], wh["id"])
    if road["status"] != "ok":
        _cancel_site(world, res["id"])
        return False
    world.events.append({"kind": "ai_build", "faction": name, "building": want, "id": res["id"]})
    return True


def _naval_site(world: Any, name: str, wh: dict) -> tuple[int, int] | None:
    """The water tile nearest the warehouse that can carry a 3x3 yard whose shore door a road can reach."""
    t = world.terrain
    cx, cy = wh["tx"], wh["ty"]
    best = None
    for dy in range(-con.TERRITORY_RADIUS + 2, con.TERRITORY_RADIUS - 1, 2):
        for dx in range(-con.TERRITORY_RADIUS + 2, con.TERRITORY_RADIUS - 1, 2):
            x, y = cx + dx, cy + dy
            if not t.in_bounds(x, y) or t.depth[y * t.w + x] < 2:
                continue
            d = abs(dx) + abs(dy)
            if best is not None and d >= best[0]:
                continue
            why, _door, _fp = con.naval_site(world, (x, y), wh)
            if why is None:
                best = (d, (x, y))
    return best[1] if best else None


def navy_step(world: Any, name: str, wh: dict, navy: list[dict]) -> None:
    from wizard_rts.military import order_move

    idle = [u for u in navy if not u.get("order") and u.get("status") in ("idle", None, "attacking", "blocked", "stuck")]
    if not idle or not getattr(world, "ai_aggressive", True):
        return
    own_yards = [b for b in world.buildings.values() if b["faction_name"] == name and b.get("footprint") and int(b.get("hp", 1)) > 0]
    for y in own_yards:  # defend the yard first
        threat = _nearest_enemy_unit(world, name, tuple(y["anchor"]), 18.0)
        if threat is not None and world.terrain.is_water(threat["tx"], threat["ty"]):
            order_move(world, [u["id"] for u in idle], threat["tx"], threat["ty"], attack_move=True)
            world.events.append({"kind": "ai_fleet_defend", "faction": name, "at": [threat["tx"], threat["ty"]]})
            return
    if len(idle) < 2 or int(world.dmb.clock.get("game_ms", 0)) < ATTACK_AFTER_MS:
        return
    cx = sum(u["tx"] for u in idle) / len(idle)
    cy = sum(u["ty"] for u in idle) / len(idle)
    best = None
    for b in world.buildings.values():
        if b["faction_name"] == name or "hp" not in b or int(b["hp"]) <= 0:
            continue
        wt = _water_near(world, (b["anchor"] if b.get("footprint") else (b["tx"], b["ty"])), 9, int(idle[0]["tx"]), int(idle[0]["ty"]))
        if wt is None:
            continue
        d = abs(wt[0] - cx) + abs(wt[1] - cy) - (60 if b.get("footprint") else 0)  # a yard is the preferred prize
        if best is None or d < best[0]:
            best = (d, wt, b)
    if best is None:
        return
    order_move(world, [u["id"] for u in idle], best[1][0], best[1][1], attack_move=True)
    world.events.append({"kind": "ai_fleet_attack", "faction": name, "target": best[2]["id"], "ships": len(idle)})


def _water_near(world: Any, tile: tuple[int, int], radius: int, sx: int, sy: int) -> tuple[int, int] | None:
    """The water tile within radius of `tile` that lies in the same water body as (sx, sy), nearest to `tile`."""
    t = world.terrain
    comp = t.water_comp[sy * t.w + sx] if t.in_bounds(sx, sy) else 0
    if not comp:
        return None
    best = None
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            x, y = tile[0] + dx, tile[1] + dy
            if t.in_bounds(x, y) and t.water_comp[y * t.w + x] == comp and (x, y) not in world.blocked:
                d = abs(dx) + abs(dy)
                if best is None or d < best[0]:
                    best = (d, (x, y))
    return best[1] if best else None


# ------------------------------------------------------------------ tribe planner

def _makes(world: Any, name: str, ware: str) -> bool:
    from wizard_rts.logistics import io_for

    return any(
        ware in io_for(world, b).get("outputs", [])
        for b in world.buildings.values()
        if b["faction_name"] == name and "hp" in b and int(b["hp"]) > 0
    )


def _resolve(world: Any, name: str, tribe: str, ware: str, seen: set, depth: int = 0, force: bool = False) -> list[str]:
    """Dependency-ordered tribe buildings still missing for a ware (deepest first)."""
    from wizard_rts import tribes

    if depth > 8 or ware in seen or ware in ("recruit", "carrier"):
        return []
    seen.add(ware)
    if not force and _makes(world, name, ware):
        return []
    cands = tribes.producers(tribe).get(ware, [])
    if force:  # an extra source of a ware whose existing makers have run dry
        have = {b["kind"] for b in world.buildings.values() if b["faction_name"] == name and int(b.get("hp", 1)) > 0}
        cands = [c for c in cands if "wl:" + c not in have]
    if not cands:
        return []
    best = cands[0]
    order: list[str] = []
    for inp in tribes.inputs_for(tribe, best, ware):
        order += _resolve(world, name, tribe, inp, seen, depth + 1)
    order.append(best)
    return order


def _mine_site(world: Any, wh: dict, resource: str) -> tuple[int, int] | None:
    best = None
    centre = (wh["tx"], wh["ty"])
    occupied = [(b["tx"], b["ty"], b["kind"]) for b in world.buildings.values() if "constructing" not in b]
    if world.terrain is not None:
        cands = [n for n in world.resource_nodes(centre, 30, resource) if world.terrain.can_build(n[0], n[1], "mine")]
    else:
        cands = [n for n in world.resource_nodes(centre, 30, resource)]
    for tx, ty in cands:
        if (tx, ty) in world.blocked or (tx, ty) in world.tree_tiles or (tx, ty) in world.road_tile_set:
            continue
        if any(max(abs(bx - tx), abs(by - ty)) <= 3 and kind in ("mine", "ironmine") or kind.startswith("wl:") and max(abs(bx - tx), abs(by - ty)) <= 2 for bx, by, kind in occupied):
            continue
        total = world.resource_total((tx, ty), 2, resource)
        if best is None or total > best[0]:
            best = (total, (tx, ty))
    return best[1] if best else None


def _build_tribe_building(world: Any, name: str, bname: str, wh: dict) -> str | None:
    from wizard_rts import wl_defs

    kind = wl_defs.PREFIX + bname
    spec = con.build_spec(kind)
    if spec is None or not _can_pay(world, name, spec["cost"]):
        return None
    mining = [a["resource"] for prog in wl_defs.building_spec(bname)["programs"].values() for cmd, a in prog if cmd == "mine"]
    if mining:
        tile = _mine_site(world, wh, mining[0])
        if tile is None:
            return None
        res = con.place_building(world, name, kind, tile[0], tile[1])
        if res["status"] != "ok":
            return None
        if con.build_road(world, name, res["id"], wh["id"])["status"] != "ok":
            _cancel_site(world, res["id"])
            return None
        return res["id"]
    return _place_near(world, name, kind, wh)


def tribe_step(world: Any, name: str, wh: dict) -> None:
    """Build what the faction's tribe needs to make its soldier wares, then its barracks."""
    from wizard_rts import tribes, wl_defs

    tribe = world.faction_info.get(name, {}).get("tribe")
    if not tribe:
        return
    have_kinds = {b["kind"] for b in world.buildings.values() if b["faction_name"] == name and int(b.get("hp", 1)) > 0}
    plan: list[str] = []
    seen: set = set()
    for ware in wl_defs.soldier_wares(tribe):
        plan += [b for b in _resolve(world, name, tribe, ware, seen) if b not in plan]
    # The tribe's own barracks (a Widelands soldier) is deprecated: the OpenRA barracks every faction starts with takes the
    # same civilian wares (conversion.recipe_for), so only the weapon and armour chain is planned (DECISIONS D6).
    if BUILD_WL_BARRACKS:
        barracks = tribes.barracks_of(tribe)
        if barracks and wl_defs.PREFIX + barracks not in have_kinds:
            plan.append(barracks)
    # a building we cannot afford needs its build-cost wares produced first
    for bname in list(plan):
        spec = con.build_spec(wl_defs.PREFIX + bname)
        for ware, n in (spec or {"cost": {}})["cost"].items():
            if _stock(world, name, ware) < n:
                for dep in _resolve(world, name, tribe, ware, set(seen), force=_stock(world, name, ware) == 0):
                    if dep not in plan:
                        plan.insert(0, dep)
    # inputs of buildings we already run that the warehouse no longer has: add another source (kilns when coal runs out)
    starved: list[str] = []
    for b in world.buildings.values():
        if b["faction_name"] == name and b["kind"].startswith("wl:") and int(b.get("hp", 1)) > 0:
            spec = wl_defs.spec_for_kind(b["kind"])
            for ware in spec["inputs"] if spec else {}:
                if ware not in ("recruit", "carrier") and _stock(world, name, ware) == 0 and ware not in starved:
                    starved.append(ware)
    for ware in starved:
        for dep in _resolve(world, name, tribe, ware, set(seen), force=True):
            if dep not in plan:
                plan.append(dep)
    for bname in plan:
        if wl_defs.PREFIX + bname in have_kinds:
            continue
        site = _build_tribe_building(world, name, bname, wh)
        if site:
            world.events.append({"kind": "ai_build", "faction": name, "building": bname, "id": site})
            return


def _deposit_site(world: Any, name: str, kind: str) -> bool:
    """A mine can only be built where a deposit still has something in it. Widelands players prospect; the simulation knows
    the deposits, so the AI reads them directly (the same information a prospecting geologist would reveal)."""
    wh = con.faction_warehouse(world, name)
    return wh is not None and _mine_site(world, wh, "coal" if kind == "mine" else "iron") is not None


def _build_mine(world: Any, name: str, kind: str, wh: dict) -> str | None:
    tile = _mine_site(world, wh, "coal" if kind == "mine" else "iron")
    if tile is None:
        return None
    res = con.place_building(world, name, kind, tile[0], tile[1])
    if res["status"] != "ok":
        return None
    if con.build_road(world, name, res["id"], wh["id"])["status"] != "ok":
        _cancel_site(world, res["id"])
        return None
    return res["id"]


def military_step(world: Any, name: str) -> None:
    wh = con.faction_warehouse(world, name)
    if wh is None or int(wh["hp"]) <= 0:
        return
    mine = _mine(world, name)
    army = [u for u in world.units.values() if u["faction_name"] == name and u.get("alive", True) and u.get("weapon") and u.get("loco") not in NAVAL]
    # recruitment: keep two orders queued per production building, within the army cap
    navy = [u for u in world.units.values() if u["faction_name"] == name and u.get("alive", True) and u.get("loco") in NAVAL]
    for b in mine:
        if b["kind"] in con.RECIPES and b.get("operational") and len(b.get("queue", [])) < 2:
            if b["kind"] in NAVAL_BUILDINGS:
                if len(navy) < MAX_NAVY:
                    con.queue_unit(world, b["id"], next(iter(con.RECIPES[b["kind"]])))
            elif len(army) < MAX_ARMY:
                unit_kind = next(iter(con.RECIPES[b["kind"]]))
                con.queue_unit(world, b["id"], unit_kind)
    navy_step(world, name, wh, navy)
    if not getattr(world, "ai_aggressive", True):
        return  # peace: factions build and recruit but do not march
    idle = [u for u in army if not u.get("order") and u.get("status") in ("idle", None, "attacking", "blocked", "stuck")]
    if not idle:
        return
    # defend first: enemies near the capital
    threat = _nearest_enemy_unit(world, name, (wh["tx"], wh["ty"]), 22.0)
    if threat is not None:
        from wizard_rts.military import order_move

        order_move(world, [u["id"] for u in idle], threat["tx"], threat["ty"], attack_move=True)
        world.events.append({"kind": "ai_defend", "faction": name, "at": [threat["tx"], threat["ty"]]})
        return
    squad = PERSONALITY.get(name, {}).get("squad", 4)
    if len(idle) < squad or int(world.dmb.clock.get("game_ms", 0)) < ATTACK_AFTER_MS:
        return
    target = _pick_target(world, name, idle)
    if target is None:
        return
    from wizard_rts.military import order_attack, order_move

    ids = [u["id"] for u in idle]
    # march together to the enemy base, then the squad attacks what it meets (attack-move),
    # then the specific building order takes over once they are in sight
    centre = (target["tx"], target["ty"])
    near = min(idle, key=lambda u: math.hypot(u["tx"] - centre[0], u["ty"] - centre[1]))
    if math.hypot(near["tx"] - centre[0], near["ty"] - centre[1]) > 12:
        order_move(world, ids, centre[0], centre[1], attack_move=True)
    else:
        for uid in ids:
            order_attack(world, uid, target["id"])
    world.events.append({"kind": "ai_attack", "faction": name, "target": target["id"], "units": len(ids)})


def _nearest_enemy_unit(world: Any, name: str, pos: tuple[int, int], radius: float) -> dict | None:
    best = None
    for u in world.units.values():
        if u["faction_name"] == name or not u.get("alive", True):
            continue
        d = math.hypot(u["tx"] - pos[0], u["ty"] - pos[1])
        if d <= radius and (best is None or d < best[0]):
            best = (d, u)
    return best[1] if best else None


def _pick_target(world: Any, name: str, squad: list[dict]) -> dict | None:
    prefs = PERSONALITY.get(name, {}).get("targets", ["warehouse"])
    cx = sum(u["tx"] for u in squad) / len(squad)
    cy = sum(u["ty"] for u in squad) / len(squad)
    best = None
    for b in world.buildings.values():
        if b["faction_name"] == name or "hp" not in b or int(b["hp"]) <= 0:
            continue
        rank = prefs.index(b["kind"]) if b["kind"] in prefs else len(prefs)
        d = math.hypot(b["tx"] - cx, b["ty"] - cy)
        score = d + rank * 25.0  # a preferred kind is worth walking 25 cells further per rank
        if best is None or score < best[0]:
            best = (score, b)
    return best[1] if best else None


def ai_quantum(world: Any) -> None:
    n = world.economy_quanta
    if n % DECIDE_EVERY != 0:
        return
    for k, name in enumerate(world.faction_info):
        if name == world.controlled_faction or (n // DECIDE_EVERY + k) % 1 != 0:
            continue
        if world.ai_factions is not None and name not in world.ai_factions:
            continue  # an agent or a human plays this faction
        economy_step(world, name)
        military_step(world, name)

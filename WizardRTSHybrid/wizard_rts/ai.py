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
import zlib
from typing import Any

from wizard_rts import construction as con
from wizard_rts import tech, territory

ROAD_LIMIT = 45  # a site more than this far from its command centre by road is not worth a wide failed search
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
ATTACK_AFTER_MS = 12 * 60_000  # was 20 minutes: the build-up alone made the factions look inert (docs/PLAYTEST_FIXES.md, AI diagnosis)
GUARD_OUT = 12  # guard posts stand this many tiles from a command centre, towards the nearest enemy
RETREAT_BELOW = 0.4  # a squad that is down to this share of its launch size is recalled
SIGHT = 32  # tiles: an enemy building this close to one of our buildings or units becomes a known target
BOTTLENECK_EVERY_MS = 60_000
BOTTLENECK_CAP = {"producer": 6, "ranger": 6, "processor": 3, "quarry": 4}
BOTTLENECK_FIX = {"log": ("producer", "ranger"), "plank": ("processor",), "granite": ("quarry",)}


def _plan(name: str, world: Any = None) -> dict[str, int]:
    plan = dict(BASE_PLAN)
    for k, v in PERSONALITY.get(name, {}).get("plan", {}).items():
        plan[k] = max(plan.get(k, 0), v)
    if world is not None:  # supply bottlenecks the faction has measured raise its targets (_bottleneck_step)
        for k, v in world.__dict__.get("_ai_bneck", {}).get(name, {}).get("boost", {}).items():
            plan[k] = plan.get(k, 0) + v
    return plan


def _mine(world: Any, name: str) -> list[dict]:
    return [b for b in world.buildings.values() if b["faction_name"] == name and "hp" in b and int(b["hp"]) > 0]


def _stock(world: Any, name: str, good: str, anchor: dict | None = None) -> int:
    """Wares in the faction's warehouses, or in one command centre's store when `anchor` is given (a settlement pays from its own)."""
    return sum(
        int(world.stocks.get(b["id"], {}).get(good, 0))
        for b in world.buildings.values()
        if b["faction_name"] == name and b["kind"] == "warehouse" and int(b.get("hp", 1)) > 0 and (anchor is None or b is anchor)
    )


FLOWING = ("log", "plank", "granite")  # base wares the faction's own producers keep making: a site may wait for them


def _can_pay(world: Any, name: str, cost: dict[str, int], anchor: dict | None = None) -> bool:
    """Widelands construction sites request their wares and wait. The AI therefore places a site when the warehouse has the
    cost, or when the only shortfall is a base ware its own working producers make (the sawmill eats logs as fast as they
    arrive, so the stock is almost always 0 even in a healthy economy)."""
    for g, n in cost.items():
        if _stock(world, name, g, anchor) >= n:
            continue
        if g in FLOWING and _makes(world, name, g, anchor):
            continue
        return False
    return True


def _affordable(world: Any, name: str, kind: str, anchor: dict | None = None) -> bool:
    return _can_pay(world, name, con.build_spec(kind)["cost"], anchor)


def _policy(kind: str) -> str:
    """Where a building wants to stand: woodcutters beside trees, foresters beside woodcutters, the rest near the warehouse."""
    from wizard_rts import wl_defs

    if kind == "producer":
        return "woodcutter"
    if kind == "ranger":
        return "forester"
    if kind == "farm":
        return "farmer"
    spec = wl_defs.spec_for_kind(kind)
    if spec:
        for role in set(spec["worker_for_program"].values()):
            for steps in (wl_defs.worker_programs(role) or {}).values():
                for cmd, args in steps:
                    if cmd == "findobject" and args.get("attrib") == "tree":
                        return "woodcutter"
                    if cmd == "plant" and args.get("attrib") == "tree_sapling":
                        return "forester"
                    if cmd == "plant" and str(args.get("attrib", "")).startswith("seed_"):
                        return "farmer"
    return "near"


def _free_arable(world: Any, tile: tuple[int, int], radius: int = 2) -> int:
    """Free arable nodes around a site: a farm sows its fields there (no tree, road, building or reservation on them)."""
    t = world.terrain
    if t is None:
        return 0
    n = 0
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            p = (tile[0] + dx, tile[1] + dy)
            if (dx or dy) and t.class_at(*p) == 0 and p not in world.tree_tiles and p not in world.blocked and p not in world.road_tile_set and p not in world.reserved_tiles:
                n += 1
    return n


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
        road = _road(world, name, res["id"], anchor["id"])
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
    elif policy == "farmer" and world.terrain is not None:
        site = _place_ranked(world, name, kind, anchor, lambda t: _free_arable(world, t) - 8 if _free_arable(world, t) >= 12 else 0)
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
    failed_roads = 0
    for r in range(4, 26, 2):
        for dy in range(-r, r + 1, 3):
            for dx in range(-r, r + 1, 3):
                if max(abs(dx), abs(dy)) != r:
                    continue
                res = con.place_building(world, name, kind, cx + dx, cy + dy)
                if res["status"] != "ok":
                    continue
                road = _road(world, name, res["id"], anchor["id"])
                if road["status"] == "ok":
                    return res["id"]
                _cancel_site(world, res["id"])
                failed_roads += 1
                if failed_roads >= 3:  # each failed road is a wide A* search: give up for now rather than try a hundred sites
                    return None
    return None


ROAD_FAILS_PER_DECISION = 4  # failed road searches (each a wide A*, about 80 ms) one faction may spend in one decision


def _road(world: Any, name: str, a: str, b: str) -> dict[str, Any]:
    """build_road for the AI with a per-decision budget of failures: a crowded base otherwise retried dozens of failing searches in one step."""
    if world.__dict__.get("_ai_road_fails", 0) >= ROAD_FAILS_PER_DECISION:
        return {"status": "rejected", "reason": "road_budget"}
    out = con.build_road(world, name, a, b, ROAD_LIMIT)
    if out["status"] != "ok" and out.get("reason") == "no_path":
        world._ai_road_fails = world.__dict__.get("_ai_road_fails", 0) + 1
    return out


def _cancel_site(world: Any, bid: str) -> None:
    from wizard_rts.lifecycle import purge_building

    purge_building(world, bid, "site_cancelled")


OUTPOST_PLAN = {"producer": 2, "ranger": 2, "quarry": 1, "processor": 1, "defense": 1}
OUTPOST_ORDER = ["producer", "ranger", "processor", "quarry", "defense"]
EXPAND_AFTER_MS = 4 * 60_000  # the home economy gets a head start before the faction asks for a second settlement
MAX_CC = 3  # command centres per faction (the home warehouse included)
EXPAND_REPEAT_MS = 3 * 60_000


def economy_step(world: Any, name: str) -> None:
    world._ai_road_fails = 0
    wh = con.faction_warehouse(world, name)
    if wh is None or int(wh["hp"]) <= 0:
        return
    for cc in territory.command_centers(world, name):
        _settlement_step(world, name, cc, main=cc is wh)
    expansion_step(world, name, wh)


def _settlement_step(world: Any, name: str, wh: dict, main: bool) -> None:
    """One settlement (a command centre and the buildings around it): repair roads, then at most one new site."""
    mine = [b for b in _mine(world, name) if territory.settlement_of(world, b) is wh]
    have: dict[str, int] = {}
    for b in mine:
        if b.get("deposit_exhausted") and b["kind"] in ("mine", "ironmine"):
            continue  # a worked-out mine does not count: the faction needs another where the deposit remains
        have[b["kind"]] = have.get(b["kind"], 0) + 1  # sites count: they are on their way
    # repair the road network: a building with no road gets one
    now_ms = int(world.dmb.clock.get("game_ms", 0))
    cool_road = world.__dict__.setdefault("_ai_noroad", {})
    for b in mine:
        if b["kind"] != "warehouse" and b["kind"] not in ("ranger",) and not world.adjacency.get(b["id"]):
            if cool_road.get(b["id"], -1) > now_ms:
                continue  # it could not be connected a moment ago: the failing search is not repeated every decision
            if _road(world, name, b["id"], wh["id"])["status"] != "ok":
                cool_road[b["id"]] = now_ms + 60_000 + zlib.crc32(b["id"].encode()) % 30_000
    if main:
        _bottleneck_step(world, name, wh)
        # a yard is planned ahead of the one-site gate: the home settlement always has something under construction, so behind it
        # the navy was never started (found in the playtest AI diagnosis: no ship in 40 game minutes)
        if naval_economy_step(world, name, wh, _mine(world, name)):
            return
    # one new site at a time per settlement
    if any(b.get("constructing") for b in mine):
        return
    plan = _plan(name, world) if main else dict(OUTPOST_PLAN)
    logs = _stock(world, name, "log", wh)
    order = ["producer", "ranger", "processor", "quarry", "hunter", "fisher", "farm", "well", "tavern", "bakery", "mine", "ironmine", "smelter", "smithy", "barracks", "vehicle_factory", "defense"] if main else list(OUTPOST_ORDER)
    if logs < 6:  # wood first when it runs short
        order = ["producer", "ranger"] + [k for k in order if k not in ("producer", "ranger")]
    for plan_kind in order:
        kind = plan_kind
        if plan_kind == "fisher":
            kind = FISHER_OF.get(world.faction_info.get(name, {}).get("tribe", ""), "")
            if not kind:
                continue
        if have.get(kind, 0) >= plan.get(plan_kind, 0) or not tech.kind_allowed(world, name, kind):
            continue
        if kind in ("mine", "ironmine") and not _deposit_site(world, name, kind):
            continue
        if not _affordable(world, name, kind, wh):
            continue
        cool = world.__dict__.setdefault("_ai_cool", {})
        key = (name, wh["id"], kind)
        now_ms = int(world.dmb.clock.get("game_ms", 0))
        if cool.get(key, -1) > now_ms:
            continue  # this kind found no site a moment ago
        site = _place_near(world, name, kind, wh) if kind not in ("mine", "ironmine") else _build_mine(world, name, kind, wh)
        if not site:
            cool[key] = now_ms + 60_000 + zlib.crc32(repr(key).encode()) % 30_000  # staggered, and deterministic (no salted hash)
        if site:
            world.events.append({"kind": "ai_build", "faction": name, "building": kind, "id": site, "settlement": wh["id"]})
            return
    if not main:
        return
    tribe_step(world, name, wh)


# ------------------------------------------------------------------ expansion (MCV)

def expansion_step(world: Any, name: str, wh: dict) -> None:
    """Decide the faction needs another settlement, build an MCV for it, drive it to a good site and deploy it."""
    if world.terrain is None or not getattr(world, "ai_expand", True):
        return
    now = int(world.dmb.clock.get("game_ms", 0))
    mine = _mine(world, name)
    mcvs = [u for u in world.units.values() if u["faction_name"] == name and u.get("alive", True) and u.get("definition") == territory.MCV_DEFINITION]
    for u in mcvs:
        _drive_mcv(world, name, u, now)
    if mcvs:
        return
    queued = any(i["unit"] == "mcv" for b in mine for i in b.get("queue", []))
    state = world.__dict__.setdefault("_ai_expand", {}).setdefault(name, {"last": -10**9})
    if queued or len(territory.command_centers(world, name)) >= MAX_CC or now < EXPAND_AFTER_MS or now - state["last"] < EXPAND_REPEAT_MS:
        return
    factories = [b for b in mine if b["kind"] == "vehicle_factory" and b.get("operational") and "mcv" in con.RECIPES["vehicle_factory"]]
    if not factories:
        return
    if _find_expansion_site(world, name, None) is None:
        return  # nowhere legal to put one: do not spend the wares
    f = factories[0]
    if con.queue_unit(world, f["id"], "mcv")["status"] != "ok":
        return
    q = f["queue"]
    item = q.pop()
    if q and q[0]["state"] == "waiting":
        q.insert(0, item)  # the settlement comes before more tanks
    else:
        q.append(item)
    con._sync_requests(world, f)
    state["last"] = now
    world.fstat(name, "mcv_queued")
    world.events.append({"kind": "ai_expand_queue", "faction": name, "building": f["id"]})


def _site_score(world: Any, name: str, tile: tuple[int, int]) -> float:
    wood = min(_trees_near(world, tile, 12), 60)
    rocks = sum(1 for rk in world.rocks.values() if max(abs(rk["tx"] - tile[0]), abs(rk["ty"] - tile[1])) <= 12)
    coal = world.resource_total(tile, 12, "coal")
    iron = world.resource_total(tile, 12, "iron")
    arable = min(_free_arable(world, tile, 6), 60) * 0.4
    enemy = min((territory.cheb(tile, (b["tx"], b["ty"])) for b in territory.command_centers(world, None) if b["faction_name"] != name), default=100)
    return wood + min(rocks, 20) * 1.5 + (15 if coal > 0 else 0) + (15 if iron > 0 else 0) + arable + min(enemy, 120) * 0.1


def _find_expansion_site(world: Any, name: str, mcv: dict | None, bad: list | None = None) -> tuple[int, int] | None:
    """A legal deployment tile with room, reachable by the MCV, rich in wood, stone, ore and fields. Best of a coarse sweep
    around the home command centre; the top few are path-checked for the vehicle's locomotor."""
    from wizard_rts.workers import find_path

    t = world.terrain
    home = con.faction_warehouse(world, name)
    if home is None:
        return None
    probe = {"id": "probe", "definition": territory.MCV_DEFINITION, "faction_name": name, "alive": True, "tx": 0, "ty": 0}
    legal = []
    for y in range(8, t.h - 8, 8):
        for x in range(8, t.w - 8, 8):
            tile = (x, y)
            d = territory.cheb(tile, (home["tx"], home["ty"]))
            if d > 110 or not t.ground(x, y) or territory.separation_problem(world, name, tile):
                continue
            if bad and any(territory.cheb(tile, tuple(b)) < 12 for b in bad):
                continue
            probe["tx"], probe["ty"] = x, y
            if territory.deploy_check(world, probe) is not None:
                continue
            legal.append((d, tile))
    legal.sort()
    if len(legal) > 40:  # score an even spread of the legal sites, not every one (scoring walks a 25x25 window)
        legal = legal[:: len(legal) // 40 + 1]
    cands = [(_site_score(world, name, tile) - d * 0.6, tile) for d, tile in legal]  # a long drive is a long exposure: stay near home
    cands.sort(reverse=True)
    start = (mcv["tx"], mcv["ty"]) if mcv else (home["tx"], home["ty"] + 3)
    for _score, tile in cands[:8]:
        if mcv is None:
            return tile  # only asked whether a site exists
        if find_path(world, start, tile, limit=600, avoid=set(), max_nodes=300_000, loco="heavywheeled") is not None:
            return tile
    return None


def _drive_mcv(world: Any, name: str, u: dict, now: int) -> None:
    from wizard_rts.military import order_move

    if u.get("deploying_ms"):
        return
    st = u.setdefault("ai", {"site": None, "bad": [], "since": now, "fails": 0})
    here = (int(u["tx"]), int(u["ty"]))
    site = st["site"]
    if site is not None and here == tuple(site):
        res = territory.deploy(world, u["id"])
        if res["status"] != "ok":
            st["bad"].append(list(site))
            st["site"] = None
            world.events.append({"kind": "ai_expand_rejected", "faction": name, "reason": res["reason"], "tile": list(site)})
        else:
            world.fstat(name, "mcv_deployed")
            world.events.append({"kind": "ai_expand_deploy", "faction": name, "tile": list(site)})
        return
    if site is None or st["fails"] >= 3 or now - st["since"] > 8 * 60_000:
        if site is not None:
            st["bad"].append(list(site))
        site = _find_expansion_site(world, name, u, st["bad"])
        st.update(site=list(site) if site else None, fails=0, since=now)
        if site is None:
            return
        world.events.append({"kind": "ai_expand_site", "faction": name, "tile": list(site)})
        order_move(world, [u["id"]], site[0], site[1])
        return
    if not u.get("order"):  # arrived short, or was blocked and gave up: reissue
        st["fails"] += 1
        order_move(world, [u["id"]], site[0], site[1])


# ------------------------------------------------------------------ navy

def naval_economy_step(world: Any, name: str, wh: dict, mine: list[dict]) -> bool:
    """A faction with a navigable shore near its warehouse builds a naval yard, then (once it is working) a submarine pen."""
    if world.terrain is None or int(world.dmb.clock.get("game_ms", 0)) < NAVAL_AFTER_MS:
        return False
    have = {b["kind"] for b in mine}
    want = "naval_yard" if "naval_yard" not in have else ("sub_pen" if "sub_pen" not in have and "barracks" in have else None)
    if want is None or not tech.kind_allowed(world, name, want) or not _affordable(world, name, want):
        return False
    if want == "sub_pen" and not any(b["kind"] == "naval_yard" and b.get("operational") for b in mine):
        return False
    site = _naval_site(world, name, wh)
    if site is None:
        return False
    res = con.place_building(world, name, want, site[0], site[1])
    if res["status"] != "ok":
        return False
    road = _road(world, name, res["id"], wh["id"])
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

def _makes(world: Any, name: str, ware: str, anchor: dict | None = None) -> bool:
    from wizard_rts.logistics import io_for

    return any(
        ware in io_for(world, b).get("outputs", [])
        for b in world.buildings.values()
        if b["faction_name"] == name and "hp" in b and int(b["hp"]) > 0 and (anchor is None or territory.settlement_of(world, b) is anchor)
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
    if spec is None or not tech.kind_allowed(world, name, kind) or not _can_pay(world, name, spec["cost"]):
        return None
    mining = [a["resource"] for prog in wl_defs.building_spec(bname)["programs"].values() for cmd, a in prog if cmd == "mine"]
    if mining:
        tile = _mine_site(world, wh, mining[0])
        if tile is None:
            return None
        res = con.place_building(world, name, kind, tile[0], tile[1])
        if res["status"] != "ok":
            return None
        if _road(world, name, res["id"], wh["id"])["status"] != "ok":
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
    if _road(world, name, res["id"], wh["id"])["status"] != "ok":
        _cancel_site(world, res["id"])
        return None
    return res["id"]


def _bottleneck_step(world: Any, name: str, wh: dict) -> None:
    """Measure what the faction's buildings could not get (logistics shortages) and raise the plan for the ware that is short."""
    now = int(world.dmb.clock.get("game_ms", 0))
    state = world.__dict__.setdefault("_ai_bneck", {}).setdefault(name, {"t": 0, "boost": {}})
    if now - state["t"] < BOTTLENECK_EVERY_MS:
        return
    state["t"] = now
    own = {b["id"] for b in world.buildings.values() if b["faction_name"] == name}
    counts: dict[str, int] = {}
    for key in [k for k in world.shortages if k[0] in own]:
        counts[key[1]] = counts.get(key[1], 0) + world.shortages.pop(key)
    if not counts:
        return
    ware, n = max(counts.items(), key=lambda kv: kv[1])
    fix = BOTTLENECK_FIX.get(ware, ())
    raised = []
    if n >= 100:
        for kind in fix:
            if state["boost"].get(kind, 0) + _plan(name).get(kind, 0) < BOTTLENECK_CAP[kind]:
                state["boost"][kind] = state["boost"].get(kind, 0) + 1
                raised.append(kind)
    world.events.append({"kind": "ai_bottleneck", "faction": name, "ware": ware, "shortages": n, "raised": raised})


def _own_points(world: Any, name: str) -> list[tuple[int, int]]:
    pts = [(b["tx"], b["ty"]) for b in world.buildings.values() if b["faction_name"] == name and int(b.get("hp", 1)) > 0]
    pts += [(u["tx"], u["ty"]) for u in world.units.values() if u["faction_name"] == name and u.get("alive", True) and u.get("weapon")]
    return pts


def _known_targets(world: Any, name: str) -> list[dict]:
    """Enemy buildings this faction has found: every home capital (start positions are public) plus whatever has come within SIGHT of
    one of its own buildings or armed units. Scouting is therefore the army's own marching: it sees what it walks past."""
    known = world.__dict__.setdefault("_ai_known", {}).setdefault(name, set())
    pts = _own_points(world, name)
    out = []
    for b in world.buildings.values():
        if b["faction_name"] == name or "hp" not in b or int(b["hp"]) <= 0:
            continue
        if b["id"] not in known:
            if b["kind"] == "warehouse" and not b.get("outpost"):
                known.add(b["id"])
            elif any(abs(b["tx"] - x) <= SIGHT and abs(b["ty"] - y) <= SIGHT for x, y in pts):
                known.add(b["id"])
                world.events.append({"kind": "ai_scouted", "faction": name, "building": b["id"], "of": b["faction_name"]})
        if b["id"] in known:
            out.append(b)
    known.intersection_update(world.buildings.keys())
    return out


def _posts(world: Any, name: str, cc: dict) -> list[tuple[int, int]]:
    """Guard posts of one command centre: three tiles GUARD_OUT towards the nearest enemy centre, spread across the approach."""
    cache = world.__dict__.setdefault("_ai_posts", {})
    key = cc["id"]
    now = int(world.dmb.clock.get("game_ms", 0))
    hit = cache.get(key)
    if hit is not None and now - hit[0] < 120_000:
        return hit[1]
    enemies = [e for e in territory.command_centers(world) if e["faction_name"] != name]
    posts: list[tuple[int, int]] = []
    if enemies:
        e = min(enemies, key=lambda e: territory.cheb((cc["tx"], cc["ty"]), (e["tx"], e["ty"])))
        dx, dy = e["tx"] - cc["tx"], e["ty"] - cc["ty"]
        norm = max(math.hypot(dx, dy), 1.0)
        ux, uy = dx / norm, dy / norm
        radius = territory.radius_of(cc)
        out = min(GUARD_OUT, max(radius - 3, 4))
        for lateral in (-6, 0, 6):
            tx = int(round(cc["tx"] + ux * out - uy * lateral))
            ty = int(round(cc["ty"] + uy * out + ux * lateral))
            tile = _free_ground_near(world, (tx, ty), world._reach_from((cc["tx"], cc["ty"])) if world.terrain is not None else None)  # land-connected
            if tile is not None:
                posts.append(tile)
    cache[key] = (now, posts)
    return posts


def _free_ground_near(world: Any, tile: tuple[int, int], reach: dict | None = None) -> tuple[int, int] | None:
    t = world.terrain
    for r in range(0, 6):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                p = (tile[0] + dx, tile[1] + dy)
                if t is not None and t.ground(*p) and p not in world.blocked and p not in world.tree_tiles and p not in world.road_tile_set \
                        and (reach is None or p in reach):
                    return p
    return None


def _station(world: Any, name: str, idle: list[dict]) -> None:
    """Idle soldiers stand guard on the approaches to the faction's command centres instead of wherever they were built."""
    from wizard_rts.military import order_move

    posts: list[tuple[int, int]] = []
    for cc in territory.command_centers(world, name):
        posts += _posts(world, name, cc)
    if not posts:
        return
    sent = 0
    slots = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1), (2, 0), (-2, 0), (0, 2), (0, -2), (2, 1), (-2, 1), (2, -1), (-2, -1)]
    for k, u in enumerate(sorted(idle, key=lambda u: u["id"])):
        base = posts[k % len(posts)]
        off = slots[(k // len(posts)) % len(slots)]  # every soldier gets its own tile around the post (a shared tile jams the others)
        post = (base[0] + off[0], base[1] + off[1])
        if world.terrain is not None and (not world.terrain.ground(*post) or post in world.blocked):
            post = base
        if abs(u["tx"] - post[0]) + abs(u["ty"] - post[1]) <= 6 or u.get("order"):
            continue
        if int(u.get("no_route_until", 0)) > int(world.dmb.clock.get("game_ms", 0)):
            continue  # it found no way a moment ago: do not ask again every decision
        if u.get("status") == "stuck":
            u["no_route_until"] = int(world.dmb.clock.get("game_ms", 0)) + 90_000
            continue
        if order_move(world, [u["id"]], post[0], post[1], attack_move=True)["status"] == "ok":
            sent += 1
        if sent >= 6:  # a few per decision: the route searches are spread out over time
            break
    if sent:
        world.events.append({"kind": "ai_station", "faction": name, "units": sent, "posts": len(posts)})


def military_step(world: Any, name: str) -> None:
    from wizard_rts.military import order_attack, order_move

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
    idle_all = [u for u in army if not u.get("order") and u.get("status") in ("idle", None, "attacking", "blocked", "stuck", "waiting_route")]
    if not getattr(world, "ai_aggressive", True):
        _station(world, name, idle_all)  # peace: factions build, recruit and stand guard but do not march
        return
    now = int(world.dmb.clock.get("game_ms", 0))
    squads = world.__dict__.setdefault("_ai_squads", {})
    squad = squads.get(name)
    alive = {u["id"]: u for u in army}
    if squad is not None:
        squad["ids"] = [i for i in squad["ids"] if i in alive]
        if len(squad["ids"]) <= max(1, int(squad["size0"] * RETREAT_BELOW)):  # the attack has failed: bring the rest home
            if squad["ids"]:
                first = alive[squad["ids"][0]]
                home = min(territory.command_centers(world, name), key=lambda c: territory.cheb((first["tx"], first["ty"]), (c["tx"], c["ty"])), default=wh)
                order_move(world, squad["ids"], home["tx"], home["ty"] + 4)
            world.events.append({"kind": "ai_retreat", "faction": name, "launched": squad["size0"], "left": len(squad["ids"]), "after_ms": now - squad["since"]})
            squads.pop(name)
            squad = None
    if squad is not None:
        tgt = world.buildings.get(squad["target"])
        if tgt is None or int(tgt.get("hp", 0)) <= 0:  # target destroyed: the next known one, or home
            members = [alive[i] for i in squad["ids"]]
            nxt = _pick_target(world, name, members) if members else None
            if nxt is None:
                squads.pop(name)
                world.events.append({"kind": "ai_squad_done", "faction": name, "left": len(members)})
                squad = None
            else:
                squad["target"] = nxt["id"]
                world.events.append({"kind": "ai_retarget", "faction": name, "target": nxt["id"], "kind_of": nxt["kind"], "units": len(members)})
                _send(world, members, nxt)
        else:
            stalled = [alive[i] for i in squad["ids"] if not alive[i].get("order")]
            if stalled:  # members that finished their march: send them on to the target again
                _send(world, stalled, tgt)
    members_ids = set(squad["ids"]) if squad is not None else set()
    idle = [u for u in idle_all if u["id"] not in members_ids]
    if not idle:
        return
    # defend first: any enemy near any of our command centres, the nearest threat
    threat = None
    for cc in territory.command_centers(world, name):
        t = _nearest_enemy_unit(world, name, (cc["tx"], cc["ty"]), 22.0)
        if t is not None:
            threat = (cc, t)
            break
    if threat is not None:
        cc, t = threat
        order_move(world, [u["id"] for u in idle], t["tx"], t["ty"], attack_move=True)
        world.events.append({"kind": "ai_defend", "faction": name, "at": [t["tx"], t["ty"]], "centre": cc["id"], "units": len(idle), "enemy": t.get("faction_name", "")})
        return
    size = PERSONALITY.get(name, {}).get("squad", 4)
    if squad is None and len(idle) >= size and now >= ATTACK_AFTER_MS:
        target = _pick_target(world, name, idle)
        if target is not None:
            squads[name] = {"ids": [u["id"] for u in idle], "size0": len(idle), "target": target["id"], "since": now}
            world.events.append({"kind": "ai_attack", "faction": name, "target": target["id"], "units": len(idle), "target_kind": target["kind"], "of": target["faction_name"],
                                 "distance": round(math.hypot(target["tx"] - idle[0]["tx"], target["ty"] - idle[0]["ty"]))})
            _send(world, idle, target)
            return
    _station(world, name, idle)


def _send(world: Any, units: list[dict], target: dict) -> None:
    """March a squad to an enemy building: attack-move until it is in sight, then the specific attack order."""
    from wizard_rts.military import order_attack, order_move

    ids = [u["id"] for u in units]
    near = min(units, key=lambda u: math.hypot(u["tx"] - target["tx"], u["ty"] - target["ty"]))
    if math.hypot(near["tx"] - target["tx"], near["ty"] - target["ty"]) > 12:
        order_move(world, ids, target["tx"], target["ty"], attack_move=True)
    else:
        for uid in ids:
            order_attack(world, uid, target["id"])


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
    for b in _known_targets(world, name):
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
        pick = tech.ai_pick(world, name)
        if pick:
            tech.draft(world, name, pick)
        economy_step(world, name)
        military_step(world, name)

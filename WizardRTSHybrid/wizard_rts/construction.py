"""Building placement, construction sites, road building and recruitment queues.

Everything here is a command that God Mode and the AI both call. A new building
is a construction site: it requests its build cost through the logistics
network, and only completes after every ware has been delivered and the build
time has run. Costs come from the Widelands tribe data where the building
exists there (lumberjack's hut, ranger's hut). OpenRA buildings, and anything
whose Widelands cost needs wares this hybrid does not make yet (granite,
grout), use a documented hybrid cost.
"""

from __future__ import annotations

import heapq
from array import array
from typing import Any

from wizard_rts.coords import tile_to_hex
from wizard_rts import wl_defs
from wizard_rts.economy import _supply
from wizard_rts import tech, territory
from wizard_rts.logistics import add_road

QUANTUM_MS = 100
TRIBE_PATIENCE_MS = 25 * 60_000  # how long a barracks waits for its tribe's soldier wares before the ax fallback
TERRITORY_RADIUS = 34  # tiles from the faction's warehouse
BUILD_MS = 20_000

BUILD_MENU: dict[str, dict[str, Any]] = {
    "producer": {
        "label": "Lumberjack's hut", "definition": "widelands.lumberjack", "game": "widelands",
        "cost": {"log": 3}, "cost_source": "barbarians/lumberjacks_hut buildcost",
    },
    "ranger": {
        "label": "Ranger's hut", "definition": "widelands.rangers_hut", "game": "widelands",
        "cost": {"log": 4}, "cost_source": "barbarians/rangers_hut buildcost",
    },
    "processor": {
        "label": "Sawmill", "definition": "widelands.sawmill", "game": "widelands",
        "cost": {"log": 2, "plank": 1}, "cost_source": "empire/sawmill buildcost minus granite (not produced yet)",
    },
    "farm": {
        "label": "Farm", "definition": "widelands.farm", "game": "widelands",
        "cost": {"log": 4, "plank": 1, "granite": 3}, "cost_source": "barbarians/farm buildcost with planks for blackwood",
    },
    "hunter": {
        "label": "Hunter's hut", "definition": "widelands.hunters_hut", "game": "widelands",
        "cost": {"log": 4, "granite": 1}, "cost_source": "barbarians/hunters_hut buildcost",
    },
    "well": {
        "label": "Well", "definition": "widelands.well", "game": "widelands",
        "cost": {"log": 4}, "cost_source": "barbarians/well buildcost",
    },
    "tavern": {
        "label": "Tavern", "definition": "widelands.tavern", "game": "widelands",
        "cost": {"log": 3, "plank": 2, "granite": 1}, "cost_source": "barbarians/tavern buildcost with planks for blackwood, no reed",
    },
    "bakery": {
        "label": "Bakery", "definition": "widelands.bakery", "game": "widelands",
        "cost": {"log": 2, "plank": 2, "granite": 2}, "cost_source": "barbarians/bakery buildcost with planks for blackwood, no reed",
    },
    "mine": {
        "label": "Coal mine", "definition": "widelands.coalmine", "game": "widelands",
        "cost": {"log": 4, "granite": 2}, "cost_source": "barbarians/coalmine buildcost",
    },
    "ironmine": {
        "label": "Iron mine", "definition": "widelands.ironmine", "game": "widelands",
        "cost": {"log": 4, "granite": 2}, "cost_source": "barbarians/ironmine buildcost",
    },
    "quarry": {
        "label": "Quarry", "definition": "widelands.quarry", "game": "widelands",
        "cost": {"log": 4}, "cost_source": "barbarians/quarry buildcost",
    },
    "smelter": {
        "label": "Smelting works", "definition": "widelands.smelting_works", "game": "widelands",
        "cost": {"log": 3, "plank": 1, "granite": 1}, "cost_source": "barbarians/smelting_works buildcost with planks for blackwood, no grout or reed",
    },
    "smithy": {
        "label": "Ax workshop", "definition": "widelands.ax_workshop", "game": "widelands",
        "cost": {"log": 3, "plank": 2, "granite": 1}, "cost_source": "hybrid-defined from barbarians/ax_workshop",
    },
    "barracks": {
        "label": "Barracks", "definition": "openra.barracks", "game": "openra",
        "cost": {"log": 2, "plank": 4}, "cost_source": "hybrid-defined; OpenRA credits and power removed by design",
    },
    "vehicle_factory": {
        "label": "War factory", "definition": "openra.weap", "game": "openra",
        "cost": {"log": 4, "plank": 6}, "cost_source": "hybrid-defined; OpenRA credits and power removed by design",
    },
    "defense": {
        "label": "Gun turret", "definition": "openra.gun", "game": "openra",
        "cost": {"plank": 3}, "cost_source": "hybrid-defined; OpenRA power removed by design",
    },
    "war_lodge": {
        "label": "War lodge", "definition": "dmb.war_lodge", "game": "hybrid",
        "cost": {"log": 4, "granite": 2}, "cost_source": "hybrid-defined Prehistoric military building (design v0.5: clubs, spears, slings); Widelands tribe barracks art",
    },
    "flame_tower": {
        "label": "Flame tower", "definition": "openra.ftur", "game": "openra",
        "cost": {"plank": 3, "granite": 2, "coal": 1}, "cost_source": "hybrid-defined; OpenRA FTUR credits and power removed by design",
    },
    "tesla_coil": {
        "label": "Tesla coil", "definition": "openra.tsla", "game": "openra",
        "cost": {"plank": 2, "granite": 3, "iron": 3, "gold": 1}, "cost_source": "hybrid-defined; OpenRA TSLA credits and power removed by design",
    },
    "naval_yard": {
        "label": "Naval yard", "definition": "openra.syrd", "game": "openra", "size": "water3",
        "cost": {"plank": 8, "granite": 2},
        "cost_source": "hybrid-defined (OpenRA SYRD costs 1000 credits); placed on a 3x3 block of water beside the shore, per its Building.TerrainTypes: Water",
    },
    "sub_pen": {
        "label": "Submarine pen", "definition": "openra.spen", "game": "openra", "size": "water3",
        "cost": {"plank": 6, "granite": 2},
        "cost_source": "hybrid-defined (OpenRA SPEN costs 800 credits); placed on a 3x3 block of water beside the shore, per its Building.TerrainTypes: Water",
    },
}

# Land footprints relative to the door tile (the tile roads and carriers use, bottom row). Taken from the picture sizes at one
# OpenRA cell (24 px) per tile: WEAP is 72x48 = 3x2 cells over its bib row, BARR is 48x48 = 2x2. Units leave through the row below.
GROUND_FOOTPRINT: dict[str, list[tuple[int, int]]] = {
    "vehicle_factory": [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0)],
    "barracks": [(-1, -1), (0, -1), (-1, 0)],
}

# Hybrid recipes: a rifleman takes one ax (barbarians/barracks consume=ax, 30 s); a tank takes granite and a plank. See docs/DECISIONS.md.
RECIPES: dict[str, dict[str, dict[str, Any]]] = {
    # Ship recipes are hybrid-defined goods for the OpenRA unit (cost scaled from its credits): no free production.
    # Patrol boat and submarine need nothing but their yard in OpenRA's tech tree, so they are the first naval slice.
    "naval_yard": {
        "patrol_boat": {"label": "Patrol boat", "definition": "openra.pt", "cost": {"plank": 3, "iron": 1}, "ms": 25_000},
    },
    "sub_pen": {
        "submarine": {"label": "Submarine", "definition": "openra.ss", "cost": {"plank": 2, "iron": 3}, "ms": 40_000},
    },
    # Prehistoric (design v0.5 section 2): clubs, spears and slings, hybrid low-tech actors (rules.HYBRID_ACTORS), paid in food and wood.
    "war_lodge": {
        "clubman": {"label": "Clubman", "definition": "dmb.clubman", "cost": {"ration": 1, "log": 1}, "ms": 20_000},
        "spearman": {"label": "Spearman", "definition": "dmb.spearman", "cost": {"ration": 1, "plank": 1}, "ms": 24_000},
        "slinger": {"label": "Slinger", "definition": "dmb.slinger", "cost": {"ration": 1, "log": 1, "granite": 1}, "ms": 26_000},
    },
    # A warehouse (command centre) sends out settlers: a Prehistoric MCV. Vehicle and cargo leave its own store; the cargo founds the new one.
    "warehouse": {
        "settlers": {
            "label": "Settlers", "definition": "dmb.settlers", "ms": 45_000,
            "build": {"log": 2, "ration": 2},
            "cargo": {"log": 4, "plank": 3, "granite": 2, "ration": 1},
            "cost": {"log": 6, "plank": 3, "granite": 2, "ration": 3},
        },
    },
    "barracks": {
        "infantry": {"label": "Rifleman", "definition": "openra.e1", "cost": {"ax": 1}, "ms": 30_000},
        "grenadier": {"label": "Grenadier", "definition": "openra.e2", "cost": {"iron": 1, "coal": 1, "ration": 1}, "ms": 32_000},
        "rocket_soldier": {"label": "Rocket soldier", "definition": "openra.e3", "cost": {"iron": 2, "coal": 1, "ration": 1}, "ms": 36_000},
        "shock_trooper": {"label": "Shock trooper", "definition": "openra.shok", "cost": {"iron": 2, "gold": 1, "ration": 1}, "ms": 40_000},
    },
    "vehicle_factory": {
        "tank": {"label": "Tank", "definition": "openra.3tnk", "cost": {"granite": 2, "plank": 1, "iron": 1}, "ms": 35_000},
        "jeep": {"label": "Ranger jeep", "definition": "openra.jeep", "cost": {"plank": 2, "granite": 1}, "ms": 22_000},
        "light_tank": {"label": "Light tank", "definition": "openra.1tnk", "cost": {"plank": 2, "granite": 1, "iron": 1}, "ms": 28_000},
        "medium_tank": {"label": "Medium tank", "definition": "openra.2tnk", "cost": {"plank": 1, "granite": 2, "iron": 2}, "ms": 32_000},
        "apc": {"label": "APC", "definition": "openra.apc", "cost": {"plank": 2, "iron": 2}, "ms": 35_000},
        "artillery": {"label": "Artillery", "definition": "openra.arty", "cost": {"plank": 2, "iron": 2, "coal": 1}, "ms": 40_000},
        "mammoth": {"label": "Mammoth tank", "definition": "openra.4tnk", "cost": {"granite": 3, "iron": 6, "coal": 2}, "ms": 70_000},
        "v2_launcher": {"label": "V2 launcher", "definition": "openra.v2rl", "cost": {"plank": 1, "iron": 3, "coal": 2}, "ms": 50_000},
        "tesla_tank": {"label": "Tesla tank", "definition": "openra.ttnk", "cost": {"iron": 4, "coal": 2, "gold": 1}, "ms": 55_000},
        "phase_tank": {"label": "Phase transport", "definition": "openra.stnk", "cost": {"plank": 2, "iron": 3, "gold": 1}, "ms": 50_000},
        "chrono_tank": {"label": "Chrono tank", "definition": "openra.ctnk", "cost": {"iron": 4, "gold": 2}, "ms": 55_000},
        # The MCV is paid in delivered wares: the vehicle itself (planks, granite) plus the starter kit it carries to the new
        # site. Everything leaves the factory's stock; on deployment the kit goes into the new command centre's store. Hybrid-defined
        # (OpenRA's MCV costs 2000 credits, no Widelands analogue).
        "mcv": {
            "label": "MCV", "definition": "openra.mcv", "ms": 60_000,
            "build": {"plank": 6, "granite": 4},
            "cargo": {"log": 3, "plank": 2, "granite": 1},
            "cost": {"log": 3, "plank": 8, "granite": 5},
        },
    },
}


# Source units that exist in the rules but are not offered yet, with the honest reason (shown greyed in God Mode).
RECIPES_LOCKED: dict[str, dict[str, str]] = {
    "naval_yard": {
        "openra.dd": "Destroyer needs a radar dome (tech building not implemented)",
        "openra.ca": "Cruiser needs the advanced tech building (not implemented)",
        "openra.lst": "Transport needs amphibious landings (not implemented)",
    },
    "sub_pen": {"openra.msub": "Missile submarine needs the tech center (not implemented)"},
}

# ------------------------------------------------------------------ placement

MENU_SIZE = {
    "naval_yard": "water3", "sub_pen": "water3",
    "producer": "small", "ranger": "small", "processor": "medium", "farm": "big", "hunter": "small", "well": "small",
    "tavern": "medium", "bakery": "medium", "mine": "mine", "ironmine": "mine", "quarry": "small",
    "smelter": "medium", "smithy": "medium", "barracks": "medium", "vehicle_factory": "big", "defense": "small",
    "war_lodge": "medium", "flame_tower": "small", "tesla_coil": "small",
}


def _program_steps(kind: str):
    from wizard_rts.workers import _programs_of

    programs = _programs_of({"kind": kind}) or {}
    for steps in programs.values():
        for cmd, args in steps:
            yield cmd, args


def site_size(kind: str, spec: dict[str, Any]) -> str:
    size = spec.get("size") or MENU_SIZE.get(kind, "small")
    return size if size in ("small", "medium", "big", "mine", "port") else "small"


def terrain_reject(world: Any, kind: str, spec: dict[str, Any], tile: tuple[int, int]) -> str | None:
    """Why the terrain forbids this building here, or None. Rules: Widelands buildcaps plus what the programmes need."""
    t = world.terrain
    if t is None:
        return None
    size = site_size(kind, spec)
    if t.is_water(*tile):
        return "water"
    if not t.can_build(tile[0], tile[1], size):
        return "no_mountain" if size == "mine" else ("no_port_space" if size == "port" else "unsuitable_terrain")
    spec_w = wl_defs.spec_for_kind(kind)
    if spec_w:
        for role in set(spec_w["worker_for_program"].values()):
            for steps in (wl_defs.worker_programs(role) or {}).values():
                for cmd, args in steps:
                    if cmd == "findspace" and args.get("resource") == "fish":
                        # a fisher or fish breeder needs fish-bearing water within reach of the building
                        if not t.cells(tile[0], tile[1], int(args["radius"]) + 1, "fish"):
                            return "no_fish"
    for cmd, args in _program_steps(kind):
        if cmd == "mine" and world.resource_total(tile, int(args["radius"]), args["resource"]) <= 0:
            return "no_deposit"
        if cmd == "findobject" and args.get("attrib") == "rocks":
            r = int(args.get("radius", 6))
            if not any(max(abs(rk["tx"] - tile[0]), abs(rk["ty"] - tile[1])) <= r for rk in world.rocks.values()):
                return "no_rocks"
    return None


def faction_warehouse(world: Any, faction_name: str) -> dict | None:
    """The faction's main command centre (its first warehouse). If it has fallen, a surviving deployed centre takes over."""
    mine = [b for b in world.buildings.values() if b["kind"] == "warehouse" and b["faction_name"] == faction_name]
    alive = [b for b in mine if int(b.get("hp", 1)) > 0]
    pool = alive or mine
    pool.sort(key=lambda b: (bool(b.get("outpost")), int(b["id"].split(":")[1])))
    return pool[0] if pool else None


def build_spec(kind: str) -> dict[str, Any] | None:
    """A menu entry for a hybrid kind, or for any runnable Widelands building ("wl:<name>")."""
    if kind in BUILD_MENU:
        return BUILD_MENU[kind]
    if kind.startswith("mdy:"):
        from wizard_rts.industry import registry

        return registry.build_spec(kind)
    spec = wl_defs.spec_for_kind(kind)
    if spec is None:
        return None
    return {
        "size": spec.get("size", ""),
        "label": spec["label"], "definition": spec["definition"], "game": "widelands", "tribe": spec["tribe"],
        "cost": dict(spec["cost"]), "cost_source": f"{spec['tribe']}/{spec['name']} buildcost (imported)",
    }


def full_menu() -> dict[str, dict[str, Any]]:
    out = {k: ({**v, "size": v.get("size") or MENU_SIZE.get(k, "")}) for k, v in BUILD_MENU.items()}
    for name in wl_defs.runnable_names():
        spec = build_spec(wl_defs.PREFIX + name)
        if spec is not None:
            out[wl_defs.PREFIX + name] = spec
    return out


def check_placement(world: Any, faction_name: str, kind: str, tx: int, ty: int) -> tuple[str | None, dict[str, Any]]:
    """Every rule `place_building` applies, with no side effects: (reason or None, context for the commit)."""
    spec = build_spec(kind)
    if spec is None:
        return "unknown_kind", {}
    info = world.faction_info.get(faction_name)
    if info is None:
        return "unknown_faction", {}
    if not tech.kind_allowed(world, faction_name, kind):
        return "locked_by_card", {"spec": spec, "info": info}
    tile = (int(tx), int(ty))
    home = faction_warehouse(world, faction_name)
    ctx: dict[str, Any] = {"spec": spec, "info": info, "tile": tile, "home": home}
    if not world.tile_in_bounds(*tile):
        return "outside_map", ctx
    home = territory.covering(world, faction_name, tile) or home
    ctx["home"] = home
    if kind.startswith("mdy:"):  # Mindustry machines: footprint, deposits underneath, belts (industry/commands.py)
        from wizard_rts.industry import commands as ind_commands

        why, mctx = ind_commands.check_machine(world, faction_name, kind, tile)
        if why is None:
            ctx["ground_footprint"] = [list(t) for t in mctx["footprint"]]
        return why, ctx
    if spec.get("size") == "water3":
        if not territory.in_territory(world, faction_name, tile):
            return "outside_territory", ctx
        why, door, fp = naval_site(world, tile, home)
        ctx.update(door=door, footprint=fp)
        return why, ctx
    if not territory.in_territory(world, faction_name, tile):
        return "outside_territory", ctx
    if tile in world.blocked or tile in world.tree_tiles or tile in world.road_tile_set or tile in world.reserved_tiles:
        return "tile_occupied", ctx
    if world.terrain is None and not world.tile_in_map(*tile):
        return "outside_map", ctx
    if any((u["tx"], u["ty"]) == tile for u in world.units.values() if u.get("alive", True)):
        return "tile_occupied", ctx
    extra = [(tile[0] + dx, tile[1] + dy) for dx, dy in GROUND_FOOTPRINT.get(kind, [])]
    if extra:
        occupied = {(u["tx"], u["ty"]) for u in world.units.values() if u.get("alive", True)}
        for p in extra:
            if not world.tile_in_bounds(*p) or (world.terrain is not None and not world.terrain.ground(*p)):
                return "footprint_blocked", ctx
            if p in world.blocked or p in world.tree_tiles or p in world.road_tile_set or p in world.reserved_tiles or p in occupied:
                return "tile_occupied", ctx
            if world.terrain is not None and not world.terrain.can_build(p[0], p[1], "small"):
                return "unsuitable_terrain", ctx
        ctx["ground_footprint"] = [list(tile)] + [list(p) for p in extra]
    return terrain_reject(world, kind, spec, tile), ctx


def place_building(world: Any, faction_name: str, kind: str, tx: int, ty: int) -> dict[str, Any]:
    why, ctx = check_placement(world, faction_name, kind, tx, ty)
    if why:
        return {"status": "rejected", "reason": why}
    spec, info, tile = ctx["spec"], ctx["info"], ctx["tile"]
    if spec.get("size") == "water3":
        return _place_naval(world, faction_name, info, kind, spec, tile, ctx["door"], ctx["footprint"])
    bid = world._building(info["id"], faction_name, kind, tile, spec["label"], spec["definition"])
    building = world.buildings[bid]
    if ctx.get("ground_footprint"):
        building["ground_footprint"] = ctx["ground_footprint"]
        for p in ctx["ground_footprint"]:
            world.blocked.add((int(p[0]), int(p[1])))
    building["operational"] = False
    building["constructing"] = {"cost": dict(spec["cost"]), "progress_ms": 0}
    building["hp"] = max(1, building["max_hp"] // 10)
    world.recipe_requests[bid] = dict(spec["cost"])
    world.events.append({"kind": "construction_started", "id": bid, "building_kind": kind, "faction": faction_name})
    return {"status": "ok", "id": bid}


def naval_site(world: Any, tile: tuple[int, int], home: dict | None) -> tuple[str | None, tuple[int, int] | None, list[tuple[int, int]]]:
    """A water-built OpenRA yard: 3x3 water footprint around `tile`, on a navigable body, beside land the faction can reach.

    Source: OpenRA RA SYRD/SPEN Building.TerrainTypes Water, Footprint 3x3, RequiresBuildableArea Adjacent. The footprint
    must be water, the water must be a real body (not a pond) and one shore tile touching the footprint, reachable on foot
    from the faction's warehouse, becomes the door the roads and carriers use.
    """
    from wizard_rts import terrain as T

    t = world.terrain
    if t is None:
        return "needs_terrain", None, []
    cx, cy = tile
    fp = [(cx + dx, cy + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
    for p in fp:
        if not t.in_bounds(*p):
            return "outside_map", None, fp
        if not t.is_water(*p):
            return "needs_water", None, fp
        if p in world.blocked or p in world.road_tile_set:
            return "tile_occupied", None, fp
    if any((u["tx"], u["ty"]) in fp for u in world.units.values() if u.get("alive", True)):
        return "tile_occupied", None, fp
    comp = t.water_comp[cy * t.w + cx]
    if t.comp_size.get(comp, 0) < T.PORT_MIN_WATER:
        return "water_too_small", None, fp
    reach = world._reach_from((home["tx"], home["ty"]), limit=90) if home is not None else {}
    doors = []
    for x, y in ((cx - 2, cy - 1), (cx - 2, cy), (cx - 2, cy + 1), (cx + 2, cy - 1), (cx + 2, cy), (cx + 2, cy + 1),
                 (cx - 1, cy - 2), (cx, cy - 2), (cx + 1, cy - 2), (cx - 1, cy + 2), (cx, cy + 2), (cx + 1, cy + 2)):
        d = (x, y)
        if t.ground(x, y) and d in reach and d not in world.blocked and d not in world.tree_tiles and d not in world.road_tile_set:
            doors.append((reach[d], d))
    if not doors:
        return "no_shore", None, fp
    return None, min(doors)[1], fp


def _place_naval(world: Any, faction_name: str, info: dict, kind: str, spec: dict, tile: tuple[int, int], door: tuple[int, int], fp: list[tuple[int, int]]) -> dict[str, Any]:
    bid = world._building(info["id"], faction_name, kind, door, spec["label"], spec["definition"])
    building = world.buildings[bid]
    building["footprint"] = [list(p) for p in fp]
    building["anchor"] = list(tile)
    for p in fp:
        world.blocked.add(p)
    building["operational"] = False
    building["constructing"] = {"cost": dict(spec["cost"]), "progress_ms": 0}
    building["hp"] = max(1, building["max_hp"] // 10)
    world.recipe_requests[bid] = dict(spec["cost"])
    world.events.append({"kind": "construction_started", "id": bid, "building_kind": kind, "faction": faction_name})
    return {"status": "ok", "id": bid, "door": list(door)}


def construction_quantum(world: Any) -> None:
    for bid, b in list(world.buildings.items()):
        site = b.get("constructing")
        if not site:
            continue
        stock = world.stocks.get(bid, {})
        if not all(int(stock.get(g, 0)) >= n for g, n in site["cost"].items()):
            continue
        site["progress_ms"] += QUANTUM_MS
        b["hp"] = min(b["max_hp"], max(b["hp"], int(b["max_hp"] * (0.1 + 0.9 * site["progress_ms"] / BUILD_MS))))
        if site["progress_ms"] >= BUILD_MS:
            for good, n in site["cost"].items():
                _supply(world, bid).remove_wares(good, n)
                world.stats["consumed_" + good] = world.stats.get("consumed_" + good, 0) + n
            b.pop("constructing")
            b["operational"] = True
            b["hp"] = b["max_hp"]
            world.recipe_requests.pop(bid, None)
            world.events.append({"kind": "construction_done", "id": bid, "building_kind": b["kind"]})
            world.fstat(b["faction_name"], "buildings_completed")


# ------------------------------------------------------------------ roads

def _road_path(world: Any, start: tuple[int, int], goal: tuple[int, int], ends: tuple[str, str] = ("", ""), limit: int = 70) -> list[tuple[int, int]] | None:
    blocked, roads, trees = world.blocked, world.road_tile_set, world.tree_tiles  # membership tests: no 20k-tile set union per search
    # Roads that already reach an endpoint share its flag: a new road may be joined along them (the hybrid has no Widelands flags,
    # so a crowded warehouse is reached along its existing trunks). Never through a tile a carrier cannot pass (the Ward Duel hazard):
    # until 12 Oct 2026 a new road could share the blocked tile, and the Red AI's construction sites starved behind it.
    shared: set[tuple[int, int]] = set()
    for end in ends:
        for _nxt, rid in world.adjacency.get(end, []):
            for t in world.roads[rid]:
                if not world.tile_blocked_for_carrier(tuple(t)):
                    shared.add(tuple(t))
    def open_tile(t: tuple[int, int]) -> bool:
        return t == goal or (((t not in blocked and t not in roads and t not in trees) or t in shared) and world.tile_in_map(*t))

    # fail fast: an endpoint walled in on all four sides (a site dropped into a forest) cannot be reached; the full search would
    # explore the whole box before saying so
    for end in (start, goal):
        if not any(open_tile((end[0] + dx, end[1] + dy)) or (end[0] + dx, end[1] + dy) == start for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            return None
    max_expand = int(__import__('os').environ.get('ROAD_CAP', 4 * (2 * limit + 1) * (2 * limit + 1) // 5))
    # A* over the (2*limit+1)^2 box around the start, with flat-array bookkeeping (12 Oct 2026, a performance rewrite: the same
    # neighbour order, heap keys and tie-breaks as the tuple/dict version, so the same path; tests/test_road_path.py compares them)
    sx, sy = start
    gx, gy = goal
    if abs(gx - sx) > limit or abs(gy - sy) > limit:
        return None
    S = 2 * limit + 1
    ox, oy = sx - limit, sy - limit
    N = S * S
    cost = array("i", [-1]) * N
    came = array("i", [-1]) * N
    memo = bytearray(N)  # 0 unknown, 1 open, 2 closed
    terr = world.terrain
    ground = terr.ground if terr is not None else world.tile_in_map
    si = limit * S + limit
    gi = (gy - oy) * S + (gx - ox)
    cost[si] = 0
    heap: list[tuple[int, int, int]] = [(0, 0, si)]
    pop, push = heapq.heappop, heapq.heappush
    n = 0
    while heap:
        _f, _c, ci = pop(heap)
        if n > max_expand:
            return None
        if ci == gi:
            path = []
            while ci != -1:
                cy, cx = divmod(ci, S)
                path.append((cx + ox, cy + oy))
                ci = came[ci] if ci != si else -1
            path.reverse()
            return path
        cy, cx = divmod(ci, S)
        x, y = cx + ox, cy + oy
        cc = cost[ci] + 1
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            lx, ly = cx + dx, cy + dy
            if lx < 0 or ly < 0 or lx >= S or ly >= S:
                continue
            ni = ly * S + lx
            m = memo[ni]
            if m == 0:
                if ni == gi:
                    m = 1
                else:
                    t = (x + dx, y + dy)
                    m = 1 if (((t not in blocked and t not in roads and t not in trees) or t in shared) and ground(t[0], t[1])) else 2
                memo[ni] = m
            if m == 2:
                continue
            old = cost[ni]
            if old == -1 or cc < old:
                cost[ni] = cc
                came[ni] = ci
                n += 1
                push(heap, (cc + abs(gx - x - dx) + abs(gy - y - dy), n, ni))
    return None


def build_road(world: Any, faction_name: str, a: str, b: str, limit: int = 70) -> dict[str, Any]:
    ba, bb = world.buildings.get(a), world.buildings.get(b)
    if ba is None or bb is None or "hp" not in ba or "hp" not in bb:
        return {"status": "rejected", "reason": "no_building"}
    if ba["faction_name"] != faction_name or bb["faction_name"] != faction_name:
        return {"status": "rejected", "reason": "not_your_building"}
    if a == b or any(n == b for n, _r in world.adjacency.get(a, [])):
        return {"status": "rejected", "reason": "already_connected"}
    path = _road_path(world, (ba["tx"], ba["ty"]), (bb["tx"], bb["ty"]), (a, b), limit)
    if path is None or len(path) < 2:
        return {"status": "rejected", "reason": "no_path"}
    rid = add_road(world, world.faction_info[faction_name]["id"], faction_name, a, b, path)
    return {"status": "ok", "road": rid, "length": len(path)}


# ------------------------------------------------------------------ recruitment

def recipe_for(world: Any, b: dict, unit_kind: str) -> dict[str, Any] | None:
    """The recipe for a unit at a building. A rifleman costs what the faction's tribe pays for a soldier."""
    recipe = RECIPES.get(b["kind"], {}).get(unit_kind)
    if recipe is None:
        return None
    if unit_kind == "infantry" and not b.get("tribe_fallback"):
        from wizard_rts import tribes, wl_defs

        tribe = world.faction_info.get(b["faction_name"], {}).get("tribe", "barbarians")
        cost = wl_defs.soldier_wares(tribe)
        if cost:
            recipe = dict(recipe)
            recipe["cost"] = cost
    return recipe


def queue_unit(world: Any, building_id: str, unit_kind: str) -> dict[str, Any]:
    b = world.buildings.get(building_id)
    if b is None or not b.get("operational", True) or b.get("constructing"):
        return {"status": "rejected", "reason": "not_operational"}
    recipe = recipe_for(world, b, unit_kind)
    if recipe is None:
        return {"status": "rejected", "reason": "cannot_build_here"}
    if not tech.unit_allowed(world, b["faction_name"], unit_kind):
        return {"status": "rejected", "reason": "locked_by_card"}
    queue = b.setdefault("queue", [])
    if len(queue) >= 5:
        return {"status": "rejected", "reason": "queue_full"}
    queue.append({"unit": unit_kind, "state": "waiting", "progress_ms": 0})
    _sync_requests(world, b)
    world.events.append({"kind": "queued", "building": building_id, "unit": unit_kind})
    return {"status": "ok", "length": len(queue)}


def cancel_queue(world: Any, building_id: str, index: int) -> dict[str, Any]:
    b = world.buildings.get(building_id)
    if b is None or not b.get("queue") or not (0 <= int(index) < len(b["queue"])):
        return {"status": "rejected", "reason": "no_such_item"}
    item = b["queue"].pop(int(index))
    if item["state"] == "building":  # goods were taken at start; refund them to the building stock and un-book the consumption
        rec = recipe_for(world, b, item["unit"])
        for good, n in rec["cost"].items():
            from wizard_rts.economy import produce

            produce(world, building_id, good, n)
            used = n - int((rec.get("cargo") or {}).get(good, 0))  # the cargo part was carried, not consumed (recruitment_quantum)
            if used:
                world.stats["consumed_" + good] = world.stats.get("consumed_" + good, 0) - used
    _sync_requests(world, b)
    world.events.append({"kind": "queue_cancelled", "building": building_id, "unit": item["unit"]})
    return {"status": "ok"}


def _sync_requests(world: Any, b: dict) -> None:
    """The barracks asks for the goods of its next queued unit (one batch ahead)."""
    queue = b.get("queue", [])
    waiting = [i for i in queue if i["state"] == "waiting"]
    if not waiting:
        world.recipe_requests.pop(b["id"], None)
        return
    need: dict[str, int] = {}
    for good, n in recipe_for(world, b, waiting[0]["unit"])["cost"].items():
        need[good] = n
    world.recipe_requests[b["id"]] = need


def _naval_exit_tile(world: Any, b: dict) -> tuple[int, int] | None:
    """A ship leaves a yard onto free water touching its footprint (OpenRA Exit cells sit on the water side)."""
    occupied = {(u["tx"], u["ty"]) for u in world.units.values() if u.get("alive", True)}
    ax, ay = b["anchor"]
    from wizard_rts.grid import ring

    for r in (2, 3, 4):
        for t in ring(ax, ay, r):
            if world.terrain.is_water(*t) and t not in occupied and t not in world.blocked:
                return t
    return None


def _exit_tile(world: Any, b: dict) -> tuple[int, int] | None:
    if b.get("footprint"):
        return _naval_exit_tile(world, b)
    occupied = {(u["tx"], u["ty"]) for u in world.units.values() if u.get("alive", True)}
    if b.get("ground_footprint"):  # units come out of the row in front of the door, never through the walls
        for dx in (0, -1, 1, -2, 2):
            t = (b["tx"] + dx, b["ty"] + 1)
            if world.tile_in_map(*t) and t not in world.blocked and t not in occupied and (world.terrain is None or world.terrain.ground(*t)):
                return t
    for r in range(1, 6):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                t = (b["tx"] + dx, b["ty"] + dy)
                if max(abs(dx), abs(dy)) != r:
                    continue
                if world.tile_in_map(*t) and t not in world.blocked and t not in occupied and t not in world.road_tile_set:
                    return t
    return None


def recruitment_quantum(world: Any) -> None:
    for bid, b in list(world.buildings.items()):
        queue = b.get("queue")
        if not queue or not b.get("operational", True):
            continue
        head = queue[0]
        recipe = recipe_for(world, b, head["unit"])
        if head["state"] == "waiting":
            stock = world.stocks.get(bid, {})
            b["wait_ms"] = int(b.get("wait_ms", 0)) + QUANTUM_MS
            if head["unit"] == "infantry" and not b.get("tribe_fallback") and b["wait_ms"] >= TRIBE_PATIENCE_MS:
                # The tribe's weapon chain has not delivered for a long time (a chain the importer cannot run yet, or a starved
                # one): the barracks falls back to the hybrid ax recipe so the faction can field infantry. Still goods-fed, and
                # recorded in an event and in the building row.
                b["tribe_fallback"] = True
                b["wait_ms"] = 0
                world.events.append({"kind": "tribe_fallback", "building": bid, "faction": b["faction_name"]})
                _sync_requests(world, b)
                continue
            if all(int(stock.get(g, 0)) >= n for g, n in recipe["cost"].items()):
                b["wait_ms"] = 0
                carried = recipe.get("cargo", {})
                for g, n in recipe["cost"].items():
                    _supply(world, bid).remove_wares(g, n)
                    used = n - int(carried.get(g, 0))  # what is loaded on the vehicle is moved, not consumed
                    if used:
                        world.stats["consumed_" + g] = world.stats.get("consumed_" + g, 0) + used
                head["state"] = "building"
                world.stats["recruit_started"] = world.stats.get("recruit_started", 0) + 1
                world.events.append({"kind": "recruit_started", "building": bid, "unit": head["unit"]})
                _sync_requests(world, b)
            continue
        # a damaged building works more slowly
        slow = max(0.25, b["hp"] / max(b["max_hp"], 1))
        head["progress_ms"] += int(QUANTUM_MS * slow)
        if head["progress_ms"] >= recipe["ms"]:
            tile = _exit_tile(world, b)
            if tile is None:
                continue
            uid = world._unit(b["faction"], b["faction_name"], head["unit"], recipe["label"], recipe["definition"], tile)
            if recipe.get("cargo"):
                world.units[uid]["cargo"] = dict(recipe["cargo"])
            rally = b.get("rally")
            if rally:
                world.units[uid]["order"] = {"kind": "move", "tile": list(rally)}
            queue.pop(0)
            world.stats["recruited"] = world.stats.get("recruited", 0) + 1
            world.events.append({"kind": "unit_produced", "building": bid, "unit": uid, "unit_kind": head["unit"]})
            world.fstat(b["faction_name"], "units_produced")
            _sync_requests(world, b)

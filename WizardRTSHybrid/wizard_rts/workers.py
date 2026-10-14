"""Tree lifecycle and the worker-program interpreter.

Workers are physical: they hold a tile, walk A* paths one tile at a time, wait
out animations, and only then change the world. A tree is felled by a worker
that reserved it; the log exists only after that tree fell. The ware drops into
the workplace's output stock. Carriers (economy.py) are separate.
"""

from __future__ import annotations

import heapq
import weakref
from array import array

INF = float("inf")
from typing import Any

from wizard_rts import flow, imm, regions, resources, visibility, wl_defs
from wizard_rts import terrain as terrain_mod
from wizard_rts.programs_data import (
    BUILDING_PROGRAMS,
    ECONOMY_TARGETS,
    FAIL_SLEEP_MS,
    FELLED_MS,
    OLD_SEED_RADIUS,
    STAGE_TABLES,
    TREE_STAGES,
    WALK_MS,
    WORKER_FOR_BUILDING,
    WORKER_PROGRAMS,
)

QUANTUM_MS = 100
ART_SPECIES = ("beech", "wheat", "oak", "birch", "spruce", "larch", "alder", "rowan", "aspen")  # species with imported sprites (scripts/import_tree_art.py)
TREE_SPECIES = ("beech", "oak", "birch", "spruce", "larch", "alder", "aspen", "rowan")  # the summer species with all four stages in the Lua


def stage_table(species: str) -> dict[str, tuple[int, float, str]]:
    """{stage: (duration_ms, die_chance_percent, next_stage)} from the species' own Lua programmes (beech and wheat keep the
    hand-checked tables). Every species grows at its own pace: an oak stands 37 minutes as an old tree, a beech 25."""
    if species in STAGE_TABLES:
        return STAGE_TABLES[species]
    cached = _TABLES.get(species)
    if cached is not None:
        return cached
    table = dict(TREE_STAGES)
    nxt = {"sapling": "pole", "pole": "mature", "mature": "old", "old": "old"}
    ok = True
    for stage in nxt:
        spec = imm.spec(f"{species}_summer_{stage}")
        if spec is None:
            ok = False
            break
        ms, die = 60_000, 0.0
        for a in spec["programs"].get("main", []):
            if a["cmd"] == "animate":
                ms = int(a.get("ms", ms))
            elif a["cmd"] in ("remove", "transform"):
                die = imm._chance(a)
        table[stage] = (ms, die, nxt[stage])
    _TABLES[species] = table if ok else dict(TREE_STAGES)
    return _TABLES[species]


_TABLES: dict[str, dict] = {}
_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def facing(dx: int, dy: int) -> str:
    if dx > 0 and dy == 0:
        return "e"
    if dx < 0 and dy == 0:
        return "w"
    if dy > 0:
        return "se" if dx >= 0 else "sw"
    if dy < 0:
        return "ne" if dx >= 0 else "nw"
    return "e"


def new_id(world: Any, prefix: str) -> str:
    n = world.counters.get(prefix, 0) + 1
    world.counters[prefix] = n
    return f"{prefix}:{n}"


# ---------------------------------------------------------------- trees

def plant_tree(world: Any, tile: tuple[int, int], stage: str, species: str = "beech") -> str:
    tree_id = new_id(world, "tree")
    world.trees[tree_id] = {
        "id": tree_id,
        "kind": "tree",
        "definition": f"widelands.{species if species in ART_SPECIES else 'beech'}",
        "species": species,
        "stage": stage,
        "tx": tile[0],
        "ty": tile[1],
        "timer_ms": stage_table(species)[stage][0],
        "reserved_by": "",
    }
    world.tree_tiles[tile] = tree_id
    return tree_id


def tile_free_for_tree(world: Any, tile: tuple[int, int]) -> bool:
    if not world.tile_in_map(*tile) or tile in world.blocked or tile in world.tree_tiles:
        return False
    if world.terrain is not None and world.terrain.class_at(*tile) != terrain_mod.ARABLE:
        return False  # trees and fields grow on arable terrain only
    return tile not in world.reserved_tiles and tile not in world.road_tile_set


def building_of(world: Any, worker: dict) -> dict:
    return world.buildings[worker["building"]]


def _shore_spots(world: Any, building: dict, args: dict) -> list[tuple[int, int]]:
    """Ground nodes within radius of the building from which the worker can reach the resource with radius 1.

    Widelands findspace=size:any resource:... picks a walkable node that holds the resource (fish live on
    shoreline nodes there); here fish sit on water tiles, so the worker stands on land beside them.
    `breed` asks for water that is below its initial amount.
    """
    t = world.terrain
    if t is None:
        return []
    res, radius = args["resource"], int(args["radius"])
    bx, by = building["tx"], building["ty"]
    out = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            tile = (bx + dx, by + dy)
            if not t.ground(*tile) or tile in world.tree_tiles or tile in world.blocked and tile != (bx, by):
                continue
            cells = t.cells(tile[0], tile[1], 1, res)
            if args.get("breed"):
                ok = any(i > a for _x, _y, a, i in cells)
            else:
                ok = any(a > 0 for _x, _y, a, _i in cells)
            if ok:
                out.append(tile)
    return out


def best_species(world: Any, tile: tuple[int, int]) -> str:
    """The species with the highest probability_to_grow here (Widelands rangers choose by terrain affinity)."""
    if world.terrain is None:
        return "beech"
    return max(TREE_SPECIES, key=lambda sp: (world.terrain.growth_probability(sp, tile[0], tile[1]), sp == "beech"))


def remove_tree(world: Any, tree_id: str, reason: str) -> None:
    tree = world.trees.pop(tree_id, None)
    if tree is None:
        return
    world.tree_tiles.pop((tree["tx"], tree["ty"]), None)
    world.events.append({"kind": "tree_removed", "id": tree_id, "reason": reason})


TREE_STRIDE = 10  # a tree is processed once per second (staggered by id), not every 100 ms: its timers are tens of seconds


def _slot_of(key: str) -> int:
    try:
        return int(key.split(":")[1]) % TREE_STRIDE
    except (IndexError, ValueError):  # an id that is not "kind:number" (never produced by new_id) still gets a stable bucket
        return 0


class TreeDict(dict):
    """world.trees, with ids bucketed by processing slot so tree_quantum visits one tenth of the trees per tick.

    Behaviour is identical to a plain dict (insertion order, snapshot); the buckets keep the same relative order inside a slot."""

    def __init__(self, *a: Any, **k: Any) -> None:
        super().__init__(*a, **k)
        self.buckets: list[dict] = [{} for _ in range(TREE_STRIDE)]
        self.fresh: list[str] = []  # added since the last tree_quantum: their "slot" field is written there, as before
        for k_ in self:
            self.buckets[_slot_of(k_)][k_] = None
            self.fresh.append(k_)

    def __reduce__(self) -> tuple:
        return (TreeDict, (dict(self),))  # pickle and deepcopy rebuild the buckets from the items (a plain dict subclass would call __setitem__ first)

    def copy(self) -> "TreeDict":
        return TreeDict(dict(self))

    def __setitem__(self, key: str, value: dict) -> None:
        if key not in self:
            self.buckets[_slot_of(key)][key] = None
            self.fresh.append(key)
        super().__setitem__(key, value)

    def pop(self, key: str, *default: Any) -> Any:
        self.buckets[_slot_of(key)].pop(key, None)
        return super().pop(key, *default)

    def __delitem__(self, key: str) -> None:
        self.buckets[_slot_of(key)].pop(key, None)
        super().__delitem__(key)


def tree_quantum(world: Any) -> None:
    phase = world.military_quanta % TREE_STRIDE
    step = QUANTUM_MS * TREE_STRIDE
    trees = world.trees
    if trees.fresh:
        for tree_id in trees.fresh:
            tree = trees.get(tree_id)
            if tree is not None and tree.get("slot") is None:
                tree["slot"] = _slot_of(tree_id)
        trees.fresh.clear()
    for tree_id in list(trees.buckets[phase]):
        tree = trees.get(tree_id)
        if tree is None:
            continue
        if "imm" in tree:
            imm.tick(world, tree, step)
            continue
        tree["timer_ms"] -= step
        if tree["timer_ms"] > 0:
            continue
        stage = tree["stage"]
        if stage == "felled":
            remove_tree(world, tree_id, "felled_gone")
            continue
        if tree["reserved_by"]:
            tree["timer_ms"] = step  # a worker is about to cut it
            continue
        table = stage_table(tree["species"])
        _duration, die, nxt = table[stage]
        if world.rng.random() * 100 < die:
            remove_tree(world, tree_id, "died" if tree["species"] != "wheat" else "rotted")
            continue
        if world.terrain is not None and tree["species"] != "wheat" and stage != "old":
            # Widelands `grow`: the next stage is reached with probability_to_grow, otherwise the tree dies
            if world.rng.random() >= world.terrain.growth_probability(tree["species"], tree["tx"], tree["ty"]):
                remove_tree(world, tree_id, "poor_soil")
                continue
        if stage == "old":
            _seed(world, tree)
            tree["timer_ms"] = table["old"][0]
            continue
        tree["stage"] = nxt
        tree["timer_ms"] = table[nxt][0]
        world.events.append({"kind": "tree_grew", "id": tree_id, "stage": nxt})


def _seed(world: Any, tree: dict) -> None:
    for _ in range(6):
        tile = (
            tree["tx"] + world.rng.randint(-OLD_SEED_RADIUS, OLD_SEED_RADIUS),
            tree["ty"] + world.rng.randint(-OLD_SEED_RADIUS, OLD_SEED_RADIUS),
        )
        if tile_free_for_tree(world, tile):
            new = plant_tree(world, tile, "sapling", tree["species"])
            world.events.append({"kind": "tree_seeded", "id": new, "parent": tree["id"]})
            return


# ---------------------------------------------------------------- paths

_PASSABLE: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()  # terrain object -> {locomotor: table}


def _passable(world: Any, loco: str) -> bytearray:
    """One byte per tile: may this locomotor enter it (static terrain only; roads only make a tile faster).

    Cached per terrain OBJECT, weakly. (It used to be keyed by id(terrain): once a world was freed, a later world whose terrain landed at the
    same address was handed the old world's table, wrong for its map: a crash with the native kernel when the sizes differed and silently wrong
    paths when they did not. Any process that plays more than one game, such as a training worker, would hit it.)"""
    from wizard_rts import rules

    t = world.terrain
    tables = _PASSABLE.get(t)
    if tables is None:
        tables = _PASSABLE[t] = {}
    got = tables.get(loco)
    if got is None:
        table = rules.speed_table(loco)
        got = tables[loco] = bytearray(1 if table[c] > 0 else 0 for c in t.cls)
    return got


_NATIVE = [False, None]  # [resolved, lib]


def _native_astar():
    if not _NATIVE[0]:
        _NATIVE[0] = True
        from wizard_rts import native

        _NATIVE[1] = native.astar_lib()
    return _NATIVE[1]


def _find_path_native(lib: Any, W: int, H: int, ok: bytearray, blk: set, joined: set | None, s: int, g: int, sx: int, sy: int, gx: int, gy: int,
                      limit: int, max_nodes: int, four: bool, move_dirs: Any) -> list[tuple[int, int]] | None:
    """The C twin of the loop below: identical results (tests/test_native_astar.py)."""
    import ctypes

    blkb = bytearray(W * H)
    n_tiles = W * H
    for i in blk:
        if 0 <= i < n_tiles:  # an avoid tile off the map is harmless in the set version, so skip it here
            blkb[i] = 1
    jb = None
    if joined is not None:
        jarr = bytearray(W * H)
        for i in joined:
            if 0 <= i < n_tiles:
                jarr[i] = 1
        jb = ctypes.addressof((ctypes.c_char * (W * H)).from_buffer(jarr))
    nd = len(move_dirs)
    ddx = (ctypes.c_int * nd)(*[d[0] for d in move_dirs])
    ddy = (ctypes.c_int * nd)(*[d[1] for d in move_dirs])
    out = (ctypes.c_int * (W * H))()
    n = lib.dmb_astar(W, H, ctypes.addressof((ctypes.c_char * (W * H)).from_buffer(ok)), ctypes.addressof((ctypes.c_char * (W * H)).from_buffer(blkb)),
                      jb, s, g, sx, sy, gx, gy, limit, max_nodes, 1 if four else 0, ddx, ddy, nd, out)
    if n < 0:
        return None
    return [(out[i] % W, out[i] // W) for i in range(n)]


def _find_path_fast(world: Any, start: tuple[int, int], goal: tuple[int, int], limit: int, avoid: set | None, max_nodes: int, loco: str,
                    join: dict | None) -> list[tuple[int, int]] | None:
    """The same A* as find_path over integer tile ids and a precomputed passability table (about three times faster)."""
    t = world.terrain
    W, H = t.w, t.h
    ok = _passable(world, loco)
    blk = {y * W + x for x, y in world.blocked}
    if avoid:
        blk |= {y * W + x for x, y in avoid}
    sx, sy = start
    gx, gy = goal
    s, g = sy * W + sx, gy * W + gx
    joined = {y * W + x for x, y in join} if join else None
    dirs = [(dx, dy, dy * W + dx) for dx, dy in world.move_dirs]
    four = len(dirs) == 4
    lib = _native_astar()
    if lib is not None:
        return _find_path_native(lib, W, H, ok, blk, joined, s, g, sx, sy, gx, gy, limit, max_nodes, four, world.move_dirs)
    open_heap = [(0.0, 0, s)]
    # flat arrays instead of dicts (12 Oct 2026, performance): the same exploration order and tie-breaks, so the same paths
    came = array("i", [-1]) * (W * H)
    cost = array("d", [INF]) * (W * H)
    cost[s] = 0.0
    counter = 0
    heappop, heappush = heapq.heappop, heapq.heappush
    xlo, xhi = max(0, sx - limit), min(W - 1, sx + limit)  # the window and the map edge as one bounds test
    ylo, yhi = max(0, sy - limit), min(H - 1, sy + limit)
    while open_heap:
        _f, _c, cur = heappop(open_heap)
        if counter > max_nodes:
            return None
        if cur == g or (joined is not None and cur in joined):
            out = []
            while cur != s:
                out.append((cur % W, cur // W))
                cur = came[cur]
            out.reverse()
            return out
        cy, cx = divmod(cur, W)
        base = cost[cur] + 1.0
        for dx, dy, di in dirs:
            nx = cx + dx
            ny = cy + dy
            if nx < xlo or nx > xhi or ny < ylo or ny > yhi:
                continue
            n = cur + di
            if not ok[n] or (n != g and n in blk):
                continue
            if dx and dy and ((cur + dx) in blk or (cur + dy * W) in blk):
                continue
            if base < cost[n]:
                cost[n] = base
                came[n] = cur
                counter += 1
                ax = gx - nx
                ay = gy - ny
                if ax < 0:
                    ax = -ax
                if ay < 0:
                    ay = -ay
                heappush(open_heap, (base + ((ax + ay) if four else (ax if ax > ay else ay)), counter, n))
    return None


def find_path(
    world: Any, start: tuple[int, int], goal: tuple[int, int], limit: int = 24, avoid: set | None = None, max_nodes: int = 60_000,
    loco: str | None = None, join: dict | None = None,
) -> list[tuple[int, int]] | None:
    """A* over open tiles. The start and goal may be blocked (a workplace door).

    `join` (tile -> index on a route someone else already found to the same goal): the search stops at the first tile it touches,
    so a platoon of units pays for one long search and a short one each (military._walk)."""
    if start == goal:
        return []
    if loco is not None and world.terrain is not None:
        return _find_path_fast(world, start, goal, limit, avoid, max_nodes, loco, join)
    open_heap: list[tuple[float, int, tuple[int, int]]] = [(0.0, 0, start)]
    four = len(world.move_dirs) == 4
    enter = world.tile_in_map if loco is None else (lambda px, py: world.tile_speed(loco, px, py) > 0)
    came: dict[tuple[int, int], tuple[int, int]] = {}
    cost = {start: 0.0}
    counter = 0
    while open_heap:
        _f, _c, cur = heapq.heappop(open_heap)
        if counter > max_nodes:
            return None
        if cur == goal or (join is not None and cur in join):
            path = []
            while cur != start:
                path.append(cur)
                cur = came[cur]
            path.reverse()
            return path
        for dx, dy in world.move_dirs:
            nxt = (cur[0] + dx, cur[1] + dy)
            if abs(nxt[0] - start[0]) > limit or abs(nxt[1] - start[1]) > limit:
                continue
            if not enter(nxt[0], nxt[1]) or (nxt != goal and (nxt in world.blocked or (avoid and nxt in avoid))):
                continue
            if dx and dy and ((cur[0] + dx, cur[1]) in world.blocked or (cur[0], cur[1] + dy) in world.blocked):
                continue
            step = cost[cur] + 1.0
            if nxt not in cost or step < cost[nxt]:
                cost[nxt] = step
                came[nxt] = cur
                counter += 1
                h = (abs(goal[0] - nxt[0]) + abs(goal[1] - nxt[1])) if four else max(abs(goal[0] - nxt[0]), abs(goal[1] - nxt[1]))
                heapq.heappush(open_heap, (step + h, counter, nxt))
    return None


# ---------------------------------------------------------------- workers

def spawn_worker(world: Any, building: dict, role: str) -> str:
    worker_id = new_id(world, "worker")
    tile = (building["tx"], building["ty"])
    world.workers[worker_id] = {
        "id": worker_id,
        "kind": "worker",
        "role": role,
        "definition": f"widelands.{role}_worker",
        "faction": building["faction"],
        "faction_name": building["faction_name"],
        "label": f"{building['faction_name']} {role}",
        "building": building["id"],
        "tx": tile[0],
        "ty": tile[1],
        "progress_ms": 0,
        "path": [],
        "anim": "idle",
        "facing": "se",
        "carrying": "",
        "program": "",
        "pc": 0,
        "wait_ms": 0,
        "target_tree": "",
        "target_tile": None,
        "returning": False,
        "status": "idle",
    }
    building["worker_id"] = worker_id
    building.setdefault("worker_ids", {})[role] = worker_id
    world.events.append({"kind": "worker_spawned", "id": worker_id, "building": building["id"], "role": role})
    return worker_id


def _object(world: Any, object_id: str) -> dict | None:
    return world.trees.get(object_id) or world.rocks.get(object_id) or world.animals.get(object_id)


def _release(world: Any, worker: dict) -> None:
    tree = _object(world, worker["target_tree"])
    if tree is not None and tree["reserved_by"] == worker["id"]:
        tree["reserved_by"] = ""
    if worker["target_tile"] is not None:
        world.reserved_tiles.discard(tuple(worker["target_tile"]))
    worker["target_tree"] = ""
    worker["target_tile"] = None


def _fail_program(world: Any, worker: dict, reason: str) -> None:
    _release(world, worker)
    world.events.append({"kind": "worker_failed", "id": worker["id"], "reason": reason})
    worker["program"] = ""
    worker["pc"] = 0
    worker["wait_ms"] = 0
    worker["status"] = "returning"
    building = world.buildings.get(worker["building"])
    if building is not None:
        building["prog_failed"] = True
        building["worker_fail"] = reason
    _begin_return(world, worker)


def _begin_return(world: Any, worker: dict) -> None:
    building = world.buildings.get(worker["building"])
    if building is None:
        return
    here = (worker["tx"], worker["ty"])
    path = find_path(world, here, (building["tx"], building["ty"]))
    worker["path"] = path if path is not None else []
    worker["anim"] = "walkload" if worker["carrying"] else "walk"
    worker["returning"] = True


def _arrive_home(world: Any, worker: dict) -> None:
    from wizard_rts.economy import produce

    building = world.buildings[worker["building"]]
    if worker["carrying"]:
        good = worker["carrying"]
        produce(world, building["id"], good, 1)
        world.stats["produce"] += 1
        world.stats["made_" + good] = world.stats.get("made_" + good, 0) + 1
        flow.note(world, building, "made", good, 1)
        world.events.append({"kind": "ware_stored", "worker": worker["id"], "building": building["id"], "good": good})
        worker["carrying"] = ""
    worker["returning"] = False
    worker["anim"] = "idle"
    worker["status"] = "idle"
    worker["program"] = ""
    building["worker_done"] = True


def worker_abort(world: Any, worker: dict, reason: str) -> None:
    _release(world, worker)
    world.events.append({"kind": "worker_aborted", "id": worker["id"], "reason": reason, "lost": worker["carrying"]})
    world.workers.pop(worker["id"], None)
    building = world.buildings.get(worker["building"])
    if building is not None:
        building["worker_id"] = ""
        building.get("worker_ids", {}).pop(worker["role"], None)
        building["respawn_ms"] = 30_000
        building["waiting_worker"] = False
        building["stack"] = [["main", 0]]


def worker_quantum(world: Any, worker: dict) -> None:
    building = world.buildings.get(worker["building"])
    if building is None or not building.get("operational", True):
        worker_abort(world, worker, "workplace_destroyed")
        return
    if worker["path"]:
        worker["progress_ms"] += QUANTUM_MS
        if worker["progress_ms"] >= WALK_MS:
            nxt = worker["path"].pop(0)
            worker["facing"] = facing(nxt[0] - worker["tx"], nxt[1] - worker["ty"])
            worker["tx"], worker["ty"] = nxt
            worker["progress_ms"] = 0
        return
    worker["progress_ms"] = 0
    if worker["returning"]:
        if (worker["tx"], worker["ty"]) == (building["tx"], building["ty"]):
            _arrive_home(world, worker)
        else:
            _begin_return(world, worker)
            if not worker["path"]:
                worker_abort(world, worker, "no_path_home")
        return
    if worker["wait_ms"] > 0:
        worker["wait_ms"] -= QUANTUM_MS
        return
    if worker["program"]:
        _run_step(world, worker)


TERRAFORM_TARGET = {"amazons": "summer_meadow1", "diking": "summer_meadow1"}  # the fertile terrain a reclaimed or improved node becomes


def _land_next_to(world: Any, tile: tuple[int, int]) -> tuple[int, int] | None:
    t = world.terrain
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        n = (tile[0] + dx, tile[1] + dy)
        if t.in_bounds(*n) and t.ground(*n) and n not in world.blocked and n not in world.tree_tiles and n not in world.reserved_tiles and n not in world.road_tile_set:
            return n
    return None


def special_space(world: Any, worker: dict, args: dict) -> tuple[tuple[int, int], tuple[int, int], list] | None:
    """findspace size:swim (a water node, the worker stands on the shore beside it) and findspace terraform:<kind> (a node that can be improved)."""
    t = world.terrain
    if t is None:
        return None
    here = (worker["tx"], worker["ty"])
    radius = int(args["radius"])
    cands: list[tuple[int, tuple[int, int], tuple[int, int]]] = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            x, y = here[0] + dx, here[1] + dy
            if not t.in_bounds(x, y):
                continue
            if args.get("swim") and not args.get("terraform"):
                if not t.is_water(x, y) or (args.get("ferry") and not t.is_shallow(x, y)):
                    continue
                stand = _land_next_to(world, (x, y))
            elif args.get("terraform") == "diking":
                if not t.is_shallow(x, y) or t.depth[y * t.w + x] != 1 or (x, y) in world.tree_tiles:
                    continue
                stand = _land_next_to(world, (x, y))
            else:  # amazons: barren (walkable, not arable) ground is made fertile
                if t.class_at(x, y) != 2 or (x, y) in world.blocked or (x, y) in world.tree_tiles or (x, y) in world.reserved_tiles:
                    continue
                stand = (x, y)
            if stand is not None:
                cands.append((abs(dx) + abs(dy), stand, (x, y)))
    for _d, stand, target in sorted(cands)[:6]:
        path = find_path(world, here, stand) if stand != here else []
        if path is not None:
            return stand, target, path
    return None


def terraform(world: Any, worker: dict, kind: str) -> bool:
    t = world.terrain
    if t is None:
        return False
    name = TERRAFORM_TARGET.get(kind)
    if name is None or name not in __import__("wizard_rts.terrain", fromlist=["defs"]).defs()["terrains"]:
        names = [n for n, d in __import__("wizard_rts.terrain", fromlist=["defs"]).defs()["terrains"].items() if d["is"] == "arable"]
        name = sorted(names)[0]
    if kind == "diking":
        obj = _object(world, worker["target_tree"])
        tile = (obj["tx"], obj["ty"]) if obj is not None else worker.get("swim_tile")
        if tile is None or not t.is_water(*tile):
            return False
        t.retype(tile[0], tile[1], name)
        if obj is not None:
            remove_tree(world, obj["id"], "dike_done")
        world.stats["land_reclaimed"] = world.stats.get("land_reclaimed", 0) + 1
    else:
        tile = worker.get("swim_tile") or (worker["tx"], worker["ty"])
        if t.class_at(*tile) != 2:
            return False
        t.retype(tile[0], tile[1], name)
        world.stats["land_improved"] = world.stats.get("land_improved", 0) + 1
    world.events.append({"kind": "terraformed", "tile": list(tile), "how": kind, "worker": worker["id"]})
    return True


def worker_program(role: str, name: str) -> list[tuple[str, dict]]:
    legacy = WORKER_PROGRAMS.get(role)
    if legacy is not None and name in legacy:
        return legacy[name]
    generic = wl_defs.worker_programs(role)
    return (generic or {}).get(name, [])


def _run_step(world: Any, worker: dict) -> None:
    steps = worker_program(worker["role"], worker["program"])
    if worker["pc"] >= len(steps):
        worker["program"] = ""
        return
    cmd, args = steps[worker["pc"]]
    worker["pc"] += 1
    here = (worker["tx"], worker["ty"])
    if cmd == "findobject":
        best = None
        attrib = args["attrib"]
        if attrib == "rocks":
            pool = list(world.rocks.values())
        elif attrib == "eatable":
            pool = [x for x in world.animals.values() if x.get("alive", True)]
        else:
            pool = list(world.trees.values())
        for tree in pool:
            if tree["reserved_by"]:
                continue
            if attrib in ("tree", "normal_tree") and "imm" not in tree and not (tree["species"] != "wheat" and tree["stage"] == "old"):
                continue
            if attrib == "flowering" and "imm" not in tree and not (tree["species"] == "wheat" and tree["stage"] == "medium"):
                continue
            if attrib == "ripe_wheat" and not (tree["species"] == "wheat" and tree["stage"] == "ripe"):
                continue
            if "imm" in tree and attrib not in imm.attributes(tree):
                continue
            if "imm" not in tree and attrib not in ("tree", "normal_tree", "flowering", "ripe_wheat", "rocks", "eatable"):
                continue
            dist = max(abs(tree["tx"] - here[0]), abs(tree["ty"] - here[1]))
            if dist > args["radius"] or (best is not None and dist >= best[0]):
                continue
            goal = (tree["tx"], tree["ty"])
            if world.terrain is not None and world.terrain.is_water(*goal):  # a dike stands in the water: the diker works from the shore beside it
                goal = _land_next_to(world, goal) or goal
            path = find_path(world, here, goal) if goal != here else []
            if path is not None:
                best = (dist, tree, path)
        if best is None:
            _fail_program(world, worker, "no_" + {"rocks": "rock", "eatable": "game", "ripe_wheat": "ripe_field"}.get(args["attrib"], "tree"))
            return
        _dist, tree, path = best
        tree["reserved_by"] = worker["id"]
        worker["target_tree"] = tree["id"]
        worker["path"] = path
        worker["anim"] = "walk"
        worker["status"] = "walking"
        world.events.append({"kind": "object_reserved", "tree": tree["id"], "worker": worker["id"]})
        if args["attrib"] == "tree":
            world.events.append({"kind": "tree_reserved", "tree": tree["id"], "worker": worker["id"]})
        if args["attrib"] == "eatable":
            tree["status"] = "frightened"
    elif cmd == "findspace" and (args.get("swim") or args.get("terraform")):
        spot = special_space(world, worker, args)
        if spot is None:
            _fail_program(world, worker, "no_space")
            return
        stand, target, path = spot
        world.reserved_tiles.add(stand)
        worker["target_tile"] = stand
        worker["swim_tile"] = target
        worker["path"] = path
        worker["anim"] = "walk"
        worker["status"] = "walking"
        worker["target_tree"] = "@water" if args.get("swim") else worker["target_tree"]
    elif cmd == "findspace":
        radius = args["radius"]
        if args.get("resource"):
            cands = _shore_spots(world, building_of(world, worker), args)
        else:
            cands = [
                (here[0] + dx, here[1] + dy)
                for dy in range(-radius, radius + 1)
                for dx in range(-radius, radius + 1)
                if (dx or dy) and tile_free_for_tree(world, (here[0] + dx, here[1] + dy))
            ]
        if args.get("resource") and not cands:
            _fail_program(world, worker, "no_" + args["resource"])
            return
        tile = None
        path = None
        best_p = -1.0
        best_pick = None
        for _ in range(args.get("saplingsearches", 5) if cands else 0):
            tile = cands[world.rng.randrange(len(cands))]
            path = find_path(world, here, tile)
            if path is None:
                continue
            p = world.terrain.growth_probability("beech", tile[0], tile[1]) if (world.terrain is not None and not args.get("resource")) else 0.0
            if p > best_p:
                best_p, best_pick = p, (tile, path)
            if world.terrain is None or args.get("resource"):
                break
        if best_pick is not None:
            tile, path = best_pick
        else:
            path = None
        if path is None:
            _fail_program(world, worker, "no_space")
            return
        world.reserved_tiles.add(tile)
        worker["target_tile"] = tile
        worker["path"] = path
        worker["anim"] = "walk"
        worker["status"] = "walking"
    elif cmd == "walk":
        # the path was prepared by findobject/findspace
        worker["anim"] = "walk"
    elif cmd == "animate":
        worker["anim"] = args["name"]
        worker["status"] = "working"
        worker["wait_ms"] = args["ms"]
        tree = _object(world, worker["target_tree"])
        if tree is not None:
            worker["facing"] = facing(tree["tx"] - worker["tx"], tree["ty"] - worker["ty"])
    elif cmd == "callobject":
        tree = _object(world, worker["target_tree"])
        if tree is None or tree["reserved_by"] != worker["id"]:
            _fail_program(world, worker, "object_gone")
            return
        tree["reserved_by"] = ""
        if "imm" in tree and args["program"] != "shrink":
            imm.call(world, tree, args["program"])
            world.events.append({"kind": "imm_called", "tree": tree["id"], "program": args["program"], "worker": worker["id"]})
        elif args["program"] == "fall":
            tree["stage"] = "felled"
            tree["timer_ms"] = FELLED_MS
            world.events.append({"kind": "tree_felled", "tree": tree["id"], "worker": worker["id"]})
        elif args["program"] == "remove":  # a hunter's kill (frisian hunters use callobject=remove)
            world.animals.pop(tree["id"], None)
            world.trees.pop(tree["id"], None)
            world.events.append({"kind": "animal_hunted", "animal": tree["id"], "worker": worker["id"], "species": tree.get("species", "")})
        elif args["program"] == "harvest":
            tree["stage"] = "harvested"
            tree["timer_ms"] = STAGE_TABLES["wheat"]["harvested"][0]
            world.events.append({"kind": "field_harvested", "tree": tree["id"], "worker": worker["id"]})
        else:  # shrink: one load of granite comes off the rock
            tree["amount"] -= 1
            world.events.append({"kind": "rock_shrunk", "rock": tree["id"], "left": tree["amount"], "worker": worker["id"]})
            if tree["amount"] <= 0:
                world.rocks.pop(tree["id"], None)
                world.events.append({"kind": "rock_gone", "rock": tree["id"]})
    elif cmd == "createware":
        if not worker["target_tree"]:
            _fail_program(world, worker, "no_source")
            return
        worker["carrying"] = args["ware"]
        kind = "log_created" if args["ware"] == "log" else "ware_created"
        world.events.append({"kind": kind, "worker": worker["id"], "tree": worker["target_tree"], "good": args["ware"]})
        worker["target_tree"] = ""
    elif cmd == "removeobject":
        animal = world.animals.get(worker["target_tree"])
        if animal is None or animal["reserved_by"] != worker["id"]:
            _fail_program(world, worker, "game_gone")
            return
        world.animals.pop(animal["id"], None)
        world.events.append({"kind": "animal_hunted", "animal": animal["id"], "worker": worker["id"], "species": animal["species"]})
    elif cmd == "plant":
        tile = worker["target_tile"]
        if tile is None or tuple(tile) != here:
            _fail_program(world, worker, "not_at_space")
            return
        world.reserved_tiles.discard(tuple(tile))
        if "shipconstruction" in args["attrib"]:
            worker["target_tile"] = None
            return  # the shipyard (maritime.py) manages the ship site; the shipwright only walks and works
        if args["attrib"] not in ("seed_wheat", "tree_sapling") and imm.candidates(args["attrib"]):
            names = imm.candidates(args["attrib"])
            at = tuple(worker["swim_tile"]) if args["attrib"] == "dike" and worker.get("swim_tile") else tuple(tile)
            tree_id = imm.make(world, at, names[world.rng.randrange(len(names))])
            if args["attrib"] == "dike":
                worker["target_tree"] = tree_id
            world.stats["fields_planted"] = world.stats.get("fields_planted", 0) + 1
            world.events.append({"kind": "field_planted", "tree": tree_id, "worker": worker["id"]})
        elif args["attrib"] == "seed_wheat":
            tree_id = plant_tree(world, tuple(tile), "tiny", "wheat")
            world.stats["fields_planted"] = world.stats.get("fields_planted", 0) + 1
            world.events.append({"kind": "field_planted", "tree": tree_id, "worker": worker["id"]})
        else:
            tree_id = plant_tree(world, tuple(tile), "sapling", best_species(world, tuple(tile)))
            world.stats["saplings_planted"] = world.stats.get("saplings_planted", 0) + 1
            world.events.append({"kind": "sapling_planted", "tree": tree_id, "worker": worker["id"]})
        worker["target_tile"] = None
    elif cmd in ("mine", "breed"):
        # Worker::run_mine / run_breed: nets and fish-breeders work the water around the spot the worker stands on
        if world.terrain is None:
            _fail_program(world, worker, "no_terrain")
            return
        fn = resources.worker_mine if cmd == "mine" else resources.worker_breed
        if not fn(world, here, args["resource"], int(args["radius"])):
            _fail_program(world, worker, "no_" + args["resource"] if cmd == "mine" else "grounds_full")
            return
        stat = "fish_caught" if cmd == "mine" and args["resource"] == "fish" else cmd + "_" + args["resource"]
        world.stats[stat] = world.stats.get(stat, 0) + 1
        if cmd == "mine":
            worker["target_tree"] = "@" + args["resource"]  # the catch: createware needs a source
    elif cmd == "createbob":
        from wizard_rts import animals as an

        bobs = [b for b in args.get("bobs", []) if b in an.ANIMAL_SPECIES]
        building = building_of(world, worker)
        if bobs:  # release game: an animal of one of the listed species appears beside the keeper
            species = bobs[world.rng.randrange(len(bobs))]
            an.spawn_animal(world, here, species)
            world.stats["game_released"] = world.stats.get("game_released", 0) + 1
            world.events.append({"kind": "animal_released", "species": species, "worker": worker["id"]})
        elif any(b.endswith("_ferry") for b in args.get("bobs", [])):  # a ferry is a worker the economy keeps as a ware until a waterway needs it
            from wizard_rts.economy import produce as _produce

            _produce(world, building["id"], "ferry", 1)
            world.stats["made_ferry"] = world.stats.get("made_ferry", 0) + 1
            world.events.append({"kind": "ferry_built", "worker": worker["id"], "building": building["id"]})
    elif cmd == "scout":
        building = building_of(world, worker)
        seen = world.__dict__.setdefault("explored", {}).setdefault(building["faction_name"], set())
        r = int(args["radius"])
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    seen.add((building["tx"] + dx, building["ty"] + dy))
        visibility.reveal(world, building["faction_name"], seen)
        worker["anim"] = "idle"
        worker["status"] = "working"
        worker["wait_ms"] = int(args["ms"])
        world.stats["scouted"] = world.stats.get("scouted", 0) + 1
        world.events.append({"kind": "scouted", "faction": building["faction_name"], "building": building["id"], "radius": r})
    elif cmd == "terraform":
        if not terraform(world, worker, args["kind"]):
            _fail_program(world, worker, "no_terrain")
            return
    elif cmd == "return":
        worker["status"] = "returning"
        _begin_return(world, worker)
        # the walk home is the final step
        worker["returning"] = True


# ---------------------------------------------------------------- production sites

def economy_needs(world: Any, faction: str, good: str) -> bool:
    """The Widelands economy-needs test: stock under the target, or an open request for the ware."""
    from wizard_rts.logistics import io_for

    have = sum(
        int(world.stocks.get(b["id"], {}).get(good, 0))
        for b in world.buildings.values()
        if b["kind"] == "warehouse" and b["faction"] == faction
    )
    if have < ECONOMY_TARGETS.get(good, 20):
        return True
    for b in world.buildings.values():
        if b["faction"] != faction:
            continue
        cap = io_for(world, b).get("requests", {}).get(good)
        if cap is not None and int(world.stocks.get(b["id"], {}).get(good, 0)) < cap:
            return True
    return False


def _mine(world: Any, building: dict, args: dict) -> bool:
    """Take one unit from the resource nodes around the building. False if it fails."""
    if world.terrain is not None:
        return resources.production_mine(world, building, args)
    res, radius = args["resource"], args["radius"]
    centre = (building["tx"], building["ty"])
    nodes = world.resource_nodes(centre, radius, res)
    left = sum(world.resource_amount(n, res) for n in nodes)
    initial = building.setdefault("deposit_initial", {}).get(res)
    if initial is None:
        initial = building["deposit_initial"][res] = left
    exhausted_for_yield = left <= initial * (1.0 - args["yield"] / 100.0)
    if not nodes or (exhausted_for_yield and world.rng.random() * 100 >= args["when_empty"]):
        building["deposit_exhausted"] = True
        return False
    node = nodes[world.rng.randrange(len(nodes))]
    world.take_resource(node, res, 1)
    world.events.append({"kind": "mined", "building": building["id"], "resource": res, "node": list(node)})
    return True


def _programs_of(building: dict) -> dict[str, list[tuple[str, dict]]] | None:
    kind = building.get("kind", "")
    if kind in BUILDING_PROGRAMS:
        return {"main": BUILDING_PROGRAMS[kind]}
    spec = wl_defs.spec_for_kind(kind)
    return spec["programs"] if spec else None


def _roles_of(building: dict) -> list[str]:
    kind = building.get("kind", "")
    if kind in BUILDING_PROGRAMS:
        role = WORKER_FOR_BUILDING.get(kind)
        return [role] if role else []
    spec = wl_defs.spec_for_kind(kind)
    return sorted(set(spec["worker_for_program"].values())) if spec else []


def _role_for_program(building: dict, program: str) -> str | None:
    kind = building.get("kind", "")
    if kind in BUILDING_PROGRAMS:
        return WORKER_FOR_BUILDING.get(kind)
    spec = wl_defs.spec_for_kind(kind)
    return spec["worker_for_program"].get(program) if spec else None


WORKER_FAIL_TEXT = {
    "no_tree": "no trees in reach", "no_rock": "no rocks in reach", "no_fish": "no fish in reach", "no_space": "no free space to work",
    "no_ripe_field": "no ripe field", "no_game": "no game to hunt", "grounds_full": "the fishing grounds are full",
    "object_gone": "its target disappeared", "no_source": "nothing to carry", "no_terrain": "needs terrain", "game_gone": "the game escaped",
}


def _fail(world: Any, building: dict, why: str, detail: str = "") -> None:
    """A programme failed. A called sub-programme (a failed `consume`, a missing worker result) ends only itself: the main programme carries on with its
    next `call`, as Widelands does with a recently failed programme, so one starved product does not block the others (V4 P2). A failure in main
    itself drops back to its start. Either way the site waits before its next attempt."""
    stack = building.get("stack") or []
    if len(stack) > 1:
        building["stack"] = stack[:1]  # main keeps its place; the failed frames are dropped
    else:
        building["stack"] = [["main", 0]]
    building["sleep_ms"] = FAIL_SLEEP_MS
    if why == "worker":
        detail = WORKER_FAIL_TEXT.get(building.get("worker_fail", ""), building.get("worker_fail", ""))
    building["stall"] = {"reason": why, "detail": detail, "at_ms": int(world.dmb.clock.get("game_ms", 0))}
    key = (building["id"], why)
    world.shortages[key] = world.shortages.get(key, 0) + 1


def _skip(building: dict) -> None:
    """return=skipped: leave the current programme. From main this costs a 10 s delay."""
    stack = building["stack"]
    stack.pop()
    if not stack:
        building["stack"] = [["main", 0]]
        building["sleep_ms"] = FAIL_SLEEP_MS


def production_quantum(world: Any) -> None:
    from wizard_rts.economy import _supply, produce

    for building in list(world.buildings.values()):
        programs = _programs_of(building)
        if programs is None or not building.get("operational", True):
            continue
        if building.get("disrupted"):  # a collapse or an outbreak closed it (disruption.py): nothing is made until it is repaired
            building["working"] = False
            continue
        roles = _roles_of(building)
        have = building.setdefault("worker_ids", {})
        missing = [r for r in roles if have.get(r) not in world.workers]
        if missing:
            if building.get("respawn_ms", 0) > 0:
                building["respawn_ms"] -= QUANTUM_MS
            else:
                for r in missing:
                    spawn_worker(world, building, r)
            continue
        if building.get("sleep_ms", 0) > 0:
            building["sleep_ms"] -= int(QUANTUM_MS * _health_factor(building))
            continue
        building["working"] = False
        stack = building.setdefault("stack", [["main", 0]])
        if building.get("waiting_worker"):
            if building.pop("worker_done", False):
                building["waiting_worker"] = False
                if building.pop("prog_failed", False):
                    _fail(world, building, "worker")
                elif stack:
                    stack[-1][1] += 1
            continue
        if not stack:
            stack.append(["main", 0])
        frame = stack[-1]
        program = programs.get(frame[0])
        if program is None or frame[1] >= len(program):
            stack.pop()
            if not stack:
                stack.append(["main", 0])
            continue
        cmd, args = program[frame[1]]
        frame[1] += 1
        stock = world.stocks.setdefault(building["id"], {})
        if cmd == "callworker":
            role = _role_for_program(building, args["program"])
            worker = world.workers.get(have.get(role)) if role else None
            if worker is None:
                frame[1] -= 1
                continue
            building.pop("worker_done", None)
            building.pop("prog_failed", None)
            worker.update(program=args["program"], pc=0, status="starting")
            building["waiting_worker"] = True
            frame[1] -= 1  # advances when the worker reports back
        elif cmd == "sleep":
            building["sleep_ms"] = args["ms"]
        elif cmd == "animate":
            building["working"] = True
            building["sleep_ms"] = args["ms"]
        elif cmd in ("needs", "return_unless_needs"):
            if not economy_needs(world, building["faction"], args["good"]):
                building["stall"] = {"reason": "not_needed", "detail": "the economy does not need %s" % args["good"], "at_ms": int(world.dmb.clock.get("game_ms", 0))}
                _skip(building)
        elif cmd == "return":
            if args.get("skipped", True):
                _skip(building)
            else:
                building["stack"] = [["main", 0]]
        elif cmd == "return_cond":
            def _holds(c: dict) -> bool:
                if c["type"] == "economy_needs":
                    ok = economy_needs(world, building["faction"], c["ware"])
                elif c["type"] == "experience":
                    ok = False  # no training sites in the hybrid: workers never need experience
                elif c["type"] == "fleet_ferry":
                    from wizard_rts import maritime

                    ok = maritime.needs_ferry(world, building["faction_name"])
                else:
                    ok = any(int(stock.get(g, 0)) >= c["n"] for g in c["wares"])
                return ok != c["not"]

            holds = any(all(_holds(c) for c in group) for group in args.get("groups", [args["conds"]]))
            if (args["mode"] == "unless" and not holds) or (args["mode"] == "when" and holds):
                building["stall"] = {"reason": "not_needed", "detail": "the economy does not need what it makes", "at_ms": int(world.dmb.clock.get("game_ms", 0))}
                _skip(building)
        elif cmd == "recruit":
            from wizard_rts import construction as con

            unit_ware = args.get("unit", "")
            if "soldier" not in unit_ware:  # recruit=barbarians_ox: an animal worker, modelled as a ware
                from wizard_rts.economy import produce as _produce

                good = unit_ware.split("_", 1)[-1]
                _produce(world, building["id"], good, 1)
                world.stats["made_" + good] = world.stats.get("made_" + good, 0) + 1
                flow.note(world, building, "made", good, 1)
                world.events.append({"kind": "produced", "building": building["id"], "good": good})
                continue
            tile = con._exit_tile(world, building)
            if tile is not None:
                uid = world._unit(building["faction"], building["faction_name"], "soldier", "Soldier", "widelands.soldier", tile)
                world.stats["recruited"] = world.stats.get("recruited", 0) + 1
                world.events.append({"kind": "unit_produced", "building": building["id"], "unit": uid, "unit_kind": "soldier"})
        elif cmd == "construct":
            from wizard_rts import maritime

            why = maritime.construct_step(world, building)
            if why is not None:
                _fail(world, building, "construct" if why != "inputs" else "inputs", {"inputs": "waiting for ship wares", "no_coast": "no water to build a ship in"}.get(why, why))
            else:
                building["working"] = True
        elif cmd == "call":
            if args["target"] in programs:
                stack.append([args["target"], 0])
        elif cmd == "consume":
            if all(int(stock.get(g, 0)) >= n for g, n in args.items()):
                for g, n in args.items():
                    _supply(world, building["id"]).remove_wares(g, n)
                    world.stats["consumed_" + g] = world.stats.get("consumed_" + g, 0) + n
                    flow.note(world, building, "consumed", g, n)
            else:
                _fail(world, building, "inputs", "waiting for " + ", ".join("%s %d" % (g, n - int(stock.get(g, 0))) for g, n in args.items() if int(stock.get(g, 0)) < n))
        elif cmd == "consume_any":
            pick = next((g for g in args["goods"] if int(stock.get(g, 0)) >= 1), None)
            if pick is not None:
                _supply(world, building["id"]).remove_wares(pick, 1)
                world.stats["consumed_" + pick] = world.stats.get("consumed_" + pick, 0) + 1
                flow.note(world, building, "consumed", pick, 1)
            else:
                _fail(world, building, "inputs", "waiting for one of " + ", ".join(args["goods"]))
        elif cmd == "consume_groups":
            picks = []
            for alts, n in args["groups"]:
                pick = next((g for g in alts if int(stock.get(g, 0)) >= n), None)
                if pick is None:
                    picks = None
                    break
                picks.append((pick, n))
            if picks is None:
                _fail(world, building, "inputs")
            else:
                for g, n in picks:
                    _supply(world, building["id"]).remove_wares(g, n)
                    world.stats["consumed_" + g] = world.stats.get("consumed_" + g, 0) + n
                    flow.note(world, building, "consumed", g, n)
        elif cmd == "mine":
            if not _mine(world, building, args):
                _fail(world, building, "deposit")
        elif cmd == "cure_needed":
            if not regions.cubes_here(world, building):
                building["stall"] = {"reason": "not_needed", "detail": "its region is clean", "at_ms": int(world.dmb.clock.get("game_ms", 0))}
                _skip(building)
        elif cmd == "cure":
            regions.cure(world, building, int(args.get("cubes", 1)))
        elif cmd == "produce":
            for g, n in args.items():
                n = regions.yield_count(world, building, n)  # an outbreak in the region lowers what a finished programme yields
                if n <= 0:
                    continue
                produce(world, building["id"], g, n)
                world.stats["produce"] += n
                world.stats["made_" + g] = world.stats.get("made_" + g, 0) + n
                flow.note(world, building, "made", g, n)
                world.events.append({"kind": "produced", "building": building["id"], "good": g})
        else:
            _fail(world, building, "unsupported")


def _health_factor(building: dict) -> float:
    """A damaged workplace sleeps more slowly, so it produces less."""
    hp, mx = int(building.get("hp", 1)), max(int(building.get("max_hp", 1)), 1)
    return max(0.25, hp / mx)


def forestry_quantum(world: Any) -> None:
    from wizard_rts.animals import animal_quantum

    animal_quantum(world)
    tree_quantum(world)
    production_quantum(world)
    for worker in list(world.workers.values()):
        worker_quantum(world, worker)

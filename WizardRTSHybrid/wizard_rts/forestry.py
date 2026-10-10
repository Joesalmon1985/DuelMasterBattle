"""Tree lifecycle and the worker-program interpreter.

Workers are physical: they hold a tile, walk A* paths one tile at a time, wait
out animations, and only then change the world. A tree is felled by a worker
that reserved it; the log exists only after that tree fell. The ware drops into
the workplace's output stock. Carriers (economy.py) are separate.
"""

from __future__ import annotations

import heapq
from typing import Any

from wizard_rts.forest_data import (
    BUILDING_PROGRAMS,
    FAIL_SLEEP_MS,
    FELLED_MS,
    OLD_SEED_RADIUS,
    TREE_STAGES,
    WALK_MS,
    WORKER_FOR_BUILDING,
    WORKER_PROGRAMS,
)

QUANTUM_MS = 100
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
        "definition": f"widelands.{species}",
        "species": species,
        "stage": stage,
        "tx": tile[0],
        "ty": tile[1],
        "timer_ms": TREE_STAGES[stage][0],
        "reserved_by": "",
    }
    world.tree_tiles[tile] = tree_id
    return tree_id


def tile_free_for_tree(world: Any, tile: tuple[int, int]) -> bool:
    if not world.tile_in_map(*tile) or tile in world.blocked or tile in world.tree_tiles:
        return False
    return tile not in world.reserved_tiles and tile not in world.road_tile_set


def remove_tree(world: Any, tree_id: str, reason: str) -> None:
    tree = world.trees.pop(tree_id, None)
    if tree is None:
        return
    world.tree_tiles.pop((tree["tx"], tree["ty"]), None)
    world.events.append({"kind": "tree_removed", "id": tree_id, "reason": reason})


def tree_quantum(world: Any) -> None:
    for tree_id in list(world.trees):
        tree = world.trees.get(tree_id)
        if tree is None:
            continue
        tree["timer_ms"] -= QUANTUM_MS
        if tree["timer_ms"] > 0:
            continue
        stage = tree["stage"]
        if stage == "felled":
            remove_tree(world, tree_id, "felled_gone")
            continue
        if tree["reserved_by"]:
            tree["timer_ms"] = QUANTUM_MS  # a worker is about to cut it
            continue
        _duration, die, nxt = TREE_STAGES[stage]
        if world.rng.random() * 100 < die:
            remove_tree(world, tree_id, "died")
            continue
        if stage == "old":
            _seed(world, tree)
            tree["timer_ms"] = TREE_STAGES["old"][0]
            continue
        tree["stage"] = nxt
        tree["timer_ms"] = TREE_STAGES[nxt][0]
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

def find_path(world: Any, start: tuple[int, int], goal: tuple[int, int], limit: int = 24) -> list[tuple[int, int]] | None:
    """A* over open tiles. The start and goal may be blocked (a workplace door)."""
    if start == goal:
        return []
    open_heap: list[tuple[float, int, tuple[int, int]]] = [(0.0, 0, start)]
    came: dict[tuple[int, int], tuple[int, int]] = {}
    cost = {start: 0.0}
    counter = 0
    while open_heap:
        _f, _c, cur = heapq.heappop(open_heap)
        if cur == goal:
            path = []
            while cur != start:
                path.append(cur)
                cur = came[cur]
            path.reverse()
            return path
        for dx, dy in _DIRS:
            nxt = (cur[0] + dx, cur[1] + dy)
            if abs(nxt[0] - start[0]) > limit or abs(nxt[1] - start[1]) > limit:
                continue
            if nxt != goal and (nxt in world.blocked or not world.tile_in_map(*nxt)):
                continue
            if dx and dy and ((cur[0] + dx, cur[1]) in world.blocked or (cur[0], cur[1] + dy) in world.blocked):
                continue
            step = cost[cur] + 1.0
            if nxt not in cost or step < cost[nxt]:
                cost[nxt] = step
                came[nxt] = cur
                counter += 1
                h = max(abs(goal[0] - nxt[0]), abs(goal[1] - nxt[1]))
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
    world.events.append({"kind": "worker_spawned", "id": worker_id, "building": building["id"]})
    return worker_id


def _release(world: Any, worker: dict) -> None:
    tree = world.trees.get(worker["target_tree"])
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
        building["respawn_ms"] = 30_000
        building["waiting_worker"] = False


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


def _run_step(world: Any, worker: dict) -> None:
    steps = WORKER_PROGRAMS[worker["role"]][worker["program"]]
    if worker["pc"] >= len(steps):
        worker["program"] = ""
        return
    cmd, args = steps[worker["pc"]]
    worker["pc"] += 1
    here = (worker["tx"], worker["ty"])
    if cmd == "findobject":
        best = None
        for tree in world.trees.values():
            if tree["stage"] != "old" or tree["reserved_by"]:
                continue
            dist = max(abs(tree["tx"] - here[0]), abs(tree["ty"] - here[1]))
            if dist > args["radius"] or (best is not None and dist >= best[0]):
                continue
            path = find_path(world, here, (tree["tx"], tree["ty"]))
            if path is not None:
                best = (dist, tree, path)
        if best is None:
            _fail_program(world, worker, "no_tree")
            return
        _dist, tree, path = best
        tree["reserved_by"] = worker["id"]
        worker["target_tree"] = tree["id"]
        worker["path"] = path
        worker["anim"] = "walk"
        worker["status"] = "walking"
        world.events.append({"kind": "tree_reserved", "tree": tree["id"], "worker": worker["id"]})
    elif cmd == "findspace":
        radius = args["radius"]
        cands = [
            (here[0] + dx, here[1] + dy)
            for dy in range(-radius, radius + 1)
            for dx in range(-radius, radius + 1)
            if (dx or dy) and tile_free_for_tree(world, (here[0] + dx, here[1] + dy))
        ]
        tile = None
        path = None
        for _ in range(args.get("saplingsearches", 5) if cands else 0):
            tile = cands[world.rng.randrange(len(cands))]
            path = find_path(world, here, tile)
            if path is not None:
                break
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
        tree = world.trees.get(worker["target_tree"])
        if tree is not None:
            worker["facing"] = facing(tree["tx"] - worker["tx"], tree["ty"] - worker["ty"])
    elif cmd == "callobject":
        tree = world.trees.get(worker["target_tree"])
        if tree is None or tree["reserved_by"] != worker["id"]:
            _fail_program(world, worker, "tree_gone")
            return
        tree["stage"] = "felled"
        tree["timer_ms"] = FELLED_MS
        tree["reserved_by"] = ""
        world.events.append({"kind": "tree_felled", "tree": tree["id"], "worker": worker["id"]})
    elif cmd == "createware":
        if not worker["target_tree"]:
            _fail_program(world, worker, "no_source")
            return
        worker["carrying"] = args["ware"]
        world.events.append({"kind": "log_created", "worker": worker["id"], "tree": worker["target_tree"]})
        worker["target_tree"] = ""
    elif cmd == "plant":
        tile = worker["target_tile"]
        if tile is None or tuple(tile) != here:
            _fail_program(world, worker, "not_at_space")
            return
        world.reserved_tiles.discard(tuple(tile))
        tree_id = plant_tree(world, tuple(tile), "sapling")
        world.events.append({"kind": "sapling_planted", "tree": tree_id, "worker": worker["id"]})
        worker["target_tile"] = None
    elif cmd == "return":
        worker["status"] = "returning"
        _begin_return(world, worker)
        # the walk home is the final step
        worker["returning"] = True


# ---------------------------------------------------------------- production sites

def production_quantum(world: Any) -> None:
    for building in list(world.buildings.values()):
        role = WORKER_FOR_BUILDING.get(building.get("kind", ""))
        if role is None or not building.get("operational", True):
            continue
        worker = world.workers.get(building.get("worker_id", ""))
        if worker is None:
            if building.get("respawn_ms", 0) > 0:
                building["respawn_ms"] -= QUANTUM_MS
            else:
                spawn_worker(world, building, role)
            continue
        if building.get("sleep_ms", 0) > 0:
            building["sleep_ms"] -= int(QUANTUM_MS * _health_factor(building))
            continue
        if building.get("waiting_worker"):
            if building.pop("worker_done", False):
                building["waiting_worker"] = False
                building["pc"] = building.get("pc", 0) + 1
                if building.pop("prog_failed", False):
                    building["sleep_ms"] = FAIL_SLEEP_MS
                    building["pc"] = 0
            continue
        actions = BUILDING_PROGRAMS[building["kind"]]
        pc = building.setdefault("pc", 0)
        if pc >= len(actions):
            building["pc"] = 0
            continue
        cmd, args = actions[pc]
        if cmd == "callworker":
            building.pop("worker_done", None)
            building.pop("prog_failed", None)
            worker.update(program=args["program"], pc=0, status="starting")
            building["waiting_worker"] = True
        elif cmd == "sleep":
            building["sleep_ms"] = args["ms"]
            building["pc"] += 1


def _health_factor(building: dict) -> float:
    """A damaged workplace sleeps more slowly, so it produces less."""
    hp, mx = int(building.get("hp", 1)), max(int(building.get("max_hp", 1)), 1)
    return max(0.25, hp / mx)


def forestry_quantum(world: Any) -> None:
    tree_quantum(world)
    production_quantum(world)
    for worker in list(world.workers.values()):
        worker_quantum(world, worker)

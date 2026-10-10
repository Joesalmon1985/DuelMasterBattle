"""Tree lifecycle and the worker-program interpreter.

Workers are physical: they hold a tile, walk A* paths one tile at a time, wait
out animations, and only then change the world. A tree is felled by a worker
that reserved it; the log exists only after that tree fell. The ware drops into
the workplace's output stock. Carriers (economy.py) are separate.
"""

from __future__ import annotations

import heapq
from typing import Any

from wizard_rts import imm, resources, wl_defs
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
ART_SPECIES = ("beech", "wheat")  # species with imported sprites; other trees draw as beech until their art is imported
TREE_SPECIES = ("beech", "oak", "birch", "spruce", "maple", "larch", "alder", "aspen", "rowan")
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
        "timer_ms": STAGE_TABLES.get(species, TREE_STAGES)[stage][0],
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


def tree_quantum(world: Any) -> None:
    phase = world.military_quanta % TREE_STRIDE
    step = QUANTUM_MS * TREE_STRIDE
    for tree_id in list(world.trees):
        tree = world.trees.get(tree_id)
        if tree is None:
            continue
        slot = tree.get("slot")
        if slot is None:
            slot = tree["slot"] = int(tree_id.split(":")[1]) % TREE_STRIDE
        if slot != phase:
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
        table = STAGE_TABLES.get(tree["species"], TREE_STAGES)
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

def find_path(
    world: Any, start: tuple[int, int], goal: tuple[int, int], limit: int = 24, avoid: set | None = None, max_nodes: int = 60_000,
    loco: str | None = None,
) -> list[tuple[int, int]] | None:
    """A* over open tiles. The start and goal may be blocked (a workplace door)."""
    if start == goal:
        return []
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
        if cur == goal:
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
            if attrib in ("tree", "normal_tree") and "imm" not in tree and not (tree["species"] == "beech" and tree["stage"] == "old"):
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
            path = find_path(world, here, (tree["tx"], tree["ty"]))
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
        if args["attrib"] not in ("seed_wheat", "tree_sapling") and imm.candidates(args["attrib"]):
            names = imm.candidates(args["attrib"])
            tree_id = imm.make(world, tuple(tile), names[world.rng.randrange(len(names))])
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


def _fail(world: Any, building: dict, why: str) -> None:
    """A programme failed: drop every frame and wait before trying again."""
    building["stack"] = [["main", 0]]
    building["sleep_ms"] = FAIL_SLEEP_MS
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
                else:
                    ok = any(int(stock.get(g, 0)) >= c["n"] for g in c["wares"])
                return ok != c["not"]

            holds = any(all(_holds(c) for c in group) for group in args.get("groups", [args["conds"]]))
            if (args["mode"] == "unless" and not holds) or (args["mode"] == "when" and holds):
                _skip(building)
        elif cmd == "recruit":
            from wizard_rts import construction as con

            unit_ware = args.get("unit", "")
            if "soldier" not in unit_ware:  # recruit=barbarians_ox: an animal worker, modelled as a ware
                from wizard_rts.economy import produce as _produce

                good = unit_ware.split("_", 1)[-1]
                _produce(world, building["id"], good, 1)
                world.stats["made_" + good] = world.stats.get("made_" + good, 0) + 1
                world.events.append({"kind": "produced", "building": building["id"], "good": good})
                continue
            tile = con._exit_tile(world, building)
            if tile is not None:
                uid = world._unit(building["faction"], building["faction_name"], "soldier", "Soldier", "widelands.soldier", tile)
                world.stats["recruited"] = world.stats.get("recruited", 0) + 1
                world.events.append({"kind": "unit_produced", "building": building["id"], "unit": uid, "unit_kind": "soldier"})
        elif cmd == "call":
            if args["target"] in programs:
                stack.append([args["target"], 0])
        elif cmd == "consume":
            if all(int(stock.get(g, 0)) >= n for g, n in args.items()):
                for g, n in args.items():
                    _supply(world, building["id"]).remove_wares(g, n)
                    world.stats["consumed_" + g] = world.stats.get("consumed_" + g, 0) + n
            else:
                _fail(world, building, "inputs")
        elif cmd == "consume_any":
            pick = next((g for g in args["goods"] if int(stock.get(g, 0)) >= 1), None)
            if pick is not None:
                _supply(world, building["id"]).remove_wares(pick, 1)
                world.stats["consumed_" + pick] = world.stats.get("consumed_" + pick, 0) + 1
            else:
                _fail(world, building, "inputs")
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
        elif cmd == "mine":
            if not _mine(world, building, args):
                _fail(world, building, "deposit")
        elif cmd == "produce":
            for g, n in args.items():
                produce(world, building["id"], g, n)
                world.stats["produce"] += n
                world.stats["made_" + g] = world.stats.get("made_" + g, 0) + n
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

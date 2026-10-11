"""Road network, transfers, carriers and requests.

Adapted in shape from Widelands' economy: buildings are nodes (their flag),
roads are edges with one carrier each, a request pulls a ware from a warehouse
that has it, and a production output is pushed to a warehouse. A ware is always
exactly one of: counted in a building's stock, waiting at a node, or on a
carrier. Nothing is created or destroyed on the way.

Provisional: one carrier per road, capacity one, no donkeys, no road upgrades,
no ware priorities beyond first come first served. Widelands source: src/economy
(Economy, Request, Supply, Transfer, RoutePlanner, Road, Carrier).
"""

from __future__ import annotations

from collections import deque
from typing import Any

from wizard_rts.economy import _supply, produce
from wizard_rts import wl_defs
from wizard_rts.programs_data import BUILDING_INPUTS, BUILDING_OUTPUTS
from wizard_rts.workers import facing, new_id

NODE_QUEUE_LIMIT = 8
LOGISTICS_PERIOD = 10  # quanta between request and output scans


def io_for(world: Any, building: dict) -> dict[str, Any]:
    if building.get("constructing"):
        return {"requests": dict(building["constructing"]["cost"])}
    kind = building.get("kind", "")
    io: dict[str, Any] = {}
    if kind in BUILDING_INPUTS:
        io["requests"] = dict(BUILDING_INPUTS[kind])
    if kind in BUILDING_OUTPUTS:
        io["outputs"] = list(BUILDING_OUTPUTS[kind])
    spec = wl_defs.spec_for_kind(kind)
    if spec is not None:
        if spec["inputs"]:
            io["requests"] = dict(spec["inputs"])
        if spec["outputs"]:
            io["outputs"] = list(spec["outputs"])
    extra = world.recipe_requests.get(building["id"])
    if extra:
        io["requests"] = {**io.get("requests", {}), **extra}
    return io


# ------------------------------------------------------------------ graph

def spawn_carrier(world: Any, road_id: str, faction_id: str, faction_name: str, tiles: list[tuple[int, int]]) -> str:
    carrier_id = str(world.dmb.ids.new("cart"))
    world.carriers[carrier_id] = {
        "id": carrier_id,
        "faction": faction_id,
        "faction_name": faction_name,
        "kind": "carrier",
        "label": f"{faction_name} carrier",
        "tx": tiles[0][0],
        "ty": tiles[0][1],
        "index": 0,
        "road_id": road_id,
        "cargo": None,
        "dir": "",
        "status": "idle",
        "definition": "widelands.carrier",
        "facing": "e",
    }
    return carrier_id


CARRIER_RESPAWN_MS = 20_000  # a road whose carrier died gets a new one from the nearest warehouse after this long


def kill_carrier(world: Any, carrier_id: str, reason: str) -> None:
    """A carrier dies: its ware is lost, and the road is without a carrier until a replacement walks out (carrier_quantum)."""
    car = world.carriers.pop(carrier_id, None)
    if car is None:
        return
    if car["cargo"]:
        world.stats["lost"] = world.stats.get("lost", 0) + 1
        world.events.append({"kind": "ware_lost", "good": car["cargo"]["good"], "at": car["road_id"]})
    if car["road_id"] in world.roads:
        world.carrier_respawn[car["road_id"]] = CARRIER_RESPAWN_MS
    world.events.append({"kind": "carrier_killed", "id": carrier_id, "road": car["road_id"], "reason": reason})


def carrier_quantum(world: Any) -> None:
    for rid in list(world.carrier_respawn):
        if rid not in world.roads:
            world.carrier_respawn.pop(rid, None)
            continue
        world.carrier_respawn[rid] -= 500  # called every five quanta
        if world.carrier_respawn[rid] <= 0:
            world.carrier_respawn.pop(rid)
            a, _b = world.road_edges[rid]
            owner = world.buildings.get(a)
            if owner is not None and not any(c["road_id"] == rid for c in world.carriers.values()):
                cid = spawn_carrier(world, rid, owner["faction"], owner["faction_name"], world.roads[rid])
                world.events.append({"kind": "carrier_respawned", "id": cid, "road": rid})


def add_road(world: Any, faction_id: str, faction_name: str, a: str, b: str, tiles: list[tuple[int, int]]) -> str:
    road_id = f"road:{new_id(world, 'r').split(':')[1]}:{a}-{b}"
    world.roads[road_id] = list(tiles)
    world.road_edges[road_id] = (a, b)
    world.road_tile_set.update(tiles)
    world.adjacency.setdefault(a, []).append((b, road_id))
    world.adjacency.setdefault(b, []).append((a, road_id))
    spawn_carrier(world, road_id, faction_id, faction_name, tiles)
    world.events.append({"kind": "road_built", "road": road_id, "a": a, "b": b})
    return road_id


def route(world: Any, src: str, dst: str) -> list[str] | None:
    if src == dst:
        return [src]
    prev: dict[str, str] = {src: ""}
    queue = deque([src])
    while queue:
        cur = queue.popleft()
        for nxt, _rid in world.adjacency.get(cur, []):
            if nxt in prev:
                continue
            prev[nxt] = cur
            if nxt == dst:
                path = [dst]
                while path[-1] != src:
                    path.append(prev[path[-1]])
                path.reverse()
                return path
            queue.append(nxt)
    return None


def _hop_road(world: Any, a: str, b: str) -> str | None:
    for nxt, rid in world.adjacency.get(a, []):
        if nxt == b:
            return rid
    return None


# ------------------------------------------------------------------ transfers

def _post(world: Any, node: str, transfer: dict) -> None:
    transfer["state"] = "waiting"
    world.node_wares.setdefault(node, []).append(transfer)


def _new_transfer(world: Any, good: str, faction: str, path: list[str]) -> dict:
    return {"id": new_id(world, "ware"), "good": good, "faction": faction, "path": path, "i": 0, "state": "waiting"}


def in_flight(world: Any, good: str | None = None, dest: str | None = None) -> int:
    n = 0
    for queue in world.node_wares.values():
        n += sum(1 for t in queue if (good is None or t["good"] == good) and (dest is None or t["path"][-1] == dest))
    for c in world.carriers.values():
        t = c["cargo"]
        if t and (good is None or t["good"] == good) and (dest is None or t["path"][-1] == dest):
            n += 1
    return n


def _warehouses(world: Any, faction: str) -> list[dict]:
    return [b for b in world.buildings.values() if b["kind"] == "warehouse" and b["faction"] == faction and b.get("operational", True)]


def _nearest(world: Any, src: str, candidates: list[str]) -> list[str] | None:
    best = None
    for cand in candidates:
        path = route(world, src, cand)
        if path is not None and (best is None or len(path) < len(best)):
            best = path
    return best


def _take(world: Any, node: str, good: str) -> bool:
    if int(world.stocks.get(node, {}).get(good, 0)) <= 0:
        return False
    _supply(world, node).remove_wares(good, 1)
    return True


def scan_requests_and_outputs(world: Any) -> None:
    # Construction sites are served before production inputs (a stable sort keeps creation order otherwise): the sawmill
    # would otherwise take every log that arrives and no new building could ever be finished.
    # Unit orders (queued recruits, an MCV) come next: they were asked for by a player or an AI commander, whereas the sawmill's
    # input is standing demand that would otherwise take every log that arrives.
    def priority(b: dict) -> int:
        return 0 if b.get("constructing") else (1 if b["id"] in world.recipe_requests else 2)

    for building in sorted(world.buildings.values(), key=priority):
        if "hp" not in building or not (building.get("operational", True) or building.get("constructing")):
            continue
        io = io_for(world, building)
        bid = building["id"]
        for good, cap in io.get("requests", {}).items():
            have = int(world.stocks.get(bid, {}).get(good, 0)) + in_flight(world, good, bid)
            if have >= cap:
                continue
            sources = [w["id"] for w in _warehouses(world, building["faction"]) if int(world.stocks.get(w["id"], {}).get(good, 0)) > 0]
            path = _nearest(world, bid, sources)  # roads are undirected
            if path is None:
                world.shortages[(bid, good)] = world.shortages.get((bid, good), 0) + 1
                continue
            path.reverse()
            if _take(world, path[0], good):
                _post(world, path[0], _new_transfer(world, good, building["faction"], path))
                world.events.append({"kind": "request_filled", "building": bid, "good": good, "from": path[0]})
        for good in io.get("outputs", []):
            if int(world.stocks.get(bid, {}).get(good, 0)) <= 0 or len(world.node_wares.get(bid, [])) >= NODE_QUEUE_LIMIT:
                continue
            path = _nearest(world, bid, [w["id"] for w in _warehouses(world, building["faction"])])
            if path is None or len(path) < 2:
                continue
            if _take(world, bid, good):
                _post(world, bid, _new_transfer(world, good, building["faction"], path))


def _arrive(world: Any, carrier: dict, transfer: dict, node: str) -> None:
    transfer["i"] += 1
    final = transfer["path"][-1]
    world.events.append({"kind": "deliver", "id": carrier["id"], "dest": node, "good": transfer["good"], "faction": carrier["faction"]})
    if node == final:
        dest = world.buildings.get(final, {})
        if dest.get("operational", True) or dest.get("constructing"):
            produce(world, final, transfer["good"], 1)
            if dest.get("kind") == "warehouse":
                world.stats["deliver"] += 1
            return
        # destination was destroyed in transit: send to a warehouse instead
        path = _nearest(world, node, [w["id"] for w in _warehouses(world, transfer["faction"])])
        if path is None or len(path) < 2:
            world.stats["lost"] = world.stats.get("lost", 0) + 1
            world.events.append({"kind": "ware_lost", "good": transfer["good"], "at": node})
            return
        transfer["path"], transfer["i"] = path, 0
    _post(world, node, transfer)


def _step_carrier(world: Any, carrier: dict) -> None:
    road = world.roads[carrier["road_id"]]
    a, b = world.road_edges[carrier["road_id"]]
    idx = int(carrier["index"])
    last = len(road) - 1

    def waiting_for_this_road(node: str) -> dict | None:
        for t in world.node_wares.get(node, []):
            if t["path"][t["i"]] == node and t["i"] + 1 < len(t["path"]) and _hop_road(world, node, t["path"][t["i"] + 1]) == carrier["road_id"]:
                return t
        return None

    target = None
    if carrier["cargo"]:
        target = last if carrier["dir"] == "ab" else 0
        if idx == target:
            node = b if carrier["dir"] == "ab" else a
            transfer, carrier["cargo"] = carrier["cargo"], None
            carrier["status"] = "idle"
            _arrive(world, carrier, transfer, node)
            return
    else:
        for end_idx, node, direction in ((0, a, "ab"), (last, b, "ba")):
            if idx == end_idx:
                t = waiting_for_this_road(node)
                if t is not None:
                    world.node_wares[node].remove(t)
                    t["state"] = "carried"
                    carrier["cargo"], carrier["dir"] = t, direction
                    carrier["status"] = "carrying"
                    world.events.append({"kind": "pickup", "id": carrier["id"], "from": node, "good": t["good"]})
                    return
        # walk to whichever end has a ware waiting; stay put otherwise
        if waiting_for_this_road(a) is not None and idx != 0:
            target = 0
        elif waiting_for_this_road(b) is not None and idx != last:
            target = last
        if target is None:
            carrier["status"] = "idle"
            return
    nxt = idx + (1 if target > idx else -1)
    step = road[nxt]
    if world.tile_blocked_for_carrier(step):
        carrier["status"] = "blocked"
        world.stats["blocked"] += 1
        world.events.append({"kind": "carrier_blocked", "id": carrier["id"], "tile": list(step), "faction": carrier["faction"]})
        return
    carrier["status"] = "carrying" if carrier["cargo"] else "moving"
    carrier["facing"] = facing(step[0] - road[idx][0], step[1] - road[idx][1])
    carrier["index"] = nxt
    carrier["tx"], carrier["ty"] = step


def logistics_quantum(world: Any) -> None:
    n = world.economy_quanta
    if n % LOGISTICS_PERIOD == 0:
        scan_requests_and_outputs(world)
    if n % 5 == 0:
        carrier_quantum(world)
        for carrier in world.carriers.values():
            _step_carrier(world, carrier)

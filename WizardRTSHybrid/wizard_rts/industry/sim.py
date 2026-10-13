"""Mindustry-style industry inside the one HybridWorld: drills, belts, power graphs, crafters, unit factories (D06, D08, D16).

Rules come from the pinned Mindustry source through registry.py (drill formula Drill.getDrillTime, Conveyor itemSpace/capacity/speed,
GenericCrafter craftTime and consume lists, ConsumeGenerator, PowerNode laser links, UnitFactory plans). One simulation quantum is
the economy quantum (100 ms = 6 Mindustry ticks). Every ware is in exactly one place: the deposit reserve, a belt tile, a machine
buffer, a warehouse/carrier (Widelands side) or a logged sink (`consumed_*`). Nothing here has its own clock or army: a produced
unit is an ordinary `world.units` entry fighting under military.py.

Integer arithmetic is used wherever state is hashed (belt positions in 1/1000 tile, drill progress in ticks); power uses floats that
are rounded in the snapshot.
"""

from __future__ import annotations

from typing import Any

from wizard_rts.industry import engine as E
from wizard_rts.industry import hybrid as H
from wizard_rts.industry import extraction as X
from wizard_rts.industry import registry as R

QUANTUM_MS = 100
TICKS_PER_Q = 6  # Mindustry runs 60 ticks per second
DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))  # belt directions 0..3: east, south, west, north (screen coordinates, y grows down)
ITEM_SPACE = 400
BELT_CAP = 3
BUFFER = 10  # Block.itemCapacity default
BATTERY_SOC = 1.0
BASE_SPEED = 180  # basic conveyor: 0.03 * 60 tiles/s = 1.8 tiles/s = 180/1000 tile per 100 ms quantum


def belt_params(kind: str) -> dict[str, int]:
    """Speed (1/1000 tile per quantum), items per tile and spacing of a belt-like block (Conveyor.speed, StackConveyor itemCapacity, Duct)."""
    sp = R.block(kind)
    f = sp["fields"] if sp and "fields" in sp else {}
    if sp is None or sp["role"] == "belt" and sp.get("class") == "Conveyor" and kind == "mdy:conveyor":
        return {"spd": BASE_SPEED, "cap": BELT_CAP, "space": ITEM_SPACE}
    speed = float(f.get("speed", 0.03))
    if sp["role"] == "stack_belt":
        return {"spd": int(round(speed * 60 * 100)), "cap": int(f.get("itemCapacity", 10)), "space": 100}
    if sp["class"] in ("Duct", "ArmoredDuct"):
        return {"spd": int(round(0.08 * 60 * 100)), "cap": 2, "space": 500}
    return {"spd": int(round(speed * 60 * 100)), "cap": BELT_CAP, "space": ITEM_SPACE}
LINE_ROLES = ("belt", "stack_belt", "conduit", "payload_belt")
LEGACY_ROLES = ("drill", "crafter", "generator", "battery", "node", "unit_factory", "belt")


class Industry:
    """Runtime state kept on `world.industry`. Everything is plain data so saves and state hashes see it."""

    def __init__(self) -> None:
        self.belts: dict[tuple[int, int], dict[str, Any]] = {}
        self.pipes: dict[tuple[int, int], dict[str, Any]] = {}  # conduit tiles: {d, liq, amt, line, cap}
        self.pbelts: dict[tuple[int, int], dict[str, Any]] = {}  # payload conveyor tiles: {d, load, line}
        self.pipe_order: list[tuple[int, int]] = []
        self.store_tiles: dict[tuple[int, int], str] = {}  # tile of a Widelands warehouse / store -> its id: a belt may end in one (the bridge between the two economies)
        self.shipments: list[dict[str, Any]] = []
        self.heat_nets: list[list[str]] = []
        self.heat_of: dict[str, int] = {}
        self.tile_owner: dict[tuple[int, int], str] = {}  # machine footprint tile -> building id
        self.links: dict[str, list[str]] = {}  # power node id -> linked building ids
        self.order: list[tuple[int, int]] = []
        self.graphs: list[list[str]] = []
        self.graph_of: dict[str, int] = {}
        self.dirty = True
        self.fresh: list[str] = []  # machines that came online and still need their power links (nodes link to blocks in range)
        self.power: dict[int, dict[str, float]] = {}  # last solve per graph: produced, demand, satisfaction, stored
        self.version = 0


def init_world(world: Any) -> None:
    world.industry = Industry()


def ind(world: Any) -> Industry:
    i = getattr(world, "industry", None)
    if i is None:
        i = world.industry = Industry()
    return i


# ------------------------------------------------------------------ structure

def is_machine(b: dict) -> bool:
    return b.get("kind", "").startswith(R.PREFIX) and not is_line(b)


def is_line(b: dict) -> bool:
    """A run of belt, stack belt, conduit or payload conveyor tiles (one building record for the whole run)."""
    sp = R.block(b.get("kind", "")) if b.get("kind", "").startswith(R.PREFIX) else None
    return bool(sp) and sp["role"] in LINE_ROLES


def footprint(b: dict) -> list[tuple[int, int]]:
    spec = R.block(b["kind"])
    n = spec["size"] if spec else 1
    return [(b["tx"] + dx, b["ty"] + dy) for dy in range(n) for dx in range(n)]


def adjacent_tiles(tiles: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The 4-neighbour ring around a footprint, in a fixed order (so dumping is deterministic)."""
    s = set(tiles)
    out: list[tuple[int, int]] = []
    for (x, y) in tiles:
        for dx, dy in DIRS:
            t = (x + dx, y + dy)
            if t not in s and t not in out:
                out.append(t)
    return out


def rebuild(world: Any) -> None:
    """Recompute the indexes after any structural change (a machine finished or died, a belt line was added)."""
    st = ind(world)
    st.tile_owner = {}
    for b in world.buildings.values():
        if is_machine(b) and b.get("mdy") is not None and int(b.get("hp", 1)) > 0:
            for t in footprint(b):
                st.tile_owner[t] = b["id"]
    # belt processing order: tiles nearest their sink first, so a full chain advances in one quantum
    depth: dict[tuple[int, int], int] = {}
    for tile in sorted(st.belts):
        seen, cur, n = set(), tile, 0
        while cur in st.belts and cur not in seen:
            seen.add(cur)
            dx, dy = DIRS[st.belts[cur]["d"]]
            cur = (cur[0] + dx, cur[1] + dy)
            n += 1
        depth[tile] = n
    st.order = sorted(st.belts, key=lambda t: (depth[t], t))
    st.store_tiles = {(b["tx"], b["ty"]): b["id"] for b in world.buildings.values()
                      if (b["kind"] == "warehouse" or b.get("store")) and not b["kind"].startswith(R.PREFIX) and b.get("operational") and not b.get("constructing") and int(b.get("hp", 1)) > 0}
    pdepth: dict[tuple[int, int], int] = {}
    for tile in sorted(st.pipes):
        seen, cur, n = set(), tile, 0
        while cur in st.pipes and cur not in seen:
            seen.add(cur)
            dx, dy = DIRS[st.pipes[cur]["d"]]
            cur = (cur[0] + dx, cur[1] + dy)
            n += 1
        pdepth[tile] = n
    st.pipe_order = sorted(st.pipes, key=lambda t: (pdepth[t], t))
    # power graphs: adjacency (Block.connectedPower) plus laser links
    ids = sorted(b["id"] for b in world.buildings.values() if is_machine(b) and b.get("mdy") is not None and int(b.get("hp", 1)) > 0
                 and _powered_role(b))
    parent = {i: i for i in ids}

    def find(a: str) -> str:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    idset = set(ids)
    for bid in ids:
        b = world.buildings[bid]
        for t in adjacent_tiles(footprint(b)):
            other = st.tile_owner.get(t)
            if other in idset and other != bid:
                union(bid, other)
    for node, targets in list(st.links.items()):
        if node not in idset:
            st.links.pop(node, None)
            continue
        st.links[node] = [t for t in targets if t in idset]
        for t in st.links[node]:
            union(node, t)
    groups: dict[str, list[str]] = {}
    for bid in ids:
        groups.setdefault(find(bid), []).append(bid)
    st.graphs = [sorted(g) for _r, g in sorted(groups.items())]
    st.graph_of = {bid: gi for gi, g in enumerate(st.graphs) for bid in g}
    st.dirty = False
    st.version += 1


def _powered_role(b: dict) -> bool:
    spec = R.block(b["kind"])
    if not spec:
        return False
    return spec["role"] in ("crafter", "generator", "battery", "node", "unit_factory") or (
        spec["role"] in E.POWER_ROLES and (spec["power_use_per_s"] > 0 or spec["power_buffer"] > 0 or spec["power_production_per_s"] > 0))


# ------------------------------------------------------------------ machine init

def _init_machine(world: Any, b: dict) -> None:
    spec = R.block(b["kind"])
    role = spec["role"]
    m: dict[str, Any] = {"role": role, "buf": {}, "out": {}, "progress": 0, "state": "idle", "dump_i": 0, "liq": {}, "heat": 0.0, "count": 0}
    if role not in LEGACY_ROLES:
        E.init_role(world, b, m, spec)
    elif role == "drill":
        m.update(target=b.pop("mdy_target", None), item="", reserve_left=-1, rate_milli=0)
    elif role == "generator":
        m.update(burn=0)
    elif role == "battery":
        m.update(stored=0.0)
    elif role == "unit_factory":
        m.update(plan=b.pop("mdy_plan", None) or (spec["plans"][0]["unit"] if spec["plans"] else ""))
    b["mdy"] = m
    b.pop("working", None)
    ind(world).dirty = True
    ind(world).fresh.append(b["id"])
    world.events.append({"kind": "industry_online", "id": b["id"], "building_kind": b["kind"]})


def machine_accepts(world: Any, b: dict, ware: str) -> bool:
    m = b.get("mdy")
    if m is None or b.get("constructing") or int(b.get("hp", 1)) <= 0:
        return False
    spec = R.block(b["kind"])
    if spec.get("recipes"):
        spec = H.effective(spec, m)
    role = m["role"]
    if role == "crafter":
        need = spec["consume_items"].get(ware)
        return need is not None and m["buf"].get(ware, 0) < max(BUFFER, 2 * need)
    if role == "generator" and spec["solar"]:
        return False
    if role == "generator" and E.special_generator(spec):
        return E.fuel_accepts(world, b, spec, m, ware)
    if role == "generator":
        item = R.item_of(ware)
        return item is not None and R.item_info(item)["flammability"] >= spec["fuel_min_flammability"] and m["buf"].get(ware, 0) < BUFFER
    if role == "unit_factory":
        need = _plan(spec, m)["requirements"].get(ware)
        return need is not None and m["buf"].get(ware, 0) < 2 * need
    return False


def _plan(spec: dict, m: dict) -> dict:
    for p in spec["plans"]:
        if p["unit"] == m["plan"]:
            return p
    return spec["plans"][0]


# ------------------------------------------------------------------ belts

def belt_accepts(st: Industry, tile: tuple[int, int], from_tile: tuple[int, int]) -> bool:
    b = st.belts.get(tile)
    if b is None:
        return False
    dx, dy = DIRS[b["d"]]
    if (tile[0] + dx, tile[1] + dy) == from_tile:
        return False  # the source is where this belt delivers to
    if b.get("armored") and from_tile not in st.belts and (tile[0] - dx, tile[1] - dy) != from_tile:
        return False  # ArmoredConveyor.acceptItem: from a non-conveyor only straight from behind, never from the side
    items = b["items"]
    return len(items) < b.get("cap", BELT_CAP) and (not items or items[-1][1] >= b.get("space", ITEM_SPACE))


def belt_put(st: Industry, tile: tuple[int, int], ware: str) -> None:
    st.belts[tile]["items"].append([ware, 0])


def _belt_step(world: Any, st: Industry) -> None:
    for tile in st.order:
        belt = st.belts[tile]
        items = belt["items"]
        speed = belt.get("spd", BASE_SPEED)
        if not items:
            continue
        dx, dy = DIRS[belt["d"]]
        nxt = (tile[0] + dx, tile[1] + dy)
        # the front item may leave the tile; the part of its move beyond the tile edge is carried into the next tile
        raw = items[0][1] + speed
        belt["blocked"] = False
        if raw >= 1000:
            ware = items[0][0]
            moved = False
            if nxt in st.belts:
                if belt_accepts(st, nxt, tile):
                    ahead = st.belts[nxt]["items"]
                    pos = raw - 1000 if not ahead else min(raw - 1000, ahead[-1][1] - st.belts[nxt].get("space", ITEM_SPACE))
                    belt_put(st, nxt, ware)
                    ahead[-1][1] = pos
                    moved = True
            else:
                owner = st.tile_owner.get(nxt)
                if owner is not None and E.accepts(world, st, world.buildings[owner], ware, tile) and E.hand_over(world, st, world.buildings[owner], ware, tile):
                    moved = True
                elif owner is None and nxt in st.store_tiles and E.deliver_to_warehouse(world, st.store_tiles[nxt], ware):
                    moved = True
            if moved:
                items.pop(0)
                start = 0
            else:
                items[0][1] = 1000
                belt["blocked"] = True
                start = 1
        else:
            items[0][1] = raw
            start = 1
        for i in range(start, len(items)):
            limit = 1000 if i == 0 else items[i - 1][1] - belt.get("space", ITEM_SPACE)
            items[i][1] = max(items[i][1], min(items[i][1] + speed, limit))


def dump(world: Any, st: Industry, b: dict, ware: str) -> bool:
    """Offer one item to the neighbours of a machine in rotating order (Building.dump)."""
    m = b["mdy"]
    ring = adjacent_tiles(footprint(b))
    n = len(ring)
    for k in range(n):
        tile = ring[(m["dump_i"] + k) % n]
        if tile in st.belts:
            src = _belt_source_tile(b, tile)
            if belt_accepts(st, tile, src):
                belt_put(st, tile, ware)
                m["dump_i"] = (m["dump_i"] + k + 1) % n
                return True
        elif tile in st.store_tiles and E.deliver_to_warehouse(world, st.store_tiles[tile], ware):
            m["dump_i"] = (m["dump_i"] + k + 1) % n
            return True
        else:
            owner = st.tile_owner.get(tile)
            if owner and owner != b["id"]:
                ob = world.buildings[owner]
                src = _belt_source_tile(b, tile)
                if E.accepts(world, st, ob, ware, src) and E.hand_over(world, st, ob, ware, src):
                    m["dump_i"] = (m["dump_i"] + k + 1) % n
                    return True
    return False


def _belt_source_tile(b: dict, belt_tile: tuple[int, int]) -> tuple[int, int]:
    """The footprint tile of `b` that touches this belt tile (used so a belt facing into the machine is refused)."""
    for t in footprint(b):
        if abs(t[0] - belt_tile[0]) + abs(t[1] - belt_tile[1]) == 1:
            return t
    return (b["tx"], b["ty"])


# ------------------------------------------------------------------ the quantum

def industry_quantum(world: Any) -> None:
    st = ind(world)
    if not st.belts and not any(b["kind"].startswith(R.PREFIX) for b in world.buildings.values()):
        return
    changed = False
    for b in list(world.buildings.values()):
        kind = b["kind"]
        if not kind.startswith(R.PREFIX):
            continue
        if R.block(kind) is not None and R.block(kind)["role"] in LINE_ROLES:
            if b.get("operational") and not b.get("constructing") and b.get("line") and not b.get("line_live"):
                _activate_line(world, st, b)
                changed = True
            elif b.get("line_live") and int(b.get("hp", 1)) <= 0:
                _destroy_line(world, st, b)
                changed = True
            continue
        if b.get("mdy") is None and b.get("operational") and not b.get("constructing") and int(b.get("hp", 1)) > 0:
            _init_machine(world, b)
            changed = True
        elif b.get("mdy") is not None and int(b.get("hp", 1)) <= 0:
            _destroy_machine(world, b)
            changed = True
    lines = {bl["line"] for bl in st.belts.values()} | {bl["line"] for bl in st.pipes.values()} | {bl["line"] for bl in st.pbelts.values()}
    for lid in sorted(lines):
        if lid not in world.buildings:  # the building was purged: its belts go with it
            for tile in [t for t, bl in st.belts.items() if bl["line"] == lid]:
                for ware, _p in st.belts.pop(tile)["items"]:
                    world.stats["consumed_" + ware] = world.stats.get("consumed_" + ware, 0) + 1
            for tile in [t for t, bl in st.pipes.items() if bl["line"] == lid]:
                p_ = st.pipes.pop(tile)
                if p_["liq"] and p_["amt"] > 0:
                    world.stats["liq_lost_" + p_["liq"]] = world.stats.get("liq_lost_" + p_["liq"], 0.0) + p_["amt"]
            for tile in [t for t, bl in st.pbelts.items() if bl["line"] == lid]:
                pb_ = st.pbelts.pop(tile)
                if pb_["load"]:
                    _lose_payload(world, pb_["load"])
            changed = True
    if changed or st.dirty or st.fresh:
        rebuild(world)
    if st.fresh:
        from wizard_rts.industry import commands

        fresh = [world.buildings[i] for i in st.fresh if i in world.buildings and world.buildings[i].get("mdy") is not None]
        st.fresh = []
        for b in fresh:
            if R.block(b["kind"])["role"] == "node":
                commands.auto_link(world, b)
            elif _powered_role(b):
                commands.attach_to_nodes(world, b)
        rebuild(world)
    machines = [b for b in world.buildings.values() if is_machine(b) and b.get("mdy") is not None]
    _power_and_machines(world, st, machines)
    _belt_step(world, st)


def _activate_line(world: Any, st: Industry, b: dict) -> None:
    role = R.block(b["kind"])["role"]
    for (x, y), d in zip(b["line"]["tiles"], b["line"]["dirs"]):
        key = (int(x), int(y))
        if role == "conduit":
            sp = R.block(b["kind"])
            st.pipes[key] = {"d": int(d), "liq": None, "amt": 0.0, "cap": float(sp["liquid_capacity"]), "line": b["id"], "armored": sp["class"] == "ArmoredConduit"}
        elif role == "payload_belt":
            st.pbelts[key] = {"d": int(d), "load": None, "prog": 0, "line": b["id"], "faction": b["faction"], "faction_name": b["faction_name"]}
        else:
            st.belts[key] = {"d": int(d), "items": [], "line": b["id"], "blocked": False, "armored": R.block(b["kind"])["class"] in ("ArmoredConveyor", "ArmoredDuct"), **belt_params(b["kind"])}
    b["line_live"] = True
    for t in b["line"]["tiles"]:
        world.reserved_tiles.discard((int(t[0]), int(t[1])))
    world.events.append({"kind": "belt_online", "id": b["id"], "tiles": len(b["line"]["tiles"])})


def _destroy_line(world: Any, st: Industry, b: dict) -> None:
    for (x, y) in b["line"]["tiles"]:
        key = (int(x), int(y))
        belt = st.belts.pop(key, None)
        for ware, _p in (belt["items"] if belt else []):
            world.stats["consumed_" + ware] = world.stats.get("consumed_" + ware, 0) + 1  # destroyed with the belt: a logged sink
        pipe = st.pipes.pop(key, None)
        if pipe and pipe["liq"] and pipe["amt"] > 0:
            world.stats["liq_lost_" + pipe["liq"]] = world.stats.get("liq_lost_" + pipe["liq"], 0.0) + pipe["amt"]
        pb = st.pbelts.pop(key, None)
        if pb and pb["load"]:
            _lose_payload(world, pb["load"])
    b["line_live"] = False


def _lose_payload(world: Any, pl: dict) -> None:
    if pl.get("type") == "block":
        for w, n in pl.get("stock", {}).items():
            world.stats["consumed_" + w] = world.stats.get("consumed_" + w, 0) + n


def _destroy_machine(world: Any, b: dict) -> None:
    m = b["mdy"]
    for bag in (m["buf"], m["out"]):
        for ware, n in bag.items():
            world.stats["consumed_" + ware] = world.stats.get("consumed_" + ware, 0) + n  # lost with the machine: a logged sink
    for ware, n in E.holdings(world, b).items():
        world.stats["consumed_" + ware] = world.stats.get("consumed_" + ware, 0) + n
    for liquid, qty in m.get("liq", {}).items():
        world.stats["liq_lost_" + liquid] = world.stats.get("liq_lost_" + liquid, 0.0) + qty
    if m.get("payload"):
        _lose_payload(world, m["payload"])
    b["mdy"] = None
    b["operational"] = False
    ind(world).links.pop(b["id"], None)
    for others in ind(world).links.values():
        if b["id"] in others:
            others.remove(b["id"])


def _power_and_machines(world: Any, st: Industry, machines: list[dict]) -> None:
    # 1. which consumers want power this quantum, and how much a generator makes
    demand: dict[int, float] = {}
    supply: dict[int, float] = {}
    batt_room: dict[int, float] = {}
    wants: dict[str, bool] = {}
    for b in machines:
        m = b["mdy"]
        spec = R.block(b["kind"])
        if spec.get("recipes"):
            spec = H.effective(spec, m)
        role = m["role"]
        g = st.graph_of.get(b["id"], -1)
        if role == "crafter":
            wants[b["id"]] = _crafter_ready(spec, m)
            if wants[b["id"]]:
                demand[g] = demand.get(g, 0.0) + spec["power_use_per_s"] * QUANTUM_MS / 1000
        elif role == "unit_factory":
            plan = _plan(spec, m)
            wants[b["id"]] = all(m["buf"].get(w, 0) >= n for w, n in plan["requirements"].items()) or m["progress"] > 0
            if wants[b["id"]]:
                demand[g] = demand.get(g, 0.0) + spec["power_use_per_s"] * QUANTUM_MS / 1000
        elif role == "generator" and E.special_generator(spec):
            supply[g] = supply.get(g, 0.0) + E.generator_step(world, st, b, spec, m, QUANTUM_MS)
        elif role == "generator" and spec["solar"]:
            supply[g] = supply.get(g, 0.0) + spec["power_production_per_s"] * QUANTUM_MS / 1000
            m["state"] = "producing"
        elif role == "generator":
            if m["burn"] <= 0:
                fuel = next((w for w in sorted(m["buf"]) if m["buf"][w] > 0 and machine_accepts_fuel(spec, w)), None)
                if fuel is not None:
                    m["buf"][fuel] -= 1
                    world.stats["consumed_" + fuel] = world.stats.get("consumed_" + fuel, 0) + 1
                    m["burn"] = int(spec["item_duration_ticks"])
            if m["burn"] > 0:
                supply[g] = supply.get(g, 0.0) + spec["power_production_per_s"] * QUANTUM_MS / 1000
                m["burn"] = max(0, m["burn"] - TICKS_PER_Q)
                m["state"] = "burning"
            else:
                m["state"] = "no fuel"
        elif role == "battery":
            batt_room[g] = batt_room.get(g, 0.0) + (spec["power_buffer"] - m["stored"])
        else:
            wants[b["id"]] = E.wants_power(world, b, spec, m)
            if wants[b["id"]]:
                demand[g] = demand.get(g, 0.0) + spec["power_use_per_s"] * QUANTUM_MS / 1000
    # 2. satisfaction per graph; batteries buffer the difference
    sat: dict[int, float] = {}
    for gi in set(list(demand) + list(supply) + list(batt_room)):
        d, s = demand.get(gi, 0.0), supply.get(gi, 0.0)
        batteries = [world.buildings[i] for i in st.graphs[gi] if gi >= 0 and world.buildings[i]["mdy"]["role"] == "battery"] if gi >= 0 else []
        stored = sum(x["mdy"]["stored"] for x in batteries)
        if d <= 0:
            sat[gi] = 1.0
            surplus = s
            for x in batteries:  # charge in id order
                room = R.block(x["kind"])["power_buffer"] - x["mdy"]["stored"]
                add = min(room, surplus)
                x["mdy"]["stored"] += add
                surplus -= add
        else:
            have = s + stored
            sat[gi] = 1.0 if have >= d else (have / d)
            take = max(0.0, d - s)  # what the batteries must give
            surplus = max(0.0, s - d)
            for x in batteries:
                if take > 0:
                    got = min(x["mdy"]["stored"], take)
                    x["mdy"]["stored"] -= got
                    take -= got
                elif surplus > 0:
                    room = R.block(x["kind"])["power_buffer"] - x["mdy"]["stored"]
                    add = min(room, surplus)
                    x["mdy"]["stored"] += add
                    surplus -= add
        st.power[gi] = {"supply": round(s * 10, 3), "demand": round(d * 10, 3), "satisfaction": round(sat[gi], 4),
                        "stored": round(sum(x["mdy"]["stored"] for x in batteries), 3)}
    # 3. machines work
    for b in machines:
        m = b["mdy"]
        spec = R.block(b["kind"])
        if spec.get("recipes"):
            spec = H.effective(spec, m)
        role = m["role"]
        if b.get("disrupted"):  # closed by a collapse or an outbreak (disruption.py): no work until repaired
            m["state"] = "closed: " + b["disrupted"]["label"].lower()
            continue
        if role == "drill":
            _drill_step(world, st, b, spec, m, sat.get(st.graph_of.get(b["id"], -1), 0.0), wants.get(b["id"], True))
        elif role == "crafter":
            _crafter_step(world, st, b, spec, m, sat.get(st.graph_of.get(b["id"], -1), 0.0), wants[b["id"]])
        elif role == "unit_factory":
            _factory_step(world, st, b, spec, m, sat.get(st.graph_of.get(b["id"], -1), 0.0), wants[b["id"]])
        b["working"] = m["state"] in ("working", "drilling", "burning", "building", "producing", "pumping", "sending", "shooting", "mending")
    sat_by_machine = {b["id"]: sat.get(st.graph_of.get(b["id"], -1), 0.0 if E.needs_power(R.block(b["kind"])) else 1.0) for b in machines}
    E.step_roles(world, st, machines, sat_by_machine, wants, sat)


def machine_accepts_fuel(spec: dict, ware: str) -> bool:
    if E.special_generator(spec):
        return E.fuel_ok(spec, ware)
    item = R.item_of(ware)
    return item is not None and R.item_info(item)["flammability"] >= spec["fuel_min_flammability"]


# ---- drills

def drill_options(world: Any, b: dict) -> dict[str, dict[str, Any]]:
    spec = R.block(b["kind"])
    return X.options(world, footprint(b), int(spec["tier"]))


def _drill_step(world: Any, st: Industry, b: dict, spec: dict, m: dict, satisfaction: float = 1.0, wants: bool = True) -> None:
    from wizard_rts import regions
    from wizard_rts.industry import fluids as F

    powered = spec.get("power_use_per_s", 0) > 0
    if powered and satisfaction <= 0:
        m["state"] = "no power"
        _flush(world, st, b, m)
        return
    pwr = satisfaction if powered else 1.0

    opts = drill_options(world, b)
    item = X.choose_item(opts, m.get("target"))
    if item is None:
        m["state"] = "no deposit"
        m["item"] = ""
        _flush(world, st, b, m)
        return
    o = opts[item]
    m["item"] = item
    m["reserve_left"] = X.reserve_left(world, o)
    ware = R.ware(item)
    if o["source"] == "deposit" and 0 <= m["reserve_left"] < int(o["units_per_item"]):
        m["state"] = "deposit used up"
        b["deposit_exhausted"] = True
        _flush(world, st, b, m)
        return
    delay = spec["drill_ticks"] + spec["hardness_multiplier"] * o["hardness"]  # Drill.getDrillTime
    m["rate_milli"] = int(round(60000 * len(o["tiles"]) / delay))  # items per minute x 1000/60... = items/s x 1000
    if sum(m["out"].values()) >= BUFFER:
        m["state"] = "output blocked"
    else:
        m["state"] = "drilling"
        boost = 1.0
        for liquid, per in spec.get("boost_liquids", {}).items():  # Drill: optional coolant/water raises the speed by liquidBoostIntensity squared
            if m["liq"].get(liquid, 0.0) >= per * TICKS_PER_Q:
                F.consume(world, b, liquid, per * TICKS_PER_Q)
                boost = max(boost, float(spec["fields"].get("liquidBoostIntensity", 1.6)) ** 2)
        m["boost"] = boost
        m["progress"] += TICKS_PER_Q * len(o["tiles"]) * pwr * boost * m.get("od", 1.0) * regions.production_factor(world, b)  # an outbreak in the region slows the drill
        if m["progress"] >= delay:
            if X.take_reserve(world, o):
                b["working_once"] = True
                m["progress"] -= int(delay)
                m["out"][ware] = m["out"].get(ware, 0) + 1
                world.stats["made_" + ware] = world.stats.get("made_" + ware, 0) + 1
                world.stats["drilled_" + ware] = world.stats.get("drilled_" + ware, 0) + 1
            else:
                m["state"] = "deposit used up"
                b["deposit_exhausted"] = True
    _flush(world, st, b, m)


def _flush(world: Any, st: Industry, b: dict, m: dict) -> None:
    """Dump at most one buffered output item per quantum (Mindustry dumpTime ~5 ticks)."""
    for ware in sorted(m["out"]):
        if m["out"][ware] > 0:
            if dump(world, st, b, ware):
                m["out"][ware] -= 1
            elif m["state"] == "drilling" and sum(m["out"].values()) >= BUFFER:
                m["state"] = "output blocked"
            break


# ---- crafters

def _crafter_ready(spec: dict, m: dict) -> bool:
    out_total = sum(m["out"].values())
    if not (all(m["buf"].get(w, 0) >= n for w, n in spec["consume_items"].items()) and out_total < BUFFER):
        return False
    for liquid, per_tick in spec.get("consume_liquids", {}).items():
        if m["liq"].get(liquid, 0.0) < per_tick * TICKS_PER_Q * 0.999:
            return False
    for liquid, per_tick in spec.get("output_liquid", {}).items():
        if m["liq"].get(liquid, 0.0) + per_tick * TICKS_PER_Q > spec.get("liquid_capacity", 10.0) + 1e-9:
            return False  # the tank is full: Mindustry stops a crafter whose liquid output cannot be emitted
    return True


def _efficiency(world: Any, b: dict, spec: dict, m: dict) -> float:
    """Attribute crafters (cultivator, vent condenser, silicon crucible): base + boost from the ground under them; heat crafters: delivered heat."""
    eff = 1.0
    f = spec.get("fields", {})
    if spec.get("attribute"):
        base = float(f.get("baseEfficiency", 1.0))
        attr = E.attribute_sum(world, b, spec["attribute"])
        eff = base + min(float(f.get("maxBoost", 1.0)), float(f.get("boostScale", 1.0)) * attr)
        if attr < float(f.get("minEfficiency", -1.0)) or eff <= 0:  # AttributeCrafter: the site must hold at least minEfficiency of the attribute
            return 0.0
    if spec.get("heat_in", 0) > 0:
        eff *= min(1.0, m.get("heat", 0.0) / spec["heat_in"])
    return eff


def _crafter_step(world: Any, st: Industry, b: dict, spec: dict, m: dict, satisfaction: float, wants: bool) -> None:
    from wizard_rts.industry import fluids as F

    eff = _efficiency(world, b, spec, m) if wants else 0.0
    if wants and eff <= 0:
        m["state"] = "needs heat" if spec.get("heat_in", 0) > 0 and m.get("heat", 0.0) <= 0 else "unsuited ground"
        _flush(world, st, b, m)
        return
    if wants:
        if spec["power_use_per_s"] > 0 and satisfaction <= 0:
            m["state"] = "no power"
        else:
            from wizard_rts import regions

            m["state"] = "working"
            m["progress"] += TICKS_PER_Q * satisfaction * eff * m.get("od", 1.0) * regions.production_factor(world, b)
            for liquid, per_tick in spec.get("consume_liquids", {}).items():
                F.consume(world, b, liquid, per_tick * TICKS_PER_Q * satisfaction * eff)
            for liquid, per_tick in spec.get("output_liquid", {}).items():
                F.produce(world, b, liquid, per_tick * TICKS_PER_Q * satisfaction * eff)
            if spec["craft_ticks"] <= 0 and spec.get("output_liquid"):
                m["progress"] = 0  # a continuous converter (pump-like): no item cycle
            elif m["progress"] >= spec["craft_ticks"]:
                m["progress"] -= spec["craft_ticks"]
                m["count"] = m.get("count", 0) + 1
                for w, n in spec["consume_items"].items():
                    m["buf"][w] -= n
                    world.stats["consumed_" + w] = world.stats.get("consumed_" + w, 0) + n
                outs = dict(spec["output_item"])
                if spec.get("results"):  # Separator.craft: one weighted draw per cycle
                    outs = {E.separator_pick(world, b, m, spec): 1}
                for w, n in outs.items():
                    m["out"][w] = m["out"].get(w, 0) + n
                    world.stats["made_" + w] = world.stats.get("made_" + w, 0) + n
    else:
        m["state"] = "output blocked" if sum(m["out"].values()) >= BUFFER else "waiting for inputs"
    _flush(world, st, b, m)


# ---- unit factory

def _factory_step(world: Any, st: Industry, b: dict, spec: dict, m: dict, satisfaction: float, wants: bool) -> None:
    from wizard_rts import tech

    plan = _plan(spec, m)
    if not tech.unit_allowed(world, b["faction_name"], plan["unit"]):
        m["state"] = "locked by card"
        return
    if not wants:
        m["state"] = "waiting for inputs"
        return
    if satisfaction <= 0:
        m["state"] = "no power"
        return
    from wizard_rts import regions

    m["state"] = "building"
    m["progress"] += TICKS_PER_Q * satisfaction * m.get("od", 1.0) * regions.production_factor(world, b)
    if m["progress"] >= plan["ticks"]:
        from wizard_rts.industry import payload as PL

        if not PL.emit_unit_from_factory(world, st, b, plan["unit"]):
            m["state"] = "exit blocked"
            m["progress"] = plan["ticks"]
            return
        m["progress"] = 0
        for w, n in plan["requirements"].items():
            m["buf"][w] -= n
            world.stats["consumed_" + w] = world.stats.get("consumed_" + w, 0) + n


def _exit_tile(world: Any, b: dict) -> tuple[int, int] | None:
    occupied = {(u["tx"], u["ty"]) for u in world.units.values() if u.get("alive", True)}
    for t in adjacent_tiles(footprint(b)):
        if world.tile_in_map(*t) and t not in world.blocked and t not in occupied and t not in ind(world).belts and t not in world.tree_tiles:
            if world.terrain is None or world.terrain.ground(*t):
                return t
    return None


def _spawn(world: Any, b: dict, unit: str, tile: tuple[int, int]) -> str:
    info = R.ground_unit(unit)
    uid = world._unit(b["faction"], b["faction_name"], "mdy_" + unit, info["label"], info["definition"], tile)
    world.fstat(b["faction_name"], "units_built")
    world.fstat(b["faction_name"], "mindustry_units_built")
    world.events.append({"kind": "unit_produced", "building": b["id"], "unit": uid, "unit_kind": "mdy_" + unit, "faction": b["faction_name"]})
    return uid


# ------------------------------------------------------------------ holdings and snapshot

def holdings(world: Any) -> dict[str, int]:
    """Wares currently held by belts and machine buffers (the ledger counts them as held)."""
    out: dict[str, int] = {}
    st = getattr(world, "industry", None)
    if st is None:
        return out
    for belt in st.belts.values():
        for ware, _p in belt["items"]:
            out[ware] = out.get(ware, 0) + 1
    for b in world.buildings.values():
        m = b.get("mdy")
        if m:
            for bag in (m["buf"], m["out"]):
                for ware, n in bag.items():
                    out[ware] = out.get(ware, 0) + n
            for ware, n in E.holdings(world, b).items():
                out[ware] = out.get(ware, 0) + n
    for sh in getattr(st, "shipments", []):
        for ware, n in sh["items"].items():
            out[ware] = out.get(ware, 0) + n
    return out


def status_text(world: Any, b: dict) -> str | None:
    m = b.get("mdy")
    if is_line(b):
        return None
    if m is None:
        return None
    spec = R.block(b["kind"])
    st = ind(world)
    role = m["role"]
    if role == "drill":
        if m["item"]:
            left = "" if m["reserve_left"] < 0 else f", {m['reserve_left']} reserve units left"
            return f"{m['state'].capitalize()}: {m['item']} at {m['rate_milli'] / 1000:.2f}/s{left}"
        return m["state"].capitalize()
    if role in ("crafter", "unit_factory"):
        g = st.power.get(st.graph_of.get(b["id"], -1))
        pw = f" (power {int(g['satisfaction'] * 100)}%)" if g and spec["power_use_per_s"] else ""
        return f"{m['state'].capitalize()}{pw}"
    if role == "generator":
        return m["state"].capitalize() if spec["solar"] else f"{m['state'].capitalize()}, {sum(m['buf'].values())} fuel"
    if role == "battery":
        return f"Stored {m['stored']:.0f} / {spec['power_buffer']:.0f}"
    if role == "node":
        return f"Linked to {len(st.links.get(b['id'], []))}"
    return None


def snapshot(world: Any) -> dict[str, Any]:
    st = getattr(world, "industry", None)
    if st is None or (not st.belts and not st.tile_owner):
        return {}
    return {
        "belts": [[x, y, bl["d"], [[w, p] for w, p in bl["items"]], 1 if bl.get("blocked") else 0] for (x, y), bl in sorted(st.belts.items())],
        "links": {n: list(t) for n, t in sorted(st.links.items())},
        "graphs": [dict(g=gi, **v) for gi, v in sorted(st.power.items()) if gi >= 0],
    }


def row(world: Any, b: dict) -> dict[str, Any]:
    """Compact machine state for the snapshot (what a renderer needs; no rules)."""
    m = b["mdy"]
    spec = R.block(b["kind"])
    out: dict[str, Any] = {"role": m["role"], "state": m["state"]}
    if m.get("liq") and spec.get("liquid_capacity"):
        out["fill"] = round(sum(m["liq"].values()) / max(1.0, float(spec["liquid_capacity"])), 2)
    if m["role"] == "turret" and "aim" in b:
        out["aim"] = b["aim"]
    if m["role"] == "drill":
        out.update(item=m["item"], rate=m["rate_milli"], left=m["reserve_left"])
    elif m["role"] == "crafter":
        out["pct"] = int(100 * min(1.0, m["progress"] / max(1, spec["craft_ticks"])))
        out["buf"] = dict(m["buf"])
    elif m["role"] == "unit_factory":
        plan = _plan(spec, m)
        out["pct"] = int(100 * min(1.0, m["progress"] / max(1, plan["ticks"])))
        out["plan"] = m["plan"]
        out["buf"] = dict(m["buf"])
    elif m["role"] == "battery":
        out["pct"] = int(100 * m["stored"] / max(1.0, spec["power_buffer"]))
    st = ind(world)
    g = st.power.get(st.graph_of.get(b["id"], -1))
    if g and spec["role"] in ("crafter", "unit_factory", "generator", "battery", "node"):
        out["power"] = g["satisfaction"]
    return out

"""Generic Mindustry block engine: item routing, storage, liquids, heat, extraction variants, walls, turrets, payloads (owner programme 13 Oct 2026).

`sim.py` keeps the original slice (belts, drills, crafters, generators, batteries, nodes, ground factory). This module adds every other
role in `blocks.py`, as small per-role behaviours on the same machine record `b["mdy"]`:

    m = {role, buf{ware:n}, out{ware:n}, progress, state, dump_i, ...role fields}

Transfers between blocks go through `give(world, st, tile, ware, from_tile)`: the one place that knows whether a tile is a belt, a router, a
machine, a store or a turret and whether it accepts the ware. Every ware is in exactly one place (a belt tile, a machine buffer, a store
stock) or a logged sink (`consumed_*`), so the ware ledger keeps balancing.
"""

from __future__ import annotations

from typing import Any

from wizard_rts.industry import blocks as B
from wizard_rts.industry import registry as R

DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))
TICKS_PER_Q = 6
QUANTUM_MS = 100
ROUTER_TICKS = 8
JUNCTION_CAP = 6
BRIDGE_CAP = 14
UNLOADER_PER_Q = 1
IMPLEMENTED = {"router", "sorter", "overflow", "junction", "bridge", "unloader", "store", "core", "pump", "conduit", "tank", "liquid_junction", "liquid_bridge",
               "heater", "heat_conductor", "wall_drill", "harvester", "crafter", "drill", "generator", "battery", "node", "belt", "stack_belt", "unit_factory", "reconstructor", "assembler", "turret", "wall", "door", "mine", "mender", "overdrive", "shield", "repair", "radar", "incinerator", "build_turret", "mass_driver", "launch_pad", "cargo", "payload_belt", "constructor", "deconstructor", "payload_driver", "payload_loader", "accelerator", "logic", "assembler_module", "diode"}
R.IMPLEMENTED_ROLES.update(IMPLEMENTED)
POWER_ROLES = {"harvester", "drill", "pump", "wall_drill", "heater", "mender", "overdrive", "shield", "turret", "reconstructor", "assembler", "assembler_module", "constructor",
               "deconstructor", "payload_driver", "payload_loader", "cargo", "launch_pad", "accelerator", "mass_driver", "build_turret", "repair", "logic",
               "incinerator", "radar", "diode", "belt", "stack_belt", "bridge", "router", "wall", "junction"}
LOGISTIC_ROLES = ("router", "sorter", "overflow", "junction", "bridge", "unloader")
STORE_ROLES = ("store", "core")


def spec(kind: str) -> dict[str, Any] | None:
    return R.block(kind)


def sp(b: dict) -> dict[str, Any]:
    return R.block(b["kind"])


# ------------------------------------------------------------------ item transfer

def tile_building(world: Any, st: Any, tile: tuple[int, int]) -> dict | None:
    owner = st.tile_owner.get(tile)
    return world.buildings.get(owner) if owner else None


def _is_store(b: dict) -> bool:
    m = b.get("mdy")
    return bool(m) and m["role"] in STORE_ROLES


def cap_of(b: dict, ware: str) -> int:
    return int(sp(b)["item_capacity"])


def store_room(world: Any, b: dict, ware: str) -> int:
    m = b["mdy"]
    if m["role"] == "core":
        return 10**9  # a core incinerates what it cannot hold (Mindustry CoreBlock.incinerate)
    return cap_of(b, ware) - int(world.stocks.setdefault(b["id"], {}).get(ware, 0))


def accepts(world: Any, st: Any, b: dict, ware: str, from_tile: tuple[int, int]) -> bool:
    """Would machine `b` take one `ware` arriving from `from_tile`? (no side effects)"""
    from wizard_rts.industry import sim as S

    m = b.get("mdy")
    if m is None or b.get("constructing") or int(b.get("hp", 1)) <= 0 or b.get("disrupted"):
        return False
    role = m["role"]
    if role in ("crafter", "generator", "unit_factory", "drill", "node", "battery"):
        return S.machine_accepts(world, b, ware) if role in ("crafter", "generator", "unit_factory") else False
    if role in STORE_ROLES:
        return store_room(world, b, ware) > 0
    if role == "router":
        return len(m["hold"]) < 1
    if role in ("sorter", "overflow"):
        return _route_target(world, st, b, ware, from_tile, probe=True) is not None
    if role == "junction":
        d = _dir_index(b, from_tile)
        return d is not None and len(m["lanes"][d]) < JUNCTION_CAP
    if role == "bridge":
        return _bridge_accepts(world, st, b, ware, from_tile)
    if role == "mass_driver":
        return m.get("item_total", 0) < int(sp(b)["item_capacity"]) and (m.get("item_ware") in (None, ware))
    if role == "turret":
        return turret_accepts(world, b, ware)
    if role in ("reconstructor", "assembler", "constructor", "launch_pad", "cargo"):
        return payload_accepts(world, b, ware)
    if role in ("heater", "pump"):
        need = sp(b)["consume_items"].get(ware)
        return need is not None and m["buf"].get(ware, 0) < max(10, 2 * need)
    if role == "mender" or role == "overdrive" or role == "shield" or role == "repair":
        return support_accepts(world, b, ware)
    if role == "incinerator":
        return not b.get("unpowered") and True
    return False


def hand_over(world: Any, st: Any, b: dict, ware: str, from_tile: tuple[int, int]) -> bool:
    """Give one ware to machine `b` (the caller has checked `accepts`). Returns True when it has been taken."""
    m = b["mdy"]
    role = m["role"]
    if role in STORE_ROLES:
        if store_room(world, b, ware) <= 0:
            return False
        if m["role"] == "core" and int(world.stocks.setdefault(b["id"], {}).get(ware, 0)) >= cap_of(b, ware):
            world.stats["consumed_" + ware] = world.stats.get("consumed_" + ware, 0) + 1  # incinerated
            world.stats["incinerated_" + ware] = world.stats.get("incinerated_" + ware, 0) + 1
            return True
        world.stocks[b["id"]][ware] = int(world.stocks[b["id"]].get(ware, 0)) + 1
        world.economy_totals.add(ware, 1) if hasattr(world.economy_totals, "add") else None
        return True
    if role == "router":
        m["hold"].append([ware, 0, from_tile])
        return True
    if role in ("sorter", "overflow"):
        tgt = _route_target(world, st, b, ware, from_tile, probe=False)
        return tgt is not None
    if role == "junction":
        d = _dir_index(b, from_tile)
        m["lanes"][d].append([ware, 0])
        return True
    if role == "bridge":
        m["buf_items"].append([ware, 0])
        m["src_tile"] = m.get("src_tile") or from_tile
        return True
    if role == "mass_driver":
        m["item_ware"] = ware
        m["item_total"] = m.get("item_total", 0) + 1
        return True
    if role == "turret":
        return turret_take(world, b, ware)
    if role in ("reconstructor", "assembler", "constructor", "launch_pad", "cargo"):
        return payload_take(world, b, ware)
    if role in ("mender", "overdrive", "shield", "repair"):
        return support_take(world, b, ware)
    if role == "incinerator":
        world.stats["consumed_" + ware] = world.stats.get("consumed_" + ware, 0) + 1
        world.stats["incinerated_" + ware] = world.stats.get("incinerated_" + ware, 0) + 1
        return True
    # original slice roles: straight into the buffer
    m["buf"][ware] = m["buf"].get(ware, 0) + 1
    return True


def deliver_to_warehouse(world: Any, wh_id: str, ware: str) -> bool:
    """A belt (or a machine) puts one ware into a Widelands warehouse or store: it joins the settlement's stock and the carriers can fetch it."""
    from wizard_rts.economy import _supply

    _supply(world, wh_id).add_wares(ware, 1)
    return True


def give(world: Any, st: Any, tile: tuple[int, int], ware: str, from_tile: tuple[int, int], ignore: str = "") -> bool:
    """Put one ware onto whatever stands on `tile` (a belt or a machine) if it takes it."""
    from wizard_rts.industry import sim as S

    if tile in st.belts:
        if S.belt_accepts(st, tile, from_tile):
            S.belt_put(st, tile, ware)
            return True
        return False
    ob = tile_building(world, st, tile)
    if ob is None and tile in st.store_tiles:
        return deliver_to_warehouse(world, st.store_tiles[tile], ware)
    if ob is None or ob["id"] == ignore:
        return False
    if accepts(world, st, ob, ware, from_tile):
        return hand_over(world, st, ob, ware, from_tile)
    return False


def neighbours(b: dict, st_footprint) -> list[tuple[int, int]]:
    from wizard_rts.industry import sim as S

    return S.adjacent_tiles(S.footprint(b))


def _dir_index(b: dict, from_tile: tuple[int, int]) -> int | None:
    """Direction an item travels when it enters 1x1 block `b` from `from_tile` (index into DIRS)."""
    dx, dy = b["tx"] - from_tile[0], b["ty"] - from_tile[1]
    return DIRS.index((dx, dy)) if (dx, dy) in DIRS else None


# ---- sorter / overflow gate: instant pass-through

def _route_target(world: Any, st: Any, b: dict, ware: str, from_tile: tuple[int, int], probe: bool) -> tuple[int, int] | None:
    from wizard_rts.industry import sim as S

    m = b["mdy"]
    d = _dir_index(b, from_tile)
    if d is None:
        return None
    me = (b["tx"], b["ty"])
    fwd = (me[0] + DIRS[d][0], me[1] + DIRS[d][1])
    left = (me[0] + DIRS[(d + 3) % 4][0], me[1] + DIRS[(d + 3) % 4][1])
    right = (me[0] + DIRS[(d + 1) % 4][0], me[1] + DIRS[(d + 1) % 4][1])

    def ok(t: tuple[int, int]) -> bool:
        if t in st.belts:
            return S.belt_accepts(st, t, me)
        ob = tile_building(world, st, t)
        return ob is not None and ob["id"] != b["id"] and accepts(world, st, ob, ware, me)

    def put(t: tuple[int, int]) -> tuple[int, int] | None:
        if probe:
            return t
        return t if give(world, st, t, ware, me) else None

    role = m["role"]
    if role == "sorter":
        match = (m.get("item") == ware)
        if bool(sp(b)["fields"].get("invert", 0)) or sp(b)["id"].startswith("inverted"):
            match = not match
        if match:
            return put(fwd) if ok(fwd) else None
        a, c = ok(left), ok(right)
        if a and c:
            pick = left if m["flip"] else right
            m["flip"] = not m["flip"]
            return put(pick)
        if a:
            return put(left)
        if c:
            return put(right)
        return None
    # overflow / underflow
    under = "underflow" in sp(b)["id"]
    first = fwd
    can_front = ok(first)
    if (can_front and not under) or (not can_front and under and False):
        return put(first)
    a, c = ok(left), ok(right)
    if under:  # underflow gate: sides first? no: the underflow gate gives to the front only when the sides are blocked
        if a or c:
            if a and c:
                pick = left if m["flip"] else right
                m["flip"] = not m["flip"]
                return put(pick)
            return put(left if a else right)
        return put(first) if can_front else None
    if a and c:
        pick = left if m["flip"] else right
        m["flip"] = not m["flip"]
        return put(pick)
    if a:
        return put(left)
    if c:
        return put(right)
    return None


def _bridge_accepts(world: Any, st: Any, b: dict, ware: str, from_tile: tuple[int, int]) -> bool:
    m = b["mdy"]
    if len(m["buf_items"]) >= BRIDGE_CAP:
        return False
    link = world.buildings.get(m.get("link") or "")
    if link is not None and from_tile in _line_tiles(b, link):
        return False  # nothing is accepted from the side the bridge sends towards
    return True


def _line_tiles(a: dict, b: dict) -> set[tuple[int, int]]:
    """The tile just beyond `a` in the direction of `b` (an input from there is refused)."""
    dx = (b["tx"] > a["tx"]) - (b["tx"] < a["tx"])
    dy = (b["ty"] > a["ty"]) - (b["ty"] < a["ty"])
    return {(a["tx"] + dx, a["ty"] + dy)}


# ------------------------------------------------------------------ per-role init

def init_role(world: Any, b: dict, m: dict, spec_: dict) -> None:
    role = m["role"]
    m.setdefault("liq", {})
    m.setdefault("heat", 0.0)
    if role == "router":
        m["hold"] = []
        m["timer"] = 0
    elif role == "sorter":
        m["item"] = b.pop("mdy_item", None)
        m["flip"] = False
    elif role == "overflow":
        m["flip"] = False
    elif role == "junction":
        m["lanes"] = [[], [], [], []]
    elif role == "bridge":
        m["buf_items"] = []
        m["link"] = b.pop("mdy_link", None)
        m["src_tile"] = None
        m["timer"] = 0
    elif role == "unloader":
        m["item"] = b.pop("mdy_item", None)
        m["rot"] = 0
    elif role in STORE_ROLES:
        world.stocks.setdefault(b["id"], {})
        if role == "core":
            b["store"] = True
    elif role == "mass_driver":
        m.update(link=b.pop("mdy_link", None), item_ware=None, item_total=0, reload=0)
    elif role == "turret":
        init_turret(world, b, m, spec_)
    elif role in ("mender", "overdrive", "shield", "repair", "radar", "incinerator", "wall", "door", "mine", "logic", "decor"):
        init_support(world, b, m, spec_)
    elif role in ("pump", "conduit", "tank", "liquid_junction", "liquid_bridge", "heater", "heat_conductor", "wall_drill"):
        init_fluid(world, b, m, spec_)
    elif role in ("reconstructor", "assembler", "assembler_module", "constructor", "deconstructor", "payload_belt", "payload_driver", "payload_loader", "cargo",
                  "launch_pad", "accelerator", "build_turret"):
        init_payload(world, b, m, spec_)


# the remaining roles are implemented in sibling modules and registered here so sim.py has one import
def init_turret(world, b, m, s):  # noqa: D103
    from wizard_rts.industry import defense

    defense.init_turret(world, b, m, s)


def turret_accepts(world, b, ware):  # noqa: D103
    from wizard_rts.industry import defense

    return defense.turret_accepts(world, b, ware)


def turret_take(world, b, ware):  # noqa: D103
    from wizard_rts.industry import defense

    return defense.turret_take(world, b, ware)


def init_support(world, b, m, s):  # noqa: D103
    from wizard_rts.industry import defense

    defense.init_support(world, b, m, s)


def support_accepts(world, b, ware):  # noqa: D103
    from wizard_rts.industry import defense

    return defense.support_accepts(world, b, ware)


def support_take(world, b, ware):  # noqa: D103
    from wizard_rts.industry import defense

    return defense.support_take(world, b, ware)


def init_fluid(world, b, m, s):  # noqa: D103
    from wizard_rts.industry import fluids

    fluids.init_fluid(world, b, m, s)


def init_payload(world, b, m, s):  # noqa: D103
    from wizard_rts.industry import payload

    payload.init_payload(world, b, m, s)


def payload_accepts(world, b, ware):  # noqa: D103
    from wizard_rts.industry import payload

    return payload.accepts(world, b, ware)


def payload_take(world, b, ware):  # noqa: D103
    from wizard_rts.industry import payload

    return payload.take(world, b, ware)


# ------------------------------------------------------------------ the quantum for the item-routing roles

def step_logistics(world: Any, st: Any, machines: list[dict]) -> None:
    for b in machines:
        m = b["mdy"]
        role = m["role"]
        if b.get("disrupted"):
            continue
        if role == "router":
            _router_step(world, st, b, m)
        elif role == "junction":
            _junction_step(world, st, b, m)
        elif role == "bridge":
            _bridge_step(world, st, b, m)
        elif role == "unloader":
            _unloader_step(world, st, b, m)
        elif role == "mass_driver":
            from wizard_rts.industry import payload

            payload.mass_driver_step(world, st, b, m)


def _router_step(world: Any, st: Any, b: dict, m: dict) -> None:
    from wizard_rts.industry import sim as S

    if not m["hold"]:
        m["state"] = "idle"
        return
    m["timer"] += TICKS_PER_Q
    item = m["hold"][0]
    if m["timer"] < ROUTER_TICKS * (1 if "duct" not in sp(b)["id"] else 1):
        return
    ring = S.adjacent_tiles(S.footprint(b))
    n = len(ring)
    me = (b["tx"], b["ty"])
    for k in range(n):
        t = ring[(m["dump_i"] + k) % n]
        if give(world, st, t, item[0], _edge_tile(b, t), ignore=b["id"]):
            m["dump_i"] = (m["dump_i"] + k + 1) % n
            m["hold"].pop(0)
            m["timer"] = 0
            m["state"] = "working"
            return
    m["state"] = "blocked"


def _edge_tile(b: dict, outside: tuple[int, int]) -> tuple[int, int]:
    from wizard_rts.industry import sim as S

    return S._belt_source_tile(b, outside)


def _junction_step(world: Any, st: Any, b: dict, m: dict) -> None:
    speed = int(sp(b)["fields"].get("speed", 26))
    me = (b["tx"], b["ty"])
    for d in range(4):
        lane = m["lanes"][d]
        if not lane:
            continue
        for it in lane:
            it[1] += TICKS_PER_Q
        ware, age = lane[0]
        if age >= speed:
            out = (me[0] + DIRS[d][0], me[1] + DIRS[d][1])
            if give(world, st, out, ware, me):
                lane.pop(0)
    m["state"] = "working" if any(m["lanes"]) else "idle"


def _bridge_step(world: Any, st: Any, b: dict, m: dict) -> None:
    from wizard_rts.industry import sim as S

    spec_ = sp(b)
    link = world.buildings.get(m.get("link") or "")
    if link is not None and (link.get("mdy") is None or int(link.get("hp", 1)) <= 0):
        link = None
    rng = int(spec_["fields"].get("range", 4))
    ptime = int(spec_["fields"].get("transportTime", 7)) if spec_["fields"].get("transportTime") else 7
    per_item = max(2, ptime)
    for it in m["buf_items"]:
        it[1] += TICKS_PER_Q
    m["timer"] += TICKS_PER_Q
    if not m["buf_items"]:
        m["state"] = "idle"
        return
    if link is not None and (link["tx"] == b["tx"] or link["ty"] == b["ty"]) and abs(link["tx"] - b["tx"]) + abs(link["ty"] - b["ty"]) <= rng:
        m["state"] = "sending"
        ware, age = m["buf_items"][0]
        transit = 4 + 2 * (abs(link["tx"] - b["tx"]) + abs(link["ty"] - b["ty"]))
        if age >= max(transit, per_item) and len(link["mdy"]["buf_items"]) < BRIDGE_CAP:
            m["buf_items"].pop(0)
            link["mdy"]["buf_items"].append([ware, 0])
            link["mdy"]["src_tile"] = (b["tx"], b["ty"])
        return
    # end of the chain: dump to the neighbours except back towards the sender
    if m["buf_items"][0][1] >= per_item:
        ware = m["buf_items"][0][0]
        ring = S.adjacent_tiles(S.footprint(b))
        me = (b["tx"], b["ty"])
        back = m.get("src_tile")
        for k in range(len(ring)):
            t = ring[(m["dump_i"] + k) % len(ring)]
            if back is not None and (t == _toward(me, back)):
                continue
            if give(world, st, t, ware, me, ignore=b["id"]):
                m["dump_i"] = (m["dump_i"] + k + 1) % len(ring)
                m["buf_items"].pop(0)
                m["state"] = "working"
                return
        m["state"] = "blocked"


def _toward(me: tuple[int, int], other: tuple[int, int]) -> tuple[int, int]:
    dx = (other[0] > me[0]) - (other[0] < me[0])
    dy = (other[1] > me[1]) - (other[1] < me[1])
    return (me[0] + dx, me[1] + dy)


def _unloader_step(world: Any, st: Any, b: dict, m: dict) -> None:
    from wizard_rts.industry import sim as S

    ring = S.adjacent_tiles(S.footprint(b))
    me = (b["tx"], b["ty"])
    sources: list[dict] = []
    dests: list[tuple[int, int]] = []
    for t in ring:
        ob = tile_building(world, st, t)
        if ob is not None and ob["id"] != b["id"] and ob.get("mdy") is not None and unloadable(ob):
            sources.append(ob)
        dests.append(t)
    if not sources:
        m["state"] = "no source"
        return
    want = m.get("item")
    for _ in range(UNLOADER_PER_Q):
        moved = False
        for src in sources:
            wares = _unloadable_wares(world, src)
            if want:
                wares = [w for w in wares if w == want]
            for ware in wares:
                for k in range(len(dests)):
                    t = dests[(m["rot"] + k) % len(dests)]
                    ob = tile_building(world, st, t)
                    if ob is not None and (ob["id"] == src["id"] or _is_store(ob)):
                        continue
                    if give(world, st, t, ware, me, ignore=src["id"]):
                        _take_unloaded(world, src, ware)
                        m["rot"] = (m["rot"] + k + 1) % len(dests)
                        moved = True
                        break
                if moved:
                    break
            if moved:
                break
        m["state"] = "working" if moved else "idle"


def unloadable(b: dict) -> bool:
    m = b.get("mdy")
    return bool(m) and m["role"] in (STORE_ROLES + ("crafter", "assembler")) and not b.get("constructing")


def _unloadable_wares(world: Any, b: dict) -> list[str]:
    m = b["mdy"]
    if m["role"] in STORE_ROLES:
        return sorted(g for g, n in world.stocks.get(b["id"], {}).items() if n > 0 and g not in ("recruit", "carrier"))
    return sorted(g for g, n in m["out"].items() if n > 0)


def _take_unloaded(world: Any, b: dict, ware: str) -> None:
    m = b["mdy"]
    if m["role"] in STORE_ROLES:
        world.stocks[b["id"]][ware] -= 1
        if world.stocks[b["id"]][ware] <= 0:
            world.stocks[b["id"]].pop(ware)
        if hasattr(world.economy_totals, "remove"):
            pass
    else:
        m["out"][ware] -= 1


# ------------------------------------------------------------------ holdings (the ware ledger)

def holdings(world: Any, b: dict) -> dict[str, int]:
    m = b.get("mdy")
    out: dict[str, int] = {}
    if not m:
        return out
    for key in ("hold",):
        for it in m.get(key, []):
            out[it[0]] = out.get(it[0], 0) + 1
    for lane in m.get("lanes", []):
        for it in lane:
            out[it[0]] = out.get(it[0], 0) + 1
    for it in m.get("buf_items", []):
        out[it[0]] = out.get(it[0], 0) + 1
    if m.get("item_ware") and m.get("item_total"):
        out[m["item_ware"]] = out.get(m["item_ware"], 0) + int(m["item_total"])
    for ware, n in m.get("payload_items", {}).items():
        out[ware] = out.get(ware, 0) + int(n)
    return out


# ------------------------------------------------------------------ crafter helpers

def separator_pick(world: Any, b: dict, m: dict, spec_: dict) -> str:
    """Separator.craft: one weighted draw from `results` (deterministic: seeded by world seed, building and cycle count)."""
    import random

    rng = random.Random(f"{world.seed}:sep:{b['id']}:{m.get('count', 0)}")
    items = sorted(spec_["results"].items())
    total = sum(w for _i, w in items)
    r = rng.random() * total
    for ware, w in items:
        if r < w:
            return ware
        r -= w
    return items[-1][0]


def attribute_sum(world: Any, b: dict, attribute: str) -> float:
    """Sum of an environment attribute over the footprint (Attribute.sumAttribute). Terrain mapping (hybrid): `spores` = fertile ground,
    `heat` / `steam` = hot ground and the shore of lava (the Widelands lava terrain), `water` = water tiles, `sand` = desert and beach, `oil` = none."""
    from wizard_rts.industry import sim as S

    t = world.terrain
    if t is None:
        return 0.0
    name = attribute.split(".")[-1]
    total = 0.0
    for (x, y) in S.footprint(b):
        if not t.in_bounds(x, y):
            continue
        tn = t.terrain_name(x, y)
        if name == "spores":
            total += 0.15 if t.cls[y * t.w + x] == 0 else 0.0
        elif name in ("heat", "steam"):
            hot = any(t.in_bounds(x + dx, y + dy) and "lava" in t.terrain_name(x + dx, y + dy) for dx, dy in DIRS + ((0, 0),))
            total += (0.75 if name == "heat" else 1.0) if hot else (0.25 if name == "heat" and ("desert" in tn or "beach" in tn) else 0.0)
        elif name == "water":
            total += 1.0 if t.is_water(x, y) else 0.0
        elif name == "sand":
            total += 1.0 if ("desert" in tn or "beach" in tn) else 0.0
    return total


# ------------------------------------------------------------------ power: generators, demand

def fuel_ok(spec_: dict, ware: str) -> bool:
    """Does a generator burn this ware? Explicit consume items win; else ConsumeItemFlammable (>= 0.2) or ConsumeItemRadioactive (>= 0.2)."""
    if spec_["consume_items"]:
        return ware in spec_["consume_items"]
    item = R.item_of(ware)
    if item is None:
        return False
    info = R.item_info(item)
    if any("Radioactive" in o for o in spec_.get("optional_consumers", [])):
        return info["radioactivity"] >= 0.2
    return info["flammability"] >= 0.2


def special_generator(spec_: dict) -> bool:
    """Generators the original slice does not model (liquids, heat, reactors, thermal): handled by `generator_step`."""
    if spec_["class"] == "SolarGenerator" or spec_["class"] == "PowerSource":
        return False
    return (bool(spec_["consume_liquids"]) or spec_["class"] != "ConsumeGenerator" or bool(spec_["consume_items"])
            or any("Radioactive" in o for o in spec_.get("optional_consumers", [])))


def generator_step(world: Any, st: Any, b: dict, spec_: dict, m: dict, dt_ms: int) -> float:
    """One quantum of a generator that is not a plain flammable burner or solar panel; returns the power units produced (per quantum)."""
    from wizard_rts.industry import fluids as F

    cls = spec_["class"]
    base = spec_["power_production_per_s"] * dt_ms / 1000.0
    m.setdefault("burn", 0)
    if cls == "ThermalGenerator":
        eff = attribute_sum(world, b, "heat")
        if "turbine" in spec_["id"]:  # turbine condenser: needs steam vents and gives water
            eff = attribute_sum(world, b, "steam")
        m["state"] = "producing" if eff > 0 else "no heat under it"
        if eff > 0:
            for liquid, per_tick in spec_["output_liquid"].items():
                F.produce(world, b, liquid, per_tick * TICKS_PER_Q * eff)
        return base * eff if eff > 0 else 0.0
    if cls == "NuclearReactor":
        return _nuclear_step(world, b, spec_, m, base)
    ok_liq = all(m["liq"].get(l, 0.0) >= per * TICKS_PER_Q * 0.999 for l, per in spec_["consume_liquids"].items() if per)
    # item cycle: one fuel item lasts itemDuration ticks
    if spec_["consume_items"] or spec_["flammable"] or spec_.get("optional_consumers"):
        if m["burn"] <= 0:
            fuel = next((w for w in sorted(m["buf"]) if m["buf"][w] > 0 and fuel_ok(spec_, w)), None)
            if fuel is not None and ok_liq:
                n = max(1, int(spec_["consume_items"].get(fuel, 1)))
                if m["buf"][fuel] >= n:
                    m["buf"][fuel] -= n
                    world.stats["consumed_" + fuel] = world.stats.get("consumed_" + fuel, 0) + n
                    m["burn"] = int(spec_["item_duration_ticks"])
        running = m["burn"] > 0 and ok_liq
    else:
        running = ok_liq  # liquid-only burners (chemical combustion chamber, pyrolysis)
    if not running:
        m["state"] = "no fuel" if (spec_["consume_items"] or spec_["flammable"]) else "no liquid"
        return 0.0
    if m["burn"] > 0:
        m["burn"] = max(0, m["burn"] - TICKS_PER_Q)
    for liquid, per in spec_["consume_liquids"].items():
        F.consume(world, b, liquid, per * TICKS_PER_Q)
    for liquid, per in spec_["output_liquid"].items():
        F.produce(world, b, liquid, per * TICKS_PER_Q)
    if spec_["heat_out"] > 0:
        m["heat_out"] = spec_["heat_out"]
    m["state"] = "producing"
    return base


def _nuclear_step(world: Any, b: dict, spec_: dict, m: dict, base: float) -> float:
    """NuclearReactor.updateTile: output follows the fuel fraction, heat rises with it, cryofluid carries heat away, 100 % heat = meltdown."""
    from wizard_rts.industry import fluids as F

    f = spec_["fields"]
    fuel = next(iter(spec_["consume_items"]), "mdy.thorium")
    cap = int(f.get("itemCapacity", 30))
    full = min(1.0, m["buf"].get(fuel, 0) / cap)
    heating = float(f.get("heating", 0.01))
    coolant_power = float(f.get("coolantPower", 0.5))
    if full > 0:
        m["heat"] += full * heating * TICKS_PER_Q
        m["burn"] = m.get("burn", 0) + TICKS_PER_Q
        if m["burn"] >= int(spec_["item_duration_ticks"]):
            m["burn"] = 0
            m["buf"][fuel] -= 1
            world.stats["consumed_" + fuel] = world.stats.get("consumed_" + fuel, 0) + 1
    if m["heat"] > 0:
        liquid = F.current_of(m) if hasattr(F, "current_of") else F.current(m)
        if liquid:
            used = min(m["liq"].get(liquid, 0.0), m["heat"] / coolant_power)
            F.consume(world, b, liquid, used)
            m["heat"] = max(0.0, m["heat"] - used * coolant_power)
    m["heat"] = max(0.0, m["heat"])
    m["state"] = "producing" if full > 0 else "no fuel"
    if m["heat"] >= 0.999:
        world.events.append({"kind": "reactor_meltdown", "id": b["id"], "faction": b["faction_name"]})
        from wizard_rts.industry import defense

        defense.explode(world, b, radius=float(f.get("explosionRadius", 19)) / 2.0, damage=int(f.get("explosionDamage", 1250)))
        return 0.0
    return base * full


def fuel_accepts(world: Any, b: dict, spec_: dict, m: dict, ware: str) -> bool:
    cap = int(spec_["item_capacity"]) if spec_["class"] == "NuclearReactor" else 10
    return fuel_ok(spec_, ware) and m["buf"].get(ware, 0) < cap


def wants_power(world: Any, b: dict, spec_: dict, m: dict) -> bool:
    """Does this machine draw its power this quantum? (ConsumePower: only while it has something to do.)"""
    if spec_["power_use_per_s"] <= 0:
        return False
    role = m["role"]
    if role == "drill":
        return m.get("item") != "" and sum(m["out"].values()) < 10
    if role == "pump":
        return m.get("pumped", 1.0) > 0 or m["state"] in ("idle", "pumping", "full")
    if role == "heater":
        return heater_ready(spec_, m)
    if role == "turret":
        return m.get("target") is not None or m.get("charge", 0) > 0 or spec_.get("class") == "PointDefenseTurret" and m.get("target") is not None
    if role in ("mender", "overdrive", "shield", "repair", "radar", "logic", "incinerator", "build_turret"):
        return True
    if role in ("reconstructor", "assembler", "constructor", "deconstructor", "payload_driver", "payload_loader", "cargo", "launch_pad", "accelerator"):
        return m.get("busy", False)
    if role == "mass_driver":
        return m.get("item_total", 0) > 0 or m.get("state") in ("shooting", "linked")
    if role == "wall_drill":
        return True
    if role in ("bridge", "stack_belt"):
        return bool(m.get("buf_items"))
    return True


def heater_ready(spec_: dict, m: dict) -> bool:
    return all(m["buf"].get(w, 0) >= n for w, n in spec_["consume_items"].items()) and all(
        m["liq"].get(l, 0.0) >= per * TICKS_PER_Q * 0.999 for l, per in spec_["consume_liquids"].items())


def needs_power(spec_: dict) -> bool:
    return spec_["power_use_per_s"] > 0


# ------------------------------------------------------------------ the generic quantum

def step_roles(world: Any, st: Any, machines: list[dict], sat_by_machine: dict[str, float], wants: dict[str, bool], sat_graph: dict[int, float]) -> None:
    """Everything the original slice does not do, once per quantum after the power solve."""
    from wizard_rts.industry import fluids as F

    F.step_pipes(world, st)
    F.step_machines(world, st, machines, sat_graph)
    diode_step(world, st, machines)
    heat_step(world, st, machines, sat_by_machine)
    for b in machines:
        m = b["mdy"]
        if b.get("disrupted"):
            continue
        if m["role"] == "wall_drill":
            _wall_drill_step(world, st, b, m, sat_by_machine.get(b["id"], 1.0))
        elif m["role"] == "harvester":
            _harvester_step(world, st, b, m, sat_by_machine.get(b["id"], 1.0))
    step_logistics(world, st, machines)
    from wizard_rts.industry import defense, payload

    defense.step(world, st, machines, sat_by_machine)
    payload.step(world, st, machines, sat_by_machine)


def _wall_drill_step(world: Any, st: Any, b: dict, m: dict, satisfaction: float) -> None:
    """WallCrafter (cliff crusher): sand from the mountain and rock tiles along the block's edge."""
    from wizard_rts.industry import sim as S
    from wizard_rts import terrain as T

    spec_ = sp(b)
    t = world.terrain
    n = 0
    if t is not None:
        for (x, y) in S.adjacent_tiles(S.footprint(b)):
            if t.in_bounds(x, y) and t.cls[y * t.w + x] == T.MINEABLE:
                n += 1
    if n == 0:
        m["state"] = "no wall in reach"
        return
    if satisfaction <= 0:
        m["state"] = "no power"
        return
    if sum(m["out"].values()) >= 10:
        m["state"] = "output blocked"
    else:
        m["state"] = "drilling"
        m["progress"] += TICKS_PER_Q * min(n, spec_["size"]) * satisfaction
        if m["progress"] >= int(spec_["fields"].get("drillTime", 110)) * 2:
            m["progress"] = 0
            ware = B.ware_of_item(str(spec_["refs"].get("output", "sand")) if False else "sand")
            m["out"][ware] = m["out"].get(ware, 0) + 1
            world.stats["made_" + ware] = world.stats.get("made_" + ware, 0) + 1
    from wizard_rts.industry import sim as S2

    S2._flush(world, st, b, m)


def heat_step(world: Any, st: Any, machines: list[dict], sat: dict[str, float]) -> None:
    """Heat networks: heaters and conductors that touch form a net; the net's heat is shared among its consumers in proportion to what they need."""
    from wizard_rts.industry import sim as S

    nodes = [b for b in machines if sp(b)["role"] in ("heater", "heat_conductor") or sp(b)["heat_in"] > 0 or sp(b)["heat_out"] > 0]
    if not nodes:
        return
    index = {b["id"]: i for i, b in enumerate(nodes)}
    parent = list(range(len(nodes)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for b in nodes:
        for t in S.adjacent_tiles(S.footprint(b)):
            oid = st.tile_owner.get(t)
            if oid in index and oid != b["id"]:
                ra, rb = find(index[b["id"]]), find(index[oid])
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    groups: dict[int, list[dict]] = {}
    for b in nodes:
        groups.setdefault(find(index[b["id"]]), []).append(b)
    for _root, g in sorted(groups.items()):
        supply = 0.0
        for b in g:
            m = b["mdy"]
            s_ = sp(b)
            if s_["role"] == "heater":
                run = heater_run(world, st, b, m, s_, sat.get(b["id"], 1.0))
                m["heat_out"] = s_["heat_out"] * run
            supply += float(m.get("heat_out", 0.0)) if s_["role"] in ("heater",) or s_["heat_out"] > 0 else 0.0
        demand = sum(sp(b)["heat_in"] for b in g if sp(b)["heat_in"] > 0)
        for b in g:
            s_ = sp(b)
            if s_["heat_in"] > 0:
                b["mdy"]["heat"] = min(s_["heat_in"] * 1.0, supply * s_["heat_in"] / demand) if demand > 0 else 0.0
            elif s_["role"] not in ("heater", "heat_conductor"):
                pass


def heater_run(world: Any, st: Any, b: dict, m: dict, spec_: dict, satisfaction: float) -> float:
    """A heat producer (electric heater, slag heater, oxidation chamber...) works while its inputs and power are there; returns 0..1 and consumes."""
    from wizard_rts.industry import fluids as F
    from wizard_rts.industry import sim as S

    if b.get("disrupted"):
        m["state"] = "closed"
        return 0.0
    if spec_["power_use_per_s"] > 0 and satisfaction <= 0:
        m["state"] = "no power"
        return 0.0
    if not heater_ready(spec_, m):
        m["state"] = "waiting for inputs"
        return 0.0
    if sum(m["out"].values()) >= 10:
        m["state"] = "output blocked"
        return 0.0
    m["state"] = "heating"
    for liquid, per in spec_["consume_liquids"].items():
        F.consume(world, b, liquid, per * TICKS_PER_Q)
    ct = spec_["craft_ticks"]
    if spec_["consume_items"] and ct > 0:
        m["progress"] += TICKS_PER_Q
        if m["progress"] >= ct:
            m["progress"] -= ct
            for w, n in spec_["consume_items"].items():
                m["buf"][w] -= n
                world.stats["consumed_" + w] = world.stats.get("consumed_" + w, 0) + n
            for w, n in spec_["output_item"].items():
                m["out"][w] = m["out"].get(w, 0) + n
                world.stats["made_" + w] = world.stats.get("made_" + w, 0) + n
    S._flush(world, st, b, m)
    return 1.0


def diode_step(world: Any, st: Any, machines: list[dict]) -> None:
    """PowerDiode.updateTile: charge flows from the battery graph behind it to the one in front when the back is fuller (fraction-wise)."""
    from wizard_rts.industry import sim as S

    for d in machines:
        if sp(d)["role"] != "diode":
            continue
        rot = int(d["mdy"].get("rot", 0)) % 4
        bx, by = DIRS[(rot + 2) % 4]
        fx, fy = DIRS[rot]
        back = st.tile_owner.get((d["tx"] + bx, d["ty"] + by))
        front = st.tile_owner.get((d["tx"] + fx, d["ty"] + fy))
        gb, gf = st.graph_of.get(back, -1), st.graph_of.get(front, -1)
        if gb < 0 or gf < 0 or gb == gf:
            continue
        bb = [world.buildings[i] for i in st.graphs[gb] if world.buildings[i]["mdy"]["role"] == "battery"]
        fb = [world.buildings[i] for i in st.graphs[gf] if world.buildings[i]["mdy"]["role"] == "battery"]
        capb = sum(sp(x)["power_buffer"] for x in bb)
        capf = sum(sp(x)["power_buffer"] for x in fb)
        if capb <= 0 or capf <= 0:
            continue
        sb, sf = sum(x["mdy"]["stored"] for x in bb), sum(x["mdy"]["stored"] for x in fb)
        fb_, ff_ = sb / capb, sf / capf
        if fb_ > ff_:
            amount = max(0.0, min(sb * (fb_ - ff_) / 2.0, capf * (1.0 - ff_)))
            left = amount
            for x in bb:
                take = min(x["mdy"]["stored"], left)
                x["mdy"]["stored"] -= take
                left -= take
            give_ = amount
            for x in fb:
                room = sp(x)["power_buffer"] - x["mdy"]["stored"]
                add = min(room, give_)
                x["mdy"]["stored"] += add
                give_ -= add


def _harvester_step(world: Any, st: Any, b: dict, m: dict, satisfaction: float) -> None:
    """Tree harvester (hybrid.py): fells a grown tree within reach every cycle and puts two logs in its output; power-driven, no worker walks."""
    from wizard_rts import workers
    from wizard_rts.industry import sim as S

    spec_ = sp(b)
    if satisfaction <= 0:
        m["state"] = "no power"
        S._flush(world, st, b, m)
        return
    if sum(m["out"].values()) >= 10:
        m["state"] = "output blocked"
        S._flush(world, st, b, m)
        return
    m["progress"] += TICKS_PER_Q * satisfaction * m.get("od", 1.0)
    m["state"] = "harvesting"
    if m["progress"] >= spec_["craft_ticks"]:
        r = int(spec_.get("harvest_radius", 9))
        best = None
        for tree in world.trees.values():
            if tree.get("species") == "wheat" or tree.get("reserved_by") or tree["stage"] not in ("old", "mature"):
                continue
            d = max(abs(tree["tx"] - b["tx"]), abs(tree["ty"] - b["ty"]))
            if d <= r and (best is None or (d, tree["id"]) < best[0]):
                best = ((d, tree["id"]), tree)
        if best is None:
            m["state"] = "no trees in reach"
            m["progress"] = spec_["craft_ticks"]
        else:
            m["progress"] -= spec_["craft_ticks"]
            workers.remove_tree(world, best[1]["id"], "harvested")
            for w_, n in spec_["output_item"].items():
                m["out"][w_] = m["out"].get(w_, 0) + n
                world.stats["made_" + w_] = world.stats.get("made_" + w_, 0) + n
            world.stats["trees_harvested"] = world.stats.get("trees_harvested", 0) + 1
    S._flush(world, st, b, m)

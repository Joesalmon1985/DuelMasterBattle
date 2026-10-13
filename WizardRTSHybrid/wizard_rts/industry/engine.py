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
POWER_ROLES = {"drill", "pump", "wall_drill", "heater", "mender", "overdrive", "shield", "turret", "reconstructor", "assembler", "assembler_module", "constructor",
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


def give(world: Any, st: Any, tile: tuple[int, int], ware: str, from_tile: tuple[int, int], ignore: str = "") -> bool:
    """Put one ware onto whatever stands on `tile` (a belt or a machine) if it takes it."""
    from wizard_rts.industry import sim as S

    if tile in st.belts:
        if S.belt_accepts(st, tile, from_tile):
            S.belt_put(st, tile, ware)
            return True
        return False
    ob = tile_building(world, st, tile)
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

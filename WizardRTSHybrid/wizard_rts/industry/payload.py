"""Payloads: unit factories, reconstructors, assemblers, constructors, payload conveyors, mass drivers, launch pads (owner programme 13 Oct 2026).

A payload is a dict: {"type": "unit", "unit": name, "faction": ..., "hp": fraction} or {"type": "block", "block": id, "stock": {}}. Factories build
one from items and power; it moves by payload conveyors (`st.pbelts` tiles) or directly into an adjacent acceptor (reconstructor, router, driver,
deconstructor, loader); with nothing in front a unit simply steps out onto the ground and becomes an ordinary `world.units` entry.
Items travelling in shipments (mass driver, launch pad, cargo loader) are held in `st.shipments` and counted by the ware ledger.
"""

from __future__ import annotations

import math
from typing import Any

from wizard_rts.industry import registry as R
from wizard_rts.industry import units as U

DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))
TICKS_PER_Q = 6
PBELT_TICKS = 20  # ticks a payload needs to cross one conveyor tile
ROLES = ("reconstructor", "assembler", "assembler_module", "constructor", "deconstructor", "payload_belt", "payload_driver", "payload_loader", "cargo",
         "launch_pad", "accelerator", "build_turret")


def init_payload(world: Any, b: dict, m: dict, spec: dict) -> None:
    role = spec["role"]
    m.update(payload=None, busy=False, rot=int(b.pop("mdy_rot", 0)) % 4, wait=0)
    if role == "constructor":
        flt = spec.get("filter") or []
        m["block"] = b.pop("mdy_block", None) or (R_kind(flt[0]) if flt else None)
    if role == "assembler":
        plans = spec.get("assembler_plans") or []
        m["plan"] = b.pop("mdy_plan", None) or (plans[0]["unit"] if plans else "")
        m["stack"] = {}
    if role in ("payload_driver", "launch_pad", "cargo"):
        m["link"] = b.pop("mdy_link", None)
        m["timer"] = 0


def R_kind(java_name: str) -> str | None:
    """Blocks.java field name (`tungstenWallLarge`) -> block kind."""
    from wizard_rts.industry import blocks as B

    for bid, blk in B.full()["blocks"].items():
        if blk.get("java_name") == java_name:
            return B.kind_of(bid)
    return None


# ------------------------------------------------------------------ item intake of payload machines

def accepts(world: Any, b: dict, ware: str) -> bool:
    spec = R.block(b["kind"])
    m = b["mdy"]
    role = m["role"]
    if role == "reconstructor":
        need = spec["consume_items"].get(ware)
        return need is not None and m["buf"].get(ware, 0) < 2 * need
    if role == "constructor":
        blk = R.block(m["block"]) if m.get("block") else None
        return bool(blk) and ware in _block_items(blk) and m["buf"].get(ware, 0) < 2 * _block_items(blk)[ware]
    if role == "assembler":
        return False
    if role in ("launch_pad", "cargo"):
        return sum(m["buf"].values()) < int(spec["item_capacity"])
    if role == "accelerator":
        return sum(m["buf"].values()) < 5000
    if role == "payload_loader":
        pl = m.get("payload")
        return pl is not None and pl.get("type") == "block" and sum(pl["stock"].values()) < pl.get("cap", 300)
    if role == "deconstructor":
        return False
    return False


def take(world: Any, b: dict, ware: str) -> bool:
    m = b["mdy"]
    if m["role"] == "payload_loader" and m.get("payload"):
        m["payload"]["stock"][ware] = m["payload"]["stock"].get(ware, 0) + 1
        return True
    m["buf"][ware] = m["buf"].get(ware, 0) + 1
    return True


def _block_items(blk: dict) -> dict[str, int]:
    from wizard_rts.industry import blocks as B

    return {B.ware_of_item(i): n for i, n in blk["source_cost"].items()}


# ------------------------------------------------------------------ payload hand-over

def front_tile(b: dict, spec: dict, rot: int) -> tuple[int, int]:
    n = spec["size"]
    cx, cy = b["tx"] + n // 2, b["ty"] + n // 2
    dx, dy = DIRS[rot]
    return (cx + dx * (n // 2 + 1) - (0 if n % 2 else 0), cy + dy * (n // 2 + 1))


def accepts_payload(world: Any, st: Any, b: dict, payload: dict, from_tile: tuple[int, int]) -> bool:
    m = b.get("mdy")
    if m is None or int(b.get("hp", 1)) <= 0 or b.get("constructing"):
        return False
    role = m["role"]
    if role in ("reconstructor", "deconstructor", "payload_loader", "payload_driver"):
        if m.get("payload") is not None:
            return False
        if role == "reconstructor":
            from wizard_rts import tech

            up = U.upgrade_of(payload["unit"])
            ok_upgrade = any(len(pair) > 1 and pair[0] == payload["unit"] for pair in (R.block(b["kind"]).get("upgrades") or []))
            return (payload.get("type") == "unit" and up is not None and ok_upgrade and tech.unit_allowed(world, b["faction_name"], up) and _facing_ok(b, from_tile))
        if role == "payload_loader":
            return payload.get("type") == "block"
        return True
    if role == "payload_belt":
        return m.get("payload") is None
    if role == "assembler":
        # UnitAssembler.acceptPayload: only what the chosen plan still needs (units by type, blocks by block), one payload at a time
        if m.get("payload") is not None:
            return False
        plan = next((p for p in R.block(b["kind"]).get("assembler_plans") or [] if p["unit"] == m.get("plan")), None)
        if plan is None:
            return False
        key = payload.get("unit") if payload.get("type") == "unit" else payload.get("block")
        jk = next((k for k in plan["payload"] if k == key or k.lower() == str(key).replace("-", "").lower() or _java_eq(k, key)), None)
        return jk is not None and m["stack"].get(jk, 0) < plan["payload"][jk]
    return False


def _facing_ok(b: dict, from_tile: tuple[int, int]) -> bool:
    """A reconstructor refuses payload from the side it faces (Reconstructor.acceptPayload: relativeTo(source) != rotation)."""
    spec = R.block(b["kind"])
    ft = front_tile(b, spec, b["mdy"]["rot"])
    return not (abs(from_tile[0] - ft[0]) + abs(from_tile[1] - ft[1]) <= 1 and from_tile == ft)


def give_payload(world: Any, st: Any, tile: tuple[int, int], payload: dict, from_tile: tuple[int, int]) -> bool:
    if tile in st.pbelts:
        pb = st.pbelts[tile]
        dx, dy = DIRS[pb["d"]]
        if (tile[0] + dx, tile[1] + dy) == from_tile or pb["load"] is not None:
            return False
        pb["load"], pb["prog"] = payload, 0
        return True
    ob_id = st.tile_owner.get(tile)
    ob = world.buildings.get(ob_id) if ob_id else None
    if ob is None or not accepts_payload(world, st, ob, payload, from_tile):
        return False
    om = ob["mdy"]
    if om["role"] == "payload_belt":
        om["payload"] = payload
        return True
    om["payload"] = payload
    om["wait"] = 0
    om["busy"] = True
    return True


def emit(world: Any, st: Any, b: dict, payload: dict) -> bool:
    """Send a finished payload out: into the acceptor in front, else (units) onto the ground. False when blocked."""
    from wizard_rts.industry import sim as S

    m = b["mdy"]
    m.setdefault("rot", 0)
    spec = R.block(b["kind"])
    ft = front_tile(b, spec, m["rot"])
    me = _edge(b, spec, m["rot"])
    if give_payload(world, st, ft, payload, me):
        return True
    if payload["type"] == "unit":
        tile = _free_tile_near(world, st, b, ft, payload["unit"])
        if tile is None:
            return False
        spawn_unit(world, b, payload, tile)
        return True
    return place_block(world, st, b, payload, ft)


def _edge(b: dict, spec: dict, rot: int) -> tuple[int, int]:
    n = spec["size"]
    cx, cy = b["tx"] + n // 2, b["ty"] + n // 2
    dx, dy = DIRS[rot]
    return (cx + dx * (n // 2), cy + dy * (n // 2))


def _free_tile_near(world: Any, st: Any, b: dict, first: tuple[int, int], unit: str) -> tuple[int, int] | None:
    from wizard_rts.industry import sim as S
    from wizard_rts import rules as _rules

    info = U.rules_for(unit) if not unit.startswith("mk2_") else (_rules.actor("openra." + unit), None)
    loco = info[0]["locomotor"] if info and info[0] else "foot"
    occupied = {(u["tx"], u["ty"]) for u in world.units.values() if u.get("alive", True)}
    ring = [first] + [t for t in S.adjacent_tiles(S.footprint(b)) if t != first]
    for t in ring:
        if not world.tile_in_bounds(*t) or world.tile_speed(loco, *t) <= 0:
            continue
        if loco != "fly" and (t in world.blocked or t in occupied or t in st.belts or t in world.tree_tiles):
            continue
        return t
    return None


def spawn_unit(world: Any, b: dict, payload: dict, tile: tuple[int, int]) -> str:
    name = payload["unit"]
    if name.startswith("mk2_"):  # an enhanced Red Alert unit from an assembly line
        uid = world._unit(b["faction"], b["faction_name"], name, U.label_of(name.replace("mk2_", "") + " mk2"), "openra." + name, tile)
        world.units[uid]["mk2"] = True
        world.fstat(b["faction_name"], "units_built")
        world.fstat(b["faction_name"], "mk2_units_built")
        world.events.append({"kind": "unit_produced", "building": b["id"], "unit": uid, "unit_kind": name, "faction": b["faction_name"]})
        return uid
    r = U.rules_for(name)
    uid = world._unit(b["faction"], b["faction_name"], "mdy_" + name, U.label_of(name), "mindustry." + name.replace("-", "_"), tile)
    u = world.units[uid]
    if payload.get("hp") and payload["hp"] < 1.0:
        u["hp"] = max(1, int(u["max_hp"] * payload["hp"]))
    u["mdy_unit"] = name
    world.fstat(b["faction_name"], "units_built")
    world.fstat(b["faction_name"], "mindustry_units_built")
    world.events.append({"kind": "unit_produced", "building": b["id"], "unit": uid, "unit_kind": "mdy_" + name, "faction": b["faction_name"]})
    return uid


def place_block(world: Any, st: Any, b: dict, payload: dict, tile: tuple[int, int]) -> bool:
    """A finished block payload is set down in front of its maker as a complete, operational building."""
    from wizard_rts.industry import commands as C
    from wizard_rts.industry import sim as S

    kind = R_kind_id(payload["block"])
    blk = R.block(kind)
    if blk is None:
        return False
    why, ctx = C.check_machine(world, b["faction_name"], kind, tile)
    if why:
        return False
    bid = world._building(b["faction"], b["faction_name"], kind, tile, blk["label"], blk["definition"])
    nb = world.buildings[bid]
    nb["operational"] = True
    nb["hp"] = nb["max_hp"]
    for t in ctx["footprint"]:
        world.blocked.add(t)
    nb["ground_footprint"] = [list(t) for t in ctx["footprint"]]
    if payload.get("stock"):
        world.stocks.setdefault(bid, {}).update(payload["stock"])
    world.events.append({"kind": "construction_done", "id": bid, "building_kind": kind, "by_payload": b["id"]})
    S.ind(world).dirty = True
    return True


def R_kind_id(java_or_id: str) -> str | None:
    from wizard_rts.industry import blocks as B

    if java_or_id in B.full()["blocks"]:
        return B.kind_of(java_or_id)
    return R_kind(java_or_id)


# ------------------------------------------------------------------ quantum

def step(world: Any, st: Any, machines: list[dict], sat: dict[str, float]) -> None:
    pbelt_step(world, st)
    for b in machines:
        m = b["mdy"]
        role = m["role"]
        if b.get("disrupted") or role not in ROLES:
            continue
        spec = R.block(b["kind"])
        s = sat.get(b["id"], 1.0)
        if role == "reconstructor":
            _reconstructor_step(world, st, b, m, spec, s)
        elif role == "assembler":
            _assembler_step(world, st, b, m, spec, s)
        elif role == "constructor":
            _constructor_step(world, st, b, m, spec, s)
        elif role == "deconstructor":
            _deconstructor_step(world, st, b, m, spec, s)
        elif role == "payload_belt":
            _router_step(world, st, b, m, spec)
        elif role == "payload_loader":
            _loader_step(world, st, b, m, spec, s)
        elif role == "payload_driver":
            _payload_driver_step(world, st, b, m, spec, s)
        elif role in ("launch_pad", "cargo"):
            _shipper_step(world, st, b, m, spec, s)
        elif role == "accelerator":
            _accelerator_step(world, st, b, m, spec, s)
    shipments_step(world, st)


def pbelt_step(world: Any, st: Any) -> None:
    for tile in sorted(st.pbelts):
        pb = st.pbelts[tile]
        if pb["load"] is None:
            continue
        pb["prog"] += TICKS_PER_Q
        if pb["prog"] < PBELT_TICKS:
            continue
        dx, dy = DIRS[pb["d"]]
        nxt = (tile[0] + dx, tile[1] + dy)
        if give_payload(world, st, nxt, pb["load"], tile):
            pb["load"] = None
            pb["prog"] = 0
        elif pb["load"]["type"] == "unit" and nxt not in st.pbelts and st.tile_owner.get(nxt) is None:
            # the end of the line: units walk off the belt
            from types import SimpleNamespace

            tmp = {"id": "pbelt", "faction": pb["faction"], "faction_name": pb["faction_name"], "tx": tile[0], "ty": tile[1]}
            free = _free_tile_for(world, st, nxt, pb["load"]["unit"])
            if free is not None:
                spawn_unit(world, tmp, pb["load"], free)
                pb["load"] = None
                pb["prog"] = 0
        else:
            pb["prog"] = PBELT_TICKS


def _free_tile_for(world: Any, st: Any, first: tuple[int, int], unit: str) -> tuple[int, int] | None:
    info = U.rules_for(unit)
    loco = info[0]["locomotor"] if info else "foot"
    occupied = {(u["tx"], u["ty"]) for u in world.units.values() if u.get("alive", True)}
    for t in [first] + [(first[0] + dx, first[1] + dy) for dx, dy in DIRS]:
        if world.tile_in_bounds(*t) and world.tile_speed(loco, *t) > 0 and (loco == "fly" or (t not in world.blocked and t not in occupied and t not in st.belts)):
            return t
    return None


def emit_unit_from_factory(world: Any, st: Any, b: dict, unit: str) -> bool:
    return emit(world, st, b, {"type": "unit", "unit": unit, "faction": b["faction_name"], "hp": 1.0})


def _reconstructor_step(world: Any, st: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    from wizard_rts.industry import fluids as F

    pl = m.get("payload")
    if pl is None:
        m["state"] = "waiting for a unit"
        m["busy"] = False
        return
    if m.get("done"):
        if emit(world, st, b, pl):
            m["payload"], m["done"], m["busy"], m["wait"] = None, False, False, 0
            world.events.append({"kind": "unit_upgraded", "building": b["id"], "unit": pl["unit"]})
        else:
            m["state"] = "exit blocked"
        return
    need_items = all(m["buf"].get(w, 0) >= n for w, n in spec["consume_items"].items())
    need_liq = all(m["liq"].get(l, 0.0) >= per * TICKS_PER_Q * 0.999 for l, per in spec["consume_liquids"].items())
    if not need_items or not need_liq:
        m["state"] = "waiting for inputs"
        m["busy"] = False
        return
    if spec["power_use_per_s"] > 0 and s <= 0:
        m["state"] = "no power"
        return
    m["busy"] = True
    m["state"] = "upgrading"
    m["wait"] += TICKS_PER_Q * s * m.get("od", 1.0)
    for liquid, per in spec["consume_liquids"].items():
        F.consume(world, b, liquid, per * TICKS_PER_Q * s)
    if m["wait"] >= int(spec["fields"].get("constructTime", 600)):
        for w, n in spec["consume_items"].items():
            m["buf"][w] -= n
            world.stats["consumed_" + w] = world.stats.get("consumed_" + w, 0) + n
        up = U.upgrade_of(pl["unit"])
        pl["unit"] = up
        m["done"] = True


def _assembler_step(world: Any, st: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    """UnitAssembler: unit payloads and block payloads delivered by conveyor are consumed against the plan; power and liquid run the build."""
    from wizard_rts.industry import fluids as F

    plans = {p["unit"]: p for p in spec.get("assembler_plans") or []}
    plan = plans.get(m.get("plan"))
    pl = m.get("payload")
    if pl is not None:  # a payload delivered into the assembler counts towards the plan
        key = pl.get("unit") if pl["type"] == "unit" else pl.get("block")
        want = plan["payload"] if plan else {}
        jk = next((k for k in want if k == key or k.lower() == str(key).replace("-", "").lower() or _java_eq(k, key)), None)
        if jk is not None and m["stack"].get(jk, 0) < want[jk]:
            m["stack"][jk] = m["stack"].get(jk, 0) + 1
            m["payload"] = None
        else:
            m["payload"] = None
            emit(world, st, b, pl)
    if plan is None:
        m["state"] = "no plan"
        return
    if not all(m["stack"].get(k, 0) >= n for k, n in plan["payload"].items()):
        m["state"] = "needs payload"
        m["busy"] = False
        return
    if spec["power_use_per_s"] > 0 and s <= 0:
        m["state"] = "no power"
        return
    if not all(m["liq"].get(l, 0.0) >= per * TICKS_PER_Q * 0.999 for l, per in spec["consume_liquids"].items()):
        m["state"] = "needs liquid"
        return
    m["busy"] = True
    m["state"] = "assembling"
    m["wait"] += TICKS_PER_Q * s * m.get("od", 1.0)
    for liquid, per in spec["consume_liquids"].items():
        F.consume(world, b, liquid, per * TICKS_PER_Q * s)
    if m["wait"] >= int(plan["time_ticks"]):
        if emit(world, st, b, {"type": "unit", "unit": plan["unit"], "faction": b["faction_name"], "hp": 1.0}):
            m["stack"] = {}
            m["wait"] = 0
            m["busy"] = False


def _java_eq(java: str, key: Any) -> bool:
    return R_kind(java) is not None and R_kind(java) == R_kind_id(str(key))


def _constructor_step(world: Any, st: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    from wizard_rts.industry import registry as RR

    if m.get("done"):
        if emit(world, st, b, m["payload"]):
            m["payload"], m["done"], m["busy"], m["wait"] = None, False, False, 0
        else:
            m["state"] = "exit blocked"
        return
    blk = R.block(m["block"]) if m.get("block") else None
    if blk is None:
        m["state"] = "no design"
        return
    items = _block_items(blk)
    if not all(m["buf"].get(w, 0) >= n for w, n in items.items()):
        m["state"] = "waiting for " + ", ".join(w for w, n in items.items() if m["buf"].get(w, 0) < n)
        m["busy"] = False
        return
    if spec["power_use_per_s"] > 0 and s <= 0:
        m["state"] = "no power"
        return
    m["busy"] = True
    m["state"] = "building"
    ticks = (20 + sum(RR.item_info(w[4:].replace("_", "-") if w.startswith("mdy.") else w)["cost"] * n for w, n in items.items())) * 1.4 / float(spec["fields"].get("buildSpeed", 0.6))
    m["wait"] += TICKS_PER_Q * s
    if m["wait"] >= ticks:
        for w, n in items.items():
            m["buf"][w] -= n
            world.stats["consumed_" + w] = world.stats.get("consumed_" + w, 0) + n
        m["payload"] = {"type": "block", "block": blk["id"], "stock": {}, "cap": int(blk["fields"].get("itemCapacity", 300))}
        m["done"] = True


def _deconstructor_step(world: Any, st: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    from wizard_rts.industry import sim as S

    pl = m.get("payload")
    # refunds are dumped as items to neighbours
    for w in sorted(m["out"]):
        if m["out"][w] > 0:
            if S.dump(world, st, b, w):
                m["out"][w] -= 1
            break
    if pl is None:
        m["state"] = "waiting for a payload"
        m["busy"] = False
        return
    if spec["power_use_per_s"] > 0 and s <= 0:
        m["state"] = "no power"
        return
    m["busy"] = True
    m["state"] = "deconstructing"
    refund: dict[str, int] = {}
    if pl["type"] == "block":
        blk = R.block(R_kind_id(pl["block"]))
        refund = _block_items(blk) if blk else {}
        for w, n in pl.get("stock", {}).items():
            refund[w] = refund.get(w, 0) + n
    else:
        for plan in _plans_for(pl["unit"]):
            refund = {w: n for w, n in plan.items()}
            break
    if sum(m["out"].values()) + sum(refund.values()) > int(spec["fields"].get("itemCapacity", 100)) * 3:
        m["state"] = "output blocked"
        return
    m["wait"] += TICKS_PER_Q * s * float(spec["fields"].get("deconstructSpeed", 1.0))
    if m["wait"] >= 60:
        m["wait"] = 0
        for w, n in refund.items():
            m["out"][w] = m["out"].get(w, 0) + n
            world.stats["made_" + w] = world.stats.get("made_" + w, 0) + n  # refunded material re-enters the books as a source
        m["payload"] = None
        m["busy"] = False


def _plans_for(unit: str) -> list[dict[str, int]]:
    from wizard_rts.industry import blocks as B

    out = []
    for blk in B.specs().values():
        for p in blk.get("plans") or []:
            if p["unit"] == unit:
                out.append({B.ware_of_item(i): int(n) for i, n in p["requirements"].items()})
    return out


def _router_step(world: Any, st: Any, b: dict, m: dict, spec: dict) -> None:
    pl = m.get("payload")
    if pl is None:
        return
    m["wait"] += TICKS_PER_Q
    if m["wait"] < PBELT_TICKS:
        return
    me = (b["tx"], b["ty"])
    n = len(DIRS)
    for k in range(n):
        d = (m.get("dump_i", 0) + k) % n
        t = (b["tx"] + DIRS[d][0] * spec["size"] if DIRS[d][0] > 0 else b["tx"] + DIRS[d][0], b["ty"] + DIRS[d][1] * spec["size"] if DIRS[d][1] > 0 else b["ty"] + DIRS[d][1])
        if give_payload(world, st, t, pl, me):
            m["payload"], m["wait"] = None, 0
            m["dump_i"] = d + 1
            return


def _loader_step(world: Any, st: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    pl = m.get("payload")
    if pl is None or pl["type"] != "block":
        return
    unloading = "unloader" in spec["id"]
    from wizard_rts.industry import sim as S

    if unloading:
        for w in sorted(pl["stock"]):
            if pl["stock"][w] > 0 and S.dump(world, st, b, w):
                pl["stock"][w] -= 1
                if pl["stock"][w] <= 0:
                    pl["stock"].pop(w)
                break
        if not pl["stock"] and emit(world, st, b, pl):
            m["payload"] = None
    elif sum(pl["stock"].values()) >= pl.get("cap", 300) and emit(world, st, b, pl):
        m["payload"] = None
    m["state"] = "working"


def _payload_driver_step(world: Any, st: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    link = world.buildings.get(m.get("link") or "")
    pl = m.get("payload")
    if pl is None or link is None or link.get("mdy") is None or link["mdy"]["role"] != "payload_driver":
        m["state"] = "no link" if pl is not None else "idle"
        if pl is not None and link is None:
            if emit(world, st, b, pl):
                m["payload"] = None
        return
    rng = float(spec["fields"].get("range", 700)) / 8.0
    if math.hypot(link["tx"] - b["tx"], link["ty"] - b["ty"]) > rng:
        m["state"] = "out of range"
        return
    if spec["power_use_per_s"] > 0 and s <= 0:
        m["state"] = "no power"
        return
    m["timer"] = m.get("timer", 0) + TICKS_PER_Q * s
    if m["timer"] >= float(spec["fields"].get("reload", 130)) and link["mdy"].get("payload") is None:
        link["mdy"]["payload"], m["payload"], m["timer"] = pl, None, 0
        link["mdy"]["busy"] = True
        m["state"] = "shooting"
    # a payload that arrived by driver leaves the far end
    if m.get("payload") is not None and m.get("link") is None:
        if emit(world, st, b, m["payload"]):
            m["payload"] = None


# ---- item mass driver, launch pad, cargo: shipments

def shipments(st: Any) -> list[dict]:
    if not hasattr(st, "shipments"):
        st.shipments = []
    return st.shipments


def ship(world: Any, st: Any, src: dict, dest_id: str, items: dict[str, int], travel_ms: int) -> None:
    now = int(world.dmb.clock.get("game_ms", 0))
    shipments(st).append({"due": now + travel_ms, "dest": dest_id, "items": dict(items), "from": src["id"]})
    world.events.append({"kind": "shipment_sent", "from": src["id"], "to": dest_id, "items": dict(items), "faction": src["faction_name"]})


def shipments_step(world: Any, st: Any) -> None:
    from wizard_rts.industry import engine as E

    if not hasattr(st, "shipments") or not st.shipments:
        return
    now = int(world.dmb.clock.get("game_ms", 0))
    keep = []
    for sh in st.shipments:
        if sh["due"] > now:
            keep.append(sh)
            continue
        dest = world.buildings.get(sh["dest"])
        if dest is None or int(dest.get("hp", 1)) <= 0 or dest.get("mdy") is None:
            for w, n in sh["items"].items():
                world.stats["consumed_" + w] = world.stats.get("consumed_" + w, 0) + n  # lost: the target is gone
            world.events.append({"kind": "shipment_lost", "to": sh["dest"], "items": sh["items"]})
            continue
        left = {}
        for w, n in sh["items"].items():
            role = dest["mdy"]["role"]
            if role in ("store", "core"):
                room = E.store_room(world, dest, w) if role == "store" else 10**9
                put = min(n, max(0, room))
                world.stocks.setdefault(dest["id"], {})[w] = int(world.stocks[dest["id"]].get(w, 0)) + put
                if n - put:
                    left[w] = n - put
                    if role == "core":
                        world.stats["consumed_" + w] = world.stats.get("consumed_" + w, 0) + (n - put)
                        left.pop(w)
            elif role in ("mass_driver", "launch_pad", "cargo"):
                dest["mdy"]["buf"][w] = dest["mdy"]["buf"].get(w, 0) + n
            else:
                dest["mdy"]["buf"][w] = dest["mdy"]["buf"].get(w, 0) + n
        if left:
            sh["items"], sh["due"] = left, now + 2000
            keep.append(sh)
    st.shipments = keep


def mass_driver_step(world: Any, st: Any, b: dict, m: dict) -> None:
    from wizard_rts.industry import sim as S

    spec = R.block(b["kind"])
    sat = st.power.get(st.graph_of.get(b["id"], -1), {}).get("satisfaction", 1.0 if spec["power_use_per_s"] <= 0 else 0.0)
    link = world.buildings.get(m.get("link") or "")
    # items that arrived (buf) are dumped like any machine output
    for w in sorted(m["buf"]):
        if m["buf"][w] > 0:
            if S.dump(world, st, b, w):
                m["buf"][w] -= 1
            break
    if link is None or link.get("mdy") is None or link["mdy"]["role"] != "mass_driver":
        m["state"] = "no link" if m.get("item_total") else "idle"
        return
    rng = float(spec["fields"].get("range", 440)) / 8.0
    if math.hypot(link["tx"] - b["tx"], link["ty"] - b["ty"]) > rng:
        m["state"] = "out of range"
        return
    if sat <= 0:
        m["state"] = "no power"
        return
    m["reload"] = m.get("reload", 0) + TICKS_PER_Q * sat
    total = int(m.get("item_total", 0))
    if total >= int(spec["fields"].get("minDistribute", 10)) and m["reload"] >= float(spec["fields"].get("reload", 200)):
        ware = m["item_ware"]
        travel = int(1000 * math.hypot(link["tx"] - b["tx"], link["ty"] - b["ty"]) / 12.0)
        ship(world, st, b, link["id"], {ware: total}, max(500, travel))
        m["item_total"], m["item_ware"], m["reload"] = 0, None, 0
        m["state"] = "shooting"
    else:
        m["state"] = "linked"


def _shipper_step(world: Any, st: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    """LaunchPad / UnitCargoLoader: ship the buffered items to the linked store, core or unload point."""
    link = world.buildings.get(m.get("link") or "")
    total = sum(m["buf"].values())
    if link is None or link.get("mdy") is None:
        m["state"] = "no destination" if total else "idle"
        return
    if spec["power_use_per_s"] > 0 and s <= 0:
        m["state"] = "no power"
        return
    m["timer"] = m.get("timer", 0) + TICKS_PER_Q * s
    interval = float(spec["fields"].get("launchTime", 600)) if m["role"] == "launch_pad" else 300.0
    cap = int(spec["item_capacity"])
    if total >= min(cap, 20) and m["timer"] >= interval:
        items = {w: n for w, n in m["buf"].items() if n > 0}
        m["buf"] = {}
        dist = math.hypot(link["tx"] - b["tx"], link["ty"] - b["ty"])
        ship(world, st, b, link["id"], items, int(2000 + dist * 150))
        m["timer"] = 0
        m["state"] = "launching"
        world.fstat(b["faction_name"], "launches")
    else:
        m["state"] = "loading"


def _accelerator_step(world: Any, st: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    m["state"] = "charging" if sum(m["buf"].values()) else "idle"
    if sum(m["buf"].values()) >= 1000 and s > 0:
        for w in list(m["buf"]):
            world.stats["consumed_" + w] = world.stats.get("consumed_" + w, 0) + m["buf"][w]
        m["buf"] = {}
        world.fstat(b["faction_name"], "interplanetary_launches")
        world.events.append({"kind": "interplanetary_launch", "faction": b["faction_name"], "id": b["id"]})
        m["state"] = "launched"

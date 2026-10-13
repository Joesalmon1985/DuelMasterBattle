"""Red Alert unit and building functions beyond shooting (owner programme 13 Oct 2026): transport, aircraft ammunition and rearming, medics, mechanics,
service depots, engineers, spies, thieves, minelayers, demolition trucks, MAD tanks, radar jammers, gap generators and the three support powers.

Everything here works on `world.units` / `world.buildings` entries and ordinary wares. Commands (`board`, `unload`, `capture`, `infiltrate`, `lay_mine`, `detonate`,
`power`) are the same for God Mode, the AI and the training API. `ability_quantum` runs once per economy quantum.
"""

from __future__ import annotations

import math
from typing import Any

from wizard_rts import rules

QUANTUM_MS = 100
TRANSPORT = {  # definition -> (capacity, accepted classes, passenger weight rule)
    "openra.apc": (5, ("infantry",)), "openra.tran": (5, ("infantry",)), "openra.mh60": (5, ("infantry",)), "openra.lst": (5, ("infantry", "vehicle")),
}
INFANTRY_LOCO = ("foot",)
HEAL_MS = 3200
REPAIR_STEP_MS = 2000
DEPOT_RADIUS = 2.5
DEPOT_IRON_PER_HP = 0.25  # one iron per 25 % of a vehicle's maximum health restored
REARM_MS = 1600
CAPTURE_MS = 8000
INFILTRATE_MS = 4000
STEAL_MAX = 8
MINE_DAMAGE = 12000
DEMO_DAMAGE = 60000
DEMO_RADIUS = 3.5
MAD_DAMAGE_PCT = 60
MAD_RADIUS = 6.0
NUKE = {"delay_ms": 9000, "radius": 5.5, "damage": 90000, "cost": {"iron": 4, "coal": 4, "gold": 2}, "charge_ms": 240_000}
CURTAIN = {"duration_ms": 15_000, "cost": {"gold": 1, "iron": 2}, "charge_ms": 120_000, "radius": 1.5}
CHRONO = {"duration_ms": 20_000, "cost": {"gold": 1, "iron": 2}, "charge_ms": 150_000, "radius": 2.5, "range": 40}
PARADROP = {"cost": {"ration": 3, "iron": 1}, "charge_ms": 180_000, "count": 5}
SPYPLANE = {"cost": {"iron": 1}, "charge_ms": 90_000, "radius": 14}
POWER_OF = {"mslo": "nuke", "iron": "curtain", "pdox": "chrono", "afld": "paradrop"}


def _now(world: Any) -> int:
    return int(world.dmb.clock.get("game_ms", 0))


def is_infantry(u: dict) -> bool:
    return u.get("loco") == "foot" and "Infantry" in (rules.actor(u["definition"]) or {}).get("target_types", [])


def is_vehicle(u: dict) -> bool:
    return u.get("loco") in ("tracked", "wheeled", "heavywheeled", "lighttracked", "heavytracked", "legs") or (u.get("loco") == "foot" and not is_infantry(u))


def _dist(a: dict, b: dict) -> float:
    return math.hypot(a["tx"] - b["tx"], a["ty"] - b["ty"])


def _live_units(world: Any, faction: str | None = None):
    for u in list(world.units.values()):
        if u.get("alive", True) and not u.get("inside") and (faction is None or u["faction_name"] == faction):
            yield u


def _own_buildings(world: Any, faction: str, kind: str):
    for b in world.buildings.values():
        if b["faction_name"] == faction and b["kind"] == kind and b.get("operational") and not b.get("constructing") and int(b.get("hp", 1)) > 0:
            yield b


# ------------------------------------------------------------------ transport

def capacity_of(u: dict) -> tuple[int, tuple]:
    return TRANSPORT.get(u["definition"], (0, ()))


def board(world: Any, unit_id: str, transport_id: str) -> dict[str, Any]:
    u, t = world.units.get(unit_id), world.units.get(transport_id)
    if u is None or t is None or not u.get("alive", True) or not t.get("alive", True):
        return {"status": "rejected", "reason": "no_unit"}
    cap, kinds = capacity_of(t)
    if not cap:
        return {"status": "rejected", "reason": "not_a_transport"}
    if u["faction"] != t["faction"]:
        return {"status": "rejected", "reason": "not_yours"}
    kind = "infantry" if is_infantry(u) else ("vehicle" if is_vehicle(u) else "other")
    if kind not in kinds or u["id"] == t["id"] or u.get("inside"):
        return {"status": "rejected", "reason": "cannot_carry"}
    if len(t.setdefault("passengers", [])) >= cap:
        return {"status": "rejected", "reason": "full"}
    u["order"] = {"kind": "board", "target": transport_id}
    u["path"] = []
    return {"status": "ok"}


def unload(world: Any, transport_id: str, tx: int | None = None, ty: int | None = None) -> dict[str, Any]:
    t = world.units.get(transport_id)
    if t is None or not t.get("alive", True) or not t.get("passengers"):
        return {"status": "rejected", "reason": "nobody_inside"}
    if t.get("loco") == "fly":
        t["landed"] = True
    placed = 0
    for pid in list(t["passengers"]):
        p = world.units.get(pid)
        if p is None:
            t["passengers"].remove(pid)
            continue
        spot = _free_tile(world, p, (t["tx"], t["ty"]))
        if spot is None:
            continue
        p.pop("inside", None)
        p["tx"], p["ty"] = spot
        t["passengers"].remove(pid)
        placed += 1
        world.events.append({"kind": "unloaded", "unit": pid, "from": transport_id})
    if t.get("loco") == "fly":
        t["landed"] = False
    return {"status": "ok" if placed else "rejected", "unloaded": placed, "reason": "" if placed else "no_room"}


def _free_tile(world: Any, u: dict, around: tuple[int, int]) -> tuple[int, int] | None:
    occupied = {(x["tx"], x["ty"]) for x in world.units.values() if x.get("alive", True) and not x.get("inside") and x.get("loco") != "fly"}
    for r in range(1, 5):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                t = (around[0] + dx, around[1] + dy)
                if world.tile_in_bounds(*t) and world.tile_speed(u.get("loco"), *t) > 0 and (t not in occupied or u.get("loco") == "fly") and t not in world.blocked:
                    return t
    return None


def _boarding_step(world: Any, u: dict) -> None:
    o = u.get("order")
    if not o or o.get("kind") != "board":
        return
    t = world.units.get(o["target"])
    if t is None or not t.get("alive", True):
        u.pop("order", None)
        return
    if _dist(u, t) <= 2.1:
        cap, _ = capacity_of(t)
        if len(t.setdefault("passengers", [])) < cap:
            t["passengers"].append(u["id"])
            u["inside"] = t["id"]
            u.pop("order", None)
            u["path"] = []
            world.events.append({"kind": "boarded", "unit": u["id"], "transport": t["id"]})
        else:
            u.pop("order", None)
        return
    from wizard_rts import military

    goal = _free_tile(world, u, (t["tx"], t["ty"])) or (t["tx"], t["ty"])  # the transport's own tile is occupied: walk to the free tile beside it
    military._walk(world, u, goal, stop_within=0.0)


def _carry_passengers(world: Any) -> None:
    for t in world.units.values():
        for pid in t.get("passengers", []):
            p = world.units.get(pid)
            if p is not None:
                p["tx"], p["ty"] = t["tx"], t["ty"]


def on_death(world: Any, u: dict, by: str) -> None:
    """A transport takes its passengers with it; a demolition truck goes off."""
    from wizard_rts import military

    for pid in list(u.get("passengers", [])):
        p = world.units.get(pid)
        if p is not None and p.get("alive", True):
            p.pop("inside", None)
            military.kill_unit(world, p, by)
    u["passengers"] = []
    if u.get("ship"):
        from wizard_rts import maritime

        maritime.sink(world, u)
    if u["definition"] == "openra.dtrk" and not u.get("detonated"):
        u["detonated"] = True
        _blast(world, u, DEMO_RADIUS, DEMO_DAMAGE, by or u["id"])


# ------------------------------------------------------------------ explosions

def _blast(world: Any, centre: dict, radius: float, damage: int, by: str, friendly: bool = True) -> None:
    from wizard_rts import military

    for e in list(world.units.values()):
        if e.get("alive", True) and not e.get("inside") and e["id"] != centre.get("id") and _dist(e, centre) <= radius and (friendly or e["faction"] != centre["faction"]):
            e["hp"] = max(0, int(e["hp"]) - damage)
            if e["hp"] <= 0:
                military.kill_unit(world, e, by)
    for b in list(world.buildings.values()):
        if "hp" in b and int(b["hp"]) > 0 and b["id"] != centre.get("id") and _dist(b, centre) <= radius + 1 and (friendly or b["faction"] != centre["faction"]):
            if not (centre.get("kind") == "mine"):
                world.damage_building(b["id"], damage, ["structure"], {}, by=by)
    world.effects.append({"t": "explosion", "x1": centre["tx"], "y1": centre["ty"], "x2": centre["tx"], "y2": centre["ty"], "ttl_ms": 1500, "keep": 3, "p": "big"})


def detonate(world: Any, unit_id: str) -> dict[str, Any]:
    """Deploy: a demolition truck goes off now; a MAD tank thumps the ground (after its deploy delay, see the quantum)."""
    from wizard_rts import military

    u = world.units.get(unit_id)
    if u is None or not u.get("alive", True):
        return {"status": "rejected", "reason": "no_unit"}
    if u["definition"] == "openra.dtrk":
        military.kill_unit(world, u, u["id"])
        return {"status": "ok"}
    if u["definition"] == "openra.qtnk":
        if u.get("deployed_ms") is None:
            u["deployed_ms"] = 0
            u["order"] = None
            u.pop("order", None)
            return {"status": "ok"}
        return {"status": "rejected", "reason": "already_deployed"}
    return {"status": "rejected", "reason": "cannot_deploy"}


# ------------------------------------------------------------------ capture, infiltration

def capture(world: Any, unit_id: str, building_id: str) -> dict[str, Any]:
    u, b = world.units.get(unit_id), world.buildings.get(building_id)
    if u is None or b is None or u["definition"] != "openra.e6":
        return {"status": "rejected", "reason": "not_an_engineer"}
    if b["faction"] == u["faction"] or int(b.get("hp", 0)) <= 0 or b.get("constructing") or "hp" not in b:
        return {"status": "rejected", "reason": "cannot_capture"}
    if b.get("kind") == "blight_nest":
        return {"status": "rejected", "reason": "cannot_capture"}
    if b.get("command_center") and int(b["hp"]) * 2 > int(b["max_hp"]):
        return {"status": "rejected", "reason": "too_strong"}  # a settlement falls only when its defenders are beaten down to half
    u["order"] = {"kind": "capture", "target": building_id, "ms": 0}
    u["path"] = []
    return {"status": "ok"}


def infiltrate(world: Any, unit_id: str, building_id: str) -> dict[str, Any]:
    u, b = world.units.get(unit_id), world.buildings.get(building_id)
    if u is None or b is None or u["definition"] not in ("openra.spy", "openra.thf") or b["faction"] == u["faction"] or int(b.get("hp", 0)) <= 0:
        return {"status": "rejected", "reason": "cannot_infiltrate"}
    u["order"] = {"kind": "infiltrate", "target": building_id, "ms": 0}
    u["path"] = []
    return {"status": "ok"}


def _order_step(world: Any, u: dict) -> None:
    from wizard_rts import military

    o = u.get("order")
    if not o or o.get("kind") not in ("capture", "infiltrate"):
        return
    b = world.buildings.get(o["target"])
    if b is None or int(b.get("hp", 0)) <= 0:
        u.pop("order", None)
        return
    if _dist(u, b) > 1.6:
        if military._walk(world, u, (b["tx"], b["ty"]), stop_within=1.2) == "stuck":
            u.pop("order", None)
        return
    u["status"] = "working"
    o["ms"] += QUANTUM_MS
    need = CAPTURE_MS if o["kind"] == "capture" else INFILTRATE_MS
    if o["ms"] < need:
        return
    u.pop("order", None)
    if o["kind"] == "capture":
        _do_capture(world, u, b)
    elif u["definition"] == "openra.thf":
        _do_steal(world, u, b)
    else:
        _do_spy(world, u, b)


def _do_capture(world: Any, u: dict, b: dict) -> None:
    from wizard_rts import military

    old = b["faction_name"]
    b["faction"], b["faction_name"] = u["faction"], u["faction_name"]
    b["label"] = f"{u['faction_name']} {b['label'].split(' ', 1)[-1]}"
    b["queue"] = []
    world.recipe_requests.pop(b["id"], None)
    for wid in [w for w, w_ in world.workers.items() if w_.get("building") == b["id"]]:
        world.workers.pop(wid)
    b["worker_ids"], b["worker_id"] = {}, ""
    b["capturedcount"] = int(b.get("capturedcount", 0)) + 1
    sid = b.get("settlement_id")
    rec = world.dmb.settlements.get(sid) if sid else None
    if rec is not None:
        rec["faction"] = u["faction_name"]
        rec["chronicle"].append({"event": "captured", "game_ms": _now(world), "cause": "engineer", "by": u["id"], "from": old})
    world.fstat(u["faction_name"], "buildings_captured")
    world.events.append({"kind": "captured", "building": b["id"], "by": u["faction_name"], "from": old, "settlement": sid or ""})
    military.kill_unit(world, u, u["id"])  # the engineer is used up


def _do_steal(world: Any, u: dict, b: dict) -> None:
    from wizard_rts import military

    store = world.stocks.get(b["id"], {})
    loot: dict[str, int] = {}
    room = STEAL_MAX
    for ware in ("gold", "iron", "coal", "ration", "plank", "granite", "log"):
        take = min(int(store.get(ware, 0)), room)
        if take > 0:
            store[ware] = int(store[ware]) - take
            if store[ware] <= 0:
                store.pop(ware)
            loot[ware] = take
            room -= take
        if room <= 0:
            break
    if loot:
        u.setdefault("cargo", {})
        for k, v in loot.items():
            u["cargo"][k] = u["cargo"].get(k, 0) + v
        wh = None
        from wizard_rts import construction as con

        wh = con.faction_warehouse(world, u["faction_name"])
        if wh is not None:
            military.order_move(world, [u["id"]], wh["tx"], wh["ty"] + 1)
            u["thief_home"] = wh["id"]
    world.fstat(u["faction_name"], "wares_stolen", sum(loot.values()))
    world.events.append({"kind": "stolen", "by": u["faction_name"], "from": b["faction_name"], "wares": loot})


def _do_spy(world: Any, u: dict, b: dict) -> None:
    """Infiltration: a radar dome reveals the victim's land; a tech centre, barracks or factory copies one drafted card the spy's faction lacks."""
    from wizard_rts import military, tech

    me, victim = u["faction_name"], b["faction_name"]
    effect = ""
    if b["kind"] == "dome":
        seen = world.__dict__.setdefault("explored", {}).setdefault(me, set())
        for o in world.buildings.values():
            if o["faction_name"] == victim:
                for dx in range(-8, 9, 2):
                    for dy in range(-8, 9, 2):
                        seen.add((o["tx"] + dx, o["ty"] + dy))
        effect = "reveal"
    elif b["kind"] in ("atek", "stek", "barracks", "vehicle_factory", "afld", "hpad", "naval_yard", "scriptorium"):
        mine = set(world.tech.get(me, {}).get("cards", []))
        steal = [c for c in world.tech.get(victim, {}).get("cards", []) if c not in mine]
        if steal:
            card = sorted(steal)[-1]
            world.tech[me]["cards"].append(card)
            tech._apply_effect(world, me, tech.lookup()[card])
            effect = "card:" + card
    world.fstat(me, "infiltrations")
    world.events.append({"kind": "infiltrated", "by": me, "victim": victim, "building": b["id"], "effect": effect})
    military.kill_unit(world, u, u["id"]) if effect == "" and False else None
    u["hp"] = u["hp"]  # the spy walks out again


def _thief_deposit(world: Any, u: dict) -> None:
    if not u.get("cargo") or not u.get("thief_home"):
        return
    home = world.buildings.get(u["thief_home"])
    if home is None or int(home.get("hp", 1)) <= 0:
        return
    if _dist(u, home) <= 2.5:
        from wizard_rts.economy import _supply

        for ware, n in sorted(u["cargo"].items()):
            _supply(world, home["id"]).add_wares(ware, int(n))
        world.events.append({"kind": "loot_delivered", "faction": u["faction_name"], "wares": dict(u["cargo"])})
        u["cargo"] = {}
        u.pop("thief_home", None)


# ------------------------------------------------------------------ mines

def lay_mine(world: Any, unit_id: str) -> dict[str, Any]:
    u = world.units.get(unit_id)
    if u is None or u["definition"] != "openra.mnly" or int(u.get("ammo", 0)) <= 0:
        return {"status": "rejected", "reason": "cannot_lay"}
    if any(b.get("kind") == "mine" and (b["tx"], b["ty"]) == (u["tx"], u["ty"]) for b in world.buildings.values()):
        return {"status": "rejected", "reason": "mine_here"}
    bid = world._building(u["faction"], u["faction_name"], "mine", (u["tx"], u["ty"]), "Mine", "dmb.mine", block=False)
    b = world.buildings[bid]
    b["hp"] = b["max_hp"] = 100
    b["armor"] = "None"
    b["hidden"] = True
    u["ammo"] = int(u["ammo"]) - 1
    world.events.append({"kind": "mine_laid", "by": unit_id, "tile": [u["tx"], u["ty"]]})
    return {"status": "ok", "mine": bid}


def _mines_step(world: Any) -> None:
    for b in list(world.buildings.values()):
        if b.get("kind") != "mine" or int(b.get("hp", 0)) <= 0:
            continue
        for u in world.units.values():
            if u.get("alive", True) and not u.get("inside") and u["faction"] != b["faction"] and u.get("loco") not in ("fly",) and (u["tx"], u["ty"]) == (b["tx"], b["ty"]):
                from wizard_rts import military

                u["hp"] = max(0, int(u["hp"]) - MINE_DAMAGE)
                world.effects.append({"t": "explosion", "x1": b["tx"], "y1": b["ty"], "x2": b["tx"], "y2": b["ty"], "ttl_ms": 700, "keep": 2, "p": "mine"})
                b["hp"] = 0
                world.buildings.pop(b["id"], None)
                if u["hp"] <= 0:
                    military.kill_unit(world, u, b["id"])
                break


# ------------------------------------------------------------------ medics, mechanics, depots, aircraft

def _heal_step(world: Any, u: dict) -> None:
    kind = {"openra.medi": "infantry", "openra.mech": "vehicle"}.get(u["definition"])
    if kind is None:
        return
    u["heal_ms"] = max(0, int(u.get("heal_ms", 0)) - QUANTUM_MS)
    if u["heal_ms"] > 0:
        return
    w = rules.weapon("Heal" if kind == "infantry" else "Repair")
    amount = abs(int(w["warheads"][0]["damage"])) if w else 3000
    rng = float(w["range"]) if w else 4.0
    best = None
    for o in _live_units(world, u["faction_name"]):
        if o is u or int(o["hp"]) >= int(o["max_hp"]):
            continue
        if (kind == "infantry" and is_infantry(o)) or (kind == "vehicle" and is_vehicle(o) and o.get("loco") != "fly"):
            d = _dist(u, o)
            if d <= rng and (best is None or d < best[0]):
                best = (d, o)
    if best is None:
        return
    o = best[1]
    o["hp"] = min(int(o["max_hp"]), int(o["hp"]) + amount)
    u["heal_ms"] = HEAL_MS
    u["status"] = "healing"
    world.stats["healed"] = world.stats.get("healed", 0) + 1
    world.effects.append({"t": "shot", "x1": u["tx"], "y1": u["ty"], "x2": o["tx"], "y2": o["ty"], "ttl_ms": 300, "keep": 2, "p": "heal"})


def _depot_step(world: Any, b: dict, dt: int = QUANTUM_MS) -> None:
    """Service depot / helipad / airfield: repairs friendly units on or next to it, paying iron from its own stock; pads also rearm aircraft."""
    kind = b["kind"]
    if kind not in ("fix", "hpad", "afld"):
        return
    b["svc_ms"] = int(b.get("svc_ms", 0)) + dt
    if b["svc_ms"] < REPAIR_STEP_MS:
        return
    b["svc_ms"] = 0
    stock = world.stocks.setdefault(b["id"], {})
    for u in _live_units(world, b["faction_name"]):
        if _dist(u, b) > DEPOT_RADIUS:
            continue
        if kind == "fix" and not (is_vehicle(u) and u.get("loco") != "fly"):
            continue
        if kind == "hpad" and not (u.get("loco") == "fly" and u["definition"] in ("openra.heli", "openra.mh60", "openra.tran")):
            continue
        if kind == "afld" and not (u.get("loco") == "fly" and u["definition"] in ("openra.yak", "openra.mig")):
            continue
        if int(u["hp"]) < int(u["max_hp"]) and int(stock.get("iron", 0)) >= 1:
            step = max(1, int(u["max_hp"]) // 8)
            u["hp"] = min(int(u["max_hp"]), int(u["hp"]) + step)
            u["repair_paid"] = float(u.get("repair_paid", 0.0)) + step / u["max_hp"]
            if u["repair_paid"] >= DEPOT_IRON_PER_HP * 4 * 0.25:
                u["repair_paid"] = 0.0
                stock["iron"] = int(stock["iron"]) - 1
                if stock["iron"] <= 0:
                    stock.pop("iron")
                world.stats["consumed_iron"] = world.stats.get("consumed_iron", 0) + 1
        if u.get("ammo_max") and int(u.get("ammo", 0)) < int(u["ammo_max"]):
            u["rearm_ms"] = int(u.get("rearm_ms", 0)) + REPAIR_STEP_MS
            if u["rearm_ms"] >= REARM_MS and int(stock.get("iron", 0)) >= 1:
                u["rearm_ms"] = 0
                u["ammo"] = min(int(u["ammo_max"]), int(u["ammo"]) + max(1, int(u["ammo_max"]) // 4))
                stock["iron"] = int(stock["iron"]) - 1
                if stock["iron"] <= 0:
                    stock.pop("iron")
                world.stats["consumed_iron"] = world.stats.get("consumed_iron", 0) + 1


def init_unit_extras(unit: dict) -> None:
    """Called for every new unit: aircraft and minelayers get an ammunition pool from the imported AmmoPool trait."""
    r = rules.actor(unit.get("definition", ""))
    if not r:
        return
    ab = r.get("abilities") or {}
    pool = ab.get("AmmoPool") or next((v for k, v in ab.items() if k.startswith("AmmoPool")), None)
    if pool and pool.get("Ammo"):
        unit["ammo_max"] = unit["ammo"] = int(pool["Ammo"])
    if r.get("locomotor") == "fly":
        unit["loco"] = "fly"
    if unit["definition"] == "openra.dog":
        pass


def spend_ammo(world: Any, unit: dict) -> bool:
    """Called before a volley: aircraft and minelayers fire from a finite pool. False when empty (the unit must rearm)."""
    if not unit.get("ammo_max"):
        return True
    if int(unit.get("ammo", 0)) <= 0:
        return False
    unit["ammo"] = int(unit["ammo"]) - 1
    return True


def _rearm_orders(world: Any, u: dict) -> None:
    """An aircraft with no ammunition flies home to the nearest pad of the right kind and waits there."""
    if u.get("loco") != "fly" or not u.get("ammo_max") or int(u.get("ammo", 0)) > 0:
        return
    pad_kind = "hpad" if u["definition"] in ("openra.heli", "openra.mh60", "openra.tran") else "afld"
    pads = sorted(_own_buildings(world, u["faction_name"], pad_kind), key=lambda b: (_dist(u, b), b["id"]))
    o = u.get("order")
    if pads and (o is None or o.get("kind") != "rearm"):
        u["order"] = {"kind": "move", "tile": [pads[0]["tx"], pads[0]["ty"]]}
        u["target"] = None
        u["rearming"] = True
    if u.get("rearming") and int(u.get("ammo", 0)) >= int(u["ammo_max"]):
        u["rearming"] = False


# ------------------------------------------------------------------ jammers, gap generators, MAD tank

def _jam_step(world: Any) -> None:
    jammers = [u for u in _live_units(world) if u["definition"] == "openra.mrj"]
    if not jammers:
        return
    keep = []
    for p in world.projectiles:
        if "Missile" in str(p.get("p", "")):
            sh = world.units.get(p["shooter"]) or world.buildings.get(p["shooter"])
            tgt = world.units.get(p["target"]["id"]) if p["target"]["kind"] == "unit" else world.buildings.get(p["target"]["id"])
            if sh is not None and tgt is not None:
                if any(j["faction"] != sh["faction"] and _dist(j, tgt) <= 5.0 for j in jammers):
                    world.stats["missiles_jammed"] = world.stats.get("missiles_jammed", 0) + 1
                    continue
        keep.append(p)
    world.projectiles[:] = keep


def shrouded(world: Any, target: dict, attacker: dict) -> bool:
    """A gap generator (or its mobile twin) hides everything within its radius from enemies that are not close (CreatesShroud)."""
    gens = world.__dict__.get("_gap_sources")
    if not gens:
        return False
    for g in gens:
        if g["faction"] != attacker["faction"] and g["faction"] == target["faction"] and _dist(g, target) <= g["r"] and _dist(attacker, target) > 3.0:
            return True
    return False


def _gap_cache(world: Any) -> None:
    out = []
    for b in world.buildings.values():
        if b["kind"] == "gap" and b.get("operational") and int(b.get("hp", 1)) > 0:
            out.append({"faction": b["faction"], "tx": b["tx"], "ty": b["ty"], "r": 7.0})
    for u in world.units.values():
        if u.get("alive", True) and u["definition"] == "openra.mgg":
            out.append({"faction": u["faction"], "tx": u["tx"], "ty": u["ty"], "r": 7.0})
    world._gap_sources = out


def _mad_step(world: Any, u: dict) -> None:
    if u["definition"] != "openra.qtnk" or u.get("deployed_ms") is None:
        return
    u["deployed_ms"] += QUANTUM_MS
    if u["deployed_ms"] >= 3000:
        u["deployed_ms"] = None
        for e in list(world.units.values()):
            if e.get("alive", True) and not e.get("inside") and e["id"] != u["id"] and e.get("loco") != "fly" and _dist(e, u) <= MAD_RADIUS and is_vehicle(e):
                e["hp"] = max(0, int(e["hp"]) - int(e["max_hp"]) * MAD_DAMAGE_PCT // 100)
                if e["hp"] <= 0:
                    from wizard_rts import military

                    military.kill_unit(world, e, u["id"])
        for b in list(world.buildings.values()):
            if "hp" in b and int(b["hp"]) > 0 and _dist(b, u) <= MAD_RADIUS and b["kind"] != "mine":
                world.damage_building(b["id"], int(b["max_hp"]) * MAD_DAMAGE_PCT // 100, ["structure"], {}, by=u["id"])
        world.effects.append({"t": "explosion", "x1": u["tx"], "y1": u["ty"], "x2": u["tx"], "y2": u["ty"], "ttl_ms": 1200, "keep": 3, "p": "mad"})


# ------------------------------------------------------------------ support powers

def power_status(world: Any, b: dict) -> dict[str, Any] | None:
    kind = POWER_OF.get(b["kind"])
    if kind is None or not b.get("operational") or b.get("constructing"):
        return None
    cfg = {"nuke": NUKE, "curtain": CURTAIN, "chrono": CHRONO, "paradrop": PARADROP}[kind]
    ready_ms = int(b.get("power_ready_ms", 0))
    stock = world.stocks.get(b["id"], {})
    paid = all(int(stock.get(g, 0)) >= n for g, n in cfg["cost"].items())
    return {"power": kind, "charged": _now(world) >= ready_ms, "charge_left_ms": max(0, ready_ms - _now(world)), "cost": dict(cfg["cost"]), "paid": paid}


def use_power(world: Any, faction: str, building_id: str, tx: int, ty: int, tx2: int | None = None, ty2: int | None = None) -> dict[str, Any]:
    b = world.buildings.get(building_id)
    if b is None or b["faction_name"] != faction:
        return {"status": "rejected", "reason": "not_yours"}
    st = power_status(world, b)
    if st is None:
        return {"status": "rejected", "reason": "no_power"}
    if not st["charged"]:
        return {"status": "rejected", "reason": "charging", "left_ms": st["charge_left_ms"]}
    if not st["paid"]:
        return {"status": "rejected", "reason": "needs_wares", "cost": st["cost"]}
    if not world.tile_in_bounds(int(tx), int(ty)):
        return {"status": "rejected", "reason": "outside_map"}
    kind = st["power"]
    cfg = {"nuke": NUKE, "curtain": CURTAIN, "chrono": CHRONO, "paradrop": PARADROP}[kind]
    if kind == "curtain":
        tgt = _find_target(world, faction, int(tx), int(ty), CURTAIN["radius"])
        if tgt is None:
            return {"status": "rejected", "reason": "no_target"}
    if kind == "chrono":
        if tx2 is None or ty2 is None or math.hypot(int(tx2) - int(tx), int(ty2) - int(ty)) > CHRONO["range"] or world.tile_speed("foot", int(tx2), int(ty2)) <= 0 and world.tile_speed("tracked", int(tx2), int(ty2)) <= 0:
            return {"status": "rejected", "reason": "bad_destination"}
    stock = world.stocks.setdefault(b["id"], {})
    for g, n in cfg["cost"].items():
        stock[g] = int(stock.get(g, 0)) - n
        if stock[g] <= 0:
            stock.pop(g)
        world.stats["consumed_" + g] = world.stats.get("consumed_" + g, 0) + n
    b["power_ready_ms"] = _now(world) + cfg["charge_ms"]
    queue = world.__dict__.setdefault("power_events", [])
    if kind == "nuke":
        queue.append({"kind": "nuke", "due": _now(world) + NUKE["delay_ms"], "tx": int(tx), "ty": int(ty), "by": b["id"], "faction": faction})
        world.events.append({"kind": "nuke_launched", "faction": faction, "tx": int(tx), "ty": int(ty)})
    elif kind == "curtain":
        tgt["invuln_until_ms"] = _now(world) + CURTAIN["duration_ms"]
        world.events.append({"kind": "iron_curtain", "faction": faction, "target": tgt["id"]})
    elif kind == "chrono":
        moved = []
        for u in _live_units(world, faction):
            if math.hypot(u["tx"] - int(tx), u["ty"] - int(ty)) <= CHRONO["radius"] and u.get("loco") != "fly":
                dest = _free_tile(world, u, (int(tx2), int(ty2)))
                if dest is not None:
                    moved.append({"unit": u["id"], "home": [u["tx"], u["ty"]]})
                    u["tx"], u["ty"], u["path"] = dest[0], dest[1], []
        queue.append({"kind": "chrono_return", "due": _now(world) + CHRONO["duration_ms"], "moves": moved})
        world.events.append({"kind": "chronoshift", "faction": faction, "units": len(moved)})
    elif kind == "paradrop":
        for k in range(PARADROP["count"]):
            u_id = world._unit(b["faction"], faction, "infantry", "Rifleman", "openra.e1", (int(tx), int(ty)))
            spot = _free_tile(world, world.units[u_id], (int(tx), int(ty)))
            if spot:
                world.units[u_id]["tx"], world.units[u_id]["ty"] = spot
        world.events.append({"kind": "paradrop", "faction": faction, "tx": int(tx), "ty": int(ty)})
    return {"status": "ok", "power": kind}


def _find_target(world: Any, faction: str, tx: int, ty: int, r: float) -> dict | None:
    best = None
    for pool in (world.units.values(), world.buildings.values()):
        for e in pool:
            if e["faction_name"] != faction or ("hp" in e and int(e["hp"]) <= 0) or e.get("alive") is False or e.get("inside"):
                continue
            d = math.hypot(e["tx"] - tx, e["ty"] - ty)
            if d <= r and (best is None or d < best[0]):
                best = (d, e)
    return best[1] if best else None


def _power_events_step(world: Any) -> None:
    q = world.__dict__.get("power_events")
    if not q:
        return
    now = _now(world)
    keep = []
    for ev in q:
        if ev["due"] > now:
            keep.append(ev)
            continue
        if ev["kind"] == "nuke":
            centre = {"id": "nuke", "tx": ev["tx"], "ty": ev["ty"], "faction": ev["faction"], "kind": "nuke"}
            _blast(world, centre, NUKE["radius"], NUKE["damage"], ev["by"], friendly=True)
            world.events.append({"kind": "nuke_detonated", "tx": ev["tx"], "ty": ev["ty"]})
        elif ev["kind"] == "chrono_return":
            for m in ev["moves"]:
                u = world.units.get(m["unit"])
                if u is not None and u.get("alive", True):
                    home = _free_tile(world, u, tuple(m["home"])) or tuple(m["home"])
                    u["tx"], u["ty"], u["path"] = home[0], home[1], []
    world.power_events = keep


# ------------------------------------------------------------------ the quantum

def ability_quantum(world: Any) -> None:
    _gap_cache(world)
    _carry_passengers(world)
    for u in list(world.units.values()):
        if not u.get("alive", True) or u.get("inside"):
            continue
        if u.get("order") and u["order"].get("kind") == "board":
            _boarding_step(world, u)
        elif u.get("order") and u["order"].get("kind") in ("capture", "infiltrate"):
            _order_step(world, u)
        if u["definition"] in ("openra.medi", "openra.mech"):
            _heal_step(world, u)
        if u["definition"] == "openra.qtnk":
            _mad_step(world, u)
        if u.get("cargo") and u.get("thief_home"):
            _thief_deposit(world, u)
        if u.get("ammo_max"):
            _rearm_orders(world, u)
    if world.military_quanta % 5 == 0:
        for b in world.buildings.values():
            if b["kind"] in ("fix", "hpad", "afld") and b.get("operational") and not b.get("constructing") and int(b.get("hp", 1)) > 0:
                _depot_step(world, b, 500)
    _mines_step(world)
    _jam_step(world)
    _power_events_step(world)

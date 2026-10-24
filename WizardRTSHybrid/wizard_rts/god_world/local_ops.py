"""Local operations: the living village (docs/PLAN_GOD_WORLD_LIVING.md stage B; docs/PLAN_GOD_WORLD_PANDEMIC.md stage 2).

Each active village runs a small network on the shared clock: sites (hub, producers, support, processors, machines, the military facility) with
typed buffers of OPERATING goods, agents (workers, carriers, trucks, builders) with routed tasks, trees that are felled and regrow, belts and pipes,
processors with recipes. Everything is in operating units (logs, granite, ore packets) and lives only here: the strategic five-slot ledger is never
read for spending nor written. The bridge is one way: the village's age, level and development (D50) decide what is built and how many work; a
blocked chain changes the picture, never a receipt. Randomness is the village's own LCG stream, saved with it. Every job, cargo, buffer and
construction is saved in the village record, so a reload resumes mid-haul and mid-build.

Growth (D50): the planner lays out the whole eventual network once as a blueprint of slots per district; founding commissions the hub, the
military facility, one seed producer per district and a small processing allowance; every successful matching roll unlocks one more slot in that
district (`growth_ticket`), up to `pips x level`. Construction (D51): every commissioned site goes PLANNED, RESERVED, FOUNDATION, BUILDING,
COMPLETED under a bounded crew of builders who walk to the site and work there; nothing operates before completion.

Worker behaviour is adapted from the Widelands worker programs transcribed in `programs_data.py`, carriers from `carrier.cc`'s fetch-and-deliver
loop, construction from `constructionsite.cc`'s staged progress; see docs/SOURCE_REUSE.md."""

from __future__ import annotations

import math
from typing import Any

from . import planner, rules

QUANTUM_MS = 100
BELT_SPEED = 1.6  # tiles per second along a belt (Mindustry's basic conveyor moves ~4.2 items/s over 8 px tiles; scaled to this world's pace)
BELT_SPACING = 0.55  # tiles between packets: the belt's capacity
PIPE_FLOW_MS = 1500  # one unit of water passes a pipe every so often
TREE_REGROW_MS = 150_000
SAPLING_GROW_MS = 45_000
TREE_CLAIM_RADIUS = 1.3  # units from the plot: the woodland a village works
PLANT_RADIUS = 4.5  # tiles around a forester's work spot where new saplings go
NO_WORK_WAIT_MS = 6000
CONSTRUCTION = ("planned", "reserved", "foundation", "building")
BUILD_MS = {"hub": 14000, "producer": 10000, "support": 9000, "processor": 16000, "military": 12000, "generator": 10000, "pump": 8000, "tank": 10000, "factory": 20000}
FOUNDATION_FRACTION = 0.3
BUILD_ORDER = {"hub": 0, "producer": 1, "military": 2, "support": 3, "processor": 4, "pump": 5, "tank": 6, "generator": 7, "factory": 8}  # the crew's priority among jobs planned together
BUILDER_ART = {1: "widelands.barbarians_carrier_worker", 2: "widelands.barbarians_carrier_worker", 3: "openra.e6", 4: "openra.e6"}


class _Rng:
    @staticmethod
    def next(ops: dict[str, Any]) -> float:
        ops["rng"] = (int(ops["rng"]) * 1103515245 + 12345) & 0x7FFFFFFF
        return ops["rng"] / float(0x7FFFFFFF)


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def built(s: dict[str, Any]) -> bool:
    return bool(s.get("commissioned")) and s["state"] not in CONSTRUCTION


# ------------------------------------------------------------------ development slots (D50)

def init_dev(world, v: dict[str, Any]) -> dict[str, Any]:
    """The per-district development record for this village's age and level: capacity, unlocked places (one at founding), receipts."""
    caps = planner.budget(world.board, v["node"], max(1, int(v["level"])))
    dev = v.setdefault("dev", {})
    for hid, cap in caps.items():
        rec = dev.setdefault(hid, {"cap": cap, "unlocked": 1, "receipts": [], "revision": int(world.production_revision), "epoch": int(world.epoch)})
        if rec.get("revision") != int(world.production_revision) or rec.get("epoch") != int(world.epoch):
            rec.update({"cap": cap, "unlocked": 1, "receipts": [], "revision": int(world.production_revision), "epoch": int(world.epoch)})
        rec["cap"] = cap  # a city raises the cap without filling it
        rec["unlocked"] = max(1, min(int(rec["unlocked"]), cap))
    for hid in list(dev):
        if hid not in caps:
            del dev[hid]
    return dev


def growth_ticket(world, v: dict[str, Any], hid: str, roll_id: str) -> bool:
    """A successful matching roll unlocks one further development place in that district, once per receipt (P05, P06)."""
    if v["status"] != "operational":
        return False
    dev = init_dev(world, v)
    rec = dev.get(hid)
    if rec is None:
        return False
    if roll_id in rec["receipts"]:
        return False
    rec["receipts"].append(roll_id)
    if len(rec["receipts"]) > 64:
        del rec["receipts"][: len(rec["receipts"]) - 64]
    if int(rec["unlocked"]) >= int(rec["cap"]):
        return False
    rec["unlocked"] = int(rec["unlocked"]) + 1
    ops = v.get("ops")
    if ops is not None:
        commission_next(world, v, ops, hid)
    return True


def district_commissioned(ops: dict[str, Any], hid: str) -> int:
    return sum(1 for s in ops["sites"].values() if s.get("district") == hid and s.get("commissioned") and not s.get("allowance"))


def commission_next(world, v: dict[str, Any], ops: dict[str, Any], hid: str) -> dict[str, Any] | None:
    """Commission the next latent slot of a district when its unlocked places allow it."""
    rec = (v.get("dev") or {}).get(hid)
    if rec is None:
        return None
    if district_commissioned(ops, hid) >= int(rec["unlocked"]):
        return None
    latent = sorted((s for s in ops["sites"].values() if s.get("district") == hid and not s.get("commissioned")), key=lambda s: int(s.get("slot", 0)))
    if not latent:
        return None
    s = latent[0]
    _commission(world, ops, s)
    return s


def _commission(world, ops: dict[str, Any], s: dict[str, Any], allowance: bool = False) -> None:
    s["commissioned"] = True
    s["allowance"] = bool(allowance or s.get("allowance", False))
    s["state"] = "planned"
    s["planned_ms"] = int(world.game_ms)
    s["work_done_ms"] = 0
    s["build_ms"] = int(BUILD_MS.get(s["kind"], 10000))


# ------------------------------------------------------------------ planning and (re)building

def ensure(world, v: dict[str, Any]) -> dict[str, Any] | None:
    """The village's ops record, planned or re-planned when its age, level or the production revision changed. Pending/historical villages have none."""
    if v["status"] not in ("operational", "rebuilding", "building"):
        return None
    ops = v.get("ops")
    age, level = int(v["age"]), max(1, int(v["level"]))
    rev = int(world.production_revision)
    if ops is not None and ops.get("age") == age and ops.get("level") == level and ops.get("revision") == rev:
        return ops
    p = planner.plan(world, v)
    now = int(world.game_ms)
    old_sites = dict(ops.get("sites", {})) if ops else {}
    old_agents = dict(ops.get("agents", {})) if ops else {}
    same_age = ops is not None and ops.get("age") == age
    sites: dict[str, dict[str, Any]] = {}
    for s in p["sites"]:
        prev = old_sites.get(s["id"]) if same_age else None
        rec = dict(s)
        if prev is not None:
            rec.update({k: prev[k] for k in ("state", "in", "out", "progress_ms", "water", "produced", "commissioned", "allowance", "planned_ms", "work_done_ms", "build_ms", "fuel_ms", "turn") if k in prev})
            rec["in"] = dict(prev.get("in", {}))
            rec["out"] = dict(prev.get("out", {}))
        else:
            rec.update({"state": "latent", "in": {}, "out": {}, "progress_ms": 0, "water": 0, "produced": 0, "commissioned": False, "allowance": False})
        rec["reserved_out"] = 0
        rec["reserved_in"] = {}
        sites[s["id"]] = rec
    old_segs = dict(ops.get("segments", {})) if ops else {}
    segments: dict[str, dict[str, Any]] = {}
    for seg in p.get("segments", []):
        prev = old_segs.get(seg["id"]) if same_age else None
        rec = dict(seg)
        rec["items"] = list(prev["items"]) if prev and prev.get("from") == seg["from"] and prev.get("to") == seg["to"] else []
        rec["fill"] = float(prev.get("fill", 0.0)) if prev else 0.0
        rec["broken"] = bool(prev.get("broken", False)) if prev else False
        rec["flow_ms"] = 0
        segments[seg["id"]] = rec
    new_ops: dict[str, Any] = {"age": age, "level": level, "revision": rev, "version": int(ops.get("version", 0)) + 1 if ops else 1,
                               "rng": int(ops["rng"]) if ops else (world.seed * 7 + sum(ord(c) for c in v["id"])) & 0x7FFFFFFF,
                               "sites": sites, "agents": {}, "hub": ops.get("hub") if ops else {"stock": {}, "shipped": {}, "received": 0}, "trees": ops.get("trees") if ops else {},
                               "carriers": int(p["carriers"]), "transport": p["transport"], "capacity": p["capacity"], "log": ops.get("log", [])[-8:] if ops else [], "throughput": {},
                               "segments": segments, "power": True, "units_made": int(ops.get("units_made", 0)) if ops else 0, "crews": 2 if level >= 2 else 1,
                               "allowance": 3 if level >= 2 else 1, "planned_ms": now}
    v["ops"] = new_ops
    dev = init_dev(world, v)
    # commissioning: the hub and the military facility, one seed producer per district, the village's processing allowance, the age's infrastructure
    if not same_age:
        for s in sites.values():
            if s["kind"] in ("hub", "military") or (s["kind"] in ("generator", "pump", "tank", "factory")) or s.get("support"):
                _commission(world, new_ops, s)
        for hid in dev:
            commission_next(world, v, new_ops, hid)
        allowance = int(new_ops["allowance"])
        for s in sorted((s for s in sites.values() if s["kind"] in ("processor", "support") and s.get("district") and not s.get("commissioned")),
                        key=lambda s: (-int(dev.get(s.get("district", ""), {}).get("cap", 0)), 0 if s["kind"] == "processor" else 1, int(s.get("slot", 0)))):
            if allowance <= 0:
                break
            _commission(world, new_ops, s, allowance=True)
            allowance -= 1
        new_ops["allowance"] = allowance
    else:
        for hid in dev:  # a city: the cap rose, places already unlocked may now be filled
            commission_next(world, v, new_ops, hid)
    # agents: builders for the crew, workers for built sites, carriers for the village; keep the ones whose ids survive
    hub = sites[f"{v['id']}:hub"]
    for k in range(int(new_ops["crews"])):
        aid = f"{v['id']}:b{k}"
        prev = old_agents.get(aid)
        rec = dict(prev) if prev else {"id": aid, "site": hub["id"], "x": hub["ex"] - 0.8 + k * 0.6, "y": hub["ey"] + 0.9, "hx": 1.0, "hy": 0.0, "anim": "idle", "cargo": "",
                                       "phase": "idle", "target": None, "wait_ms": 0, "job": None}
        rec.update({"kind": "builder", "art": BUILDER_ART.get(age, BUILDER_ART[1])})
        if not same_age or rec.get("job") not in sites:
            rec.update({"phase": "idle", "job": None})
        new_ops["agents"][aid] = rec
    for s in sites.values():
        if not built(s):
            continue
        _spawn_workers(new_ops, s, old_agents)
    kind = "truck" if p["transport"] == "truck" else "carrier"
    art = planner.chains()["carrier_art"].get(kind, "")
    for k in range(int(p["carriers"])):
        aid = f"{v['id']}:c{k}"
        prev = old_agents.get(aid)
        rec = dict(prev) if prev else {"id": aid, "site": hub["id"], "x": hub["ex"] + (k - p["carriers"] / 2.0) * 0.5, "y": hub["ey"] + 0.6, "hx": 1.0, "hy": 0.0, "anim": "idle",
                                       "cargo": "", "phase": "idle", "target": None, "wait_ms": 0, "job": None}
        rec.update({"kind": kind, "art": art})  # a carrier of the historic age drives a truck in the modern one
        new_ops["agents"][aid] = rec
    _claim_trees(world, v, new_ops)
    _supersede_history(world, v, new_ops)
    return new_ops


def _spawn_workers(ops: dict[str, Any], s: dict[str, Any], old_agents: dict[str, Any] | None = None) -> None:
    n = int(s.get("workers", 0)) if s["kind"] in ("producer", "support") else 0
    for k in range(n):
        aid = f"{s['id']}:w{k}"
        if aid in ops["agents"]:
            continue
        prev = (old_agents or {}).get(aid)
        rec = dict(prev) if prev else {"id": aid, "kind": "worker", "site": s["id"], "x": s["ex"], "y": s["ey"], "hx": 0.0, "hy": 1.0, "anim": "idle", "cargo": "", "phase": "home",
                                       "target": None, "wait_ms": 0}
        rec.update({"art": s.get("worker", ""), "task": s.get("task", ""), "work_anim": s.get("work_anim", ""), "kind": "worker", "site": s["id"]})
        ops["agents"][aid] = rec


def _claim_trees(world, v: dict[str, Any], ops: dict[str, Any]) -> None:
    """The village works the trees of its woodland districts that lie within reach of its plot and are not another village's."""
    board = world.board
    claims = world.tree_claims
    cx, cy = board.node_xy(v["node"])
    reach = TREE_CLAIM_RADIUS * float(board.unit)
    wood = {s["hex"] for s in ops["sites"].values() if s["kind"] == "producer" and s.get("task") == "fell"}
    kept = {}
    for i, t in enumerate(board.trees):
        key = str(i)
        if key in ops["trees"]:
            kept[key] = ops["trees"][key]
            claims[key] = v["id"]
            continue
        if t["hex"] not in wood or claims.get(key, v["id"]) != v["id"]:
            continue
        if _dist((t["x"], t["y"]), (cx, cy)) > reach:
            continue
        claims[key] = v["id"]
        kept[key] = {"x": float(t["x"]), "y": float(t["y"]), "hex": t["hex"], "species": t.get("species", "beech"), "stage": "old", "ms": 0}
    for key, t in ops["trees"].items():
        if key.startswith("p") and key not in kept:
            kept[key] = t  # saplings the forester planted
    ops["trees"] = kept


def _supersede_history(world, v: dict[str, Any], ops: dict[str, Any]) -> None:
    """A new village on a historical node builds over the frozen remains its own buildings cover (D49): never two hubs, never a workshop on a workshop."""
    for h in world.villages.values():
        if h["status"] != "historical" or h["node"] != v["node"] or not h.get("frozen") or h["id"] == v["id"]:
            continue
        for fs in h["frozen"].get("sites", []):
            if fs["kind"] == "hub":
                fs["superseded"] = True
                continue
            if any(_dist((fs["x"], fs["y"]), (s["x"], s["y"])) < 2.2 for s in ops["sites"].values()):
                fs["superseded"] = True
        for seg in h["frozen"].get("segments", []):
            seg["superseded"] = True
        h["frozen"]["streets"] = []


def freeze(world, v: dict[str, Any]) -> None:
    """A village leaves production: its actual built picture is frozen for history (D49), its claims freed, its ops stopped."""
    ops = v.get("ops")
    if ops:
        sites = [{"id": s["id"], "kind": s["kind"], "role": s["role"], "art": s["art"], "name": s["name"], "x": s["x"], "y": s["y"], "props": s.get("props", ""), "superseded": False}
                 for s in ops["sites"].values() if built(s)]
        segs = [{"id": g["id"], "kind": g["kind"], "pts": g["pts"], "superseded": False} for g in ops.get("segments", {}).values()
                if built(ops["sites"].get(g["from"], {"state": "latent"})) and built(ops["sites"].get(g["to"], {"state": "latent"}))]
        hub = next((s for s in ops["sites"].values() if s["kind"] == "hub"), None)
        streets = [[s["ex"], s["ey"], hub["ex"], hub["ey"]] for s in ops["sites"].values() if hub and built(s) and s["kind"] in ("producer", "processor", "support", "military")]
        v["frozen"] = {"age": int(v["age"]), "sites": sites, "segments": segs, "streets": streets if ops["transport"] != "belt" else [], "name": v["name"], "faction": v["faction"]}
    release(world, v)


def release(world, v: dict[str, Any]) -> None:
    """A village leaves production (historical, cancelled): its tree claims are freed and its ops stop."""
    ops = v.get("ops")
    if ops:
        for key in list(ops.get("trees", {})):
            if world.tree_claims.get(key) == v["id"]:
                world.tree_claims.pop(key, None)
    v.pop("ops", None)


def complete_all(world, v: dict[str, Any]) -> dict[str, Any]:
    """Tests and fixtures only: commission every slot of the blueprint and finish construction at once."""
    ops = ensure(world, v)
    assert ops is not None
    for hid, rec in (v.get("dev") or {}).items():
        rec["unlocked"] = rec["cap"]
    for s in ops["sites"].values():
        if not s.get("commissioned"):
            _commission(world, ops, s)
        s["state"] = "idle"
        s["work_done_ms"] = int(s.get("build_ms", 0))
        _spawn_workers(ops, s)
    for a in ops["agents"].values():
        if a["kind"] == "builder":
            a.update({"phase": "idle", "job": None})
    return ops


# ------------------------------------------------------------------ the step

def step_all(world) -> None:
    for vid in sorted(world.villages):
        v = world.villages[vid]
        if v["status"] not in ("operational", "rebuilding"):
            continue
        ops = ensure(world, v)
        if ops is None:
            continue
        step(world, v, ops, QUANTUM_MS)


def step(world, v: dict[str, Any], ops: dict[str, Any], dt_ms: int) -> None:
    caps = planner.chains()["caps"]
    sites = ops["sites"]
    for s in sites.values():
        if not built(s):
            continue
        if s["kind"] == "processor":
            _step_processor(s, ops, dt_ms, caps)
        elif s["kind"] == "producer" and not s.get("worker"):
            _step_machine(s, ops, dt_ms, caps)
        elif s["kind"] == "generator":
            _step_generator(s, ops, dt_ms)
        elif s["kind"] == "pump":
            _step_pump(s, ops, dt_ms)
        elif s["kind"] == "factory":
            _step_factory(world, v, s, ops, dt_ms, caps)
    _step_segments(ops, dt_ms, caps)
    for key, t in ops["trees"].items():
        if t["stage"] in ("stump", "sapling"):
            t["ms"] = int(t["ms"]) - dt_ms
            if t["ms"] <= 0:
                t["stage"] = "old"
                t["ms"] = 0
    for aid in sorted(ops["agents"]):
        a = ops["agents"][aid]
        if a["kind"] == "worker":
            _step_worker(world, v, ops, a, dt_ms, caps)
        elif a["kind"] == "builder":
            _step_builder(world, v, ops, a, dt_ms)
        else:
            _step_carrier(world, v, ops, a, dt_ms, caps)


def _move(a: dict[str, Any], target: tuple[float, float], speed: float, dt_ms: int) -> bool:
    """Move toward the target; heading follows the motion. Returns True on arrival."""
    dx, dy = target[0] - a["x"], target[1] - a["y"]
    d = math.hypot(dx, dy)
    stepd = speed * dt_ms / 1000.0
    if d <= stepd or d < 1e-6:
        a["x"], a["y"] = target[0], target[1]
        return True
    a["hx"], a["hy"] = dx / d, dy / d
    a["x"] += a["hx"] * stepd
    a["y"] += a["hy"] * stepd
    return False


def _speed(kind: str) -> float:
    return float(planner.chains()["speeds_tiles_per_s"].get(kind, 1.6))


def _site_of(ops: dict[str, Any], a: dict[str, Any]) -> dict[str, Any] | None:
    return ops["sites"].get(a["site"])


# ------------------------------------------------------------------ construction (D51)

def _step_builder(world, v: dict[str, Any], ops: dict[str, Any], a: dict[str, Any], dt_ms: int) -> None:
    speed = _speed("worker")
    phase = a["phase"]
    if a["wait_ms"] > 0:
        a["wait_ms"] -= dt_ms
        if a["wait_ms"] > 0:
            return
    if phase == "idle":
        queue = sorted((s for s in ops["sites"].values() if s.get("commissioned") and s["state"] == "planned"), key=lambda s: (int(s.get("planned_ms", 0)), BUILD_ORDER.get(s["kind"], 9), s["id"]))
        if not queue:
            a["anim"] = "idle"
            a["wait_ms"] = 1000
            return
        s = queue[0]
        s["state"] = "reserved"
        s["crew"] = a["id"]
        a["job"] = s["id"]
        a["phase"] = "to_site"
        a["anim"] = "walkload"
        a["cargo"] = ""
    elif phase == "to_site":
        s = ops["sites"].get(a.get("job") or "")
        if s is None:
            a["job"], a["phase"] = None, "idle"
            return
        if _move(a, (s["ex"], s["ey"]), speed, dt_ms):
            a["phase"] = "building"
            a["anim"] = "build"
            if s["state"] == "reserved":
                s["state"] = "foundation"
    elif phase == "building":
        s = ops["sites"].get(a.get("job") or "")
        if s is None:
            a["job"], a["phase"] = None, "idle"
            return
        s["work_done_ms"] = int(s.get("work_done_ms", 0)) + dt_ms
        total = max(1, int(s.get("build_ms", 10000)))
        if s["state"] == "foundation" and s["work_done_ms"] >= total * FOUNDATION_FRACTION:
            s["state"] = "building"
        if s["work_done_ms"] >= total:
            s["state"] = "idle"
            s["completed_ms"] = int(world.game_ms)
            s.pop("crew", None)
            _spawn_workers(ops, s)
            ops["log"].append({"kind": "built", "site": s["id"], "name": s["name"], "game_ms": int(world.game_ms)})
            ops["log"] = ops["log"][-8:]
            a["job"] = None
            a["phase"] = "to_home"
            a["anim"] = "walk"
    elif phase == "to_home":
        hub = next(s for s in ops["sites"].values() if s["kind"] == "hub")
        k = int(a["id"].rsplit("b", 1)[-1]) if a["id"].rsplit("b", 1)[-1].isdigit() else 0
        if _move(a, (hub["ex"] - 0.8 + k * 0.6, hub["ey"] + 0.9), speed, dt_ms):
            a["phase"] = "idle"
            a["anim"] = "idle"
            a["wait_ms"] = 600


def build_progress(s: dict[str, Any]) -> float:
    if built(s):
        return 1.0
    if s["state"] in ("latent", "planned", "reserved"):
        return 0.0
    return min(1.0, int(s.get("work_done_ms", 0)) / float(max(1, int(s.get("build_ms", 10000)))))


# ------------------------------------------------------------------ workers

def _work_point(world, v: dict[str, Any], ops: dict[str, Any], s: dict[str, Any]) -> tuple[float, float] | None:
    """Where the worker of this site works next: a standing tree, the quarry face, the hunting ground, a field patch, a stump to plant."""
    task = s.get("task", "")
    board = world.board
    if task == "fell":
        best = None
        for key, t in ops["trees"].items():
            if t["stage"] != "old" or t.get("busy"):
                continue
            d = _dist((t["x"], t["y"]), (s["ex"], s["ey"]))
            if best is None or d < best[0]:
                best = (d, key)
        if best is None:
            return None
        ops["trees"][best[1]]["busy"] = True
        s["_tree"] = best[1]
        t = ops["trees"][best[1]]
        return (t["x"] + 0.3, t["y"] + 0.4)
    if task == "plant":
        best = None
        for key, t in ops["trees"].items():
            if t["stage"] != "stump" or t.get("busy"):
                continue
            d = _dist((t["x"], t["y"]), (s["ex"], s["ey"]))
            if best is None or d < best[0]:
                best = (d, key)
        if best is not None:
            ops["trees"][best[1]]["busy"] = True
            s["_tree"] = best[1]
            t = ops["trees"][best[1]]
            return (t["x"] + 0.3, t["y"] + 0.4)
        # no stump to replant: the forester plants a new sapling on free ground toward the woodland (the ranger's findspace)
        if sum(1 for t in ops["trees"].values() if t["stage"] != "stump") >= 60:
            return None
        wx, wy = board.work_site(s["hex"]) if s.get("hex") else (s["ex"], s["ey"])
        d = _dist((wx, wy), (s["ex"], s["ey"]))
        f = min(1.0, 5.0 / max(d, 1e-6))
        bx, by = s["ex"] + (wx - s["ex"]) * f, s["ey"] + (wy - s["ey"]) * f
        grid = world.terrain
        for _ in range(12):
            ang = _Rng.next(ops) * math.tau
            r = 1.0 + _Rng.next(ops) * PLANT_RADIUS
            x, y = bx + math.cos(ang) * r, by + math.sin(ang) * r
            if grid is not None:
                tx, ty = int(x), int(y)
                if not grid.in_bounds(tx, ty) or grid.cls[ty * grid.w + tx] not in (0, 1, 2):
                    continue
            if any(_dist((x, y), (o["x"], o["y"])) < 1.2 for o in ops["sites"].values()) or any(_dist((x, y), (t["x"], t["y"])) < 0.9 for t in ops["trees"].values()):
                continue
            key = f"p{ops['version']}_{len(ops['trees'])}_{int(_Rng.next(ops) * 1e6)}"
            ops["trees"][key] = {"x": round(x, 2), "y": round(y, 2), "hex": s.get("hex", ""), "species": "beech", "stage": "stump", "ms": SAPLING_GROW_MS, "busy": True}
            s["_tree"] = key
            return (x + 0.3, y + 0.4)
        return None
    if task in ("quarry", "hunt", "field", "tend"):
        if s.get("hex"):
            wx, wy = board.work_site(s["hex"])
        else:
            wx, wy = s["ex"], s["ey"]
        reach = {"quarry": 2.5, "hunt": 5.5, "field": 2.6, "tend": 1.8}[task]
        d = _dist((wx, wy), (s["ex"], s["ey"]))
        if task in ("field", "tend") or d > 9.0:
            lim = 3.0 if task in ("field", "tend") else 7.0
            f = min(1.0, lim / max(d, 1e-6))
            wx, wy = s["ex"] + (wx - s["ex"]) * f, s["ey"] + (wy - s["ey"]) * f
        ang = _Rng.next(ops) * math.tau
        r = _Rng.next(ops) * reach
        return (wx + math.cos(ang) * r, wy + math.sin(ang) * r)
    return None


def _step_worker(world, v: dict[str, Any], ops: dict[str, Any], a: dict[str, Any], dt_ms: int, caps: dict[str, int]) -> None:
    s = _site_of(ops, a)
    if s is None or not built(s):
        a["anim"] = "idle"
        return
    phase = a["phase"]
    if a["wait_ms"] > 0:
        a["wait_ms"] -= dt_ms
        a["anim"] = "idle" if phase != "working" else a["anim"]
        if a["wait_ms"] > 0:
            return
    task = s.get("task", "")
    if phase == "home":
        if s["kind"] == "producer" and int(s["out"].get(s["good"], 0)) >= caps["site_out"]:
            s["state"] = "full"
            a["anim"] = "idle"
            a["wait_ms"] = 1500
            return
        if task == "mine":
            a["phase"] = "working"
            a["anim"] = "inside"
            a["wait_ms"] = int(s["work_ms"])
            s["state"] = "working"
            return
        target = _work_point(world, v, ops, s)
        if target is None:
            s["state"] = "no_work"
            a["anim"] = "idle"
            a["wait_ms"] = NO_WORK_WAIT_MS
            return
        a["target"] = [target[0], target[1]]
        a["phase"] = "to_work"
        a["anim"] = "walk"
        s["state"] = "working"
    elif phase == "to_work":
        if _move(a, (a["target"][0], a["target"][1]), _speed("worker"), dt_ms):
            a["phase"] = "working"
            a["anim"] = a.get("work_anim") or "idle"
            a["wait_ms"] = int(s["work_ms"])
    elif phase == "working":
        key = s.pop("_tree", None)
        if task == "fell" and key in ops["trees"]:
            t = ops["trees"][key]
            t["stage"], t["ms"], t["busy"] = "stump", TREE_REGROW_MS, False
        elif task == "plant" and key in ops["trees"]:
            t = ops["trees"][key]
            t["stage"], t["ms"], t["busy"] = "sapling", SAPLING_GROW_MS, False
        if task == "mine":
            a["phase"] = "home"
            a["anim"] = "idle"
            s["out"][s["good"]] = int(s["out"].get(s["good"], 0)) + 1
            s["produced"] = int(s.get("produced", 0)) + 1
            ops["throughput"][s["good"]] = int(ops["throughput"].get(s["good"], 0)) + 1
            s["state"] = "idle"
            a["x"], a["y"] = s["ex"], s["ey"]
            return
        a["cargo"] = s["good"] if s["kind"] == "producer" else ""
        a["phase"] = "to_home"
        a["anim"] = "walkload" if a["cargo"] else "walk"
        a["target"] = [s["ex"], s["ey"]]
    elif phase == "to_home":
        if _move(a, (s["ex"], s["ey"]), _speed("worker"), dt_ms):
            if a["cargo"]:
                s["out"][a["cargo"]] = int(s["out"].get(a["cargo"], 0)) + 1
                s["produced"] = int(s.get("produced", 0)) + 1
                ops["throughput"][a["cargo"]] = int(ops["throughput"].get(a["cargo"], 0)) + 1
                a["cargo"] = ""
            a["phase"] = "home"
            a["anim"] = "idle"
            s["state"] = "idle"
            a["wait_ms"] = 800


# ------------------------------------------------------------------ machines

def _step_generator(s: dict[str, Any], ops: dict[str, Any], dt_ms: int) -> None:
    """Coal in, power out: the village is powered while the generator burns. No coal, no power (the processors say so)."""
    if int(s.get("fuel_ms", 0)) > 0:
        s["fuel_ms"] = int(s["fuel_ms"]) - dt_ms
        s["state"] = "working"
    elif int(s["in"].get("coal", 0)) > 0:
        s["in"]["coal"] = int(s["in"]["coal"]) - 1
        s["fuel_ms"] = int(s["work_ms"])
        s["state"] = "working"
    else:
        s["state"] = "short"
    ops["power"] = s["state"] == "working"


def _step_pump(s: dict[str, Any], ops: dict[str, Any], dt_ms: int) -> None:
    """A pump at the shore (or a water extractor) fills its outlet pipe one unit at a time."""
    s["progress_ms"] = int(s.get("progress_ms", 0)) + dt_ms
    if s["progress_ms"] < int(s["work_ms"]):
        s["state"] = "working"
        return
    s["progress_ms"] = 0
    pipe = next((g for g in ops.get("segments", {}).values() if g["kind"] == "pipe" and g["from"] == s["id"]), None)
    if pipe is None or pipe.get("broken") or float(pipe.get("fill", 0.0)) >= 1.0:
        s["state"] = "full"
        return
    pipe["fill"] = min(1.0, float(pipe.get("fill", 0.0)) + 0.34)
    s["produced"] = int(s.get("produced", 0)) + 1
    ops["throughput"]["water"] = int(ops["throughput"].get("water", 0)) + 1
    s["state"] = "working"


def _step_factory(world, v: dict[str, Any], s: dict[str, Any], ops: dict[str, Any], dt_ms: int, caps: dict[str, int]) -> None:
    """The ground factory: its recipe in, one unit out, within the garrison quota; beyond the quota it stops (no infinite stream)."""
    if s.get("power") and not ops.get("power", True):
        s["state"] = "unpowered"
        return
    if s["state"] == "working":
        s["progress_ms"] = int(s.get("progress_ms", 0)) + dt_ms
        if s["progress_ms"] >= int(s["work_ms"]):
            s["progress_ms"] = 0
            if world.recruit_at(v, art=s.get("unit", ""), name="Dagger"):
                s["produced"] = int(s.get("produced", 0)) + 1
                ops["units_made"] = int(ops.get("units_made", 0)) + 1
                s["state"] = "idle"
            else:
                s["state"] = "full"
        return
    if s["state"] == "full":
        if world.recruit_at(v, art=s.get("unit", ""), name="Dagger"):
            s["produced"] = int(s.get("produced", 0)) + 1
            ops["units_made"] = int(ops.get("units_made", 0)) + 1
            s["state"] = "idle"
        return
    recipe = s.get("recipe", {})
    if all(int(s["in"].get(g, 0)) >= n for g, n in recipe.items()):
        for g, n in recipe.items():
            s["in"][g] = int(s["in"][g]) - n
        s["state"] = "working"
        s["progress_ms"] = 0
    else:
        s["state"] = "short"


def _step_segments(ops: dict[str, Any], dt_ms: int, caps: dict[str, int]) -> None:
    """Belts: packets pulled from the source's outlet, spaced along the line, delivered at the end when the destination accepts (else they wait and
    the belt backs up). Pipes: a fill level that drains into a tank or a consumer. A broken segment moves nothing; an unbuilt end moves nothing."""
    sites = ops["sites"]
    by_src: dict[str, list[dict[str, Any]]] = {}
    for seg in ops.get("segments", {}).values():
        by_src.setdefault(seg["from"], []).append(seg)
    ordered: list[dict[str, Any]] = []
    for src_id, group in by_src.items():
        group.sort(key=lambda g: (0 if sites.get(g["to"], {}).get("kind") == "generator" else 1, g["id"]))
        turn = int(sites.get(src_id, {}).get("turn", 0)) % max(1, len(group))
        ordered += group[turn:] + group[:turn]
    picked: set[str] = set()
    for seg in ordered:
        if seg.get("broken"):
            continue
        src = sites.get(seg["from"])
        dst = sites.get(seg["to"])
        if src is None or dst is None or not built(src) or not built(dst):
            continue
        if seg["kind"] == "pipe":
            seg["flow_ms"] = int(seg.get("flow_ms", 0)) + dt_ms
            if seg["flow_ms"] < PIPE_FLOW_MS:
                continue
            seg["flow_ms"] = 0
            if src["kind"] == "tank" and int(src.get("water", 0)) > 0 and float(seg.get("fill", 0.0)) < 1.0:
                src["water"] = int(src["water"]) - 1
                seg["fill"] = min(1.0, float(seg.get("fill", 0.0)) + 0.34)
            if float(seg.get("fill", 0.0)) >= 0.34:
                if dst["kind"] == "tank":
                    if int(dst.get("water", 0)) < int(dst.get("cap", 12)):
                        dst["water"] = int(dst.get("water", 0)) + 1
                        seg["fill"] = max(0.0, float(seg["fill"]) - 0.34)
                        dst["state"] = "working" if int(dst["water"]) < int(dst.get("cap", 12)) else "full"
                elif int(dst.get("water", 0)) < 4:
                    dst["water"] = int(dst.get("water", 0)) + 1
                    seg["fill"] = max(0.0, float(seg["fill"]) - 0.34)
            continue
        length = float(seg.get("length", 1.0))
        step_t = BELT_SPEED * dt_ms / 1000.0 / length
        spacing = BELT_SPACING / length
        items = seg["items"]
        for i, it in enumerate(items):
            limit = 1.0 if i == 0 else items[i - 1]["t"] - spacing
            it["t"] = min(limit, float(it["t"]) + step_t)
        if items and float(items[0]["t"]) >= 1.0 - 1e-9:
            good = items[0]["good"]
            accepted = False
            if dst["kind"] == "hub":
                hub = ops["hub"]
                hub["stock"][good] = int(hub["stock"].get(good, 0)) + 1
                hub["received"] = int(hub.get("received", 0)) + 1
                if hub["stock"][good] > caps["hub_stock"]:
                    hub["stock"][good] = caps["hub_stock"]
                    hub["shipped"][good] = int(hub["shipped"].get(good, 0)) + 1
                accepted = True
            elif good in dst.get("recipe", {}) and int(dst["in"].get(good, 0)) < caps["site_in"] * (2 if dst["kind"] == "factory" else 1):
                dst["in"][good] = int(dst["in"].get(good, 0)) + 1
                accepted = True
            if accepted:
                items.pop(0)
        good = seg.get("good") or src.get("good", "")
        if good and src["id"] not in picked and int(src["out"].get(good, 0)) > 0 and (not items or float(items[-1]["t"]) >= spacing):
            src["out"][good] = int(src["out"][good]) - 1
            items.append({"good": good, "t": 0.0})
            picked.add(src["id"])
            src["turn"] = int(src.get("turn", 0)) + 1


def _step_machine(s: dict[str, Any], ops: dict[str, Any], dt_ms: int, caps: dict[str, int]) -> None:
    """A drill or cultivator: no worker, the machine itself produces one packet per cycle (needs water when it says so)."""
    if int(s["out"].get(s["good"], 0)) >= caps["site_out"]:
        s["state"] = "full"
        return
    if s.get("needs_water") and int(s.get("water", 0)) <= 0:
        s["state"] = "short"
        return
    s["state"] = "working"
    s["progress_ms"] = int(s.get("progress_ms", 0)) + dt_ms
    if s["progress_ms"] >= int(s["work_ms"]):
        s["progress_ms"] = 0
        if s.get("needs_water"):
            s["water"] = int(s["water"]) - 1
        s["out"][s["good"]] = int(s["out"].get(s["good"], 0)) + 1
        s["produced"] = int(s.get("produced", 0)) + 1
        ops["throughput"][s["good"]] = int(ops["throughput"].get(s["good"], 0)) + 1


def _step_processor(s: dict[str, Any], ops: dict[str, Any], dt_ms: int, caps: dict[str, int]) -> None:
    if s["state"] == "working":
        s["progress_ms"] = int(s.get("progress_ms", 0)) + dt_ms
        if s["progress_ms"] >= int(s["work_ms"]):
            s["progress_ms"] = 0
            s["out"][s["good"]] = int(s["out"].get(s["good"], 0)) + 1
            s["produced"] = int(s.get("produced", 0)) + 1
            ops["throughput"][s["good"]] = int(ops["throughput"].get(s["good"], 0)) + 1
            s["state"] = "idle"
        return
    if int(s["out"].get(s["good"], 0)) >= caps["site_out"]:
        s["state"] = "full"
        return
    if s.get("power") and not ops.get("power", True):
        s["state"] = "unpowered"
        return
    recipe = s.get("recipe", {})
    if all(int(s["in"].get(g, 0)) >= n for g, n in recipe.items()):
        for g, n in recipe.items():
            s["in"][g] = int(s["in"][g]) - n
        s["state"] = "working"
        s["progress_ms"] = 0
    else:
        s["state"] = "short"


# ------------------------------------------------------------------ carriers and trucks

def _consumer_for(ops: dict[str, Any], good: str, caps: dict[str, int], frm: tuple[float, float]) -> dict[str, Any] | None:
    """The nearest built processor that wants this good and has room (and is not fed by belt), else the hub."""
    best = None
    belted = {g["to"] for g in ops.get("segments", {}).values() if g["kind"] == "belt" and g.get("good") == good}
    for s in ops["sites"].values():
        if s["kind"] != "processor" or not built(s) or good not in s.get("recipe", {}) or s["id"] in belted:
            continue
        have = int(s["in"].get(good, 0)) + int(s["reserved_in"].get(good, 0))
        if have >= caps["site_in"]:
            continue
        d = _dist((s["ex"], s["ey"]), frm)
        if best is None or d < best[0]:
            best = (d, s)
    if best is not None:
        return best[1]
    for s in ops["sites"].values():
        if s["kind"] == "hub" and built(s):
            return s
    return None


def _step_carrier(world, v: dict[str, Any], ops: dict[str, Any], a: dict[str, Any], dt_ms: int, caps: dict[str, int]) -> None:
    speed = _speed(a["kind"])
    phase = a["phase"]
    if a["wait_ms"] > 0:
        a["wait_ms"] -= dt_ms
        if a["wait_ms"] > 0:
            return
    belt_fed: set[str] = {g["from"] for g in ops.get("segments", {}).values() if g["kind"] == "belt"}
    if phase == "idle":
        best = None
        for s in ops["sites"].values():
            if s["kind"] not in ("producer", "processor") or not built(s):
                continue
            for good, n in s["out"].items():
                if int(n) - int(s.get("reserved_out", 0)) <= 0:
                    continue
                if s["id"] in belt_fed and any(g["from"] == s["id"] and g.get("good") == good for g in ops["segments"].values()):
                    continue  # that outlet is a belt's
                dest = _consumer_for(ops, good, caps, (s["ex"], s["ey"]))
                if dest is None or dest["id"] == s["id"]:
                    continue
                d = _dist((a["x"], a["y"]), (s["ex"], s["ey"]))
                if best is None or d < best[0]:
                    best = (d, s, good, dest)
        if best is None:
            a["anim"] = "idle"
            a["wait_ms"] = 1200
            return
        _d, s, good, dest = best
        s["reserved_out"] = int(s.get("reserved_out", 0)) + 1
        if dest["kind"] != "hub":
            dest["reserved_in"][good] = int(dest["reserved_in"].get(good, 0)) + 1
        a["job"] = {"from": s["id"], "good": good, "to": dest["id"]}
        a["phase"] = "to_pickup"
        a["anim"] = "walk"
    elif phase == "to_pickup":
        job = a["job"]
        s = ops["sites"].get(job["from"])
        if s is None:
            a["job"], a["phase"] = None, "idle"
            return
        if _move(a, (s["ex"], s["ey"]), speed, dt_ms):
            s["reserved_out"] = max(0, int(s.get("reserved_out", 0)) - 1)
            if int(s["out"].get(job["good"], 0)) > 0:
                s["out"][job["good"]] = int(s["out"][job["good"]]) - 1
                a["cargo"] = job["good"]
                a["phase"] = "to_deliver"
                a["anim"] = "walkload"
            else:
                dest = ops["sites"].get(job["to"])
                if dest is not None and dest["kind"] != "hub":
                    dest["reserved_in"][job["good"]] = max(0, int(dest["reserved_in"].get(job["good"], 0)) - 1)
                a["job"], a["phase"], a["anim"] = None, "idle", "idle"
    elif phase == "to_deliver":
        job = a["job"]
        dest = ops["sites"].get(job["to"])
        if dest is None:
            a["cargo"], a["job"], a["phase"] = "", None, "idle"
            return
        if _move(a, (dest["ex"], dest["ey"]), speed, dt_ms):
            good = a["cargo"]
            if dest["kind"] == "hub":
                hub = ops["hub"]
                hub["stock"][good] = int(hub["stock"].get(good, 0)) + 1
                hub["received"] = int(hub.get("received", 0)) + 1
                if hub["stock"][good] > caps["hub_stock"]:
                    hub["stock"][good] = caps["hub_stock"]
                    hub["shipped"][good] = int(hub["shipped"].get(good, 0)) + 1
            else:
                dest["in"][good] = int(dest["in"].get(good, 0)) + 1
                dest["reserved_in"][good] = max(0, int(dest["reserved_in"].get(good, 0)) - 1)
            a["cargo"] = ""
            a["job"] = None
            a["phase"] = "to_home"
            a["anim"] = "walk"
    elif phase == "to_home":
        hub = next(s for s in ops["sites"].values() if s["kind"] == "hub")
        k = int(a["id"].rsplit("c", 1)[-1]) if a["id"].rsplit("c", 1)[-1].isdigit() else 0
        home = (hub["ex"] + (k - int(ops["carriers"]) / 2.0) * 0.5, hub["ey"] + 0.6)
        if _move(a, home, speed, dt_ms):
            a["phase"] = "idle"
            a["anim"] = "idle"
            a["wait_ms"] = 400


# ------------------------------------------------------------------ the viewer's picture

def _site_view(s: dict[str, Any]) -> dict[str, Any]:
    return {"id": s["id"], "kind": s["kind"], "role": s["role"], "art": s["art"], "name": s["name"], "x": s["x"], "y": s["y"], "ex": s["ex"], "ey": s["ey"], "state": s["state"],
            "in": {g: n for g, n in s["in"].items() if n}, "out": {g: n for g, n in s["out"].items() if n}, "good": s.get("good", ""), "hex": s.get("hex", ""),
            "progress": (min(1.0, int(s.get("progress_ms", 0)) / float(max(1, int(s.get("work_ms", 1))))) if s["kind"] in ("processor", "producer", "factory") else 0.0),
            "props": s.get("props", ""), "dir": s.get("dir"), "support": bool(s.get("support", False)), "build": round(build_progress(s), 3), "district": s.get("district", ""),
            "slot": int(s.get("slot", 0)), "allowance": bool(s.get("allowance", False))}


def view(v: dict[str, Any]) -> dict[str, Any] | None:
    ops = v.get("ops")
    if ops is None:
        return None
    sites = [_site_view(s) for s in ops["sites"].values() if s.get("commissioned")]
    for s_ in sites:
        src = ops["sites"][s_["id"]]
        if src["kind"] in ("tank", "pump", "producer") and src.get("water") is not None:
            s_["water"] = int(src.get("water", 0))
        if src["kind"] == "generator":
            s_["fuel"] = int(src["in"].get("coal", 0))
    agents = []
    for a in ops["agents"].values():
        agents.append({"id": a["id"], "kind": a["kind"], "art": a["art"], "x": round(float(a["x"]), 3), "y": round(float(a["y"]), 3), "heading": round(math.atan2(float(a["hy"]), float(a["hx"])), 3),
                       "anim": a["anim"], "cargo": a["cargo"], "site": a["site"], "job": a.get("job") if a["kind"] == "builder" else None})
    trees = [{"key": k, "x": t["x"], "y": t["y"], "stage": t["stage"], "species": t.get("species", "beech")} for k, t in ops["trees"].items()]
    hub = next((s for s in ops["sites"].values() if s["kind"] == "hub"), None)
    streets = []
    if hub is not None:
        for s in ops["sites"].values():
            if s.get("commissioned") and s["kind"] in ("producer", "processor", "support", "military"):
                streets.append([s["ex"], s["ey"], hub["ex"], hub["ey"]])
    segments = [{"id": g["id"], "kind": g["kind"], "pts": g["pts"], "items": [{"good": it["good"], "t": round(float(it["t"]), 3)} for it in g.get("items", [])], "fill": round(float(g.get("fill", 0.0)), 2),
                 "broken": bool(g.get("broken", False)), "good": g.get("good", ""), "active": bool(built(ops["sites"].get(g["from"], {"state": "latent"})) and built(ops["sites"].get(g["to"], {"state": "latent"})))}
                for g in ops.get("segments", {}).values() if ops["sites"].get(g["from"], {}).get("commissioned") and ops["sites"].get(g["to"], {}).get("commissioned")]
    dev = {hid: {"cap": int(r["cap"]), "unlocked": int(r["unlocked"]), "commissioned": district_commissioned(ops, hid)} for hid, r in (v.get("dev") or {}).items()}
    return {"sites": sites, "agents": agents, "trees": trees, "hub": {"stock": dict(ops["hub"]["stock"]), "shipped": dict(ops["hub"]["shipped"]), "received": int(ops["hub"].get("received", 0))},
            "streets": streets, "transport": ops["transport"], "throughput": dict(ops["throughput"]), "capacity": dict(ops["capacity"]), "segments": segments,
            "power": bool(ops.get("power", True)), "units_made": int(ops.get("units_made", 0)), "dev": dev, "latent": sum(1 for s in ops["sites"].values() if not s.get("commissioned"))}


def view_lean(v: dict[str, Any]) -> dict[str, Any] | None:
    """Out of the viewer's window: the military site and the hub only (the overview markers need nothing more)."""
    ops = v.get("ops")
    if ops is None:
        return None
    sites = [_site_view(s) for s in ops["sites"].values() if s["kind"] in ("hub", "military") and s.get("commissioned")]
    for s_ in sites:
        s_["in"], s_["out"] = {}, {}
    return {"sites": sites, "agents": [], "trees": [], "hub": {"stock": {}, "shipped": {}, "received": int(ops["hub"].get("received", 0))}, "streets": [],
            "transport": ops["transport"], "throughput": {}, "capacity": dict(ops["capacity"]), "lean": True, "segments": [], "power": True, "units_made": int(ops.get("units_made", 0)), "dev": {}}


def good_name(good: str) -> str:
    return str(planner.chains()["good_names"].get(good, good.replace("_", " ")))

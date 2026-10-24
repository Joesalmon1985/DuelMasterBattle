"""The local village planner (docs/PLAN_GOD_WORLD_LIVING.md stage B): what a village builds and where, from its capacity budget.

Capacity per district is `pips(token) x level` in station-equivalents. The planner spends it on producers (one per three capacity, at most four),
support (a forester for woodland, a well for farmland), a processor where the age has one (a second when the district is large and the village a
city), and carriers for the whole village. Every site is placed on buildable ground inside the village plot, toward the district's work site,
clear of the hub, of the road corridors and of each other, in a deterministic order. Reuse: the proximity-and-space scoring is adapted from the
Widelands default AI (`src/ai/defaultai.cc`: `construct_building`, `consider_productionsite_influence`), reduced to this world's data; see
docs/SOURCE_REUSE.md. Nothing here touches the strategic ledger: a plan is a picture of capacity, never a cost."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from wizard_rts import terrain as T

from . import rules

_DATA = Path(__file__).resolve().parents[1] / "data" / "god_world" / "chains.json"
SITE_GAP = 2.7  # tiles between site anchors
HUB_CLEAR = 2.4  # tiles kept clear around the hub for its yard and entrance
CORRIDOR_CLEAR = 1.4
MAX_PRODUCERS = 4


@lru_cache(maxsize=1)
def chains() -> dict[str, Any]:
    with open(_DATA, encoding="utf-8") as fh:
        return json.load(fh)


def chain(age: int, role: str) -> dict[str, Any] | None:
    return chains()["ages"].get(str(age), {}).get(role)


def hub_spec(age: int, level: int) -> dict[str, Any]:
    h = dict(chains()["hubs"][str(age)])
    if level >= 2:
        h["art"] = h.get("city_art", h["art"])
        h["name"] = h.get("city_name", h["name"])
    return h


def transport_kind(age: int) -> str:
    return str(chains()["transport"].get(str(age), "carrier"))


def budget(board, node: str, level: int) -> dict[str, int]:
    """Capacity per touching productive region, in station-equivalents."""
    return {hid: rules.pips(token) * max(1, level) for hid, _role, token in board.productive_hexes(node)}


def counts_for(cap: int, level: int, has_processor: bool) -> dict[str, int]:
    producers = max(1, min(MAX_PRODUCERS, math.ceil(cap / 3.0)))
    workers = 2 if cap >= 8 else 1
    processors = 0
    if has_processor:
        processors = 2 if (producers >= 3 and level >= 2) else 1
    return {"producers": producers, "workers_per_producer": workers, "processors": processors}


class Plot:
    """Buildable ground around a node: a set of free tiles and the obstacles a site must keep clear of."""

    def __init__(self, world, node: str) -> None:
        self.world = world
        self.board = world.board
        self.grid = world.terrain
        self.node = node
        self.cx, self.cy = self.board.node_xy(node)
        self.unit = float(self.board.unit)
        self.radius = float(self.board.embedding["plot_radius"]) + 2.0 if self.board.embedding else 1.0
        emb = self.board.embedding
        self.corridor = {tuple(t) for t in emb.get("corridor_tiles", [])} if emb else set()
        self.taken: list[tuple[float, float, float]] = []  # (x, y, clearance) of placed sites

    def buildable(self, x: float, y: float, mine_ok: bool = False) -> bool:
        if self.grid is None:
            return True
        tx, ty = int(x), int(y)
        if not self.grid.in_bounds(tx, ty):
            return False
        cls = self.grid.cls[ty * self.grid.w + tx]
        ok = (T.ARABLE, T.WALKABLE, T.MINEABLE) if mine_ok else (T.ARABLE, T.WALKABLE)
        if cls not in ok:
            return False
        if (tx, ty) in self.corridor:
            return False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (tx + dx, ty + dy) in self.corridor and math.hypot(dx, dy) <= CORRIDOR_CLEAR:
                    return False
        return True

    def free(self, x: float, y: float, gap: float = SITE_GAP) -> bool:
        if math.hypot(x - self.cx, y - self.cy) < HUB_CLEAR:
            return False
        for px, py, clear in self.taken:
            if math.hypot(x - px, y - py) < max(gap, clear):
                return False
        # another village's sites are never closer than two units anyway (the distance rule); other plots' hubs are kept clear
        for v in self.world.villages.values():
            if v["node"] != self.node and v["status"] in ("operational", "rebuilding", "building", "pending"):
                ox, oy = self.board.node_xy(v["node"])
                if math.hypot(x - ox, y - oy) < 4.5:
                    return False
        return True

    def place(self, ideal: tuple[float, float], mine_ok: bool = False, gap: float = SITE_GAP, clearance: float = SITE_GAP, force: bool = False) -> tuple[float, float] | None:
        """The free buildable tile nearest the ideal spot (a deterministic spiral), or None; `force` takes the nearest free tile of any ground."""
        ix, iy = ideal
        best = None
        for r in range(0, 9):
            cands = []
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = int(ix) + dx + 0.5, int(iy) + dy + 0.5
                    if math.hypot(x - self.cx, y - self.cy) > self.radius + 3.0:
                        continue
                    if not self.free(x, y, gap):
                        continue
                    if not self.buildable(x, y, mine_ok) and not (force and self.grid is not None and self.grid.in_bounds(int(x), int(y)) and self.grid.cls[int(y) * self.grid.w + int(x)] != T.WATER):
                        continue
                    cands.append((math.hypot(x - ix, y - iy), x, y))
            if cands:
                cands.sort()
                best = (cands[0][1], cands[0][2])
                break
        if best is not None:
            self.taken.append((best[0], best[1], clearance))
        return best


def plan(world, village: dict[str, Any]) -> dict[str, Any]:
    """The village's local network for its age and level: hub, districts with producers/support/processors, the military facility, carriers.
    Returns {"sites": [...], "carriers": n, "capacity": {hex: n}}; ids are stable per village, age, district and index."""
    board = world.board
    vid = village["id"]
    age = int(village["age"])
    level = max(1, int(village["level"]))
    node = village["node"]
    plot = Plot(world, node)
    cx, cy = plot.cx, plot.cy
    unit = plot.unit
    sites: list[dict[str, Any]] = []
    hub = hub_spec(age, level)
    sites.append({"id": f"{vid}:hub", "kind": "hub", "role": "", "art": hub["art"], "name": hub["name"], "x": round(cx, 2), "y": round(cy, 2), "ex": round(cx, 2), "ey": round(cy + 1.4, 2),
                  "hex": "", "good": "", "props": hub.get("props", "")})
    caps = budget(board, node, level)
    districts = sorted(((hid, cap) for hid, cap in caps.items()), key=lambda t: (-t[1], t[0]))
    # directions: toward each district's work site; the military wedge is the free side (or the smallest district's)
    dirs: dict[str, tuple[float, float]] = {}
    for hid, _cap in districts:
        wx, wy = board.work_site(hid)
        d = math.hypot(wx - cx, wy - cy) or 1.0
        dirs[hid] = ((wx - cx) / d, (wy - cy) / d)
    for hid, cap in districts:
        role = board.role(hid)
        spec = chain(age, role)
        if spec is None:
            continue
        ux, uy = dirs[hid]
        vx, vy = -uy, ux
        c = counts_for(cap, level, "processor" in spec)
        wx, wy = board.work_site(hid)
        reach = min(math.hypot(wx - cx, wy - cy), unit * 1.05)
        mine = spec["producer"]["task"] == "mine"
        # producers: along the district direction, fanning out; mines may stand on the mountain itself
        for i in range(c["producers"]):
            depth = 3.4 + 2.3 * (i // 2)
            lat = (1.0 if i % 2 == 0 else -1.0) * (1.9 if c["producers"] > 1 else 0.0)
            ideal = (cx + ux * depth + vx * lat, cy + uy * depth + vy * lat)
            if mine:
                ideal = (cx + ux * min(reach, depth + 3.0) + vx * lat, cy + uy * min(reach, depth + 3.0) + vy * lat)
            pos = plot.place(ideal, mine_ok=mine)
            if pos is None and i == 0:
                pos = plot.place((cx + ux * 4.0, cy + uy * 4.0), mine_ok=True, force=True)  # every district has at least its first producer
            if pos is None:
                continue
            p = spec["producer"]
            sites.append({"id": f"{vid}:{hid}:a{age}:prod{i}", "kind": "producer", "role": role, "art": p["art"], "name": p["name"], "x": round(pos[0], 2), "y": round(pos[1], 2),
                          "ex": round(pos[0], 2), "ey": round(pos[1] + 1.2, 2), "hex": hid, "good": spec["good"], "worker": p.get("worker", ""), "task": p["task"],
                          "work_ms": int(p.get("work_ms", 12000)), "work_anim": p.get("work_anim", ""), "workers": c["workers_per_producer"],
                          "needs_water": bool(p.get("needs_water", False))})
        second = spec.get("second")
        if second is not None:
            ideal = (cx + ux * min(reach, 7.5) - vx * 3.6, cy + uy * min(reach, 7.5) - vy * 3.6)
            pos = plot.place(ideal, mine_ok=True)
            if pos is not None:
                sites.append({"id": f"{vid}:{hid}:a{age}:second", "kind": "producer", "role": role, "art": second["art"], "name": second["name"], "x": round(pos[0], 2), "y": round(pos[1], 2),
                              "ex": round(pos[0], 2), "ey": round(pos[1] + 1.2, 2), "hex": hid, "good": second["good"], "worker": second.get("worker", ""), "task": second["task"],
                              "work_ms": int(second.get("work_ms", 12000)), "work_anim": second.get("work_anim", ""), "workers": 1, "needs_water": False})
        support = spec.get("support")
        if support is not None and cap >= 2:
            ideal = (cx + ux * 5.6 + vx * 4.2, cy + uy * 5.6 + vy * 4.2)
            pos = plot.place(ideal)
            if pos is not None:
                sites.append({"id": f"{vid}:{hid}:a{age}:support", "kind": "support", "role": role, "art": support["art"], "name": support["name"], "x": round(pos[0], 2), "y": round(pos[1], 2),
                              "ex": round(pos[0], 2), "ey": round(pos[1] + 1.2, 2), "hex": hid, "good": "", "worker": support.get("worker", ""), "task": support.get("task", ""),
                              "work_ms": int(support.get("work_ms", 0)), "work_anim": support.get("work_anim", ""), "workers": 1 if support.get("worker") else 0})
        proc = spec.get("processor")
        for k in range(c["processors"]):
            if proc is None:
                break
            ideal = (cx + ux * 2.9 - vx * (2.4 + 2.6 * k), cy + uy * 2.9 - vy * (2.4 + 2.6 * k))
            pos = plot.place(ideal)
            if pos is None:
                continue
            sites.append({"id": f"{vid}:{hid}:a{age}:proc{k}", "kind": "processor", "role": role, "art": proc["art"], "name": proc["name"], "x": round(pos[0], 2), "y": round(pos[1], 2),
                          "ex": round(pos[0], 2), "ey": round(pos[1] + 1.2, 2), "hex": hid, "good": proc["out"], "recipe": dict(proc["recipe"]), "work_ms": int(proc.get("work_ms", 15000)),
                          "power": bool(proc.get("power", False))})
    # the military facility: on the side with no district, else beside the smallest district
    used = [dirs[h] for h, _c in districts]
    if used:
        sx = -sum(d[0] for d in used)
        sy = -sum(d[1] for d in used)
        if math.hypot(sx, sy) < 0.3:  # three balanced districts: take the gap between the two largest
            a, b = used[0], used[1]
            sx, sy = -(a[0] + b[0]) * 0.5 - used[-1][0] * 0.2, -(a[1] + b[1]) * 0.5 - used[-1][1] * 0.2
        d = math.hypot(sx, sy) or 1.0
        mx, my = sx / d, sy / d
    else:
        mx, my = 0.0, -1.0
    mil = rules.military_spec(age)
    pos = plot.place((cx + mx * 3.6, cy + my * 3.6), gap=2.2, clearance=3.0)
    if pos is not None:
        sites.append({"id": f"{vid}:mil", "kind": "military", "role": "", "art": mil["facility"], "name": mil.get("facility_name", "Barracks"), "x": round(pos[0], 2), "y": round(pos[1], 2),
                      "ex": round(pos[0], 2), "ey": round(pos[1] + 1.3, 2), "hex": "", "good": "", "dir": [round(mx, 3), round(my, 3)]})
    segments: list[dict[str, Any]] = []
    if age >= 4:
        _plan_industry(world, village, plot, sites, segments, mx, my)
    producers_total = sum(1 for s in sites if s["kind"] == "producer")
    carriers = min(6, 1 + producers_total // 2)
    return {"sites": sites, "carriers": carriers, "capacity": caps, "transport": transport_kind(age), "age": age, "level": level, "segments": segments}


def _belt(vid: str, n: int, src: dict[str, Any], dst: dict[str, Any], kind: str = "belt", good: str = "") -> dict[str, Any]:
    """A directional segment from one site's outlet to another's inlet: an L on the tile grid (Mindustry belts turn at right angles)."""
    ax, ay = float(src["x"]) + 1.1, float(src["y"]) + 0.4
    bx, by = float(dst["x"]) - 1.1, float(dst["y"]) + 0.4
    pts = [[round(ax, 2), round(ay, 2)]]
    if abs(bx - ax) > 0.3 and abs(by - ay) > 0.3:
        pts.append([round(bx, 2), round(ay, 2)])
    pts.append([round(bx, 2), round(by, 2)])
    length = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
    return {"id": f"{vid}:{kind}{n}", "kind": kind, "from": src["id"], "to": dst["id"], "pts": pts, "length": round(max(length, 0.5), 2), "good": good}


def _plan_industry(world, village: dict[str, Any], plot: Plot, sites: list[dict[str, Any]], segments: list[dict[str, Any]], mx: float, my: float) -> None:
    """Age 4: belts from drills to processors and processors to the core; support drills (and a support smelter) for inputs the village's own
    regions do not yield; a coal-fed generator for power; a pump, tank and pipes for the cultivator; the ground factory fed with silicon and lead.
    Support deposits are local operating sources, never strategic entitlements."""
    vid = village["id"]
    age = int(village["age"])
    data = chains()
    hub = next(s for s in sites if s["kind"] == "hub")
    cx, cy = float(hub["x"]), float(hub["y"])
    yard_dir = (-mx, -my)  # the industrial yard spreads away from the military side
    ydx, ydy = yard_dir
    ypx, ypy = -ydy, ydx
    support_spec = data.get("support_goods", {}).get(str(age), {})
    produced: dict[str, list[dict[str, Any]]] = {}
    for s in sites:
        if s["kind"] in ("producer", "processor") and s.get("good"):
            produced.setdefault(s["good"], []).append(s)
    n_seg = 0
    yard_slots = [(cx + ydx * 4.6 + ypx * (k - 2) * 2.9, cy + ydy * 4.6 + ypy * (k - 2) * 2.9) for k in range(6)] +                  [(cx + ydx * 7.4 + ypx * (k - 2) * 2.9, cy + ydy * 7.4 + ypy * (k - 2) * 2.9) for k in range(6)]
    slot_i = [0]

    def next_slot() -> tuple[float, float] | None:
        while slot_i[0] < len(yard_slots):
            ideal = yard_slots[slot_i[0]]
            slot_i[0] += 1
            pos = plot.place(ideal, mine_ok=True, gap=2.4, clearance=2.4)
            if pos is not None:
                return pos
        return None

    def ensure_source(good: str, depth: int = 0, dedicated: str = "") -> dict[str, Any] | None:
        """A site in this village that yields `good`: a district producer or processor, else a support site (a drill, or a smelter and its drills).
        `dedicated` asks for a support site of its own (the generator's coal), whatever the districts yield."""
        if not dedicated and good in produced and produced[good]:
            return produced[good][0]
        spec = support_spec.get(good)
        if spec is None or depth > 2:
            return produced[good][0] if produced.get(good) else None
        pos = next_slot()
        if pos is None:
            return produced[good][0] if produced.get(good) else None
        sid = f"{vid}:a{age}:support_{good}{dedicated}"
        if "recipe" in spec:
            site = {"id": sid, "kind": "processor", "role": "", "art": spec["art"], "name": spec["name"], "x": round(pos[0], 2), "y": round(pos[1], 2), "ex": round(pos[0], 2), "ey": round(pos[1] + 1.2, 2),
                    "hex": "", "good": good, "recipe": dict(spec["recipe"]), "work_ms": int(spec["work_ms"]), "power": True, "support": True}
            sites.append(site)
            produced.setdefault(good, []).append(site)
            for g in spec["recipe"]:
                src = ensure_source(g, depth + 1)
                if src is not None:
                    segments.append(_belt(vid, len(segments), src, site, good=g))
            return site
        site = {"id": sid, "kind": "producer", "role": "", "art": spec["art"], "name": spec["name"], "x": round(pos[0], 2), "y": round(pos[1], 2), "ex": round(pos[0], 2), "ey": round(pos[1] + 1.2, 2),
                "hex": "", "good": good, "worker": "", "task": "drill", "work_ms": int(spec["work_ms"]), "work_anim": "", "workers": 0, "needs_water": False, "support": True}
        sites.append(site)
        if not dedicated:
            produced.setdefault(good, []).append(site)
        return site

    # district chains: every producer feeds its district's processor (else the core); every processor feeds the core; processors get their other inputs
    for s in list(sites):
        if s["kind"] == "producer" and s.get("hex"):
            procs = [p for p in sites if p["kind"] == "processor" and p.get("hex") == s["hex"] and s["good"] in p.get("recipe", {})]
            dst = procs[0] if procs else hub
            segments.append(_belt(vid, len(segments), s, dst, good=s["good"]))
    for p in list(sites):
        if p["kind"] == "processor" and p.get("hex"):
            segments.append(_belt(vid, len(segments), p, hub, good=p["good"]))
            for g in p.get("recipe", {}):
                if any(seg["to"] == p["id"] and seg.get("good") == g for seg in segments):
                    continue
                src = ensure_source(g)
                if src is not None:
                    segments.append(_belt(vid, len(segments), src, p, good=g))
    # power: a combustion generator fed with coal
    gen_pos = next_slot()
    if gen_pos is not None:
        gen = {"id": f"{vid}:a{age}:generator", "kind": "generator", "role": "", "art": "mindustry.block.combustion_generator", "name": "Combustion generator", "x": round(gen_pos[0], 2),
               "y": round(gen_pos[1], 2), "ex": round(gen_pos[0], 2), "ey": round(gen_pos[1] + 1.0, 2), "hex": "", "good": "", "recipe": {"coal": 1}, "work_ms": 25000, "fuel": 0}
        sites.append(gen)
        src = ensure_source("coal", dedicated="_gen")  # its own drill: power never waits behind the mixers
        if src is not None:
            segments.append(_belt(vid, len(segments), src, gen, good="coal"))
    # water: the cultivator drinks from a pump at the shore through a tank; without a shore in reach, a water extractor beside it
    cult = next((s for s in sites if s["kind"] == "producer" and s.get("needs_water")), None)
    if cult is not None:
        shore = _nearest_shore(world, (cx, cy), 15.0)
        tank_pos = next_slot()
        if shore is not None and tank_pos is not None:
            pump = {"id": f"{vid}:a{age}:pump", "kind": "pump", "role": "", "art": "mindustry.block.mechanical_pump", "name": "Mechanical pump", "x": round(shore[0], 2), "y": round(shore[1], 2),
                    "ex": round(shore[0], 2), "ey": round(shore[1] + 0.8, 2), "hex": "", "good": "water", "work_ms": int(data["water"][str(age)]["pump"]["rate_ms"])}
            tank = {"id": f"{vid}:a{age}:tank", "kind": "tank", "role": "", "art": "mindustry.block.liquid_tank", "name": "Liquid tank", "x": round(tank_pos[0], 2), "y": round(tank_pos[1], 2),
                    "ex": round(tank_pos[0], 2), "ey": round(tank_pos[1] + 1.2, 2), "hex": "", "good": "water", "cap": int(data["water"][str(age)]["tank"]["cap"])}
            sites += [pump, tank]
            segments.append(_belt(vid, len(segments), pump, tank, kind="pipe", good="water"))
            segments.append(_belt(vid, len(segments), tank, cult, kind="pipe", good="water"))
        else:
            ex_pos = plot.place((float(cult["x"]) + 2.4, float(cult["y"])), mine_ok=True, gap=2.2, clearance=2.2)
            if ex_pos is not None:
                extractor = {"id": f"{vid}:a{age}:extractor", "kind": "pump", "role": "", "art": "mindustry.block.water_extractor", "name": "Water extractor", "x": round(ex_pos[0], 2), "y": round(ex_pos[1], 2),
                             "ex": round(ex_pos[0], 2), "ey": round(ex_pos[1] + 1.0, 2), "hex": "", "good": "water", "work_ms": 4000}
                sites.append(extractor)
                segments.append(_belt(vid, len(segments), extractor, cult, kind="pipe", good="water"))
    # the ground factory: silicon and lead by belt, a unit at the end
    fac = data.get("factory", {}).get(str(age))
    if fac is not None:
        mil = next((s for s in sites if s["kind"] == "military"), None)
        ideal = (float(mil["x"]) + ypx * 3.0, float(mil["y"]) + ypy * 3.0) if mil else (cx + mx * 6.0, cy + my * 6.0)
        pos = plot.place(ideal, mine_ok=True, gap=2.6, clearance=2.8)
        if pos is None:
            pos = next_slot()
        if pos is not None:
            factory = {"id": f"{vid}:a{age}:factory", "kind": "factory", "role": "", "art": fac["art"], "name": fac["name"], "x": round(pos[0], 2), "y": round(pos[1], 2), "ex": round(pos[0], 2),
                       "ey": round(pos[1] + 1.4, 2), "hex": "", "good": "unit", "recipe": dict(fac["recipe"]), "work_ms": int(fac["work_ms"]), "unit": fac["unit"], "power": True}
            sites.append(factory)
            for g in fac["recipe"]:
                src = ensure_source(g)
                if src is not None:
                    segments.append(_belt(vid, len(segments), src, factory, good=g))


def _nearest_shore(world, origin: tuple[float, float], radius: float) -> tuple[float, float] | None:
    """The nearest land tile beside water within the radius (a pump stands on the shore)."""
    grid = world.terrain
    if grid is None:
        return None
    ox, oy = int(origin[0]), int(origin[1])
    best = None
    r = int(radius)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            x, y = ox + dx, oy + dy
            if not grid.in_bounds(x, y) or grid.cls[y * grid.w + x] not in (T.ARABLE, T.WALKABLE):
                continue
            if not any(grid.in_bounds(x + ex, y + ey) and grid.cls[(y + ey) * grid.w + x + ex] == T.WATER for ex, ey in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                continue
            d = math.hypot(dx, dy)
            if d > radius or d < 2.5:
                continue
            if best is None or d < best[0]:
                best = (d, x + 0.5, y + 0.5)
    return (best[1], best[2]) if best else None

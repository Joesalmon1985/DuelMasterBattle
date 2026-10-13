"""The logical catastrophe overlay (D12, S09): a flat-top hex partition of the square-grid map, outbreak cubes and their effects.

The overlay is NON-PHYSICAL. No movement, placement, territory or pathfinding rule reads it (a test proves placement and routes are
identical with and without outbreaks); only production speed, settlement unrest, quest generation, visible clues and the loss
counter read it. Every tile belongs to exactly one region (cube rounding of the axial coordinates). The square grid stays authoritative.

Cadence (S09, data in data/outbreaks.json): every 10 game minutes one cube is added to a deterministically chosen region; every 5
minutes a region holding 2 or more cubes infects its emptiest neighbour (one new cube; the source keeps its own); a cube added to a region that already holds the cap
(3) is an *outbreak*: it spreads one cube to every neighbour. Eight outbreaks end the cycle (terminal loss, an explicit rule). Only the
wizard can treat: he must stand in the region and stay for the channel time; one cube is removed per treatment, with a cooldown.
"""

from __future__ import annotations

import json
import math
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).with_name("data") / "outbreaks.json"
SQRT3 = math.sqrt(3.0)
NEIGHBOURS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))


@lru_cache(maxsize=1)
def config() -> dict[str, Any]:
    return json.loads(DATA.read_text())


def const(name: str) -> int:
    return int(config()["constants"][name])


def _round_axial(q: float, r: float) -> tuple[int, int]:
    x, z = q, r
    y = -x - z
    rx, ry, rz = round(x), round(y), round(z)
    dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return int(rx), int(rz)


def axial_of(tx: int, ty: int, w: int, h: int, size: int) -> tuple[int, int]:
    x, y = tx + 0.5 - w / 2.0, ty + 0.5 - h / 2.0
    return _round_axial((2.0 / 3.0 * x) / size, (-1.0 / 3.0 * x + SQRT3 / 3.0 * y) / size)


@lru_cache(maxsize=8)
def partition(w: int, h: int, size: int) -> tuple[tuple[tuple[int, int], ...], bytes | list[int], dict[tuple[int, int], int]]:
    """(region axial list sorted, tile -> region index table, axial -> index). Computed once per map size."""
    table = [0] * (w * h)
    index: dict[tuple[int, int], int] = {}
    axials: list[tuple[int, int]] = []
    cache: dict[tuple[int, int], int] = {}
    for ty in range(h):
        for tx in range(w):
            a = axial_of(tx, ty, w, h, size)
            if a not in cache:
                cache[a] = len(axials)
                axials.append(a)
            table[ty * w + tx] = cache[a]
    # canonical order: sorted axial coordinates, so region ids do not depend on scan order
    order = sorted(range(len(axials)), key=lambda i: axials[i])
    remap = {old: new for new, old in enumerate(order)}
    sorted_axials = tuple(axials[i] for i in order)
    table = [remap[v] for v in table]
    index = {a: i for i, a in enumerate(sorted_axials)}
    return sorted_axials, table, index


class Regions:
    def __init__(self, w: int, h: int) -> None:
        self.w, self.h, self.size = w, h, const("region_size")
        self.axials, self.table, self.index = partition(w, h, self.size)
        self.cubes = [0] * len(self.axials)
        self.kind: list[str] = [""] * len(self.axials)
        self.neighbours = [[self.index[(q + dq, r + dr)] for dq, dr in NEIGHBOURS if (q + dq, r + dr) in self.index] for q, r in self.axials]
        self.outbreaks = 0
        self.era_outbreaks: dict[int, int] = {}  # outbreaks per era index: the per-era loss counter (plan v2 7.2); not part of the snapshot
        self.lost_by = ""
        self.added = 0
        self.next_cube_ms = const("interval_ms")
        self.next_spread_ms = const("spread_ms")
        self.treat: dict[str, Any] | None = None
        self.treat_ready_ms = 0
        self.treated = 0
        self.lost = False
        self.log: list[dict[str, Any]] = []

    def region_at(self, tx: int, ty: int) -> int:
        return self.table[ty * self.w + tx]

    def rid(self, i: int) -> str:
        q, r = self.axials[i]
        return f"region:{q},{r}"


def state(world: Any) -> Regions | None:
    if world.terrain is None:
        return None
    s = world.__dict__.get("regions")
    if s is None:
        s = world.regions = Regions(world.terrain.w, world.terrain.h)
    return s


def kind_for_era(era: int) -> dict[str, Any]:
    kinds = config()["kinds"]
    best = kinds[0]
    for k in kinds:
        if k["era"] <= era:
            best = k
    return best


def _matches(pattern_list: list[str], kind: str) -> bool:
    import fnmatch

    return any(p == "*" or fnmatch.fnmatchcase(kind, p) for p in pattern_list)


def production_factor(world: Any, building: dict) -> float:
    """Multiplier (0..1] on a workplace's speed from the outbreak in its region. 1.0 when there is none."""
    s = world.__dict__.get("regions")
    if s is None or not any(s.cubes):
        return 1.0
    i = s.region_at(building["tx"], building["ty"])
    n = s.cubes[i]
    if n <= 0:
        return 1.0
    k = next((x for x in config()["kinds"] if x["id"] == s.kind[i]), None)
    if k is None or not _matches(config()["groups"][k["affects"]]["kinds"], building["kind"]):
        return 1.0
    return max(float(k["min_factor"]), float(k["factor"]) ** n)


def yield_count(world: Any, building: dict, n: int) -> int:
    """Items a finished programme actually yields under an outbreak: n x factor with a fractional carry per building (deterministic;
    no random draw). The inputs were consumed either way, so the shortfall is a real loss, counted in stats['outbreak_losses']."""
    f = production_factor(world, building)
    if f >= 1.0:
        return n
    carry = float(building.get("_yield_carry", 0.0)) + n * f
    got = int(carry)
    building["_yield_carry"] = carry - got
    world.stats["outbreak_losses"] = world.stats.get("outbreak_losses", 0) + (n - got)
    return got


def _add_cube(world: Any, s: Regions, i: int, now: int, source: str, depth: int = 0) -> None:
    cap = const("cube_cap")
    k = kind_for_era(int(getattr(world, "era_index", 0)))
    if s.cubes[i] == 0:
        s.kind[i] = k["id"]
    if s.cubes[i] >= cap:
        s.outbreaks += 1
        e = int(getattr(world, "era_index", 0))
        s.era_outbreaks[e] = s.era_outbreaks.get(e, 0) + 1
        s.log.append({"game_ms": now, "event": "outbreak", "region": s.rid(i), "source": source})
        world.events.append({"kind": "outbreak", "region": s.rid(i), "count": s.outbreaks, "hazard": s.kind[i]})
        _outbreak_damage(world, s, i, now)
        if depth == 0:  # one level of chain: the neighbours each receive a cube, an outbreak there does not cascade again this tick
            for n in s.neighbours[i]:
                _add_cube(world, s, n, now, "spread", depth=1)
        return
    s.cubes[i] += 1
    s.added += 1
    world.events.append({"kind": "outbreak_cube", "region": s.rid(i), "cubes": s.cubes[i], "source": source, "hazard": s.kind[i]})


def _outbreak_damage(world: Any, s: Regions, i: int, now: int) -> None:
    """An overflowing region (cubes at the cap) burns its busiest workplace down and shakes the settlements in it (P1.4: consequences
    that change the economy, not a colour). Command centres are spared: a catastrophe ruins workplaces, war ruins settlements."""
    from wizard_rts.lifecycle import begin_destruction

    if not hasattr(world, "recipe_requests"):  # a stub world of the outbreak environment: cubes only, no buildings to burn
        return
    cands = [b for b in sorted(world.buildings.values(), key=lambda x: x["id"]) if "hp" in b and int(b["hp"]) > 0 and not b.get("command_center") and b["kind"] != "blight_nest"
             and not b.get("constructing") and not b.get("destroyed") and s.region_at(b["tx"], b["ty"]) == i]
    if cands:
        victim = sorted(cands, key=lambda b: (not b.get("working"), not b.get("working_once"), b["id"]))[0]
        victim["hp"] = 0
        begin_destruction(world, victim)
        world.stats["catastrophe_buildings_lost"] = world.stats.get("catastrophe_buildings_lost", 0) + 1
        world.fstat(victim["faction_name"], "catastrophe_losses")
        world.events.append({"kind": "catastrophe_destroyed", "id": victim["id"], "faction": victim["faction_name"], "building_kind": victim["kind"],
                             "region": s.rid(i), "hazard": s.kind[i], "tile": [victim["tx"], victim["ty"]]})
    for rec in world.dmb.settlements.values():
        if rec["state"] == "standing" and s.region_at(rec["tile"][0], rec["tile"][1]) == i:
            rec["unrest"] = min(1.0, float(rec.get("unrest", 0.0)) + 0.2)


def cubes_here(world: Any, building: dict) -> int:
    s = state(world)
    return 0 if s is None else s.cubes[s.region_at(building["tx"], building["ty"])]


def cure(world: Any, building: dict, cubes: int = 1) -> int:
    """A clinic's finished cycle: remove up to `cubes` outbreak cubes from its own region (the wizard's treatment, by a building). Returns how many."""
    s = state(world)
    if s is None:
        return 0
    i = s.region_at(building["tx"], building["ty"])
    n = min(cubes, s.cubes[i])
    if n <= 0:
        return 0
    s.cubes[i] -= n
    s.cured = getattr(s, "cured", 0) + n
    world.fstat(building["faction_name"], "cubes_cured", n)
    world.stats["cubes_cured"] = world.stats.get("cubes_cured", 0) + n
    world.events.append({"kind": "cube_cured", "building": building["id"], "faction": building["faction_name"], "region": s.rid(i), "cubes_left": s.cubes[i]})
    return n


def _pick_region(world: Any, s: Regions) -> int:
    """Deterministic: a seeded stream per cube number, among regions that hold a building (an empty wilderness cannot suffer)."""
    rng = random.Random(f"{world.seed}:outbreak:{s.added + s.outbreaks}")
    inhabited = sorted({s.region_at(b["tx"], b["ty"]) for b in world.buildings.values() if "hp" in b and b["kind"] != "blight_nest"})
    pool = inhabited or list(range(len(s.axials)))
    return pool[rng.randrange(len(pool))]


def regions_quantum(world: Any) -> None:
    s = state(world)
    if s is None or s.lost:
        return
    now = int(world.dmb.clock.get("game_ms", 0))
    if getattr(world, "outbreaks_enabled", True):
        if now >= s.next_cube_ms:
            s.next_cube_ms = now + int(const("interval_ms") * float(getattr(world, "outbreak_interval_scale", 1.0)))  # scenario difficulty knob
            _add_cube(world, s, _pick_region(world, s), now, "cadence")
        if now >= s.next_spread_ms:
            s.next_spread_ms = now + const("spread_ms")
            for i in range(len(s.cubes)):
                if s.cubes[i] >= 2 and s.neighbours[i]:
                    tgt = min(s.neighbours[i], key=lambda n: (s.cubes[n], n))
                    if s.cubes[tgt] < const("cube_cap"):
                        _add_cube(world, s, tgt, now, "spread")  # the infection spreads: the source keeps its cubes, so untreated regions escalate
    _treatment(world, s, now)
    if world.economy_quanta % 600 == 0:  # once a game minute: unrest from the cubes in each settlement's region
        _unrest(world, s)
    per_era = int(getattr(world, "loss_outbreaks_per_era", config()["constants"].get("loss_outbreaks_per_era", const("loss_outbreaks"))))
    total = int(getattr(world, "loss_outbreaks_total", const("loss_outbreaks")))
    era_now = s.era_outbreaks.get(int(getattr(world, "era_index", 0)), 0)
    if (s.outbreaks >= total or era_now >= per_era) and not s.lost:
        s.lost = True
        s.lost_by = "total" if s.outbreaks >= total else "era"
        world.cycle_pending = True  # terminal loss: the cycle ends by explicit rule (history.cycle_reset)
        world.collective_loss = True  # every faction loses: no winner, whatever the VP (plan v2 7.2)
        world.events.append({"kind": "terminal_loss", "outbreaks": s.outbreaks, "era_outbreaks": era_now, "cause": s.lost_by, "collective": True})


def _unrest(world: Any, s: Regions) -> None:
    for rec in world.dmb.settlements.values():
        if rec["state"] != "standing":
            continue
        i = s.region_at(rec["tile"][0], rec["tile"][1])
        k = next((x for x in config()["kinds"] if x["id"] == s.kind[i]), None)
        if s.cubes[i] > 0 and k:
            rec["unrest"] = min(1.0, float(rec.get("unrest", 0.0)) + float(k["unrest"]) * s.cubes[i])
        else:
            rec["unrest"] = max(0.0, float(rec.get("unrest", 0.0)) - 0.01)


# ------------------------------------------------------------------ treatment (the wizard only)

def player_region(world: Any) -> int | None:
    s = state(world)
    if s is None:
        return None
    return s.region_at(int(world.player["tx"]), int(world.player["ty"]))


def begin_treatment(world: Any) -> dict[str, Any]:
    s = state(world)
    if s is None:
        return {"status": "rejected", "reason": "no_regions"}
    now = int(world.dmb.clock.get("game_ms", 0))
    i = player_region(world)
    if s.cubes[i] <= 0:
        return {"status": "rejected", "reason": "nothing_to_treat", "region": s.rid(i)}
    if s.treat is not None:
        return {"status": "rejected", "reason": "already_treating"}
    if now < s.treat_ready_ms:
        return {"status": "rejected", "reason": "recovering", "ready_in_ms": s.treat_ready_ms - now}
    s.treat = {"region": i, "until_ms": now + const("treat_ms")}
    world.events.append({"kind": "treatment_started", "region": s.rid(i)})
    return {"status": "started", "region": s.rid(i), "until_ms": s.treat["until_ms"]}


def _treatment(world: Any, s: Regions, now: int) -> None:
    t = s.treat
    if t is None:
        return
    if player_region(world) != t["region"]:  # the wizard walked out of the region: the treatment is abandoned
        s.treat = None
        world.events.append({"kind": "treatment_abandoned", "region": s.rid(t["region"])})
        return
    if now >= t["until_ms"]:
        i = t["region"]
        if s.cubes[i] > 0:
            s.cubes[i] -= 1
            s.treated += 1
            world.events.append({"kind": "treatment_done", "region": s.rid(i), "cubes": s.cubes[i]})
            story = world.__dict__.get("story")
            for q in (story["quests"].values() if story else []):
                if q.get("family") == "outbreak" and q["region"] == s.rid(i):
                    q["treated_by_wizard"] = True
        s.treat = None
        s.treat_ready_ms = now + const("treat_cooldown_ms")


# ------------------------------------------------------------------ presentation

def entity_rows(world: Any) -> list[dict[str, Any]]:
    """Visible clues: one marker per cube near the region's busiest building (placeholder smoke/withered ground)."""
    s = world.__dict__.get("regions")
    if s is None or not any(s.cubes):
        return []
    rows = []
    by_region: dict[int, list[dict]] = {}
    for b in sorted(world.buildings.values(), key=lambda x: x["id"]):
        if "hp" in b:
            by_region.setdefault(s.region_at(b["tx"], b["ty"]), []).append(b)
    for i, n in enumerate(s.cubes):
        if n <= 0:
            continue
        cand = by_region.get(i) or []
        k = next((x for x in config()["kinds"] if x["id"] == s.kind[i]), config()["kinds"][0])
        for c in range(n):
            if cand:
                b = cand[(c * 7) % len(cand)]
                tx, ty = b["tx"] + 2 + c, b["ty"] + 2
            else:
                q, r = s.axials[i]
                tx, ty = int(s.w / 2 + 1.5 * s.size * q), int(s.h / 2 + SQRT3 * s.size * (r + q / 2))
            rows.append({"id": f"clue:{s.rid(i)}:{c}", "class": "landmark", "kind": "outbreak_clue", "definition": "story.outbreak", "faction": "", "faction_name": "",
                         "label": k["clue"], "tx": max(0, min(s.w - 1, tx)), "ty": max(0, min(s.h - 1, ty)), "alive": True, "region": s.rid(i), "hazard": s.kind[i]})
    return rows


def impact(world: Any, s: Regions, i: int) -> dict[str, Any]:
    """What an outbreak is doing to the economy of one region right now (P1.4: the effect must be visible and measurable)."""
    rows = [b for b in world.buildings.values() if "hp" in b and int(b["hp"]) > 0 and not b.get("constructing") and s.region_at(b["tx"], b["ty"]) == i]
    slowed = [b for b in rows if production_factor(world, b) < 1.0]
    k = next((x for x in config()["kinds"] if x["id"] == s.kind[i]), None)
    return {"label": k["label"] if k else "", "clue": k["clue"] if k else "", "affects": k["affects"] if k else "",
            "factor": round(max(float(k["min_factor"]), float(k["factor"]) ** s.cubes[i]), 2) if k and s.cubes[i] else 1.0,
            "slowed": len(slowed), "closed": sum(1 for b in rows if b.get("disrupted")), "buildings": len(rows)}


def snapshot(world: Any) -> dict[str, Any]:
    s = world.__dict__.get("regions")
    if s is None:
        return {}
    now = int(world.dmb.clock.get("game_ms", 0))
    here = s.region_at(int(world.player["tx"]), int(world.player["ty"]))
    return {"size": s.size, "count": len(s.axials), "cubes": {s.rid(i): n for i, n in enumerate(s.cubes) if n}, "kinds": {s.rid(i): s.kind[i] for i, n in enumerate(s.cubes) if n},
            "impact": {s.rid(i): impact(world, s, i) for i, n in enumerate(s.cubes) if n},
            "outbreaks": s.outbreaks, "loss_at": const("loss_outbreaks"), "treated": s.treated, "lost": s.lost, "treating": s.treat is not None,
            "treat_left_ms": max(0, int(s.treat["until_ms"]) - now) if s.treat else 0, "treat_ms": const("treat_ms"),
            "ready_in_ms": max(0, s.treat_ready_ms - now), "next_cube_ms": s.next_cube_ms, "next_cube_in_ms": max(0, s.next_cube_ms - now),
            "player_region": s.rid(here), "player_cubes": s.cubes[here]}


def fixture_outbreak(world: Any, cubes: int = 2, cadence: bool = False) -> dict[str, Any]:
    """Developer fixture: put cubes in the region the wizard stands in and one neighbour, and (by default) stop the cadence so a
    scenario is not disturbed. The story bridge then opens a healer's quest by itself from that state."""
    from wizard_rts import tech

    if not tech.god_allowed(world):
        raise PermissionError("the outbreak fixture is a developer/test command")
    s = state(world)
    i = player_region(world)
    k = kind_for_era(int(getattr(world, "era_index", 0)))
    s.cubes[i] = min(const("cube_cap"), cubes)
    s.kind[i] = k["id"]
    nb = s.neighbours[i][0]
    s.cubes[nb] = 1
    s.kind[nb] = k["id"]
    world.outbreaks_enabled = bool(cadence)
    return {"region": s.rid(i), "cubes": s.cubes[i], "neighbour": s.rid(nb), "kind": k["id"]}

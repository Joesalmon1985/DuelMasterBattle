"""Workplace disruptions: real, visible closures that stop production until they are repaired (D22 story cause, P1.4 catastrophes).

A disruption is a state on a building, `b["disrupted"] = {cause, label, since_ms, repair, repair_ms, progress_ms, by}`:
- the building's programme does not run while it is disrupted (workers.production_quantum, industry drills), so its output is
  measurably lost; the snapshot row carries the label, and Godot draws a marker;
- the faction repairs it with its own legal means: the building requests the `repair` wares over the roads (logistics.io_for adds
  them to its requests), and once they are delivered the repair takes `repair_ms` of game time; the wares are then consumed;
- the wizard can end a disruption early through a story effect (`clear`, called with a quest receipt by story.apply_effects).

Causes (all deterministic: seeded per building and game minute, never by iterating a set or wall clock):
- `collapse`: a mine's gallery caves in. Base chance per working mine per game minute, raised by war damage below half health and by
  an outbreak in its region. Repair: timber props (logs) and a long dig-out. This replaced the exhausted vein as the miner quest's
  cause when mineral sites became inexhaustible (D22).
- `sickness` (and the era's other outbreak kinds): a workplace in a hex region with outbreak cubes closes; the chance grows with the
  cubes. Repair: rations for the sick, slower while the region is still infected.
- `outbreak_fire`: when a region overflows (regions._add_cube at the cap) its busiest workplace burns down (lifecycle destruction).
"""

from __future__ import annotations

import random
from typing import Any

CHECK_EVERY = 600  # economy quanta: once a game minute
COLLAPSE_PER_MIN = 0.004  # a working mine caves in about once in four game hours on its own
COLLAPSE_DAMAGED = 0.03  # below half health (war damage)
COLLAPSE_OUTBREAK = 0.01  # per cube in the mine's region
SICK_PER_CUBE = 0.012  # chance per game minute per cube that an affected workplace in the region closes
REPAIR = {
    "collapse": ({"log": 4}, 12 * 60_000, "Gallery collapsed"),
    "sickness": ({"ration": 2}, 4 * 60_000, "Workers sick"),
    "blight": ({"ration": 1, "water": 1}, 4 * 60_000, "Fields blighted"),
    "toxic_spill": ({"plank": 2, "water": 2}, 5 * 60_000, "Toxic spill"),
    "signal_fault": ({"iron": 1, "plank": 1}, 5 * 60_000, "Signal fault"),
}
MINE_KINDS = ("mine", "ironmine")


def is_mine(b: dict) -> bool:
    k = b.get("kind", "")
    return k in MINE_KINDS or (k.startswith("wl:") and "mine" in k) or k in ("mdy:mechanical_drill", "mdy:pneumatic_drill")


def active(b: dict) -> bool:
    return bool(b.get("disrupted"))


def disrupt(world: Any, b: dict, cause: str, by: str = "") -> bool:
    """Close a workplace. False if it is already disrupted, not a standing finished building, or a command centre."""
    if b.get("disrupted") or b.get("constructing") or int(b.get("hp", 1)) <= 0 or b.get("command_center") or b.get("destroyed"):
        return False
    wares, ms, label = REPAIR.get(cause, REPAIR["sickness"])
    now = int(world.dmb.clock.get("game_ms", 0))
    b["disrupted"] = {"cause": cause, "label": label, "since_ms": now, "repair": dict(wares), "repair_ms": int(ms), "progress_ms": 0, "by": by}
    b["stall"] = {"reason": "disrupted", "detail": label, "at_ms": now}
    world.fstat(b["faction_name"], "disruptions")
    world.stats["disruptions"] = world.stats.get("disruptions", 0) + 1
    world.events.append({"kind": "disrupted", "id": b["id"], "faction": b["faction_name"], "cause": cause, "label": label, "building_kind": b["kind"],
                         "tile": [b["tx"], b["ty"]]})
    return True


def clear(world: Any, b: dict, how: str) -> bool:
    d = b.pop("disrupted", None)
    if d is None:
        return False
    if (b.get("stall") or {}).get("reason") == "disrupted":
        b.pop("stall", None)
    now = int(world.dmb.clock.get("game_ms", 0))
    world.stats["disruption_ms_lost"] = world.stats.get("disruption_ms_lost", 0) + now - int(d["since_ms"])
    world.events.append({"kind": "disruption_cleared", "id": b["id"], "faction": b["faction_name"], "cause": d["cause"], "how": how,
                         "lasted_ms": now - int(d["since_ms"])})
    return True


def requests(b: dict, stock: dict[str, int]) -> dict[str, int]:
    """Repair wares the building still asks the roads for (added to logistics.io_for)."""
    d = b.get("disrupted")
    if not d:
        return {}
    return {g: n for g, n in d["repair"].items() if int(stock.get(g, 0)) < n}


def _region_cubes(world: Any, b: dict) -> tuple[int, str]:
    rg = world.__dict__.get("regions")
    if rg is None:
        return 0, ""
    i = rg.region_at(b["tx"], b["ty"])
    return rg.cubes[i], rg.kind[i]


def disruption_quantum(world: Any) -> None:
    every = 10  # repairs progress once a game second
    if world.economy_quanta % every == 0:
        _repairs(world, every * 100)
    if world.economy_quanta % CHECK_EVERY or world.economy_quanta == 0 or not getattr(world, "disruptions_enabled", True):
        return
    from wizard_rts import regions

    now = int(world.dmb.clock.get("game_ms", 0))
    minute = now // 60_000
    for bid, b in sorted(world.buildings.items()):
        if b.get("disrupted") or b.get("constructing") or "hp" not in b or int(b["hp"]) <= 0 or b.get("command_center"):
            continue
        if not b.get("operational", True) or b["kind"] in ("warehouse",):
            continue
        rng = random.Random(f"{world.seed}:disrupt:{bid}:{minute}")
        cubes, hazard = _region_cubes(world, b)
        if is_mine(b) and b.get("working_once"):
            p = COLLAPSE_PER_MIN + COLLAPSE_OUTBREAK * cubes
            if int(b["hp"]) * 2 < int(b.get("max_hp", 1)):
                p += COLLAPSE_DAMAGED
            if rng.random() < p:
                disrupt(world, b, "collapse", by="tremor" if cubes else ("war_damage" if int(b["hp"]) * 2 < int(b.get("max_hp", 1)) else "age"))
                continue
        if cubes and hazard and regions.production_factor(world, b) < 1.0 and rng.random() < SICK_PER_CUBE * cubes:
            disrupt(world, b, hazard if hazard in REPAIR else "sickness", by="outbreak")


def _repairs(world: Any, dt_ms: int) -> None:
    from wizard_rts.economy import _supply

    for bid, b in sorted(world.buildings.items()):
        d = b.get("disrupted")
        if not d:
            continue
        if int(b.get("hp", 1)) <= 0:
            b.pop("disrupted", None)
            continue
        stock = world.stocks.get(bid, {})
        if any(int(stock.get(g, 0)) < n for g, n in d["repair"].items()):
            continue  # waiting for the repair wares to be carried in
        cubes, _h = _region_cubes(world, b)
        d["progress_ms"] = int(d["progress_ms"]) + (dt_ms // 2 if cubes and d["cause"] != "collapse" else dt_ms)
        if d["progress_ms"] >= int(d["repair_ms"]):
            for g, n in d["repair"].items():
                _supply(world, bid).remove_wares(g, n)
                world.stats["consumed_" + g] = world.stats.get("consumed_" + g, 0) + n
            clear(world, b, "repaired")
            world.fstat(b["faction_name"], "repairs")


def summary(world: Any, faction: str | None = None) -> dict[str, Any]:
    rows = [b for b in world.buildings.values() if b.get("disrupted") and (faction is None or b["faction_name"] == faction)]
    by: dict[str, int] = {}
    for b in rows:
        by[b["disrupted"]["cause"]] = by.get(b["disrupted"]["cause"], 0) + 1
    return {"count": len(rows), "by_cause": by}

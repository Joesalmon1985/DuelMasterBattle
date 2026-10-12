"""Faction rise, decline, split and collapse from real conditions (D18, S12), and the full-cycle reset (D11, S07).

All of it is computed from state, never from a ranking:
- decline: the faction lost its capital (its home settlement is destroyed) or none of its buildings has worked for 10 game minutes;
- collapse: it holds no command centre and no MCV. Its buildings become ruins (the normal destruction lifecycle) and its units die;
- split: it holds `SPLIT_MIN_SETTLEMENTS` or more, the two largest are further apart than `SPLIT_DISTANCE` with no road link, and one has
  a settlement `unrest` of at least `SPLIT_UNREST`. The disconnected settlements, their buildings, workers and units go to a new
  successor faction with its own id. (Nothing in the simulation produces `unrest` yet: tests and the future outbreak/quest systems set it.)
- full-cycle reset (`cycle_reset`): a NEW world in which only the wizard persists; the six homelands are re-dealt by S07 from what the
  previous cycle's factions peaked at. It is a different transition from an ordinary era change (`vp.advance_era`).
"""

from __future__ import annotations

import zlib
from typing import Any

from wizard_rts import settlements, territory, vp

DECLINE_IDLE_MS = 10 * 60_000
SPLIT_MIN_SETTLEMENTS = 4
SPLIT_DISTANCE = 50  # S12 leaves N open: about three settlement radii (outposts are 16, homes 34)
SPLIT_UNREST = 0.6
CHECK_EVERY = 10


def state(world: Any) -> dict[str, Any]:
    st = world.__dict__.get("history")
    if st is None:
        st = world.history = {"faction": {n: {"state": "active", "last_productive_ms": 0, "peak": {"settlements": 0, "centroid": None, "weight": 0}}
                                          for n in world.faction_info}, "chronicle": [], "cycle": 0}
    return st


def _note(world: Any, faction: str, event: str, **kw: Any) -> None:
    now = int(world.dmb.clock.get("game_ms", 0))
    state(world)["chronicle"].append({"game_ms": now, "faction": faction, "event": event, **kw})
    world.events.append({"kind": "faction_" + event, "faction": faction, **kw})


def has_mcv(world: Any, faction: str) -> bool:
    return any(u["faction_name"] == faction and u.get("alive", True) and u.get("definition") == territory.MCV_DEFINITION for u in world.units.values())


def collapse(world: Any, faction: str) -> None:
    from wizard_rts.lifecycle import begin_destruction
    from wizard_rts.military import kill_unit

    fs = state(world)["faction"][faction]
    fs["state"] = "collapsed"
    for b in sorted(world.buildings.values(), key=lambda x: x["id"]):
        if b["faction_name"] == faction and not b.get("destroyed") and "hp" in b:
            b["hp"] = 0
            begin_destruction(world, b)
    for u in sorted(world.units.values(), key=lambda x: x["id"]):
        if u["faction_name"] == faction and u.get("alive", True):
            kill_unit(world, u, "collapse")
    _note(world, faction, "collapsed", ruins=sum(1 for b in world.buildings.values() if b["faction_name"] == faction))


def _connected(world: Any, a: str, b: str) -> bool:
    seen, stack = {a}, [a]
    while stack:
        cur = stack.pop()
        for nxt, _r in world.adjacency.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return b in seen


def split_candidates(world: Any, faction: str) -> tuple[dict, dict] | None:
    st = settlements.standing(world, faction)
    if len(st) < SPLIT_MIN_SETTLEMENTS:
        return None
    size = {r["id"]: sum(1 for b in world.buildings.values() if b.get("settlement_id") == r["id"] or settlements.of(world, b) == r["id"]) for r in st}
    ranked = sorted(st, key=lambda r: (-size[r["id"]], r["id"]))
    a, b = ranked[0], ranked[1]
    dist = max(abs(a["tile"][0] - b["tile"][0]), abs(a["tile"][1] - b["tile"][1]))
    if dist <= SPLIT_DISTANCE or _connected(world, a["centre"], b["centre"]):
        return None
    if max(float(a.get("unrest", 0.0)), float(b.get("unrest", 0.0))) < SPLIT_UNREST:
        return None
    return a, b


def split(world: Any, faction: str, breakaway: dict) -> str:
    """The breakaway settlement and everything of the faction nearer to it than to its other centres becomes a new faction."""
    base = f"{faction}-{sum(1 for n in world.faction_info if n.startswith(faction + '-')) + 2}"
    parent = world.faction_info[faction]
    fid = str(world.dmb.ids.new("faction"))
    world.faction_info[base] = {"id": fid, "name": base, "color": parent["color"], "tribe": parent.get("tribe", "barbarians"), "parent": faction}
    state(world)["faction"][base] = {"state": "active", "last_productive_ms": int(world.dmb.clock.get("game_ms", 0)), "peak": {"settlements": 0, "centroid": None, "weight": 0}}
    from wizard_rts import tech

    world.tech[base] = {"cards": list(world.tech[faction]["cards"]), "offers": [], "round": world.tech[faction]["round"], "next_round_ms": 0}
    bx, by = breakaway["tile"]
    others = [r for r in settlements.standing(world, faction) if r["id"] != breakaway["id"]]

    def near_breakaway(tx: int, ty: int) -> bool:
        db = max(abs(tx - bx), abs(ty - by))
        return all(db < max(abs(tx - o["tile"][0]), abs(ty - o["tile"][1])) for o in others)

    moved_b = moved_u = 0
    for b in sorted(world.buildings.values(), key=lambda x: x["id"]):
        if b["faction_name"] == faction and near_breakaway(b["tx"], b["ty"]):
            b["faction_name"], b["faction"] = base, fid
            if b.get("settlement_id") in world.dmb.settlements:
                world.dmb.settlements[b["settlement_id"]]["faction"] = base
            moved_b += 1
    for u in sorted(world.units.values(), key=lambda x: x["id"]):
        if u["faction_name"] == faction and u.get("alive", True) and near_breakaway(u["tx"], u["ty"]):
            u["faction_name"], u["faction"] = base, fid
            moved_u += 1
    for w in list(world.workers.values()) + list(world.carriers.values()):
        if w.get("faction_name") == faction and w.get("building") in world.buildings and world.buildings[w["building"]]["faction_name"] == base:
            w["faction_name"], w["faction"] = base, fid
    _note(world, faction, "split", successor=base, settlement=breakaway["id"], buildings=moved_b, units=moved_u)
    return base


def history_quantum(world: Any) -> None:
    if world.economy_quanta % CHECK_EVERY:
        return
    st = state(world)
    now = int(world.dmb.clock.get("game_ms", 0))
    for name in list(world.faction_info):
        fs = st["faction"].setdefault(name, {"state": "active", "last_productive_ms": now, "peak": {"settlements": 0, "centroid": None, "weight": 0}})
        if fs["state"] == "collapsed":
            continue
        mine = settlements.standing(world, name)
        if len(mine) > fs["peak"]["settlements"] or (not fs["peak"]["centroid"] and mine):
            _record_peak(world, name, mine)
        if any(b["faction_name"] == name and b.get("working") for b in world.buildings.values()):
            fs["last_productive_ms"] = now
        if not mine and not has_mcv(world, name):
            collapse(world, name)
            continue
        home = next((r for r in world.dmb.settlements.values() if r["faction"] == name and r.get("home")), None)
        lost_capital = home is not None and home["state"] != "standing"
        idle = now - fs["last_productive_ms"] >= DECLINE_IDLE_MS and any(b["faction_name"] == name for b in world.buildings.values())
        if (lost_capital or idle) and fs["state"] == "active":
            fs["state"] = "declining"
            _note(world, name, "declined", why="lost_capital" if lost_capital else "idle_10_minutes")
        elif not (lost_capital or idle) and fs["state"] == "declining":
            fs["state"] = "active"
            _note(world, name, "recovered")
        cand = split_candidates(world, name)
        if cand is not None:
            split(world, name, cand[1])


def _record_peak(world: Any, faction: str, mine: list[dict]) -> None:
    weights = []
    for r in mine:
        n = sum(1 for b in world.buildings.values() if b["faction_name"] == faction and "hp" in b
                and max(abs(b["tx"] - r["tile"][0]), abs(b["ty"] - r["tile"][1])) <= 34)
        weights.append((max(1, n), r["tile"]))
    total = sum(w for w, _t in weights)
    cx = sum(w * t[0] for w, t in weights) / total
    cy = sum(w * t[1] for w, t in weights) / total
    state(world)["faction"][faction]["peak"] = {"settlements": len(mine), "centroid": [round(cx, 2), round(cy, 2)], "weight": total,
                                                "vp": vp.faction_vp(world, faction), "game_ms": int(world.dmb.clock.get("game_ms", 0))}


# ------------------------------------------------------------------ full-cycle reset (D11, S07)

def fertility(world: Any, tile: tuple[int, int], radius: int = 20) -> int:
    t = world.terrain
    n = 0
    for y in range(max(0, tile[1] - radius), min(t.h, tile[1] + radius + 1)):
        for x in range(max(0, tile[0] - radius), min(t.w, tile[0] + radius + 1)):
            if t.cls[y * t.w + x] == 0:  # arable
                n += 1
    return n


def deal_homelands(world: Any) -> list[int]:
    """S07 (as implemented): rank the previous cycle's factions by peak VP then peak settlement count (ties by name); rank the six
    homelands by fertility (ties by index). The strongest faction's *previous peak centroid* decides which fertile homeland it
    inherits: it takes the most fertile homeland nearest to that centroid among the top three; every other faction takes the
    remaining homelands in fertility order following the same rank. Returns start_index per faction (FACTIONS order)."""
    st = state(world)
    names = list(world.faction_info)
    root_names = [n for n in names if "-" not in n][:6] or names[:6]
    starts = [tuple(s) for s in world.terrain.starts]
    fert = {i: fertility(world, s) for i, s in enumerate(starts)}
    homelands = sorted(fert, key=lambda i: (-fert[i], i))
    rank = sorted(root_names, key=lambda n: (-int(st["faction"].get(n, {}).get("peak", {}).get("vp", 0)),
                                             -int(st["faction"].get(n, {}).get("peak", {}).get("settlements", 0)), n))
    top = rank[0]
    centroid = st["faction"].get(top, {}).get("peak", {}).get("centroid")
    assignment: dict[str, int] = {}
    pool = list(homelands)
    if centroid:
        cands = pool[:3]
        pick = min(cands, key=lambda i: (max(abs(starts[i][0] - centroid[0]), abs(starts[i][1] - centroid[1])), i))
        assignment[top] = pick
        pool.remove(pick)
        rest = [n for n in rank if n != top]
    else:
        rest = list(rank)
    for n in rest:
        assignment[n] = pool.pop(0)
    return [assignment[n] for n in root_names] + [i for i in range(len(starts)) if i not in assignment.values()][:0]


def cycle_reset(world: Any) -> Any:
    """Return a NEW HybridWorld for the next cycle. Persisting: the wizard (pose, Aspect scores) and a summary of the old cycle.
    Not persisting: every settlement, building, unit, worker, person, quest, item, road and stock (D11)."""
    from wizard_rts.world import HybridWorld

    st = state(world)
    cycle = int(st["cycle"]) + 1
    perm = deal_homelands(world)
    fresh = HybridWorld(world.seed + 1000 * cycle, terrain=world.terrain is not None, map_size=world.map_size, profile=world.profile,
                        start_perm=perm)
    fresh.history = {"faction": {n: {"state": "active", "last_productive_ms": 0, "peak": {"settlements": 0, "centroid": None, "weight": 0}} for n in fresh.faction_info},
                     "chronicle": [], "cycle": cycle}
    fresh.past_cycles = list(getattr(world, "past_cycles", [])) + [{
        "cycle": cycle - 1, "seed": world.seed, "game_ms": int(world.dmb.clock.get("game_ms", 0)), "era": vp.era_state(world)["index"],
        "peaks": {n: dict(f["peak"]) for n, f in st["faction"].items()}, "vp": vp.totals(world), "homeland_deal": perm}]
    # the wizard keeps his character: pose and Aspect scores. Nothing else crosses over.
    fresh.player = {"tx": fresh.player["tx"], "ty": fresh.player["ty"], "facing": world.player.get("facing", "down")}
    from sim.dmb.narrative.aspects import AspectService

    scores = dict(AspectService(world.dmb)._store().get("scores", {}).get("player", {}))
    if scores:
        store = AspectService(fresh.dmb)._store()
        store.setdefault("scores", {})["player"] = scores
    world.events.append({"kind": "cycle_reset", "cycle": cycle})
    return fresh


def snapshot(world: Any) -> dict[str, Any]:
    st = state(world)
    return {"cycle": st["cycle"], "factions": {n: f["state"] for n, f in st["faction"].items()}, "chronicle": st["chronicle"][-12:],
            "cycle_pending": bool(getattr(world, "cycle_pending", False))}

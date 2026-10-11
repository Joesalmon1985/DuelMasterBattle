"""Stationary-entity diagnostics: who is not making progress, where, doing what, and why.

Playtest 1 reported workers and carriers "walking on the spot in front of buildings". The cause was presentation (a walking loop
on idle figures, fixed in hybrid_art.gd), but the question "is anything genuinely stuck?" needs an answer from the authoritative
simulation, not from a picture. `watch_quantum` records, once a second, when each mobile entity last changed tile or finished a
task; `stuck_report` lists the ones that have had no meaningful progress for a while with everything needed to debug them:

    id, class, tile, destination, task, path, movement progress, animation, cargo, blocked reason, time without progress.

Nothing here changes the simulation. An entity that is waiting for a reason (a worker inside its hut, a carrier on a road with no
ware to move) is not reported; one that should be moving but is not is reported with the reason the simulation can name.
"""

from __future__ import annotations

from typing import Any

WATCH_EVERY = 10  # quanta (one second)
DEFAULT_STALL_MS = 20_000


def watch_quantum(world: Any) -> None:
    """Called every WATCH_EVERY quanta: remember where each mobile entity was and since when it has not moved on."""
    if world.economy_quanta % WATCH_EVERY:
        return
    now = int(world.dmb.clock.get("game_ms", 0))
    seen = world.__dict__.setdefault("_watch", {})
    live = set()
    for cls, table in (("worker", world.workers), ("carrier", world.carriers), ("unit", world.units)):
        for eid, e in table.items():
            if cls == "unit" and not e.get("alive", True):
                continue
            live.add(eid)
            key = (e["tx"], e["ty"], _task(cls, e))
            w = seen.get(eid)
            if w is None or w["key"] != key or w["tile_progress"] != _progress(cls, e):
                seen[eid] = {"key": key, "since": now, "tile_progress": _progress(cls, e)}
    for eid in [i for i in seen if i not in live]:
        del seen[eid]


def _progress(cls: str, e: dict) -> int:
    if cls == "carrier":
        return int(e.get("index", 0)) * 10 + (1 if e.get("cargo") else 0)
    if cls == "worker":
        return int(e.get("pc", 0)) * 1000 + len(e.get("path") or [])
    return len(e.get("path") or [])


def _task(cls: str, e: dict) -> str:
    if cls == "worker":
        return "%s:%s" % (e.get("program", ""), e.get("anim", ""))
    if cls == "carrier":
        return "carry" if e.get("cargo") else "wait"
    order = e.get("order") or {}
    return "%s:%s" % (order.get("kind", "none"), e.get("status", ""))


def _blocked_reason(world: Any, cls: str, e: dict) -> str:
    if cls == "carrier":
        road = world.roads.get(e["road_id"], [])
        nxt = road[min(len(road) - 1, e["index"] + 1)] if road else None
        if nxt is not None and world.tile_blocked_for_carrier(tuple(nxt)):
            return "hazard on the road: the carrier waits for the wizard to clear it"
        if e.get("status") == "blocked":
            return "tile blocked"
        return "no ware is waiting on this road" if not e.get("cargo") else "carrying but not advancing"
    if cls == "unit":
        st = e.get("status", "")
        return {
            "blocked": "another unit stands on the next tile",
            "stuck": "no route to the destination for this locomotor",
            "waiting_route": "route search budget for this quantum was spent",
            "deploying": "unfolding into a command centre",
        }.get(st, "no order" if not e.get("order") else "ordered but not moving (%s)" % st)
    if cls == "worker":
        if e.get("path"):
            return "walking a path but not advancing"
        if e.get("wait_ms", 0) > 0:
            return "working (waiting out an animation)"
        return "program step has not completed (%s)" % e.get("program", "")
    return ""


def _destination(cls: str, e: dict) -> Any:
    if cls == "carrier":
        road = e.get("cargo") and e["cargo"].get("path")
        return road[-1] if road else None
    if e.get("path"):
        return list(e["path"][-1])
    order = e.get("order") or {}
    return order.get("tile") or order.get("target")


def stuck_report(world: Any, min_ms: int = DEFAULT_STALL_MS) -> list[dict[str, Any]]:
    """Entities that should be making progress and have not for `min_ms` of game time."""
    now = int(world.dmb.clock.get("game_ms", 0))
    seen = world.__dict__.get("_watch", {})
    out = []
    for cls, table in (("worker", world.workers), ("carrier", world.carriers), ("unit", world.units)):
        for eid, e in table.items():
            w = seen.get(eid)
            if w is None or now - w["since"] < min_ms:
                continue
            if not _should_move(world, cls, e):
                continue
            out.append({
                "id": eid, "class": cls, "tile": [e["tx"], e["ty"]], "destination": _destination(cls, e), "task": _task(cls, e),
                "path_left": len(e.get("path") or []), "move_progress": e.get("progress_ms", 0), "anim": e.get("anim", ""),
                "cargo": (e.get("cargo") or {}).get("good") if cls == "carrier" else (e.get("carrying") or ""),
                "blocked_reason": _blocked_reason(world, cls, e), "stalled_ms": now - w["since"], "faction": e.get("faction_name", ""),
            })
    out.sort(key=lambda r: -r["stalled_ms"])
    return out


def _should_move(world: Any, cls: str, e: dict) -> bool:
    """Is this entity supposed to be progressing right now (so that standing still is a problem)?"""
    if cls == "carrier":
        return bool(e.get("cargo")) or e.get("status") == "blocked"
    if cls == "unit":
        if e.get("deploying_ms"):
            return False
        return bool(e.get("order")) and e.get("status") in ("blocked", "stuck", "waiting_route", "moving", "ordered")
    if cls == "worker":
        b = world.buildings.get(e["building"])
        inside = b is not None and (e["tx"], e["ty"]) == (b["tx"], b["ty"]) and e.get("anim") == "idle" and not e.get("path")
        return not inside and bool(e.get("path")) and e.get("wait_ms", 0) <= 0
    return False

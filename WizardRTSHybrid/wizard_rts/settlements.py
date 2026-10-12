"""Stable settlement identity and chronicle (D04, roadmap M3/M4 foundation).

A settlement is a command centre (a faction's first warehouse, or a deployed MCV) and the territory around it. It gets a persistent
`settlement:N` id the moment the centre exists; the id is never reused (re-founding on the same tile makes a new one, S02). The record
lives in `world.dmb.settlements` (the legacy WorldState slot, so the legacy quest/people code can bind to it) and keeps a chronicle of
founded / destroyed events with the game time and cause. VP and eras are layered on this in `vp.py`.
"""

from __future__ import annotations

from typing import Any


def register(world: Any, building: dict) -> str:
    """Create the settlement record for a new command-centre building and stamp its id on the building."""
    store = world.dmb.settlements
    sid = str(world.dmb.ids.new("settlement"))
    n = len(store) + 1
    faction = building["faction_name"]
    home = not building.get("outpost") and not any(r["faction"] == faction for r in store.values())
    store[sid] = {
        "id": sid, "faction": faction, "name": f"{faction} {'home' if home else 'outpost'} {n}", "centre": building["id"],
        "tile": [building["tx"], building["ty"]], "founded_ms": int(world.dmb.clock.get("game_ms", 0)), "state": "standing",
        "home": home, "chronicle": [{"event": "founded", "game_ms": int(world.dmb.clock.get("game_ms", 0)), "cause": "founding"}],
    }
    building["settlement_id"] = sid
    from wizard_rts import vp

    vp.note_founded(world, sid, faction)
    return sid


def of(world: Any, building: dict) -> str | None:
    """The settlement a building belongs to (nearest command centre of its faction, as territory.settlement_of)."""
    from wizard_rts import territory

    cc = territory.settlement_of(world, building)
    return cc.get("settlement_id") if cc else None


def record(world: Any, sid: str) -> dict[str, Any] | None:
    return world.dmb.settlements.get(sid)


def mark_destroyed(world: Any, building: dict, cause: str = "destroyed", by: str = "") -> None:
    sid = building.get("settlement_id")
    rec = world.dmb.settlements.get(sid) if sid else None
    if rec is None or rec["state"] != "standing":
        return
    rec["state"] = "destroyed"
    rec["chronicle"].append({"event": "destroyed", "game_ms": int(world.dmb.clock.get("game_ms", 0)), "cause": cause, "by": by})
    world.events.append({"kind": "settlement_destroyed", "settlement": sid, "faction": rec["faction"], "cause": cause, "by": by})


def standing(world: Any, faction: str | None = None) -> list[dict[str, Any]]:
    return [r for r in world.dmb.settlements.values() if r["state"] == "standing" and (faction is None or r["faction"] == faction)]

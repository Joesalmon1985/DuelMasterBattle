"""Victory points and era progress (D04, D07, D09; S01-S04).

VP is *derived from the settlement chronicle*, never kept as a free counter:
  standing VP   +1 per settlement of the faction in state `standing` (a deployed MCV or the home command centre; an undeployed MCV is not one)
  conquest VP   +1 to the faction that dealt the final blow to a settlement's command centre, written once under the ledger key
                `<settlement_id>:destroyed`; wizard-caused destruction awards nothing and simply ends the owner's standing VP (S03).
The ledger (`world.dmb.definitions["vp_ledger"]`) is idempotent: a key can be written once, so repeated events, saves and reloads never
double count, and `replay` recomputes every faction's VP from the chronicle alone to prove the live totals.

Era progress (S04): an era ends when some faction has gained `era_vp_threshold` VP since the era began, or after `era_max_ms` (the
stall guard). Both are configurable world attributes, tuned by `scripts/vp_report.py` rather than assumed. An ordinary era change keeps
every building, unit and person; it opens the next card pool and gives every faction one extra draft round (S05).
"""

from __future__ import annotations

from typing import Any

from wizard_rts import settlements, tech

ERA_VP_THRESHOLD = 6  # S04 proposed 10; measured by scripts/vp_report.py: 10 VP was not reached in 40 minutes on three seeds (top VP 3 at 14-16 min, 5 at 26-39 min), so 6 is the working default
ERA_MAX_MS = 60 * 60_000
CHECK_EVERY = 10  # economy quanta


def ledger(world: Any) -> dict[str, Any]:
    return world.dmb.definitions.setdefault("vp_ledger", {})


def note_founded(world: Any, sid: str, faction: str) -> None:
    key = f"{sid}:founded"
    ledger(world).setdefault(key, {"sid": sid, "event": "founded", "faction": faction, "game_ms": int(world.dmb.clock.get("game_ms", 0))})


def on_destroyed(world: Any, building: dict, by: str) -> dict[str, Any] | None:
    """A settlement's command centre reached 0 HP. `by` is the id of the shooter (unit or building) or 'wizard'."""
    sid = building.get("settlement_id")
    if not sid or building.get("kind") != "warehouse":
        return None
    key = f"{sid}:destroyed"
    led = ledger(world)
    if key in led:
        return {"status": "idempotent"}
    owner = building["faction_name"]
    shooter = world.units.get(by) or world.buildings.get(by)
    winner = shooter["faction_name"] if shooter is not None and by != "wizard" else ""
    if winner == owner:
        winner = ""  # a faction cannot score by destroying its own settlement
    cause = "wizard" if by == "wizard" else ("faction" if winner else "other")
    led[key] = {"sid": sid, "event": "destroyed", "faction": owner, "winner": winner, "cause": cause, "by": by, "game_ms": int(world.dmb.clock.get("game_ms", 0))}
    settlements.mark_destroyed(world, building, cause=cause, by=by)
    world.events.append({"kind": "vp_conquest", "settlement": sid, "owner": owner, "winner": winner, "cause": cause})
    return {"status": "ok", "winner": winner, "cause": cause}


def faction_vp(world: Any, faction: str) -> int:
    standing = len(settlements.standing(world, faction))
    awards = sum(1 for e in ledger(world).values() if e["event"] == "destroyed" and e.get("winner") == faction)
    return standing + awards


def totals(world: Any) -> dict[str, int]:
    return {name: faction_vp(world, name) for name in world.faction_info}


def replay(world: Any) -> dict[str, int]:
    """Recompute every faction's VP from the chronicle and the ledger alone (no live building lookups)."""
    out = {name: 0 for name in world.faction_info}
    for rec in world.dmb.settlements.values():
        destroyed = any(c["event"] == "destroyed" for c in rec["chronicle"])
        if rec["chronicle"] and rec["chronicle"][0]["event"] == "founded" and not destroyed and rec["faction"] in out:
            out[rec["faction"]] += 1
    for e in ledger(world).values():
        if e["event"] == "destroyed" and e.get("winner") in out:
            out[e["winner"]] += 1
    return out


# ------------------------------------------------------------------ eras

def era_state(world: Any) -> dict[str, Any]:
    st = world.__dict__.get("era")
    if st is None:
        st = world.era = {"index": 0, "started_ms": 0, "base": {}, "log": []}
        st["base"] = totals(world)
    return st


def progress(world: Any) -> int:
    st = era_state(world)
    return max((v - st["base"].get(f, 0) for f, v in totals(world).items()), default=0)


def advance_era(world: Any, reason: str) -> bool:
    """An ordinary era transition (D09/D11): nothing is destroyed. False when already in the last era."""
    st = era_state(world)
    if st["index"] >= len(tech.ERAS) - 1:
        return False
    now = int(world.dmb.clock.get("game_ms", 0))
    st["index"] += 1
    st["started_ms"] = now
    st["base"] = totals(world)
    st["log"].append({"era": tech.ERAS[st["index"]], "game_ms": now, "reason": reason, "vp": dict(st["base"])})
    world.era_index = st["index"]
    tech.on_era_change(world)
    world.events.append({"kind": "era_advanced", "era": tech.ERAS[st["index"]], "reason": reason})
    return True


def vp_quantum(world: Any) -> None:
    if world.economy_quanta % CHECK_EVERY:
        return
    st = era_state(world)
    now = int(world.dmb.clock.get("game_ms", 0))
    threshold = int(getattr(world, "era_vp_threshold", ERA_VP_THRESHOLD))
    due = "vp_threshold" if progress(world) >= threshold else ("stall_guard" if now - st["started_ms"] >= int(getattr(world, "era_max_ms", ERA_MAX_MS)) else "")
    if due:
        if not advance_era(world, due) and not getattr(world, "cycle_pending", False):
            world.cycle_pending = True  # the last era is over: the full historical cycle ends (history.cycle_reset builds the next world)
            world.events.append({"kind": "cycle_due", "reason": due})


def snapshot(world: Any) -> dict[str, Any]:
    st = era_state(world)
    return {"era": tech.ERAS[st["index"]], "era_index": st["index"], "vp": totals(world), "progress": progress(world),
            "threshold": int(getattr(world, "era_vp_threshold", ERA_VP_THRESHOLD)), "started_ms": st["started_ms"]}


def set_era(world: Any, index: int) -> None:
    """Developer fixture: jump to an era without playing the VP race (the owner's safe accelerated progression)."""
    if not tech.god_allowed(world):
        raise PermissionError("set_era is a developer/test command")
    st = era_state(world)
    st["index"] = max(0, min(int(index), len(tech.ERAS) - 1))
    st["started_ms"] = int(world.dmb.clock.get("game_ms", 0))
    st["base"] = totals(world)
    world.era_index = st["index"]
    tech.on_era_change(world)

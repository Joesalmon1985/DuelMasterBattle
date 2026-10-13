"""Victory points and era progress (D04, D07, D09; S01-S04).

VP is *derived from the settlement chronicle*, never kept as a free counter:
  standing VP   +1 per settlement of the faction in state `standing` (a deployed MCV or the home command centre; an undeployed MCV is not one)
  conquest VP   +1 to the faction that dealt the final blow to a settlement's command centre, written once under the ledger key
                `<settlement_id>:destroyed`; wizard-caused destruction awards nothing and simply ends the owner's standing VP (S03).
The ledger (`world.dmb.definitions["vp_ledger"]`) is idempotent: a key can be written once, so repeated events, saves and reloads never
double count, and `replay` recomputes every faction's VP from the chronicle alone to prove the live totals.

Era progress (S04, revised 12 Oct 2026): an era ends when the WORLD has gained `ERA_VP_THRESHOLDS[era]` VP since the era began (the
sum over factions of each one's positive gain: a founded settlement or a conquest; a loss does not count against it), or after
`era_max_ms` (the stall guard, reported separately as a non-natural transition). The leader-only rule of the first M4 version could not
be met without conquest (a faction holds at most a few settlements), so every measured transition was a stall-guard one. Both are configurable world attributes, tuned by `scripts/vp_report.py` rather than assumed. An ordinary era change keeps
every building, unit and person; it opens the next card pool and gives every faction one extra draft round (S05).
"""

from __future__ import annotations

from typing import Any

from wizard_rts import settlements, tech

ERA_VP_THRESHOLD = 6  # legacy single threshold; a world attribute era_vp_threshold overrides every era (developer pacing switch)
ERA_VP_THRESHOLDS = (6, 8, 8)  # world VP gained to leave Prehistoric, Historic, Modern; Modern was 10 until measured (+1 VP per ~10 min in Modern)
ERA_MAX_MS = 75 * 60_000
CHECK_EVERY = 10  # economy quanta
ERA_VP_END = 8  # drafting v2: one faction's current VP that ends an era (plan 5.6 candidates 8-14; provisional 8 from the 90-min probe where leaders reach 8-9 by minute 40; the P12 study decides)
ERA_VP_STEP = 4  # drafting v2: the bar of the next era is the leader's current VP plus this (never below ERA_VP_END), so a standing lead cannot end every era at once
ERA_SUSTAIN_MS = 60_000  # debounce, not a minimum era length


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


def gains(world: Any) -> dict[str, int]:
    st = era_state(world)
    return {f: max(0, v - st["base"].get(f, 0)) for f, v in totals(world).items()}


def progress(world: Any) -> int:
    return sum(gains(world).values())


def threshold(world: Any) -> int:
    if "era_vp_threshold" in world.__dict__:
        return int(world.era_vp_threshold)
    st = era_state(world)
    return ERA_VP_THRESHOLDS[min(st["index"], len(ERA_VP_THRESHOLDS) - 1)]


def advance_era(world: Any, reason: str) -> bool:
    """An ordinary era transition (D09/D11): nothing is destroyed. False when already in the last era."""
    st = era_state(world)
    if st["index"] >= len(tech.ERAS) - 1:
        return False
    now = int(world.dmb.clock.get("game_ms", 0))
    from wizard_rts import draft

    if draft.enabled(world):
        draft.end_era(world)  # the leftover-pack rule reads current VP at this instant, before the new era starts
    st["index"] += 1
    st["started_ms"] = now
    st["base"] = totals(world)
    st["bar"] = max(int(getattr(world, "era_vp_end", ERA_VP_END)), max(st["base"].values(), default=0) + int(getattr(world, "era_vp_step", ERA_VP_STEP)))
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
    from wizard_rts import draft

    if draft.enabled(world):  # plan v2 5.4: a faction's CURRENT VP reaching the era bar, held for the sustain window
        top = max(totals(world).values(), default=0)
        if top >= int(st.get("bar", getattr(world, "era_vp_end", ERA_VP_END))):
            st.setdefault("above_since", now)
        else:
            st.pop("above_since", None)
        due = "vp_threshold" if "above_since" in st and now - st["above_since"] >= int(getattr(world, "era_sustain_ms", ERA_SUSTAIN_MS)) else (
            "stall_guard" if now - st["started_ms"] >= int(getattr(world, "era_max_ms", ERA_MAX_MS)) else "")
        if due:
            st.pop("above_since", None)
            if not advance_era(world, due) and not getattr(world, "cycle_pending", False):
                world.cycle_pending = True
                world.events.append({"kind": "cycle_due", "reason": due})
        return
    due = "vp_threshold" if progress(world) >= threshold(world) else ("stall_guard" if now - st["started_ms"] >= int(getattr(world, "era_max_ms", ERA_MAX_MS)) else "")
    if due:
        if not advance_era(world, due) and not getattr(world, "cycle_pending", False):
            world.cycle_pending = True  # the last era is over: the full historical cycle ends (history.cycle_reset builds the next world)
            world.events.append({"kind": "cycle_due", "reason": due})


def draft_on(world: Any) -> bool:
    from wizard_rts import draft

    return draft.enabled(world)


def snapshot(world: Any) -> dict[str, Any]:
    st = era_state(world)
    now = int(world.dmb.clock.get("game_ms", 0))
    guard = int(getattr(world, "era_max_ms", ERA_MAX_MS))
    last = st["log"][-1] if st["log"] else None
    return {"era": tech.ERAS[st["index"]], "era_index": st["index"], "vp": totals(world), "progress": progress(world), "gains": gains(world),
            "threshold": int(st.get("bar", threshold(world))) if draft_on(world) else threshold(world), "started_ms": st["started_ms"], "elapsed_ms": now - st["started_ms"],
            "stall_guard_in_ms": max(0, st["started_ms"] + guard - now), "next_era": tech.ERAS[st["index"] + 1] if st["index"] + 1 < len(tech.ERAS) else "",
            "last_reason": last["reason"] if last else "", "log": [dict(e) for e in st["log"]]}


def set_era(world: Any, index: int) -> None:
    """Developer fixture: jump to an era without playing the VP race (the owner's safe accelerated progression)."""
    if not tech.god_allowed(world):
        raise PermissionError("set_era is a developer/test command")
    st = era_state(world)
    st["index"] = max(0, min(int(index), len(tech.ERAS) - 1))
    st["started_ms"] = int(world.dmb.clock.get("game_ms", 0))
    st["base"] = totals(world)
    st["bar"] = max(int(getattr(world, "era_vp_end", ERA_VP_END)), max(st["base"].values(), default=0) + int(getattr(world, "era_vp_step", ERA_VP_STEP)))
    world.era_index = st["index"]
    tech.on_era_change(world)

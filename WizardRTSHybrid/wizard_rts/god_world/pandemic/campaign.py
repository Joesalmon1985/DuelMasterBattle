"""The campaign in the world (D54, D56): begun when an age starts running, one responder turn every `pandemic_turn` of game time on the shared
clock, the six responders manufactured at their factions' base facilities under a recorded supply contract (no strategic cost: the contract is a
record, the hand is untouched), won or lost on the published conditions. A loss pauses the run and offers a retry from the age's checkpoint (the
same island, the same bases, a new crisis seed) or a new world. Everything lives in `world.pandemic` and is saved with the world."""

from __future__ import annotations

import json
from typing import Any

from .. import rules as world_rules
from . import coordinator, presentation, rules as R, scenario

FX_KEEP_MS = 30_000
MANUFACTURE_GAP_MS = 2500


def crisis_seed(world, retries: int) -> int:
    return (int(world.seed) * 1000003 + int(world.epoch) * 7919 + int(retries) * 104729) & 0x7FFFFFFF


def begin(world, retries: int = 0) -> dict[str, Any]:
    """A new campaign for the current age: the scenario on today's bases, the responders contracted at their base facilities, the first turn
    one cadence away so the responders can emerge."""
    sc = scenario.build(world)
    seed = crisis_seed(world, retries)
    st = R.new_campaign(sc, seed)
    now = int(world.game_ms)
    contracts = []
    for i, r in enumerate(st["responders"]):
        base_v = next((v for v in world.villages.values() if v["node"] == r["home"] and v["status"] in ("operational", "rebuilding", "building")), None)
        site = ""
        if base_v is not None and base_v.get("ops"):
            mil = next((s for s in base_v["ops"]["sites"].values() if s["kind"] == "military"), None)
            site = mil["id"] if mil else ""
        contracts.append({"responder": r["id"], "role": r["role"], "faction": r["faction"], "village": base_v["id"] if base_v else "", "site": site,
                          "game_ms": now, "ready_ms": now + MANUFACTURE_GAP_MS * (i + 1), "age": int(world.age), "epoch": int(world.epoch)})
        r["ready_ms"] = now + MANUFACTURE_GAP_MS * (i + 1)
    camp = {"state": st, "age": int(world.age), "epoch": int(world.epoch), "seed": seed, "retries": int(retries), "started_ms": now, "contracts": contracts,
            "next_turn_ms": now + world_rules.timing("pandemic_turn"), "fx": [], "turns": [], "bases": sc["bases"], "ended_ms": None}
    world.pandemic = camp
    world.pandemic_won = False
    world.pandemic_lost = None
    world.history.setdefault("pandemic_contracts", []).extend(contracts)
    world.log("pandemic_begin", age=int(world.age), seed=seed, retries=int(retries), posts=list(st["posts"]))
    return camp


def step(world) -> None:
    """Called every quantum while the world runs: one responder turn when the cadence is due; the result closes the campaign."""
    camp = world.pandemic
    if camp is None or world.phase != "RUNNING":
        return
    st = camp["state"]
    now = int(world.game_ms)
    if st["result"] is not None:
        if camp["ended_ms"] is None:  # a result reached outside a turn (a test's hand, a loaded save): closed the same way
            _close(world, camp, now)
        return
    if world.game_ms < int(camp["next_turn_ms"]):
        return
    actor = R.current(st)
    taken = coordinator.take_turn(st)
    camp["next_turn_ms"] = now + world_rules.timing("pandemic_turn")
    camp["turns"].append({"game_ms": now, "responder": actor["id"], "actions": [a.get("kind") for a in taken], "outbreaks": int(st["outbreaks"]), "cured": len(R.summary(st)["cured"])})
    camp["turns"] = camp["turns"][-60:]
    for r in st["responders"]:
        if len(r.get("path", [])) > 1:
            r["anim"] = {"path": list(r["path"]), "start_ms": now, "end_ms": now + world_rules.timing("pandemic_turn") - 2000}
            r["path"] = [r["location"]]
    for ev in st["last"]:
        camp["fx"].append(dict(ev, game_ms=now))
    camp["fx"] = [f for f in camp["fx"] if now - int(f["game_ms"]) <= FX_KEEP_MS][-80:]
    if st["result"] is not None:
        _close(world, camp, now)


def _close(world, camp: dict[str, Any], now: int) -> None:
    st = camp["state"]
    if st["result"] == "won":
        camp["ended_ms"] = now
        world.pandemic_won = True
        world.history.setdefault("pandemic", []).append(_record(world, camp))
        world.log("pandemic_won", age=int(world.age), turns=int(st["turn_count"]), outbreaks=int(st["outbreaks"]))
        if world.economic_qualified is not None:
            from .. import ages

            eq = world.economic_qualified
            ages.trigger(world, eq["faction"], eq["cause"])
    elif st["result"] == "lost":
        camp["ended_ms"] = now
        world.pandemic_lost = {"reason": st["lost_reason"], "age": int(world.age), "turns": int(st["turn_count"]), "outbreaks": int(st["outbreaks"]), "game_ms": now, "retries": int(camp["retries"])}
        world.history.setdefault("pandemic", []).append(_record(world, camp))
        world.paused = True
        world.log("pandemic_lost", age=int(world.age), reason=st["lost_reason"], turns=int(st["turn_count"]), outbreaks=int(st["outbreaks"]))


def retry(world) -> dict[str, Any]:
    """After a loss: the same age from its checkpoint (the island as it stands, the same bases) with a new crisis seed; the run resumes."""
    camp = world.pandemic
    if camp is None or world.pandemic_lost is None:
        return {"status": "rejected", "reason": "no_loss_to_retry"}
    retries = int(camp["retries"]) + 1
    begin(world, retries=retries)
    world.pandemic_retries = retries
    world.paused = False
    world.log("pandemic_retry", age=int(world.age), retries=retries)
    return {"status": "ok", "retries": retries, "seed": int(world.pandemic["seed"])}


def _record(world, camp: dict[str, Any]) -> dict[str, Any]:
    s = R.summary(camp["state"])
    return {"age": int(camp["age"]), "epoch": int(camp["epoch"]), "seed": int(camp["seed"]), "retries": int(camp["retries"]), "result": s["result"], "lost_reason": s["lost_reason"],
            "turns": s["turn_count"], "outbreaks": s["outbreaks"], "cured": s["cured"], "started_ms": int(camp["started_ms"]), "ended_ms": int(camp["ended_ms"] or world.game_ms),
            "minutes": round(((camp["ended_ms"] or world.game_ms) - camp["started_ms"]) / 60000.0, 1)}


def view(world, window: list[float] | None = None) -> dict[str, Any] | None:
    return presentation.view(world, world.pandemic, window) if world.pandemic is not None else None


def gate(world) -> dict[str, Any]:
    eq = world.economic_qualified
    return {"enabled": bool(world.pandemic_enabled), "economic": {"faction": eq["faction"], "game_ms": int(eq.get("game_ms", 0))} if eq else None,
            "pandemic_won": bool(world.pandemic_won), "pandemic_lost": world.pandemic_lost, "retries": int(world.pandemic_retries),
            "open": world.gate_open()}


def checkpoint_json(camp: dict[str, Any]) -> str:
    return json.dumps(camp, sort_keys=True)

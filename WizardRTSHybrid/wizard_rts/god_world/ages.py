"""Victory points and the shared age rollover (PRD 10). One faction at 10 current-age VP moves the whole world on, once, in one deterministic
transaction: every faction keeps its two most productive villages (by theoretical output, then level, then id) as level-one settlements of
the new age; everything else becomes history. The fourth age ends with a recorded result instead of a fifth age."""

from __future__ import annotations

from typing import Any

from . import composition, rules


def rank_villages(world, fid: str) -> list[dict[str, Any]]:
    cands = []
    for v in world.faction_villages(fid, ("operational",)):
        cands.append({"village": v["id"], "name": v["name"], "node": v["node"], "level": int(v["level"]),
                      "expected": round(composition.expected_output(world.board, v["node"], int(v["level"])), 4),
                      "pips": world.board.node_pips(v["node"])})
    cands.sort(key=lambda c: (-c["expected"], -c["level"], c["village"]))
    return cands


def trigger(world, winner: str, cause: dict[str, Any]) -> None:
    """Called by the world after the completion that put `winner` at the target. Records the result; advances the age unless this is the last one."""
    vp = {f: world.vp(f) for f in world.fids}
    record = {"age": int(world.age), "winner": winner, "vp": vp, "cause": dict(cause), "game_ms": int(world.game_ms), "pulses": int(world.pulses),
              "villages": sum(1 for v in world.villages.values() if v["status"] == "operational"),
              "cities": sum(1 for v in world.villages.values() if v["status"] == "operational" and int(v["level"]) >= 2),
              "trades": int(world.counters["trades"]), "bank_trades": int(world.counters["bank_trades"]), "roads": int(world.counters["roads"])}
    world.history["age_winners"].append(record)
    if world.age >= rules.last_age():
        if world.final_result is None:
            world.final_result = {**record, "winners": [w["winner"] for w in world.history["age_winners"]], "complete": True}
            world.log("final_result", winner=winner, vp=vp)
            world.save_requested = "final"
        return
    _transition(world, winner, cause, vp)


def _cancel_commitments(world) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    led = world.ledger
    for jid in sorted(world.journeys):
        j = world.journeys[jid]
        if j["type"] == "expedition":
            v = world.villages.get(j["village"])
            if v is not None and v.get("rid"):
                led.release(v["rid"])
                receipts.append({"kind": "expedition_refunded", "faction": j["faction"], "village": v["id"]})
            if v is not None:
                world.node_reserved.pop(v["node"], None)
                v["status"] = "cancelled"
                v["rid"] = None
                v["construction"] = None
        elif j["type"] == "caravan":
            if j.get("cargo"):
                led.unload_cargo(j["cargo"])  # to its owner: the initiator before the exchange, the initiator's return goods after it
                receipts.append({"kind": "caravan_unloaded", "faction": j["faction"], "journey": jid, "exchanged": bool(j.get("exchanged"))})
            if j.get("escrow"):
                led.release_escrow(j["escrow"])
                receipts.append({"kind": "escrow_released", "faction": j["partner"], "journey": jid})
        elif j["type"] == "bank":
            if j.get("cargo"):
                led.unload_cargo(j["cargo"])
                receipts.append({"kind": "bank_cargo_returned", "faction": j["faction"], "journey": jid})
        j["phase"] = "done"
    world.journeys = {}
    for eid in sorted(world.roads):
        r = world.roads[eid]
        if r["status"] == "building":
            led.release(r["rid"])
            receipts.append({"kind": "road_refunded", "faction": r["faction"], "edge": eid})
            del world.roads[eid]
    for vid in sorted(world.villages):
        v = world.villages[vid]
        if v.get("upgrade"):
            led.release(v["upgrade"]["rid"])
            receipts.append({"kind": "city_refunded", "faction": v["faction"], "village": vid})
            v["upgrade"] = None
        if v.get("rid"):
            led.release(v["rid"])
            v["rid"] = None
    world.node_reserved = {}
    world.pending_completions = []
    return receipts


def _transition(world, winner: str, cause: dict[str, Any], vp: dict[str, int]) -> None:
    old_age = int(world.age)
    tid = f"t{world.epoch}"
    selected: dict[str, list[str]] = {}
    candidates: dict[str, list[dict[str, Any]]] = {}
    for fid in world.fids:
        ranked = rank_villages(world, fid)
        if len(ranked) < 2:
            raise ValueError(f"faction {fid} has {len(ranked)} completed villages at the age boundary; a normal run always has two")
        candidates[fid] = ranked
        selected[fid] = [ranked[0]["village"], ranked[1]["village"]]
    world.phase = "TRANSITIONING"
    receipts = _cancel_commitments(world)
    archived = {fid: world.ledger.archive_faction(fid, f"age {old_age} closed") for fid in world.fids}
    keep = {v for vids in selected.values() for v in vids}
    retired = []
    for vid in sorted(world.villages):
        v = world.villages[vid]
        if vid in keep:
            v["history"].append({"age": old_age, "event": "carried", "level": int(v["level"]), "game_ms": int(world.game_ms)})
            v["level"] = 1
            v["status"] = "rebuilding"
            v["age"] = old_age + 1
            v["epoch"] = int(world.epoch) + 1
            v["produced"] = {r: 0 for r in rules.ROLES}
            v["construction"] = {"kind": "age", "started_ms": int(world.game_ms), "done_ms": int(world.game_ms) + rules.timing("transition_build")}
            v["ready_ms"] = int(world.game_ms) + rules.timing("transition_build")
            v["next_recruit_ms"] = v["ready_ms"] + rules.timing("military_interval")
        elif v["status"] in ("operational",):
            v["history"].append({"age": old_age, "event": "retired", "level": int(v["level"]), "game_ms": int(world.game_ms)})
            v["status"] = "historical"
            v["retired_age"] = old_age
            v["final_level"] = int(v["level"])
            retired.append(vid)
            world.history["retired"].append({"village": vid, "faction": v["faction"], "age": old_age, "level": int(v["level"])})
    for r in world.roads.values():
        if r["status"] == "complete":
            r["status"] = "historical"
            r["retired_age"] = old_age
    for u in world.units.values():
        if u["status"] == "active":
            u["status"] = "veteran"
    for fid in world.fids:
        world.ai[fid] = {**world.ai[fid], "goal": "", "reason": "the new age is being built", "plan": "", "target_node": None, "target_since_ms": 0}
    world._reach_cache = {}
    world.touch_topology()
    world.age = old_age + 1
    world.epoch += 1
    world.pulses = 0
    world.progress_pulse = 0
    world.last_roll = None
    world.next_roll_ms = None
    grants: dict[str, dict[str, int]] = {}
    for fid in world.fids:
        low = world.villages[selected[fid][1]]
        goods: dict[str, int] = {}
        for _h, role, _t in world.board.productive_hexes(low["node"]):
            goods[role] = goods.get(role, 0) + 1
        world.ledger.grant(fid, goods, "transition")
        grants[fid] = goods
    world.transition = {"id": tid, "phase": "TRANSITIONING", "age_from": old_age, "age_to": old_age + 1, "winner": winner, "cause": dict(cause), "vp": vp,
                        "candidates": candidates, "selected": selected, "retired": retired, "archived": archived, "receipts": receipts, "grants": grants,
                        "started_ms": int(world.game_ms), "ready_ms": int(world.game_ms) + rules.timing("transition_build"), "completed_ms": None}
    world.history["transitions"].append({k: world.transition[k] for k in ("id", "age_from", "age_to", "winner", "vp", "selected", "retired", "started_ms")})
    world.ledger.check()
    world.log("age_transition", id=tid, age_from=old_age, age_to=old_age + 1, winner=winner, selected=selected, retired=len(retired))
    world.save_requested = "boundary"


def sites_ready(world) -> None:
    """The carried villages' new-age districts are up: production resumes, the AIs wake, the transition is complete."""
    t = world.transition
    if t is None or t.get("phase") != "TRANSITIONING":
        return
    for vid in [v for vids in t["selected"].values() for v in vids]:
        v = world.villages[vid]
        if v["status"] == "rebuilding":
            v["status"] = "operational"
            v["construction"] = None
    t["phase"] = "RUNNING"
    t["completed_ms"] = int(world.game_ms)
    world.phase = "RUNNING"
    world.next_roll_ms = int(world.game_ms) + rules.timing("roll_interval")
    world.touch_topology()
    world.log("age_started", age=int(world.age), name=rules.age_name(world.age), vp={f: world.vp(f) for f in world.fids}, grants=t["grants"])
    world.save_requested = "age_started"

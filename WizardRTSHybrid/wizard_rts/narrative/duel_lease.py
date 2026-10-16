"""Story Ward Duel leases: the wizard's lesson and quest duels, played on the retained board and verified by Python.

A lease (`world.dmb.leases[id]`, kind `story_ward_duel`) has the shape of the hazard lease (`encounter`, `bot_seed`, `checkpoint`, `pause_token`)
so `DmbDuelLeaseAdapter` hosts it unchanged. Godot never owns an outcome: on finish it reports the casts it saw, and `resolve` re-scores every
cast against the enemy ward that Python reproduces (the lease's `fixed_ward`, or `WeaveBot.generate_ward` from `bot_seed`, which is parity-tested
against the GDScript). A report that does not verify voids the lease.
"""

from __future__ import annotations

import copy
import json
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from sim.dmb.adventure.duels import encounter_for_tier
from sim.dmb.time.clock import ClockService

from wizard_rts.duel import ward
from wizard_rts.narrative import events, party, wizard

KIND = "story_ward_duel"
OPPONENTS = Path(__file__).resolve().parents[1] / "data" / "narrative" / "opponents.json"
WIN_OUTCOMES = ("victory",)
HISTORY_KEYS = ("pattern", "fracture", "echo", "broke")


@lru_cache(maxsize=1)
def opponents() -> dict[str, Any]:
    return {k: v for k, v in json.loads(OPPONENTS.read_text()).items() if k.startswith("opponent.")}


def _leases(world: Any) -> dict[str, Any]:
    return world.dmb.leases


def active(world: Any, seat: str | None = None) -> dict[str, Any] | None:
    """The open story duel of the wizard acting now (or of `seat`). Every wizard has at most one; they do not see each other's."""
    mine = party.current(world) if seat is None else seat
    for lid, rec in sorted(_leases(world).items()):
        if rec.get("kind") == KIND and rec.get("state") == "ACTIVE" and rec.get("seat", "") == mine:
            return rec
    return None


def active_any(world: Any) -> list[dict[str, Any]]:
    return [rec for _lid, rec in sorted(_leases(world).items()) if rec.get("kind") == KIND and rec.get("state") == "ACTIVE"]


def _mine(world: Any, rec: dict[str, Any] | None) -> bool:
    return rec is not None and rec.get("kind") == KIND and rec.get("seat", "") == party.current(world)


def public_view(rec: dict[str, Any]) -> dict[str, Any]:
    return {"duel_id": rec["id"], "kind": KIND, "engine": "DmbBattleSim", "scene": rec["scene"], "encounter": copy.deepcopy(rec["encounter"]),
            "bot_seed": rec["bot_seed"], "progression_id": rec["progression_id"], "purpose": rec["purpose"], "has_checkpoint": bool(rec["checkpoint"])}


def _combatants(world: Any, opp: dict[str, Any], fixed_ward: list[int] | None) -> tuple[dict, dict]:
    player = wizard.combatant(world, int(opp.get("player_max_casts", opp.get("max_casts", 8))))  # a forgiving budget for the apprentice is configuration, not a different rule
    pool = list(player["attack_pool"])
    enemy = {"id": "story_rival", "display_name": opp["display_name"], "archetype": "wizard", "kind": "wizard",
             "weave_size": player["weave_size"], "ward_size": player["ward_size"], "attack_pool": list(pool), "ward_pool": list(pool),
             "allow_repeats": True, "max_casts": int(opp.get("max_casts", 8)), "min_cast_seconds": 5.0, "max_cast_seconds": 60.0,
             "bot_logic": opp["bot_logic"], "bot_solver_cap": int(opp.get("bot_solver_cap", 60)), "bot_mistake_rate": float(opp.get("bot_mistake_rate", 0.0)),
             "think_min_seconds": float(opp["think_min_seconds"]), "think_max_seconds": float(opp["think_max_seconds"])}
    if fixed_ward:
        enemy["fixed_ward"] = [int(x) for x in fixed_ward]
    if opp.get("ward_pool"):  # an opponent that only weaves some colours (the rats): its Ward is drawn from them, and Python reproduces it from the same pool
        enemy["ward_pool"] = [int(c) for c in opp["ward_pool"] if int(c) in pool] or list(pool)
    w = wizard.wiz(world)
    if w.pop("wounded", None):  # a lost scrap with a rat (pests.py): one cast fewer in the next duel, then it heals
        player["max_casts"] = max(2, int(player["max_casts"]) - 1)
        player["wounded"] = True
    return player, enemy


def begin(world: Any, opponent_id: str, *, purpose: str, fixed_ward: list[int] | None = None, display_name: str | None = None,
          spec: dict[str, Any] | None = None) -> dict[str, Any]:
    """Open a lease against `opponent_id` (from `opponents.json`, or `spec` for an opponent built at run time: the Trial's monsters); the reply has the
    shape `DmbDuelLeaseAdapter.begin_from_start_reply` reads."""
    if spec is None and opponent_id not in opponents():
        return {"status": "rejected", "reason": "unknown_opponent"}
    cur = active(world)
    if cur is not None:
        return {"status": "rejected", "reason": "duel_open", "payload": {"public": public_view(cur), "duel": cur}}
    opp = spec if spec is not None else opponents()[opponent_id]
    if spec is not None and spec.get("fixed_ward") and not fixed_ward:
        fixed_ward = list(spec["fixed_ward"])
    attempts = wizard.wiz(world)["duels"]["attempts"]
    attempt = 1 + sum(1 for a in attempts if a["purpose"] == purpose)
    bot_seed = zlib.crc32(f"{world.seed}|{purpose}|{attempt}".encode()) & 0x7FFFFFFF
    player, enemy = _combatants(world, opp, fixed_ward)
    if display_name:
        enemy["display_name"] = display_name
    encounter = encounter_for_tier(opp["tier"])
    encounter["player_combatant"], encounter["enemy_combatant"] = player, enemy
    encounter["attack_pool"], encounter["ward_pool"] = list(player["attack_pool"]), list(player["ward_pool"])
    lid = world.dmb.ids.new("lease")
    # one wizard alone freezes the world while they fight, as always; with company the world keeps living (the others are not in the duel)
    token = "" if party.multi(world) else ClockService(world.dmb.clock).acquire_pause("story_duel", lid)
    rec = {"id": lid, "kind": KIND, "state": "ACTIVE", "playable": True, "engine": "DmbBattleSim", "scene": "res://client/scenes/game_board.tscn",
           "bot_seed": bot_seed, "progression_id": opp["tier"], "encounter": encounter, "checkpoint": {}, "forced_defeat_by_cast": 0,
           "pause_token": token, "opponent": opponent_id, "purpose": purpose, "attempt": attempt, "fixed_ward": list(fixed_ward or []), "cube_id": "",
           "seat": party.current(world)}
    _leases(world)[lid] = rec
    events.log(world, "duel_begun", lease=lid, opponent=opponent_id, purpose=purpose, attempt=attempt)
    return {"status": "started", "payload": {"public": public_view(rec), "duel": rec}}


def checkpoint(world: Any, lease_id: str, cp: dict[str, Any]) -> dict[str, Any]:
    rec = _leases(world).get(lease_id)
    if not _mine(world, rec):
        return {"status": "missing_duel"}
    if rec["state"] != "ACTIVE":
        return {"status": "idempotent", "outcome": rec.get("outcome")}
    prior = rec["checkpoint"]
    if prior.get("secret") is not None and cp.get("secret") is not None and list(prior["secret"]) != list(cp["secret"]):
        return {"status": "rejected", "reason": "secret_reroll_forbidden"}
    merged = copy.deepcopy(prior)
    merged.update(copy.deepcopy(cp))
    rec["checkpoint"] = merged
    return {"status": "saved", "duel_id": lease_id}


def expected_enemy_ward(rec: dict[str, Any]) -> list[int]:
    if rec["fixed_ward"]:
        return [int(x) for x in rec["fixed_ward"]]
    enc = rec["encounter"]
    p, e = enc["player_combatant"], enc["enemy_combatant"]
    me = ward.Combatant(id="e", weave_size=e["weave_size"], attack_pool=list(e["attack_pool"]), ward_size=e["ward_size"], ward_pool=list(e["ward_pool"]),
                        allow_repeats=e["allow_repeats"], max_casts=e["max_casts"], bot_logic=e["bot_logic"])
    target = ward.Combatant(id="p", weave_size=p["weave_size"], attack_pool=list(p["attack_pool"]), ward_size=p["ward_size"], ward_pool=list(p["ward_pool"]),
                            allow_repeats=p["allow_repeats"], max_casts=p["max_casts"])
    return ward.WeaveBot(me, target, int(rec["bot_seed"])).generate_ward()


def verify(rec: dict[str, Any], report: dict[str, Any]) -> tuple[bool, str]:
    """Is the reported duel something the rules could have produced? (ward, every cast's feedback, the outcome's claim.)"""
    enc = rec["encounter"]
    p, e = enc["player_combatant"], enc["enemy_combatant"]
    enemy_ward = expected_enemy_ward(rec)
    if [int(x) for x in report.get("enemy_ward", [])] != enemy_ward:
        return False, "enemy_ward_mismatch"
    history = list(report.get("history", []))
    if len(history) > int(p["max_casts"]) or len(history) != int(report.get("player_casts", len(history))):
        return False, "cast_count"
    broke_any = False
    for h in history:
        if any(k not in h for k in HISTORY_KEYS):
            return False, "history_shape"
        pattern = [int(x) for x in h["pattern"]]
        if len(pattern) != int(p["weave_size"]) or any(x not in p["attack_pool"] for x in pattern):
            return False, "illegal_cast"
        r = ward.score_attack(enemy_ward, pattern)
        if (r["fracture"], r["echo"], bool(r["broken"])) != (int(h["fracture"]), int(h["echo"]), bool(h["broke"])):
            return False, "feedback_mismatch"
        broke_any = broke_any or bool(r["broken"])
    outcome = str(report.get("outcome", ""))
    if outcome == "victory" and not broke_any and int(report.get("enemy_casts", 0)) < int(e["max_casts"]):
        return False, "victory_unearned"
    if outcome in ("clash",) and not broke_any:
        return False, "clash_unearned"
    if outcome == "defeat" and broke_any:
        return False, "broke_ward_but_no_win"
    if outcome == "stalemate" and broke_any and int(report.get("enemy_casts", 0)) != len(history):
        return False, "broke_ward_but_no_win"  # a draw is both Wards broken in the same round (ward.py): the enemy cast as often as the player
    return True, "ok"


LETHAL = "stranger_duel"  # the one duel whose only winning end is a verified victory (campaign.py): any other way out of it is the apprentice's death


def _voided(world: Any, rec: dict[str, Any], why: str) -> None:
    if rec["purpose"] == LETHAL:
        from wizard_rts.narrative import campaign

        campaign.on_duel_void(world, rec, why)


def _release(world: Any, rec: dict[str, Any]) -> None:
    if rec.get("pause_token"):
        ClockService(world.dmb.clock).release_pause(rec["pause_token"])


def release_spared(world: Any, seat: str, why: str) -> bool:
    """End `seat`'s story duel without a verdict and without any penalty (the stranger withdrew from somebody else's victory)."""
    rec = active(world, seat)
    if rec is None:
        return False
    _release(world, rec)
    rec["state"], rec["outcome"] = "VOIDED", why
    events.log(world, "duel_released", lease=rec["id"], why=why, seat=seat)
    return True


def resolve(world: Any, lease_id: str, report: dict[str, Any]) -> dict[str, Any]:
    rec = _leases(world).get(lease_id)
    if not _mine(world, rec):
        return {"status": "rejected", "reason": "missing_duel"}
    if rec["state"] != "ACTIVE":
        return {"status": "idempotent", "outcome": rec.get("outcome"), "verified": rec["state"] == "RESOLVED"}
    ok, why = verify(rec, report)
    _release(world, rec)
    if not ok:
        rec["state"], rec["outcome"] = "VOIDED", "void"
        events.log(world, "duel_voided", lease=lease_id, why=why)
        _voided(world, rec, "rejected")
        return {"status": "rejected", "reason": "report_rejected", "detail": why, "purpose": rec["purpose"]}
    outcome = str(report["outcome"])
    result = "won" if outcome in WIN_OUTCOMES else ("lost" if outcome == "defeat" else "draw")
    rec["state"], rec["outcome"] = "RESOLVED", result
    duels = wizard.wiz(world)["duels"]
    if result == "won":
        duels["won"] += 1
    elif result == "lost":
        duels["lost"] += 1
    duels["attempts"].append({"purpose": rec["purpose"], "attempt": rec["attempt"], "outcome": result, "casts": int(report.get("player_casts", 0)),
                              "game_ms": int(world.dmb.clock.get("game_ms", 0))})
    events.log(world, "duel_resolved", lease=lease_id, purpose=rec["purpose"], outcome=result)
    return {"status": "resolved", "outcome": result, "verified": True, "purpose": rec["purpose"], "attempt": rec["attempt"]}


def abandon(world: Any, reason: str = "abandoned") -> dict[str, Any]:
    rec = active(world)
    if rec is None:
        return {"status": "ok", "closed": False}
    _release(world, rec)
    rec["state"], rec["outcome"] = "VOIDED", reason
    events.log(world, "duel_voided", lease=rec["id"], why=reason)
    _voided(world, rec, reason)
    return {"status": "ok", "closed": True, "purpose": rec["purpose"]}

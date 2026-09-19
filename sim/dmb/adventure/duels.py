"""Hazard duel entry for eligible cubes (C10 / T074 / G04 / T091 retained duel)."""

from __future__ import annotations

import copy
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from sim.dmb.hazards.service import CatastropheService
from sim.dmb.player.visits import VisitService

# C10 / G04 baseline encounter configuration for retained GameBoard + DmbBattleSim.
G04_WARD_ENCOUNTER = {
    "slot_count": 4,
    "colour_count": 6,
    "max_casts": 10,
    "allow_repeats": True,
    "attack_pool": [0, 1, 3, 4, 6, 9],
    "ward_pool": [0, 1, 3, 4, 6, 9],
    "min_cast_seconds": 5.0,
    "max_cast_seconds": 60.0,
    "player_combatant": {
        "id": "player",
        "display_name": "You",
        "archetype": "player",
        "kind": "player",
        "weave_size": 4,
        "ward_size": 4,
        "attack_pool": [0, 1, 3, 4, 6, 9],
        "ward_pool": [0, 1, 3, 4, 6, 9],
        "allow_repeats": True,
        "max_casts": 10,
        "min_cast_seconds": 5.0,
        "max_cast_seconds": 60.0,
    },
    "enemy_combatant": {
        "id": "hazard_rival",
        "display_name": "Manifestation",
        "archetype": "wizard",
        "kind": "wizard",
        "weave_size": 4,
        "ward_size": 4,
        "attack_pool": [0, 1, 3, 4, 6, 9],
        "ward_pool": [0, 1, 3, 4, 6, 9],
        "allow_repeats": True,
        "max_casts": 10,
        "min_cast_seconds": 5.0,
        "max_cast_seconds": 60.0,
        "bot_logic": "candidate_filter",
        "bot_solver_cap": 60,
        "bot_mistake_rate": 0.0,
        "think_min_seconds": 8.0,
        "think_max_seconds": 18.0,
    },
}

_PROGRESSION_PATH = (
    Path(__file__).resolve().parents[3]
    / "godot_project"
    / "content"
    / "source"
    / "duel_rules"
    / "progression.json"
)

# Essence pool indices used by retained BattleSim (legacy colour ids).
_DEFAULT_POOL = [0, 1, 3, 4, 6, 9]
_EXTENDED_POOL = [0, 1, 3, 4, 6, 9, 2, 5]  # up to 8 colours


def load_duel_progression(path: Path | None = None) -> dict[str, Any]:
    target = path or _PROGRESSION_PATH
    if not target.is_file():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def score_feedback(secret: list[int], guess: list[int]) -> tuple[int, int]:
    """C10 multiplicity feedback: exact positions, then colour-only without double-count."""
    if len(secret) != len(guess):
        raise ValueError("secret and guess length mismatch")
    exact = 0
    secret_remaining: list[int] = []
    guess_remaining: list[int] = []
    for s, g in zip(secret, guess):
        if int(s) == int(g):
            exact += 1
        else:
            secret_remaining.append(int(s))
            guess_remaining.append(int(g))
    counts = Counter(secret_remaining)
    colour_only = 0
    for g in guess_remaining:
        if counts.get(g, 0) > 0:
            colour_only += 1
            counts[g] -= 1
    return exact, colour_only


def rival_legal_candidates(
    *,
    slot_count: int,
    colour_count: int,
    allow_repeats: bool,
    history: list[dict[str, Any]],
    opponent_secret: list[int] | None = None,
) -> list[list[int]]:
    """Filter candidates consistent with observed feedback only.

    ``opponent_secret`` is accepted solely to prove it is never consulted.
    """
    del opponent_secret  # Explicitly unused — no secret-read shortcut.
    colours = list(range(colour_count))
    if allow_repeats:
        from itertools import product

        universe = [list(p) for p in product(colours, repeat=slot_count)]
    else:
        from itertools import permutations

        universe = [list(p) for p in permutations(colours, slot_count)]
    survivors: list[list[int]] = []
    for candidate in universe:
        ok = True
        for entry in history:
            guess = [int(x) for x in entry["guess"]]
            exact, colour_only = score_feedback(candidate, guess)
            if exact != int(entry["exact"]) or colour_only != int(entry["colour_only"]):
                ok = False
                break
        if ok:
            survivors.append(candidate)
    return survivors


def resolve_progression_request(
    *,
    slot_count: int,
    colour_count: int,
    progression: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Clamp to supported caps; overflow uses authored reward alternative."""
    rules = progression if progression is not None else load_duel_progression()
    caps = rules.get("supported_caps") or {"max_slot_count": 6, "max_colour_count": 8}
    max_slots = int(caps.get("max_slot_count") or 6)
    max_colours = int(caps.get("max_colour_count") or 8)
    if slot_count <= max_slots and colour_count <= max_colours:
        return {
            "status": "ok",
            "slot_count": int(slot_count),
            "colour_count": int(colour_count),
            "overflow": False,
        }
    reward = dict(rules.get("overflow_reward") or {})
    return {
        "status": "overflow",
        "slot_count": min(int(slot_count), max_slots),
        "colour_count": min(int(colour_count), max_colours),
        "overflow": True,
        "reward": reward,
    }


def encounter_for_tier(tier_id: str | None = None, *, era: str | None = None) -> dict[str, Any]:
    """Build a retained DmbBattleSim encounter from authored progression."""
    rules = load_duel_progression()
    tier: dict[str, Any] = dict(rules.get("baseline") or {})
    if era:
        binding = rules.get("era_binding") or {}
        tier_id = str(binding.get(era) or tier.get("id"))
    if tier_id:
        for entry in rules.get("progression") or []:
            if str(entry.get("id")) == str(tier_id):
                tier = dict(entry)
                break
    slots = int(tier.get("slot_count") or 4)
    colours = int(tier.get("colour_count") or 6)
    resolved = resolve_progression_request(slot_count=slots, colour_count=colours, progression=rules)
    slots = int(resolved["slot_count"])
    colours = int(resolved["colour_count"])
    pool = list(_EXTENDED_POOL[:colours]) if colours > len(_DEFAULT_POOL) else list(_DEFAULT_POOL[:colours])
    if len(pool) < colours:
        pool = list(range(colours))
    max_casts = int(tier.get("max_casts") or 10)
    allow_repeats = bool(tier.get("allow_repeats", True))
    encounter = copy.deepcopy(G04_WARD_ENCOUNTER)
    encounter["slot_count"] = slots
    encounter["colour_count"] = colours
    encounter["max_casts"] = max_casts
    encounter["allow_repeats"] = allow_repeats
    encounter["attack_pool"] = list(pool)
    encounter["ward_pool"] = list(pool)
    encounter["progression_id"] = tier.get("id") or "duel.baseline_c10"
    encounter["overflow"] = bool(resolved.get("overflow"))
    if resolved.get("overflow"):
        encounter["overflow_reward"] = resolved.get("reward")
    for side in ("player_combatant", "enemy_combatant"):
        combatant = encounter[side]
        combatant["weave_size"] = slots
        combatant["ward_size"] = slots
        combatant["attack_pool"] = list(pool)
        combatant["ward_pool"] = list(pool)
        combatant["allow_repeats"] = allow_repeats
        combatant["max_casts"] = max_casts
    return encounter


class HazardDuelService:
    """Prepare playable hazard duels — retained GameBoard lease, not a win button."""

    def __init__(self, world_state: Any):
        self.state = world_state
        self.service = CatastropheService(world_state)
        self.visits = VisitService(world_state)

    def can_start(self, cube_id: str) -> dict[str, Any]:
        cube = (self.service._cat().get("cubes") or {}).get(cube_id)
        if cube is None or not cube.get("active", True):
            return {"ok": False, "reason": "missing_cube"}
        if cube.get("type") == "pollution":
            return {"ok": False, "reason": "pollution_no_duel"}
        check = self.visits.can_treat(str(cube.get("hex_id")))
        if not check.get("ok"):
            return {"ok": False, "reason": check.get("reason")}
        return {"ok": True, "cube": cube}

    def begin(
        self,
        cube_id: str,
        *,
        lease_id: str | None = None,
        era: str | None = None,
        progression_id: str | None = None,
    ) -> dict[str, Any]:
        """Grant a ward-duel lease for retained game_board + DmbBattleSim.

        Does not attach MastermindDuel as live authority. Mastermind remains
        available as reference scoring via begin_mastermind_reference().
        """
        gate = self.can_start(cube_id)
        if not gate.get("ok"):
            return {"status": "rejected", **gate}
        self.state.clock.setdefault("pause_tokens", {})["hazard_duel"] = True
        from sim.dmb.military.buffs import BuffService

        BuffService(self.state).set_frozen(True)
        for lease in (getattr(self.state, "leases", {}) or {}).values():
            if isinstance(lease, dict) and lease.get("state") == "ACTIVE":
                lease["state"] = "FREEZING"
                lease["freeze_reason"] = "hazard_duel"
        duel_id = lease_id or self.state.ids.new("lease")
        cube = gate["cube"]
        if not isinstance(getattr(self.state, "rng", None), dict):
            self.state.rng = {}
        stream = int(self.state.rng.get("stream", 0) or 0)
        bot_seed = (stream ^ (zlib_crc(cube_id))) & 0x7FFFFFFF
        self.state.rng["stream"] = stream + 1
        era_name = era or str((getattr(self.state, "definitions", {}) or {}).get("era") or "prehistoric")
        encounter = encounter_for_tier(progression_id, era=None if progression_id else era_name)
        encounter["enemy_combatant"]["display_name"] = f"Manifestation ({cube.get('type', 'hazard')})"
        record = {
            "id": duel_id,
            "kind": "hazard_ward_duel",
            "cube_id": cube_id,
            "hex_id": cube.get("hex_id"),
            "type": cube.get("type"),
            "state": "ACTIVE",
            "playable": True,
            "engine": "DmbBattleSim",
            "scene": "res://client/scenes/game_board.tscn",
            "bot_seed": bot_seed,
            "era": era_name,
            "progression_id": encounter.get("progression_id"),
            "encounter": encounter,
            "checkpoint": {},
            "forced_defeat_by_cast": 0,
            "pause_token": "hazard_duel",
        }
        self.state.leases[duel_id] = record
        return {
            "status": "started",
            "duel": record,
            "public": self.public_view(record),
        }

    def begin_mastermind_reference(self, cube_id: str, *, lease_id: str | None = None) -> dict[str, Any]:
        """Reference-only Mastermind attach (scoring evidence). Not production Challenge."""
        gate = self.can_start(cube_id)
        if not gate.get("ok"):
            return {"status": "rejected", **gate}
        self.state.clock.setdefault("pause_tokens", {})["hazard_duel"] = True
        from sim.dmb.military.buffs import BuffService

        BuffService(self.state).set_frozen(True)
        duel_id = lease_id or self.state.ids.new("lease")
        cube = gate["cube"]
        record = {
            "id": duel_id,
            "kind": "hazard_duel",
            "cube_id": cube_id,
            "hex_id": cube.get("hex_id"),
            "type": cube.get("type"),
            "state": "ACTIVE",
            "playable": True,
        }
        from sim.dmb.adventure.mastermind import MastermindDuel

        if not isinstance(getattr(self.state, "rng", None), dict):
            self.state.rng = {}
        stream = int(self.state.rng.get("stream", 0) or 0)
        MastermindDuel.attach(record, rng=random.Random(stream ^ (zlib_crc(cube_id) & 0xFFFFFFFF)))
        self.state.rng["stream"] = stream + 1
        self.state.leases[duel_id] = record
        return {
            "status": "started",
            "duel": record,
            "public": MastermindDuel.public_view(record),
        }

    @staticmethod
    def public_view(duel: dict[str, Any]) -> dict[str, Any]:
        return {
            "duel_id": duel.get("id"),
            "cube_id": duel.get("cube_id"),
            "hex_id": duel.get("hex_id"),
            "kind": duel.get("kind"),
            "engine": duel.get("engine", "DmbBattleSim"),
            "scene": duel.get("scene", "res://client/scenes/game_board.tscn"),
            "encounter": copy.deepcopy(duel.get("encounter") or {}),
            "bot_seed": duel.get("bot_seed"),
            "progression_id": duel.get("progression_id"),
            "era": duel.get("era"),
            "has_checkpoint": bool(duel.get("checkpoint")),
        }

    def save_checkpoint(self, duel_id: str, checkpoint: dict[str, Any]) -> dict[str, Any]:
        duel = (getattr(self.state, "leases", {}) or {}).get(duel_id)
        if duel is None:
            return {"status": "missing_duel"}
        if duel.get("resolved"):
            return {"status": "idempotent", "duel_id": duel_id, "outcome": duel.get("outcome")}
        # Preserve private secrets / RNG / window / input — never reroll on resume.
        prior = dict(duel.get("checkpoint") or {})
        merged = copy.deepcopy(prior)
        merged.update(copy.deepcopy(checkpoint))
        # Lock secret once set.
        if prior.get("secret") is not None and checkpoint.get("secret") is not None:
            if list(prior["secret"]) != list(checkpoint["secret"]):
                return {"status": "rejected", "reason": "secret_reroll_forbidden"}
            merged["secret"] = list(prior["secret"])
        if prior.get("rng_state") is not None and "rng_state" not in checkpoint:
            merged["rng_state"] = copy.deepcopy(prior["rng_state"])
        duel["checkpoint"] = merged
        duel["checkpoint_version"] = int(duel.get("checkpoint_version") or 0) + 1
        return {
            "status": "saved",
            "duel_id": duel_id,
            "checkpoint_version": duel["checkpoint_version"],
            "checkpoint": copy.deepcopy(merged),
        }

    def resume(self, duel_id: str) -> dict[str, Any]:
        """Resume mid-window without secret reroll; world clocks stay frozen."""
        duel = (getattr(self.state, "leases", {}) or {}).get(duel_id)
        if duel is None:
            return {"status": "missing_duel"}
        if duel.get("resolved"):
            return {"status": "already_resolved", "outcome": duel.get("outcome")}
        checkpoint = copy.deepcopy(duel.get("checkpoint") or {})
        self.state.clock.setdefault("pause_tokens", {})["hazard_duel"] = True
        from sim.dmb.military.buffs import BuffService

        BuffService(self.state).set_frozen(True)
        return {
            "status": "resumed",
            "duel_id": duel_id,
            "checkpoint": checkpoint,
            "secret": list(checkpoint.get("secret") or []),
            "next_feedback": checkpoint.get("next_feedback"),
            "window": checkpoint.get("window"),
            "input": checkpoint.get("input"),
            "rng_state": checkpoint.get("rng_state"),
            "public": self.public_view(duel),
        }

    def tick_duel_clock(self, duel_id: str, *, duel_ms: int) -> dict[str, Any]:
        """Advance private duel clock only — Game Time / World Turn stay put."""
        duel = (getattr(self.state, "leases", {}) or {}).get(duel_id)
        if duel is None:
            return {"status": "missing_duel"}
        turn_before = int(self.state.clock.get("turn") or 0)
        game_ms_before = int(self.state.clock.get("game_ms") or 0)
        checkpoint = duel.setdefault("checkpoint", {})
        checkpoint["duel_ms"] = int(checkpoint.get("duel_ms") or 0) + int(duel_ms)
        assert int(self.state.clock.get("turn") or 0) == turn_before
        assert int(self.state.clock.get("game_ms") or 0) == game_ms_before
        return {
            "status": "ticked",
            "duel_ms": checkpoint["duel_ms"],
            "world_turn": turn_before,
            "world_game_ms": game_ms_before,
        }

    def resolve(
        self,
        duel_id: str,
        *,
        success: bool,
        command_id: str | None = None,
        apply_recovery_on_failure: bool = False,
    ) -> dict[str, Any]:
        duel = (getattr(self.state, "leases", {}) or {}).get(duel_id)
        if duel is None:
            return {"status": "missing_duel"}
        if duel.get("resolved"):
            # Idempotent duplicate / stale retransmission — same receipt, no second mutation.
            return {
                "status": "idempotent",
                "duel_id": duel_id,
                "outcome": duel.get("outcome"),
                "allowance_spent": duel.get("allowance_spent", False),
                "removal": duel.get("removal"),
                "recovery": duel.get("recovery"),
                "terminal": False,
            }
        cube_id = str(duel.get("cube_id"))
        cube = (self.service._cat().get("cubes") or {}).get(cube_id)
        self.state.clock.get("pause_tokens", {}).pop("hazard_duel", None)
        from sim.dmb.military.buffs import BuffService

        BuffService(self.state).set_frozen(False)

        if not success:
            duel["resolved"] = True
            duel["outcome"] = "failure"
            duel["allowance_spent"] = False
            recovery = None
            if apply_recovery_on_failure:
                from sim.dmb.player.recovery import RecoveryService

                recovery = RecoveryService(self.state).apply_return(
                    from_node_id=str(duel.get("hex_id") or self.state.player.get("node_id")),
                    command_id=command_id or f"recovery:{duel_id}",
                )
                duel["recovery"] = recovery
            return {
                "status": "failed",
                "allowance_spent": False,
                "terminal": False,
                "recovery": recovery,
            }

        if cube is None or not cube.get("active", True):
            duel["resolved"] = True
            duel["outcome"] = "world_resolved"
            duel["allowance_spent"] = False
            return {
                "status": "world_resolved",
                "allowance_spent": False,
                "reason": "cube_already_gone",
            }

        removed = self.service.remove_cube(cube_id, authority=f"duel:{duel_id}")
        recorded = self.visits.record_success(str(cube.get("hex_id")), command_id or duel_id)
        duel["resolved"] = True
        duel["outcome"] = "success"
        duel["allowance_spent"] = recorded.get("status") == "recorded"
        duel["removal"] = removed
        return {
            "status": "success",
            "removal": removed,
            "visit": recorded,
            "allowance_spent": recorded.get("status") == "recorded",
            "terminal": False,
        }


def zlib_crc(value: str) -> int:
    import zlib

    return zlib.crc32(str(value).encode("utf-8")) & 0xFFFFFFFF

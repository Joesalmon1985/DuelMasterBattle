"""Hazard duel entry for eligible cubes (C10 / T074 / G04 retained duel)."""

from __future__ import annotations

import copy
import random
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

    def begin(self, cube_id: str, *, lease_id: str | None = None) -> dict[str, Any]:
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
        encounter = copy.deepcopy(G04_WARD_ENCOUNTER)
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
            "encounter": encounter,
            "checkpoint": {},
            "forced_defeat_by_cast": 0,
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
            "has_checkpoint": bool(duel.get("checkpoint")),
        }

    def save_checkpoint(self, duel_id: str, checkpoint: dict[str, Any]) -> dict[str, Any]:
        duel = (getattr(self.state, "leases", {}) or {}).get(duel_id)
        if duel is None:
            return {"status": "missing_duel"}
        if duel.get("resolved"):
            return {"status": "idempotent", "duel_id": duel_id, "outcome": duel.get("outcome")}
        duel["checkpoint"] = copy.deepcopy(checkpoint)
        return {"status": "saved", "duel_id": duel_id}

    def resolve(self, duel_id: str, *, success: bool, command_id: str | None = None) -> dict[str, Any]:
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
            return {"status": "failed", "allowance_spent": False, "terminal": False}

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

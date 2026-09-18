"""Hazard duel entry for eligible cubes (C10 / T074)."""

from __future__ import annotations

import random
from typing import Any

from sim.dmb.hazards.service import CatastropheService
from sim.dmb.player.visits import VisitService


class HazardDuelService:
    """Prepare playable hazard duels — not a win button."""

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
        gate = self.can_start(cube_id)
        if not gate.get("ok"):
            return {"status": "rejected", **gate}
        # Freeze world clocks for duel.
        self.state.clock.setdefault("pause_tokens", {})["hazard_duel"] = True
        from sim.dmb.military.buffs import BuffService

        BuffService(self.state).set_frozen(True)
        # Freeze battle leases.
        for lease in (getattr(self.state, "leases", {}) or {}).values():
            if isinstance(lease, dict) and lease.get("state") == "ACTIVE":
                lease["state"] = "FREEZING"
                lease["freeze_reason"] = "hazard_duel"
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
        # Seed from world RNG stream so save/resume does not reroll mid-duel secrets.
        stream = int(self.state.rng.get("stream", 0) or 0)
        MastermindDuel.attach(record, rng=random.Random(stream ^ (hash(cube_id) & 0xFFFFFFFF)))
        self.state.rng["stream"] = stream + 1
        self.state.leases[duel_id] = record
        return {
            "status": "started",
            "duel": record,
            "public": MastermindDuel.public_view(record),
        }

    def resolve(self, duel_id: str, *, success: bool, command_id: str | None = None) -> dict[str, Any]:
        duel = (getattr(self.state, "leases", {}) or {}).get(duel_id)
        if duel is None:
            return {"status": "missing_duel"}
        if duel.get("resolved"):
            return {"status": "idempotent", "duel_id": duel_id}
        cube_id = str(duel.get("cube_id"))
        cube = (self.service._cat().get("cubes") or {}).get(cube_id)
        # Unfreeze
        self.state.clock.get("pause_tokens", {}).pop("hazard_duel", None)
        from sim.dmb.military.buffs import BuffService

        BuffService(self.state).set_frozen(False)

        if not success:
            duel["resolved"] = True
            duel["outcome"] = "failure"
            # Failed duel consumes no successful-treatment allowance.
            return {"status": "failed", "allowance_spent": False, "terminal": False}

        if cube is None or not cube.get("active", True):
            duel["resolved"] = True
            duel["outcome"] = "world_resolved"
            return {
                "status": "world_resolved",
                "allowance_spent": False,
                "reason": "cube_already_gone",
            }

        removed = self.service.remove_cube(cube_id, authority=f"duel:{duel_id}")
        recorded = self.visits.record_success(str(cube.get("hex_id")), command_id or duel_id)
        if recorded.get("status") == "rejected":
            # Should not remove a different cube; already removed the specific one only.
            pass
        duel["resolved"] = True
        duel["outcome"] = "success"
        return {
            "status": "success",
            "removal": removed,
            "visit": recorded,
            "allowance_spent": recorded.get("status") == "recorded",
            "terminal": False,
        }

"""Exclusive encounter lease registry with battle handoff helpers (C02/C07 T064)."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from sim.dmb.core.types import TypeValidationError
from sim.dmb.military.offscreen import OffscreenBattleResolver


@dataclass
class Lease:
    lease_id: str
    kind: str
    entity_ids: list[str]
    version: int
    state: str
    checkpoint: dict[str, Any]
    checkpoint_hash: str
    owner_session: str = ""
    closed_result: dict[str, Any] | None = None
    pending_reinforcements: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EncounterRegistry:
    leases: dict[str, Lease] = field(default_factory=dict)
    entity_index: dict[str, str] = field(default_factory=dict)
    closed_results: dict[str, dict[str, Any]] = field(default_factory=dict)

    @staticmethod
    def _hash(checkpoint: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(checkpoint, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def prepare(self, kind: str, ids: list[str], snapshot: dict[str, Any], lease_id: str) -> Lease:
        for entity_id in ids:
            if entity_id in self.entity_index:
                raise TypeValidationError(f"entity already leased: {entity_id}")
        return Lease(
            lease_id=lease_id,
            kind=kind,
            entity_ids=list(ids),
            version=0,
            state="PREPARED",
            checkpoint=dict(snapshot),
            checkpoint_hash=self._hash(snapshot),
        )

    def grant(
        self,
        kind: str,
        ids: list[str],
        snapshot: dict[str, Any],
        lease_id: str,
        *,
        owner_session: str = "",
    ) -> Lease:
        for entity_id in ids:
            if entity_id in self.entity_index:
                raise TypeValidationError(f"entity already leased: {entity_id}")
        lease = self.prepare(kind, ids, snapshot, lease_id)
        lease.owner_session = owner_session
        self.leases[lease_id] = lease
        for entity_id in ids:
            self.entity_index[entity_id] = lease_id
        lease.state = "ACTIVE"
        lease.version = 1
        return lease

    def checkpoint(self, lease_id: str, delta: dict[str, Any], *, version: int, base_hash: str) -> Lease:
        if lease_id not in self.leases:
            raise TypeValidationError("unknown lease")
        lease = self.leases[lease_id]
        if lease.version != version or lease.checkpoint_hash != base_hash:
            raise TypeValidationError("stale lease checkpoint")
        lease.checkpoint.update(delta)
        lease.checkpoint_hash = self._hash(lease.checkpoint)
        lease.version += 1
        return lease

    def close(self, lease_id: str, result: dict[str, Any]) -> dict[str, Any]:
        lease = self.leases.pop(lease_id)
        for entity_id in lease.entity_ids:
            self.entity_index.pop(entity_id, None)
        lease.state = "CLOSED"
        payload = {
            "lease_id": lease_id,
            "result": result,
            "final_version": lease.version,
            "authority": "server",
            "checkpoint": deepcopy(lease.checkpoint),
        }
        self.closed_results[lease_id] = payload
        lease.closed_result = payload
        return payload

    def resume(self, lease_id: str, *, session_id: str, expected_version: int) -> Lease:
        lease = self.leases.get(lease_id)
        if lease is None:
            raise TypeValidationError("lease closed or missing")
        if lease.owner_session and lease.owner_session != session_id:
            raise TypeValidationError("stale client cannot resume old lease")
        if lease.version != expected_version:
            raise TypeValidationError("stale lease version")
        return lease

    def freeze_all(self, reason: str) -> list[str]:
        frozen = []
        for lease in self.leases.values():
            if lease.state == "ACTIVE":
                lease.state = "FREEZING"
                lease.checkpoint["freeze_reason"] = reason
                frozen.append(lease.lease_id)
        return frozen

    def queue_reinforcement(self, lease_id: str, unit_state: dict[str, Any]) -> dict[str, Any]:
        """Versioned new-unit handshake; duplicate id adds once."""
        lease = self.leases.get(lease_id)
        if lease is None:
            raise TypeValidationError("unknown lease")
        uid = str(unit_state["id"])
        existing = {str(u.get("id")) for u in lease.pending_reinforcements}
        checkpoint_units = (lease.checkpoint.get("units") or {})
        if uid in existing or uid in checkpoint_units:
            return {"status": "duplicate", "unit_id": uid, "added": False}
        lease.pending_reinforcements.append(deepcopy(unit_state))
        lease.checkpoint.setdefault("pending_reinforcements", []).append(uid)
        lease.version += 1
        lease.checkpoint_hash = self._hash(lease.checkpoint)
        if uid not in lease.entity_ids:
            lease.entity_ids.append(uid)
            self.entity_index[uid] = lease_id
        return {"status": "queued", "unit_id": uid, "added": True, "version": lease.version}

    def close_for_travel(
        self,
        lease_id: str,
        *,
        world_state: Any,
        acknowledged_checkpoint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Close outgoing local lease at acknowledged checkpoint, then offscreen resolve."""
        lease = self.leases.get(lease_id)
        if lease is None:
            raise TypeValidationError("unknown lease")
        if acknowledged_checkpoint is not None:
            # Apply acknowledged unit health before close (merge patches).
            units_patch = acknowledged_checkpoint.get("units") or {}
            existing = lease.checkpoint.setdefault("units", {})
            for uid, patch in units_patch.items():
                base = dict(existing.get(uid) or {})
                base.update(deepcopy(patch))
                existing[uid] = base
            for key, value in acknowledged_checkpoint.items():
                if key == "units":
                    continue
                lease.checkpoint[key] = deepcopy(value)
            if world_state is not None:
                from sim.dmb.military.units import MilitaryService

                MilitaryService(world_state).receive_checkpoint(lease_id, acknowledged_checkpoint)
        snap = deepcopy(lease.checkpoint)
        closed = self.close(lease_id, {"reason": "travel", "handoff": "offscreen"})
        resolver = OffscreenBattleResolver(world_state)
        outcome = resolver.resolve(snap)
        if world_state is not None:
            resolver.commit_to_world(outcome)
        closed["offscreen"] = {
            "outcome": outcome.get("outcome"),
            "casualties": outcome.get("casualties"),
            "sim_ms": outcome.get("sim_ms"),
        }
        return closed

    def retain_on_wait(self, lease_id: str) -> Lease:
        """Wait retains local ownership — lease stays ACTIVE."""
        lease = self.leases.get(lease_id)
        if lease is None:
            raise TypeValidationError("unknown lease")
        if lease.state not in {"ACTIVE", "FREEZING"}:
            raise TypeValidationError("lease not retainable")
        lease.state = "ACTIVE"
        lease.checkpoint["retained_on_wait"] = True
        return lease

    def reject_stale_checkpoint(self, lease_id: str, *, version: int, base_hash: str) -> None:
        lease = self.leases.get(lease_id)
        if lease is None:
            # Closed — stale cannot overwrite result.
            if lease_id in self.closed_results:
                raise TypeValidationError("stale checkpoint cannot overwrite closed result")
            raise TypeValidationError("unknown lease")
        if lease.version != version or lease.checkpoint_hash != base_hash:
            raise TypeValidationError("stale lease checkpoint")

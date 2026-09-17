"""Exclusive encounter lease registry."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from sim.dmb.core.types import TypeValidationError


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


@dataclass
class EncounterRegistry:
    leases: dict[str, Lease] = field(default_factory=dict)
    entity_index: dict[str, str] = field(default_factory=dict)

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
        # Failed preparation must leave original owners intact: validate first.
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
        return {"lease_id": lease_id, "result": result, "final_version": lease.version, "authority": "server"}

    def resume(self, lease_id: str, *, session_id: str, expected_version: int) -> Lease:
        lease = self.leases.get(lease_id)
        if lease is None:
            raise TypeValidationError("lease closed or missing")
        if lease.owner_session and lease.owner_session != session_id:
            raise TypeValidationError("stale client cannot resume old lease")
        if lease.version != expected_version:
            raise TypeValidationError("stale lease version")
        return lease

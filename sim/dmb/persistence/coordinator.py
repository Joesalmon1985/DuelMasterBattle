"""Coordinated save/load barrier and bounded recovery checkpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sim.dmb.core.events import EventJournal
from sim.dmb.core.replay import ReplayLog
from sim.dmb.core.state import WorldState
from sim.dmb.core.world import WorldSim
from sim.dmb.persistence.repository import SaveRepository

RECOVERY_SLOT = "_recovery"
RECOVERY_INTERVAL_MS = 5000


def _strip_ephemeral_save_tokens(snapshot: dict[str, Any], active_token: str | None = None) -> None:
    """Remove temporary save-barrier tokens so loads do not leave Game Time frozen."""
    world = snapshot.get("world")
    if not isinstance(world, dict):
        return
    clock = world.get("clock")
    if not isinstance(clock, dict):
        return
    tokens = dict(clock.get("pause_tokens") or {})
    if active_token:
        tokens.pop(active_token, None)
    clock["pause_tokens"] = {
        key: value for key, value in tokens.items() if not str(key).startswith("save:")
    }


@dataclass
class SaveCoordinator:
    sim: WorldSim
    repository: SaveRepository
    _pending_load: dict[str, Any] | None = None
    last_recovery_game_ms: int = 0
    recovery_reasons: list[str] = field(default_factory=list)

    def request_save(self, slot: str) -> dict[str, Any]:
        token = self.sim.clock.acquire_pause("save", "coordinator")
        try:
            snapshot = self.sim.snapshot()
            _strip_ephemeral_save_tokens(snapshot, active_token=token)
            path = self.repository.write(slot, snapshot)
            return {"slot": slot, "path": str(path), "world_version": self.sim.state.world_version}
        finally:
            self.sim.clock.release_pause(token)

    def prepare_load(self, slot: str) -> dict[str, Any]:
        payload = self.repository.read(slot)
        _strip_ephemeral_save_tokens(payload)
        self._pending_load = payload
        return {
            "slot": slot,
            "world_id": payload["world"]["world_id"],
            "world_version": payload["world"]["world_version"],
        }

    def commit_load(self) -> WorldSim:
        if self._pending_load is None:
            raise RuntimeError("no prepared load")
        payload = self._pending_load
        _strip_ephemeral_save_tokens(payload)
        state = WorldState.from_dict(payload["world"])
        sim = WorldSim(state=state)
        sim.events = EventJournal.from_dict(payload.get("events", {}))
        sim.replay = ReplayLog.from_dict(payload.get("replay", {}))
        self._pending_load = None
        self.sim = sim
        self.last_recovery_game_ms = int(sim.state.clock.get("game_ms", 0))
        return sim

    def write_recovery_checkpoint(self, reason: str = "periodic") -> dict[str, Any]:
        """Persist a coordinated recovery checkpoint (C02 bounded restart)."""
        prepared = self.prepare_recovery_checkpoint(reason=reason)
        write = prepared.get("write")
        if callable(write):
            write()
        return {**prepared.get("saved", {}), "recovery": prepared.get("recovery")}

    def prepare_recovery_checkpoint(self, reason: str = "periodic") -> dict[str, Any]:
        """Snapshot under the save barrier, then return a deferred atomic writer.

        The caller should send the command reply before invoking ``write`` so disk
        I/O does not block the bridge round-trip. Snapshot remains consistent and
        atomic replacement is unchanged.
        """
        game_ms = int(self.sim.state.clock.get("game_ms", 0))
        meta = {
            "reason": reason,
            "game_ms": game_ms,
            "world_version": self.sim.state.world_version,
            "node_id": self.sim.state.player.get("node_id"),
            "position": list(self.sim.state.player.get("position") or []),
        }
        self.sim.state.clock["recovery_meta"] = dict(meta)
        token = self.sim.clock.acquire_pause("save", "coordinator")
        try:
            snapshot = self.sim.snapshot()
            _strip_ephemeral_save_tokens(snapshot, active_token=token)
        finally:
            self.sim.clock.release_pause(token)
        self.last_recovery_game_ms = game_ms
        self.recovery_reasons.append(reason)

        def _write() -> dict[str, Any]:
            path = self.repository.write(RECOVERY_SLOT, snapshot)
            return {
                "slot": RECOVERY_SLOT,
                "path": str(path),
                "world_version": snapshot.get("world", {}).get("world_version"),
            }

        return {"recovery": meta, "write": _write, "saved": {"slot": RECOVERY_SLOT}}

    def maybe_write_recovery_checkpoint(self, *, force: bool = False, reason: str = "periodic") -> dict[str, Any] | None:
        prepared = self.maybe_prepare_recovery_checkpoint(force=force, reason=reason)
        if not prepared:
            return None
        write = prepared.get("write")
        if callable(write):
            write()
        return {**prepared.get("saved", {}), "recovery": prepared.get("recovery")}

    def maybe_prepare_recovery_checkpoint(
        self, *, force: bool = False, reason: str = "periodic"
    ) -> dict[str, Any] | None:
        if self.sim.state.clock.get("pause_tokens"):
            return None
        game_ms = int(self.sim.state.clock.get("game_ms", 0))
        if not force and game_ms - self.last_recovery_game_ms < RECOVERY_INTERVAL_MS:
            return None
        return self.prepare_recovery_checkpoint(reason)

    def restore_recovery_checkpoint(self) -> dict[str, Any]:
        """Restore last recovery checkpoint. Reports rollback relative to live clock."""
        live_ms = int(self.sim.state.clock.get("game_ms", 0))
        prepared = self.prepare_load(RECOVERY_SLOT)
        restored = self.commit_load()
        recovered_ms = int(restored.state.clock.get("game_ms", 0))
        rollback_ms = max(0, live_ms - recovered_ms)
        meta = dict(restored.state.clock.get("recovery_meta") or {})
        meta["rollback_ms"] = rollback_ms
        meta["restored_game_ms"] = recovered_ms
        meta["slot"] = RECOVERY_SLOT
        meta["world_version"] = restored.state.world_version
        return {"sim": restored, "prepared": prepared, "meta": meta}

    def has_recovery_checkpoint(self) -> bool:
        try:
            self.repository.read(RECOVERY_SLOT)
            return True
        except Exception:
            return False

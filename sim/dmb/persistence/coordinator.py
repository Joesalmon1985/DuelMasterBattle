"""Coordinated save/load barrier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.events import EventJournal
from sim.dmb.core.replay import ReplayLog
from sim.dmb.core.state import WorldState
from sim.dmb.core.world import WorldSim
from sim.dmb.persistence.repository import SaveRepository


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
        return sim

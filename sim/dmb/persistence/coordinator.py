"""Coordinated save/load barrier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.events import EventJournal
from sim.dmb.core.replay import ReplayLog
from sim.dmb.core.state import WorldState
from sim.dmb.core.world import WorldSim
from sim.dmb.persistence.repository import SaveRepository


@dataclass
class SaveCoordinator:
    sim: WorldSim
    repository: SaveRepository
    _pending_load: dict[str, Any] | None = None

    def request_save(self, slot: str) -> dict[str, Any]:
        token = self.sim.clock.acquire_pause("save", "coordinator")
        try:
            snapshot = self.sim.snapshot()
            path = self.repository.write(slot, snapshot)
            return {"slot": slot, "path": str(path), "world_version": self.sim.state.world_version}
        finally:
            self.sim.clock.release_pause(token)

    def prepare_load(self, slot: str) -> dict[str, Any]:
        payload = self.repository.read(slot)
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
        state = WorldState.from_dict(payload["world"])
        sim = WorldSim(state=state)
        sim.events = EventJournal.from_dict(payload.get("events", {}))
        sim.replay = ReplayLog.from_dict(payload.get("replay", {}))
        self._pending_load = None
        self.sim = sim
        return sim

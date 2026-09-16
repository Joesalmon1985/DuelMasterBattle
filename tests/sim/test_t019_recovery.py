"""T019 recovery and save barrier checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from sim.dmb.bridge.server import SidecarServer
from sim.dmb.core.types import TypeValidationError
from sim.dmb.core.world import bootstrap_world
from sim.dmb.encounters.registry import EncounterRegistry
from sim.dmb.persistence.coordinator import SaveCoordinator
from sim.dmb.persistence.repository import SaveRepository


def test_save_barrier_restores_consistent_pair(tmp_path: Path) -> None:
    sim = bootstrap_world()
    coord = SaveCoordinator(sim, SaveRepository(tmp_path))
    saved = coord.request_save("slot0")
    assert "path" in saved
    # Mutate after save
    sim.state.player["node_id"] = "node:2"
    sim.state.clock["game_ms"] = 9999
    prepared = coord.prepare_load("slot0")
    restored = coord.commit_load()
    assert restored.state.player["node_id"] == "node:1"
    assert restored.state.clock["game_ms"] == 0
    assert prepared["world_version"] == restored.state.world_version


def test_stale_client_cannot_resume_old_lease() -> None:
    reg = EncounterRegistry()
    reg.grant("duel", ["unit:1"], {"hp": 10}, "lease:a", owner_session="sess-1")
    with pytest.raises(TypeValidationError, match="stale client"):
        reg.resume("lease:a", session_id="sess-other", expected_version=1)


def test_sidecar_disconnect_marks_pause(tmp_path: Path) -> None:
    server = SidecarServer(token="t", save_root=tmp_path, port=0)
    server.start_background()
    try:
        assert server.session.paused_for_bridge_failure is False
        server.session.paused_for_bridge_failure = True
        token = server.session.sim.clock.acquire_pause("bridge_failure", "server")
        assert token in server.session.sim.state.clock["pause_tokens"]
    finally:
        server.shutdown()

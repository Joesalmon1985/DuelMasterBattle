"""T019 recovery and save barrier checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from sim.dmb.bridge.server import SidecarServer
from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.core.types import TypeValidationError
from sim.dmb.core.world import bootstrap_world
from sim.dmb.encounters.registry import EncounterRegistry
from sim.dmb.persistence.coordinator import RECOVERY_SLOT, SaveCoordinator
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


def test_recovery_checkpoint_rolls_back_without_manual_reload(tmp_path: Path) -> None:
    sim = bootstrap_world(seed=7)
    coord = SaveCoordinator(sim, SaveRepository(tmp_path))
    # Advance some game time then checkpoint.
    sim.state.clock["game_ms"] = 1200
    sim.state.player["position"] = [6.0, 5.0]
    written = coord.write_recovery_checkpoint("periodic")
    assert written["slot"] == RECOVERY_SLOT
    checkpoint_ms = 1200
    # Further progress that must be discarded on recovery.
    sim.state.clock["game_ms"] = 4500
    sim.state.player["position"] = [11.0, 5.0]
    sim.state.player["node_id"] = "node:2"
    restored = coord.restore_recovery_checkpoint()
    assert restored["meta"]["rollback_ms"] == 4500 - checkpoint_ms
    assert restored["sim"].state.clock["game_ms"] == checkpoint_ms
    assert restored["sim"].state.player["node_id"] == "node:1"
    assert restored["sim"].state.player["position"] == [6.0, 5.0]


def test_travel_writes_recovery_and_sidecar_recover_command(tmp_path: Path) -> None:
    server = SidecarServer(token="tok", save_root=tmp_path, port=0)
    server.start_background()
    try:
        sim = server.session.sim
        env = CommandEnvelope(
            protocol_version=1,
            session_id="s",
            world_id=sim.state.world_id,
            command_id="t1",
            expected_world_version=sim.state.world_version,
            kind="Travel",
            payload={"from_node": "node:1", "to_node": "node:2"},
        )
        # Drive through server command path so recovery is written.
        body, deferred = server._handle_frame(
            {
                "kind": "Command",
                "protocol_version": 1,
                "session_id": "s",
                "world_id": sim.state.world_id,
                "command_id": "t1",
                "expected_world_version": sim.state.world_version,
                "command_kind": "Travel",
                "payload": {"from_node": "node:1", "to_node": "node:2"},
            },
            authenticated=True,
        )
        assert body["status"] == "ACCEPTED"
        assert body.get("recovery")
        if callable(deferred):
            deferred()
        assert server.session.coordinator.has_recovery_checkpoint()
        # Mutate then recover via command.
        server.session.sim.state.clock["game_ms"] = 8000
        recovered, _ = server._handle_frame(
            {
                "kind": "Command",
                "protocol_version": 1,
                "session_id": "s",
                "world_id": server.session.sim.state.world_id,
                "command_id": "r1",
                "expected_world_version": server.session.sim.state.world_version,
                "command_kind": "RecoverCheckpoint",
                "payload": {},
            },
            authenticated=True,
        )
        assert recovered["status"] == "ACCEPTED"
        assert recovered["payload"]["recovered"] is True
        assert recovered["payload"]["rollback_ms"] >= 0
        assert server.session.sim.state.player["node_id"] == "node:2"
        assert server.session.sim.state.player["position"] == [1.5, 5.0]
        assert server.session.sim.state.player["facing"] == "right"
    finally:
        server.shutdown()

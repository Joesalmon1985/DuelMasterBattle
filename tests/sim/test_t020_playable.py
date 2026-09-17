"""Playable FX-CLOCK command behaviours for G01."""

from __future__ import annotations

from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.core.world import bootstrap_world
from sim.dmb.testing.fixtures import run_fx_clock


def _env(sim, cid, kind, payload):
    return CommandEnvelope(
        protocol_version=1,
        session_id="g01",
        world_id=sim.state.world_id,
        command_id=cid,
        expected_world_version=sim.state.world_version,
        kind=kind,
        payload=payload,
    )


def test_fx_clock_still_passes() -> None:
    assert run_fx_clock().status == "PASS"


def test_observe_unknown_then_interact_reveals_name() -> None:
    sim = bootstrap_world(seed=7)
    person_id = next(iter(sim.state.people))
    obs = sim.dispatch(_env(sim, "o1", "Observe", {"entity_id": person_id}))
    assert obs.status == "ACCEPTED"
    assert obs.payload["known"] is False
    assert obs.payload["label"] == "unknown"
    inter = sim.dispatch(_env(sim, "i1", "Interact", {"entity_id": person_id}))
    assert inter.status == "ACCEPTED"
    assert inter.payload["known"] is True
    assert inter.payload.get("name") == "Mira"
    assert "debug" not in (inter.payload or {})


def test_sync_pose_does_not_advance_turn() -> None:
    sim = bootstrap_world(seed=7)
    turn = int(sim.state.clock["turn"])
    ver = sim.state.world_version
    reply = sim.dispatch(_env(sim, "p1", "SyncPose", {"position": [6, 6], "facing": "right"}))
    assert reply.status == "ACCEPTED"
    assert int(sim.state.clock["turn"]) == turn
    assert sim.state.world_version == ver
    assert sim.state.player["position"] == [6.0, 6.0]


def test_held_wait_unique_press_ids() -> None:
    sim = bootstrap_world(seed=7)
    a = sim.dispatch(_env(sim, "w1", "Wait", {"current_node": "node:1", "press_id": "a"}))
    b = sim.dispatch(_env(sim, "w2", "Wait", {"current_node": "node:1", "press_id": "a"}))
    c = sim.dispatch(_env(sim, "w3", "Wait", {"current_node": "node:1", "press_id": "b"}))
    assert a.status == "ACCEPTED"
    assert b.status == "REJECTED"
    assert c.status == "ACCEPTED"
    assert int(sim.state.clock["turn"]) == 2


def test_save_does_not_persist_ephemeral_save_pause_token(tmp_path) -> None:
    from sim.dmb.persistence.coordinator import SaveCoordinator
    from sim.dmb.persistence.repository import SaveRepository
    from sim.dmb.time.clock import ClockService

    sim = bootstrap_world(seed=7)
    assert not sim.state.clock.get("pause_tokens")
    coord = SaveCoordinator(sim, SaveRepository(tmp_path))
    saved = coord.request_save("g01_playtest")
    assert "path" in saved
    loaded = coord.prepare_load("g01_playtest")
    assert loaded["slot"] == "g01_playtest"
    sim2 = coord.commit_load()
    tokens = sim2.state.clock.get("pause_tokens") or {}
    assert not any(str(k).startswith("save:") for k in tokens)
    # Game Time must continue after loading an unpaused save.
    clock = ClockService(sim2.state.clock)
    before = int(sim2.state.clock["game_ms"])
    seq = int(sim2.state.clock.get("clock_sequence", 0))
    quanta = clock.request_advance(100, seq + 1)
    assert quanta == 1
    assert int(sim2.state.clock["game_ms"]) == before + 100

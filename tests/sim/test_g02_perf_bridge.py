"""G02 performance / bridge regressions: lean views, deferred recovery, ordering."""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import pytest

from sim.dmb.bridge.codec import FrameCodec
from sim.dmb.bridge.server import SidecarServer
from sim.dmb.core.world import bootstrap_world
from sim.dmb.persistence.coordinator import SaveCoordinator
from sim.dmb.persistence.repository import SaveRepository
from sim.dmb.testing.fixtures import load_fixture


def _roundtrip(sock: socket.socket, codec: FrameCodec, payload: dict) -> dict:
    sock.sendall(codec.encode(payload))
    buf = b""
    while True:
        chunk = sock.recv(65536)
        assert chunk
        buf += chunk
        frames = FrameCodec().feed(buf)
        if frames:
            return frames[0]


def _handshake(sock: socket.socket, codec: FrameCodec, token: str) -> dict:
    return _roundtrip(
        sock,
        codec,
        {
            "kind": "Handshake",
            "protocol_version": 1,
            "session_id": "perf",
            "token": token,
            "role": "local_client",
            "game_build_id": "g02",
        },
    )


def test_economy_view_excludes_receipts_by_default(tmp_path: Path) -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    view = sim.state.read_view("economy")
    assert "command_receipts" not in view
    assert "knowledge_raw" not in view
    assert "leases" not in view
    assert "stocks" in view
    assert "carts" in view
    assert "fx_cargo" in view


def test_economy_view_fields_filter(tmp_path: Path) -> None:
    sim = load_fixture("FX-CARGO", seed=202)
    lean = sim.state.read_view("economy", fields=["fx_cargo", "carts"])
    assert "fx_cargo" in lean
    assert "carts" in lean
    assert "stocks" not in lean
    assert "command_receipts" not in lean
    debug = sim.state.read_view("debug", fields=["command_receipts"])
    assert "command_receipts" in debug


def test_request_view_fields_over_bridge(tmp_path: Path) -> None:
    server = SidecarServer(token="secret", save_root=tmp_path, port=0, fixture="FX-CARGO", seed=202)
    server.start_background()
    try:
        sock = socket.create_connection((server.host, server.port), timeout=2)
        codec = FrameCodec()
        assert _handshake(sock, codec, "secret")["status"] == "ACCEPTED"
        reply = _roundtrip(
            sock,
            codec,
            {"kind": "RequestView", "scope": "economy", "fields": ["fx_cargo", "stocks"]},
        )
        assert reply["status"] == "ACCEPTED"
        view = reply["view"]
        assert "fx_cargo" in view
        assert "stocks" in view
        assert "command_receipts" not in view
        assert "carts" not in view
    finally:
        server.shutdown()


def test_recovery_disk_write_happens_after_reply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = SidecarServer(token="secret", save_root=tmp_path, port=0, fixture="FX-CARGO", seed=202)
    server.start_background()
    order: list[str] = []
    original_write = SaveRepository.write
    release = threading.Event()

    def tracked_write(self, slot, snapshot):  # noqa: ANN001
        order.append("disk_enter")
        # Hold the write so the client can observe the reply while disk is busy.
        release.wait(timeout=2.0)
        order.append("disk_done")
        return original_write(self, slot, snapshot)

    monkeypatch.setattr(SaveRepository, "write", tracked_write)
    try:
        sock = socket.create_connection((server.host, server.port), timeout=2)
        codec = FrameCodec()
        hs = _handshake(sock, codec, "secret")
        assert hs["status"] == "ACCEPTED"
        version = int(hs["world_version"])
        t0 = time.perf_counter()
        sock.sendall(
            codec.encode(
                {
                    "kind": "Command",
                    "protocol_version": 1,
                    "session_id": "perf",
                    "world_id": hs["world_id"],
                    "command_id": "wait-1",
                    "expected_world_version": version,
                    "command_kind": "Wait",
                    "payload": {"current_node": "node:1", "press_id": "w1"},
                }
            )
        )
        buf = b""
        while True:
            chunk = sock.recv(65536)
            assert chunk
            buf += chunk
            frames = FrameCodec().feed(buf)
            if frames:
                order.append("reply")
                reply = frames[0]
                break
        reply_ms = (time.perf_counter() - t0) * 1000.0
        release.set()
        deadline = time.time() + 2.0
        while "disk_done" not in order and time.time() < deadline:
            time.sleep(0.01)
        assert reply["status"] == "ACCEPTED"
        assert "reply" in order
        assert "disk_enter" in order
        assert order.index("reply") < order.index("disk_done")
        # Reply must not wait for the artificial disk stall.
        assert reply_ms < 150.0, f"reply blocked on disk ({reply_ms:.1f} ms)"
    finally:
        release.set()
        server.shutdown()


def test_duplicate_command_id_returns_receipt(tmp_path: Path) -> None:
    server = SidecarServer(token="secret", save_root=tmp_path, port=0)
    server.start_background()
    try:
        sock = socket.create_connection((server.host, server.port), timeout=2)
        codec = FrameCodec()
        hs = _handshake(sock, codec, "secret")
        version = int(hs["world_version"])
        cmd = {
            "kind": "Command",
            "protocol_version": 1,
            "session_id": "perf",
            "world_id": hs["world_id"],
            "command_id": "dup-1",
            "expected_world_version": version,
            "command_kind": "Wait",
            "payload": {"current_node": "node:1", "press_id": "dup"},
        }
        first = _roundtrip(sock, codec, cmd)
        assert first["status"] == "ACCEPTED"
        second = _roundtrip(sock, codec, cmd)
        assert second["status"] in {"ACCEPTED", "DUPLICATE"} or second.get("code") in {
            "DUPLICATE",
            "OK",
        }
        # World version must not advance twice for the same id.
        assert int(second.get("world_version", version)) == int(first.get("world_version", version))
    finally:
        server.shutdown()


def test_stale_expected_world_version_rejects(tmp_path: Path) -> None:
    server = SidecarServer(token="secret", save_root=tmp_path, port=0)
    server.start_background()
    try:
        sock = socket.create_connection((server.host, server.port), timeout=2)
        codec = FrameCodec()
        hs = _handshake(sock, codec, "secret")
        bad = _roundtrip(
            sock,
            codec,
            {
                "kind": "Command",
                "protocol_version": 1,
                "session_id": "perf",
                "world_id": hs["world_id"],
                "command_id": "stale-1",
                "expected_world_version": int(hs["world_version"]) - 1,
                "command_kind": "Wait",
                "payload": {"current_node": "node:1", "press_id": "stale"},
            },
        )
        assert bad["status"] == "REJECTED"
    finally:
        server.shutdown()


def test_prepare_recovery_keeps_consistent_snapshot(tmp_path: Path) -> None:
    sim = bootstrap_world(seed=7)
    coord = SaveCoordinator(sim, SaveRepository(tmp_path))
    prepared = coord.prepare_recovery_checkpoint(reason="unit")
    assert "recovery" in prepared
    assert callable(prepared["write"])
    saved = prepared["write"]()
    assert Path(saved["path"]).is_file()
    payload = json.loads(Path(saved["path"]).read_text(encoding="utf-8"))
    assert payload["world"]["world_id"] == sim.state.world_id

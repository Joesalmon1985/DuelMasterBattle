"""T016 sidecar protocol behavioural checks."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from sim.dmb.bridge.codec import FrameCodec
from sim.dmb.bridge.server import SidecarServer


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


def test_wrong_token_and_version_reject(tmp_path: Path) -> None:
    server = SidecarServer(token="secret", save_root=tmp_path, port=0)
    server.start_background()
    try:
        sock = socket.create_connection((server.host, server.port), timeout=2)
        codec = FrameCodec()
        bad = _roundtrip(
            sock,
            codec,
            {
                "kind": "Handshake",
                "protocol_version": 1,
                "session_id": "s",
                "token": "nope",
                "role": "local_client",
            },
        )
        assert bad["status"] == "REJECTED"
        sock.close()
        sock = socket.create_connection((server.host, server.port), timeout=2)
        bad_ver = _roundtrip(
            sock,
            codec,
            {
                "kind": "Handshake",
                "protocol_version": 99,
                "session_id": "s",
                "token": "secret",
                "role": "local_client",
            },
        )
        assert bad_ver["status"] == "REJECTED"
    finally:
        server.shutdown()


def test_accepted_command_increments_version_once(tmp_path: Path) -> None:
    server = SidecarServer(token="secret", save_root=tmp_path, port=0)
    server.start_background()
    try:
        sock = socket.create_connection((server.host, server.port), timeout=2)
        codec = FrameCodec()
        hs = _roundtrip(
            sock,
            codec,
            {
                "kind": "Handshake",
                "protocol_version": 1,
                "session_id": "s",
                "token": "secret",
                "role": "local_client",
            },
        )
        assert hs["status"] == "ACCEPTED"
        v0 = int(hs["world_version"])
        reply = _roundtrip(
            sock,
            codec,
            {
                "kind": "Command",
                "protocol_version": 1,
                "session_id": "s",
                "world_id": hs["world_id"],
                "command_id": "c1",
                "expected_world_version": v0,
                "command_kind": "Travel",
                "payload": {"from_node": "node:1", "to_node": "node:2"},
            },
        )
        assert reply["status"] == "ACCEPTED"
        assert int(reply["world_version"]) == v0 + 1
    finally:
        server.shutdown()


def test_server_binds_loopback_only(tmp_path: Path) -> None:
    server = SidecarServer(token="secret", save_root=tmp_path, host="127.0.0.1", port=0)
    assert server.host in {"127.0.0.1", "::1"}
    server.start_background()
    try:
        assert server.port > 0
    finally:
        server.shutdown()


def test_non_loopback_bind_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="loopback"):
        SidecarServer(token="secret", save_root=tmp_path, host="0.0.0.0", port=0)


def test_lost_ack_retry_returns_prior_receipt(tmp_path: Path) -> None:
    server = SidecarServer(token="secret", save_root=tmp_path, port=0)
    server.start_background()
    try:
        sock = socket.create_connection((server.host, server.port), timeout=2)
        codec = FrameCodec()
        hs = _roundtrip(
            sock,
            codec,
            {
                "kind": "Handshake",
                "protocol_version": 1,
                "session_id": "s",
                "token": "secret",
                "role": "local_client",
            },
        )
        cmd = {
            "kind": "Command",
            "protocol_version": 1,
            "session_id": "s",
            "world_id": hs["world_id"],
            "command_id": "retry-1",
            "expected_world_version": hs["world_version"],
            "command_kind": "Wait",
            "payload": {"current_node": "node:1", "press_id": "p1"},
        }
        first = _roundtrip(sock, codec, cmd)
        second = _roundtrip(sock, codec, cmd)
        assert first["status"] == "ACCEPTED"
        assert second["status"] == "DUPLICATE"
        assert first["world_version"] == second["world_version"]
    finally:
        server.shutdown()

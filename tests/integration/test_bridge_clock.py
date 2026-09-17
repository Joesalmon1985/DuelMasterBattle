"""T024 / G01 end-to-end bridge clock smoke."""

from __future__ import annotations

import socket
from pathlib import Path

from sim.dmb.bridge.codec import FrameCodec
from sim.dmb.bridge.server import SidecarServer
from sim.dmb.testing.fixtures import run_fx_clock


def _rpc(sock: socket.socket, payload: dict) -> dict:
    codec = FrameCodec()
    sock.sendall(codec.encode(payload))
    buf = b""
    while True:
        buf += sock.recv(65536)
        frames = FrameCodec().feed(buf)
        if frames:
            return frames[0]


def test_fx_clock_python_path() -> None:
    assert run_fx_clock().status == "PASS"


def test_bridge_travel_wait_pause_save_recovery(tmp_path: Path) -> None:
    server = SidecarServer(token="g01", save_root=tmp_path, port=0)
    server.start_background()
    try:
        sock = socket.create_connection((server.host, server.port), timeout=2)
        hs = _rpc(
            sock,
            {
                "kind": "Handshake",
                "protocol_version": 1,
                "session_id": "g01",
                "token": "g01",
                "role": "local_client",
            },
        )
        assert hs["status"] == "ACCEPTED"
        world_id = hs["world_id"]
        version = hs["world_version"]

        def command(cid: str, kind: str, payload: dict, ver: int) -> dict:
            return _rpc(
                sock,
                {
                    "kind": "Command",
                    "protocol_version": 1,
                    "session_id": "g01",
                    "world_id": world_id,
                    "command_id": cid,
                    "expected_world_version": ver,
                    "command_kind": kind,
                    "payload": payload,
                },
            )

        travel = command("t1", "Travel", {"from_node": "node:1", "to_node": "node:2"}, version)
        assert travel["status"] == "ACCEPTED"
        version = travel["world_version"]
        wait = command("w1", "Wait", {"current_node": "node:2", "press_id": "p1"}, version)
        assert wait["status"] == "ACCEPTED"
        version = wait["world_version"]
        pause = command("p1", "Pause", {"reason": "menu"}, version)
        assert pause["status"] == "ACCEPTED"
        version = pause["world_version"]
        token = pause["payload"]["token"]
        resume = command("r1", "Resume", {"token": token}, version)
        assert resume["status"] == "ACCEPTED"
        version = resume["world_version"]
        save = command("s1", "Save", {"slot": "g01"}, version)
        assert save["status"] == "ACCEPTED"
        # Disconnect semantics
        sock.close()
        server.session.paused_for_bridge_failure = True
        assert server.session.sim.state.legacy_godot_world_tick_enabled is False
        assert server.session.sim.state.legacy_godot_world_save_enabled is False
    finally:
        server.shutdown()

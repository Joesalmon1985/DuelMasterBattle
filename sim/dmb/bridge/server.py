"""Loopback sidecar server owning the single world writer."""

from __future__ import annotations

import json
import socket
import socketserver
import threading
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sim.dmb.bridge.codec import FrameCodec
from sim.dmb.bridge.protocol import PROTOCOL_VERSION, ROLE_LOCAL_CLIENT
from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.core.world import WorldSim, bootstrap_world
from sim.dmb.persistence.coordinator import SaveCoordinator
from sim.dmb.persistence.repository import SaveRepository


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    # MappingProxyType and similar mappings
    if hasattr(value, "items"):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return deepcopy(value)


@dataclass
class SidecarSession:
    sim: WorldSim
    token: str
    session_id: str
    save_root: Path
    coordinator: SaveCoordinator = field(init=False)
    paused_for_bridge_failure: bool = False

    def __post_init__(self) -> None:
        self.coordinator = SaveCoordinator(self.sim, SaveRepository(self.save_root))


class SidecarServer:
    def __init__(self, token: str, save_root: Path, host: str = "127.0.0.1", port: int = 0) -> None:
        if host not in {"127.0.0.1", "::1"}:
            raise ValueError("bind only loopback")
        self.token = token
        self.save_root = Path(save_root)
        self.save_root.mkdir(parents=True, exist_ok=True)
        self.session = SidecarSession(
            sim=bootstrap_world(),
            token=token,
            session_id="pending",
            save_root=self.save_root,
        )
        self._server = ThreadedServer((host, port), self._make_handler())
        self.host, self.port = self._server.server_address[:2]

    def _make_handler(self):
        outer = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                codec = FrameCodec()
                authenticated = False
                while True:
                    chunk = self.request.recv(65536)
                    if not chunk:
                        outer.session.paused_for_bridge_failure = True
                        token = outer.session.sim.clock.acquire_pause("bridge_failure", "server")
                        outer.session.sim.state.clock.setdefault("bridge_failure_tokens", []).append(token)
                        return
                    try:
                        frames = codec.feed(chunk)
                    except ValueError:
                        outer.session.paused_for_bridge_failure = True
                        return
                    for frame in frames:
                        reply = outer._handle_frame(frame, authenticated)
                        if frame.get("kind") == "Handshake" and reply.get("status") == "ACCEPTED":
                            authenticated = True
                        self.request.sendall(codec.encode(reply))

        return Handler

    def _handle_frame(self, frame: dict[str, Any], authenticated: bool) -> dict[str, Any]:
        kind = frame.get("kind")
        if kind == "Handshake":
            if frame.get("token") != self.token:
                return {"status": "REJECTED", "code": "BAD_TOKEN"}
            if int(frame.get("protocol_version", -1)) != PROTOCOL_VERSION:
                return {"status": "REJECTED", "code": "BAD_PROTOCOL"}
            if frame.get("role") != ROLE_LOCAL_CLIENT:
                return {"status": "REJECTED", "code": "BAD_ROLE"}
            self.session.session_id = str(frame.get("session_id", "session"))
            return {
                "status": "ACCEPTED",
                "protocol_version": PROTOCOL_VERSION,
                "world_version": self.session.sim.state.world_version,
                "world_id": self.session.sim.state.world_id,
                "capabilities": ["Travel", "Wait", "AdvanceGame", "Save", "Load", "Pause", "Resume"],
            }
        if not authenticated:
            return {"status": "REJECTED", "code": "UNAUTHENTICATED"}
        if kind == "RequestView":
            return {
                "status": "ACCEPTED",
                "view": _jsonable(self.session.sim.state.read_view(str(frame.get("scope", "player")))),
            }
        if kind == "Command":
            envelope = CommandEnvelope(
                protocol_version=int(frame.get("protocol_version", 1)),
                session_id=str(frame.get("session_id", self.session.session_id)),
                world_id=str(frame.get("world_id", self.session.sim.state.world_id)),
                command_id=str(frame["command_id"]),
                expected_world_version=int(frame["expected_world_version"]),
                kind=str(frame["command_kind"]),
                payload=dict(frame.get("payload", {})),
            )
            # Presentation pose sync may lag a clock tick; accept current version.
            if envelope.kind == "SyncPose":
                envelope = CommandEnvelope(
                    protocol_version=envelope.protocol_version,
                    session_id=envelope.session_id,
                    world_id=envelope.world_id,
                    command_id=envelope.command_id,
                    expected_world_version=self.session.sim.state.world_version,
                    kind=envelope.kind,
                    payload=envelope.payload,
                )
            if envelope.kind == "Save":
                saved = self.session.coordinator.request_save(str(envelope.payload.get("slot", "slot0")))
                result = self.session.sim.dispatch(envelope)
                body = result.to_dict()
                body["save"] = saved
                return body
            if envelope.kind == "Load":
                self.session.coordinator.prepare_load(str(envelope.payload.get("slot", "slot0")))
                self.session.sim = self.session.coordinator.commit_load()
                self.session.coordinator = SaveCoordinator(self.session.sim, SaveRepository(self.save_root))
                return {
                    "status": "ACCEPTED",
                    "code": "OK",
                    "command_id": envelope.command_id,
                    "world_version": self.session.sim.state.world_version,
                    "events": [],
                    "payload": {"loaded": True},
                }
            return self.session.sim.dispatch(envelope).to_dict()
        return {"status": "REJECTED", "code": "UNKNOWN_KIND"}

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def start_background(self) -> threading.Thread:
        thread = threading.Thread(target=self.serve_forever, name="dmb-sidecar", daemon=True)
        thread.start()
        return thread

    def shutdown(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def endpoint_file(self, path: Path) -> None:
        path.write_text(
            json.dumps({"host": self.host, "port": self.port, "token": self.token}, indent=2) + "\n",
            encoding="utf-8",
        )


class ThreadedServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

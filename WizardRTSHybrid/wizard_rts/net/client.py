"""A Python client of the production protocol: what the Godot client sends, for the automated two-client harness and for
scripts. Blocking request/reply over one TCP connection; `discover()` finds hosts by UDP probe."""

from __future__ import annotations

import json
import socket
import time
from typing import Any

from wizard_rts.net import protocol


class NetClient:
    def __init__(self, host: str, port: int, timeout: float = 5.0, name: str = "Wizard", game: str = protocol.GAME_VERSION, proto: int = protocol.PROTOCOL_VERSION) -> None:
        self.host, self.port = host, int(port)
        self.timeout = timeout
        self.name = name
        self.game = game
        self.proto = proto
        self.sock: socket.socket | None = None
        self.buffer = b""
        self.player_id = ""
        self.token = ""
        self.move_seq = 0
        self.cast_seq = 0
        self.pose: dict[str, Any] = {}
        self.bytes_in = 0
        self.bytes_out = 0

    # ---------------------------------------------------------------- transport
    def connect(self) -> "NetClient":
        s = socket.create_connection((self.host, self.port), timeout=self.timeout)
        try:
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        self.sock = s
        self.buffer = b""
        return self

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def op(self, message: dict[str, Any]) -> dict[str, Any]:
        assert self.sock is not None, "not connected"
        data = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        self.sock.sendall(data)
        self.bytes_out += len(data)
        while b"\n" not in self.buffer:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise ConnectionError("host closed the connection")
            self.bytes_in += len(chunk)
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))

    # ---------------------------------------------------------------- protocol helpers
    def hello(self, code: str = "", token: str | None = None, secret: str | None = None) -> dict[str, Any]:
        msg: dict[str, Any] = {"op": "hello", "protocol": self.proto, "game": self.game, "name": self.name, "code": code}
        if token or self.token:
            msg["token"] = token or self.token
        if secret:
            msg["secret"] = secret
        reply = self.op(msg)
        if reply.get("status") == "ok":
            self.player_id = str(reply["player_id"])
            self.token = str(reply["token"])
            self.pose = dict(reply.get("pose", {}))
            self.move_seq = int(self.pose.get("seq", 0))
        return reply

    def start(self) -> dict[str, Any]:
        return self.op({"op": "start"})

    def state(self, full: bool = False, radius: int | None = None) -> dict[str, Any]:
        msg: dict[str, Any] = {"op": "state", "seq": self.move_seq}
        if full:
            msg["full"] = True
        if radius is not None:
            msg["radius"] = radius
        reply = self.op(msg)
        if reply.get("status") == "ok":
            self.pose = dict(reply.get("pose", self.pose))
        return reply

    def move(self, tx: int, ty: int, facing: str = "down", seq: int | None = None) -> dict[str, Any]:
        if seq is None:
            self.move_seq += 1
            seq = self.move_seq
        reply = self.op({"op": "move", "seq": seq, "tx": tx, "ty": ty, "facing": facing})
        if reply.get("status") == "ok":
            self.pose = {k: reply[k] for k in ("tx", "ty", "facing", "hex", "seq") if k in reply}
        return reply

    def step(self, dx: int, dy: int) -> dict[str, Any]:
        facing = "right" if dx > 0 else "left" if dx < 0 else "down" if dy > 0 else "up"
        return self.move(int(self.pose["tx"]) + dx, int(self.pose["ty"]) + dy, facing)

    def challenge(self, target: str, fmt: Any = "three") -> dict[str, Any]:
        return self.op({"op": "pvp_challenge", "target": target, "format": fmt})

    def respond(self, duel_id: str, accept: bool) -> dict[str, Any]:
        return self.op({"op": "pvp_respond", "duel_id": duel_id, "accept": accept})

    def ward(self, ward: list[int]) -> dict[str, Any]:
        self.cast_seq = 0  # a new duel: cast sequence numbers start again (the duel view carries the host's count as `cast_seq`)
        return self.op({"op": "pvp_ward", "ward": ward})

    def cast(self, attack: list[int], cast_seq: int | None = None) -> dict[str, Any]:
        auto = cast_seq is None
        if auto:
            cast_seq = self.cast_seq + 1
        reply = self.op({"op": "pvp_cast", "attack": attack, "cast_seq": cast_seq})
        if auto and reply.get("status") == "ok":
            self.cast_seq = int(reply.get("duel", {}).get("cast_seq", cast_seq))  # the host's count is the truth
        return reply

    def duel(self) -> dict[str, Any]:
        return self.op({"op": "pvp_view"})


def discover(timeout: float = 1.0, port: int = protocol.DISCOVERY_PORT, targets: list[str] | None = None) -> list[dict[str, Any]]:
    """Broadcast a probe and collect the hosts that answer (each dict carries its `host` address and `port`)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.settimeout(0.2)
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    probe = f"{protocol.DISCOVERY_MAGIC}?{protocol.PROTOCOL_VERSION}".encode("utf-8")
    deadline = time.monotonic() + timeout
    try:
        for target in targets or ["255.255.255.255", "127.0.0.1"]:
            try:
                s.sendto(probe, (target, port))
            except OSError:
                pass
        while time.monotonic() < deadline:
            try:
                data, addr = s.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                info = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(info, dict) or info.get("dmb") != 1:
                continue
            key = (addr[0], int(info.get("port", 0)))
            if key in seen:
                continue
            seen.add(key)
            info["host"] = addr[0]
            found.append(info)
    finally:
        s.close()
    return found

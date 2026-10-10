"""Local simulation server. One world, newline-delimited JSON on 127.0.0.1.

This is process separation for the Godot presentation, not a network game.
The hybrid does not read WizardRTSHybrid/external.
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
_ROOT = _HERE.parent
for entry in (str(_HERE), str(_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from wizard_rts.world import HybridWorld  # noqa: E402


def _handle(world: HybridWorld, message: dict) -> dict:
    op = str(message.get("op", ""))
    if op == "snapshot":
        return {"status": "ok", "snapshot": world.snapshot()}
    if op == "pose":
        return world.set_pose(int(message.get("tx", 0)), int(message.get("ty", 0)), str(message.get("facing", "down")))
    if op == "advance":
        return world.advance(int(message.get("ms", 0)), int(message.get("sequence", 0)))
    if op == "interact":
        return world.interact()
    if op == "resolve":
        return world.resolve(
            str(message.get("duel_id", "")),
            bool(message.get("success", False)),
            str(message.get("command_id") or "") or None,
        )
    return {"status": "rejected", "reason": "unknown_op"}


def serve(port: int) -> None:
    world = HybridWorld(seed=int(os.environ.get("HYBRID_SEED", "507")))
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(1)
    print(f"HYBRID_SIM_READY {port}", flush=True)
    while True:
        conn, _addr = server.accept()
        with conn:
            buffer = b""
            try:
                while True:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if not line.strip():
                            continue
                        try:
                            message = json.loads(line.decode("utf-8"))
                        except json.JSONDecodeError:
                            reply = {"status": "rejected", "reason": "bad_json"}
                        else:
                            reply = _handle(world, message)
                        conn.sendall(json.dumps(reply).encode("utf-8") + b"\n")
            except (ConnectionError, OSError):
                continue


def main() -> None:
    port = int(os.environ.get("HYBRID_SIM_PORT", "8765"))
    serve(port)


if __name__ == "__main__":
    main()

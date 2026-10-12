"""The packaged hybrid must run while external/ is hidden.

The driver refuses any open() under WizardRTSHybrid/external and any TCP
connect that is not the local sim port.
"""

from __future__ import annotations

import builtins
import socket
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
_ROOT = _HERE.parent
for entry in (str(_HERE), str(_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

_EXTERNAL = (_HERE / "external").resolve()
_REAL_OPEN = builtins.open
_REAL_CONNECT = socket.socket.connect


def _guard_open(path, *args, **kwargs):
    text = str(path).replace("\\", "/")
    if "WizardRTSHybrid/external" in text or str(_EXTERNAL) in str(path):
        raise RuntimeError(f"clean environment opened external path: {path}")
    return _REAL_OPEN(path, *args, **kwargs)


def _guard_connect(self, address):
    host = address[0] if isinstance(address, tuple) and address else ""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError(f"clean environment connected to {address}")
    return _REAL_CONNECT(self, address)


def test_packaged_world_without_external(tmp_path: Path) -> None:
    builtins.open = _guard_open
    socket.socket.connect = _guard_connect
    try:
        from wizard_rts.world import HybridWorld

        world = HybridWorld()
        pose = world.set_pose(world.player["tx"] + 1, world.player["ty"], "right")
        assert pose["status"] == "ok"
        assert int(world.dmb.clock["game_ms"]) == 0
        advanced = world.advance(60_000, 1)
        assert advanced["quanta"] > 0
        assert world.stats["produce"] > 0
        unit = next(iter(world.units.values()))
        world.move([unit["id"]], unit["tx"] + 3, unit["ty"])
        world.advance(10_000, 2)
        assert world.stats["move"] > 0
        # Walk the avatar onto the hazard tile's neighbour and resolve once.
        hx, hy = world.hazard_tile
        for step in ((hx - 1, hy), (hx, hy - 1), (hx + 1, hy), (hx, hy + 1)):
            if world.tile_in_map(*step) and step not in world.blocked:
                moved = world.set_pose(step[0], step[1], "up")
                if moved["status"] == "ok":
                    break
        started = world.interact()
        assert started["status"] == "started"
        duel_id = started["payload"]["duel"]["id"]
        paused_ms = int(world.dmb.clock["game_ms"])
        assert world.advance(10_000, 2)["quanta"] == 0
        resolved = world.resolve(duel_id, True, "clean:1")
        assert resolved["status"] == "success"
        assert int(world.dmb.clock["game_ms"]) == paused_ms
        again = world.resolve(duel_id, True, "clean:1")
        assert again["status"] == "idempotent"
        loaded = [Path(m.__file__).resolve() for m in sys.modules.values() if getattr(m, "__file__", None)]
        assert all(_EXTERNAL not in path.parents for path in loaded)
        marker = tmp_path / "clean_ok.txt"
        marker.write_text("ok", encoding="utf-8")
        assert marker.read_text(encoding="utf-8") == "ok"
    finally:
        builtins.open = _REAL_OPEN
        socket.socket.connect = _REAL_CONNECT

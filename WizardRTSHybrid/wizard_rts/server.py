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

from wizard_rts import construction as con  # noqa: E402
from wizard_rts.coords import tile_to_hex  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def _handle(world: HybridWorld, message: dict) -> dict:
    op = str(message.get("op", ""))
    if op == "snapshot":
        return {"status": "ok", "snapshot": world.snapshot(tree_sync=(False if message.get("tree_delta") else None))}
    if op == "pose":
        if message.get("light"):
            # the wizard crossed a tile: tell the clock where he stands without shipping the whole world back
            reply = world.set_pose(int(message.get("tx", 0)), int(message.get("ty", 0)), str(message.get("facing", "down")), snapshot=False)
            reply["hex"] = list(tile_to_hex(world.player["tx"], world.player["ty"]))
            return reply
        return world.set_pose(int(message.get("tx", 0)), int(message.get("ty", 0)), str(message.get("facing", "down")))
    if op == "advance":
        return world.advance(int(message.get("ms", 0)), int(message.get("sequence", 0)), tree_sync=(True if message.get("tree_delta") else None))
    if op == "control":
        return world.control(str(message.get("faction", "")))
    if op == "build":
        return world.build(str(message.get("faction", "")), str(message.get("kind", "")), int(message.get("tx", 0)), int(message.get("ty", 0)))
    if op == "road":
        return world.road(str(message.get("faction", "")), str(message.get("a", "")), str(message.get("b", "")))
    if op == "queue":
        return world.queue(str(message.get("building", "")), str(message.get("unit", "")))
    if op == "cancel":
        return world.cancel(str(message.get("building", "")), int(message.get("index", 0)))
    if op == "move":
        return world.move(list(message.get("units", [])), int(message.get("tx", 0)), int(message.get("ty", 0)), bool(message.get("attack_move", False)))
    if op == "fire":
        reply = world.fire(str(message.get("target", "")))
        if message.get("light"):
            reply.pop("snapshot", None)
        return reply
    if op == "deploy":
        return world.deploy(str(message.get("unit", "")))
    if op == "stop":
        return world.stop(list(message.get("units", [])))
    if op == "rally":
        return world.rally(str(message.get("building", "")), int(message.get("tx", 0)), int(message.get("ty", 0)))
    if op == "demolish":
        return world.demolish(str(message.get("building", "")))
    if op == "menu":
        return {"status": "ok", "build_menu": con.full_menu(), "recipes": con.RECIPES, "locked": con.RECIPES_LOCKED}
    if op == "ai":
        world.ai_enabled = bool(message.get("enabled", True))
        return {"status": "ok", "ai_enabled": world.ai_enabled}
    if op == "speed":
        return world.set_speed(int(message.get("scale", 1)))
    if op == "order":
        return world.order(str(message.get("unit", "")), str(message.get("target", "")))
    if op == "terrain":
        if world.terrain is None:
            return {"status": "ok", "terrain": None}
        return {"status": "ok", "terrain": world.terrain.wire()}
    if op == "tile":
        return world.tile_info(int(message.get("tx", 0)), int(message.get("ty", 0)))
    if op == "resources":
        return {"status": "ok", "nodes": world.resource_region(int(message.get("x0", 0)), int(message.get("y0", 0)), int(message.get("x1", 0)), int(message.get("y1", 0)))}
    if op == "suggest":
        # a site the simulation would accept (God Mode "suggest" and the headed tests)
        from wizard_rts import ai

        kind = str(message.get("kind", ""))
        wh = con.faction_warehouse(world, str(message.get("faction", "")))
        if kind in ("naval_yard", "sub_pen") and wh is not None and world.terrain is not None:
            site = ai._naval_site(world, str(message.get("faction", "")), wh)
            return {"status": "ok" if site else "rejected", "tile": list(site) if site else None, "reason": "" if site else "no_coast"}
        if kind == "mcv_site":
            unit = world.units.get(str(message.get("unit", "")))
            site = ai._find_expansion_site(world, str(message.get("faction", "")), unit) if unit is not None else None
            return {"status": "ok" if site else "rejected", "tile": list(site) if site else None, "reason": "" if site else "no_site"}
        return {"status": "rejected", "reason": "unsupported_kind"}
    if op == "spawn":
        if os.environ.get("HYBRID_ALLOW_SPAWN") != "1":
            return {"status": "rejected", "reason": "spawn_disabled"}
        faction = str(message.get("faction", ""))
        if faction not in world.faction_info:
            return {"status": "rejected", "reason": "unknown_faction"}
        definition = str(message.get("definition", ""))
        tile = (int(message.get("tx", 0)), int(message.get("ty", 0)))
        from wizard_rts import rules

        r = rules.actor(definition)
        if r is None or not r.get("mobile") or world.tile_speed(r.get("locomotor"), *tile) <= 0:
            return {"status": "rejected", "reason": "cannot_stand_there"}
        uid = world._unit(world.faction_info[faction]["id"], faction, definition.split(".")[-1], r["name"], definition, tile)
        return {"status": "ok", "id": uid}
    if op == "damage":
        # test hook (same gate as spawn): a hit through the one shared building-damage path
        if os.environ.get("HYBRID_ALLOW_SPAWN") != "1":
            return {"status": "rejected", "reason": "spawn_disabled"}
        building = str(message.get("building", ""))
        if building not in world.buildings:
            return {"status": "rejected", "reason": "no_target"}
        dealt = world.damage_building(building, int(message.get("amount", 1)), ["structure"], {}, by="test")
        return {"status": "ok", "dealt": dealt, "snapshot": world.snapshot()}
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
    world = HybridWorld(seed=int(os.environ.get("HYBRID_SEED", "507")), map_size=os.environ.get("HYBRID_MAP", "standard"))
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
                        conn.sendall(json.dumps(reply, separators=(",", ":")).encode("utf-8") + b"\n")
            except (ConnectionError, OSError):
                continue


def main() -> None:
    port = int(os.environ.get("HYBRID_SIM_PORT", "8765"))
    serve(port)


if __name__ == "__main__":
    main()

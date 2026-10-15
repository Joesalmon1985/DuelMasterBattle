"""The narrative log. Nothing here appends to `world.events` (the simulation's event stream is not ours to extend); narrative events live in
`world.narrative["log"]` and are published to the client through `story.snapshot()["narrative"]["events"]`."""

from __future__ import annotations

from typing import Any

from wizard_rts.narrative import config


def log(world: Any, kind: str, **fields: Any) -> dict[str, Any]:
    n = world.narrative
    entry = {"game_ms": int(world.dmb.clock.get("game_ms", 0)), "kind": kind, **fields}
    n["log"].append(entry)
    cap = config.log_cap()
    if len(n["log"]) > cap:
        del n["log"][: cap // 2]
    return entry


def recent(world: Any, count: int = 20) -> list[dict[str, Any]]:
    return list(world.narrative["log"][-count:])

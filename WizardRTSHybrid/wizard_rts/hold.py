"""Hold a person in place while the wizard talks to them (Wizard Mode conversations).

A worker, carrier or soldier carries `held_until_ms` (game time) while it is being talked to; the three movement loops skip a held body entirely, so
its position, its programme or order, its timers and the ware in its hands stay exactly as they were, and everyone else keeps simulating. The key
is absent in every world no wizard has talked in, so nothing changes there (hash baselines are untouched). `held_until_ms` is also a failsafe:
a conversation that nobody closes releases the body by itself, so no one is ever stranded. Callers: `workers.worker_quantum`,
`logistics.logistics_quantum`, `military._unit_step`; the owner of the lifecycle is `narrative/conversation.py`.
"""

from __future__ import annotations

from typing import Any

FAILSAFE_MS = 30_000
STILL = ("anim", "status")  # presentation fields set to "idle" while held (so the figure stands instead of walking on the spot) and restored after


def is_held(world: Any, row: dict) -> bool:
    until = row.get("held_until_ms")
    if until is None:
        return False
    if int(world.dmb.clock.get("game_ms", 0)) >= int(until):
        release(row)
        return False
    return True


def hold(world: Any, row: dict, ms: int = FAILSAFE_MS) -> None:
    if "held_until_ms" not in row:
        row["held_prev"] = {k: row[k] for k in STILL if k in row}
        for k in row["held_prev"]:
            row[k] = "idle"
    row["held_until_ms"] = int(world.dmb.clock.get("game_ms", 0)) + int(ms)


def release(row: dict) -> None:
    if row.pop("held_until_ms", None) is not None:
        for k, v in row.pop("held_prev", {}).items():
            row[k] = v

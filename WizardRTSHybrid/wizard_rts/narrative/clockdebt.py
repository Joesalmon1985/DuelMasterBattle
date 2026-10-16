"""Offline progression: how much simulated time a world is owed for the real time its installation was closed (plan amendment 10).

The relationship is bounded on both ends so a phone can pay it with the real simulation: `minutes_per_real_hour` of simulated time per real hour away,
never more than `cap_minutes` per reopening, nothing for an absence shorter than a minute or longer than `max_absence_days` (a clock that jumped), and
the host stops early when `budget_s` of its own CPU time is spent (`net/host.py` pays the debt in slices while the lobby is open). The debt is a number of
milliseconds computed outside the world from the save's `closed_at`; the world itself never reads the wall clock, so determinism holds.
"""

from __future__ import annotations

from typing import Any

from wizard_rts.narrative import config


def settings() -> dict[str, Any]:
    return {"minutes_per_real_hour": float(config.get("catch_up", "minutes_per_real_hour", 10)), "cap_minutes": float(config.get("catch_up", "cap_minutes", 20)),
            "budget_s": float(config.get("catch_up", "budget_s", 120)), "max_absence_days": float(config.get("catch_up", "max_absence_days", 30)),
            "min_absence_s": float(config.get("catch_up", "min_absence_s", 60))}


def owed_ms(closed_at: float | None, now: float) -> int:
    """Simulated milliseconds owed for the absence between `closed_at` (the save's wall-clock time) and `now`."""
    if not closed_at:
        return 0
    s = settings()
    elapsed = float(now) - float(closed_at)
    if elapsed < s["min_absence_s"] or elapsed > s["max_absence_days"] * 86400.0:
        return 0  # too short to matter, or a clock that jumped (forwards or back): nothing is owed, nothing is fabricated
    minutes = min(elapsed / 3600.0 * s["minutes_per_real_hour"], s["cap_minutes"])
    return int(minutes * 60_000)


def describe(owed: int, paid: int, forfeited: int) -> dict[str, Any]:
    return {"owed_ms": int(owed), "paid_ms": int(paid), "forfeited_ms": int(forfeited), "left_ms": max(0, int(owed) - int(paid) - int(forfeited))}

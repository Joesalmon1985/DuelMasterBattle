"""Minimal player state helpers for visits (C08 / T072)."""

from __future__ import annotations

from typing import Any


def ensure_player_visit_state(state: Any) -> dict[str, Any]:
    player = state.player
    visits = player.setdefault("visits", {"current": None, "ledgers": {}})
    visits.setdefault("current", None)
    visits.setdefault("ledgers", {})
    return visits

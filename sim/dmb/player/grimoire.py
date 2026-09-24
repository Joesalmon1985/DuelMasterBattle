"""Discovered spells for the Grimoire UI (C13 / T107).

Casting still requires a local target session — this export never grants remote casts.
"""

from __future__ import annotations

from typing import Any

from sim.dmb.core.state import WorldState

# Baseline discovered set for MVP; board.grimoire may extend.
_DEFAULT_SPELLS = [
    {
        "id": "ward",
        "label": "Ward",
        "semantic_id": "card.spell.ward",
        "remote_cast": False,
    },
    {
        "id": "attack",
        "label": "Attack",
        "semantic_id": "card.spell.attack",
        "remote_cast": False,
    },
]


def export_grimoire(state: WorldState) -> dict[str, Any]:
    authored = list((state.board.get("grimoire") or {}).get("spells") or [])
    spells = authored if authored else list(_DEFAULT_SPELLS)
    prepared = str((state.player or {}).get("prepared_spell") or "")
    return {
        "spells": spells,
        "prepared_spell": prepared,
        "remote_cast_allowed": False,
    }

"""The wizard's own progress: spells known, weave size, lessons done, duel record (`world.narrative["wizard"]`, plan section 2.5).

Spell ids are the retained palette's: 0 Flame, 1 Frost, 6 Vine (`tutorial.palette`, configurable). Everything here is narrative state that
crosses a cycle reset with the wizard and is saved with the world.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from wizard_rts.narrative import config

WORLDVIEWS = Path(__file__).resolve().parents[1] / "data" / "narrative" / "worldviews.json"

SPELL_NAMES = {0: "Flame", 1: "Frost", 3: "Stone", 4: "Light", 6: "Vine", 9: "Arcane", 2: "Water", 5: "Wind"}
FLAME = 0


def wiz(world: Any) -> dict[str, Any]:
    return world.narrative["wizard"]


def palette() -> list[int]:
    return [int(s) for s in config.get("tutorial", "palette", [0, 1, 6])]


def spells(world: Any) -> list[int]:
    return list(wiz(world)["spells"])


def knows(world: Any, spell: int) -> bool:
    return int(spell) in wiz(world)["spells"]


def learn(world: Any, spell_ids: list[int], weave_size: int | None = None) -> None:
    w = wiz(world)
    for s in spell_ids:
        if int(s) not in w["spells"]:
            w["spells"].append(int(s))
    w["spells"].sort()
    if weave_size is not None:
        w["weave_size"] = max(int(w["weave_size"]), int(weave_size))


def lesson_done(world: Any, lesson: str) -> bool:
    return lesson in wiz(world)["lessons"]


def complete_lesson(world: Any, lesson: str) -> bool:
    """Record a lesson once (game time); True the first time."""
    w = wiz(world)
    if lesson in w["lessons"]:
        return False
    w["lessons"][lesson] = int(world.dmb.clock.get("game_ms", 0))
    return True


# ------------------------------------------------------------------ what the apprentice believes (worldviews) and knows (facts)

def worldview_table() -> dict[str, dict[str, Any]]:
    """{code: {key, name, delta}} for the seven worldviews (`data/narrative/worldviews.json`, a copy of the Dialogue Factory's `worldviews.json`)."""
    return {w["code"]: w for w in _worldview_file()["worldviews"]}


@lru_cache(maxsize=1)
def _worldview_file() -> dict[str, Any]:
    return json.loads(WORLDVIEWS.read_text())


def worldview_scores(world: Any) -> dict[str, int]:
    stored = wiz(world)["worldview"]
    return {code: int(stored.get(code, 0)) for code in worldview_table()}


def apply_worldview_delta(world: Any, receipt_id: str, delta: dict[str, int]) -> bool:
    """Add a worldview delta to the apprentice's leanings, once per `receipt_id` (the pattern of `AspectService.apply_change_once`). True when applied."""
    w = wiz(world)
    receipts = w.setdefault("worldview_receipts", {})
    if receipt_id in receipts:
        return False
    for code, d in sorted(delta.items()):
        w["worldview"][code] = int(w["worldview"].get(code, 0)) + int(d)
    receipts[receipt_id] = {"game_ms": int(world.dmb.clock.get("game_ms", 0)), "delta": dict(delta)}
    return True


def apply_worldview_choice(world: Any, receipt_id: str, code: str) -> bool:
    """The established delta of choosing the `code` reply (the Dialogue Factory's per-reply deltas), once."""
    return apply_worldview_delta(world, receipt_id, worldview_table()[code]["delta"])


def worldview_primary(world: Any) -> str:
    """The code the apprentice leans towards most (ties by the table's order); empty until a choice has been made."""
    scores = worldview_scores(world)
    best = max(scores.values(), default=0)
    return next((c for c in worldview_table() if scores[c] == best and best > 0), "")


def knows_fact(world: Any, fact: str) -> bool:
    return fact in wiz(world).setdefault("facts", [])


def learn_fact(world: Any, fact: str) -> bool:
    facts = wiz(world).setdefault("facts", [])
    if fact in facts:
        return False
    facts.append(fact)
    return True


def combatant(world: Any, max_casts: int = 8) -> dict[str, Any]:
    """The player's duel combatant: ward and weave of the size the wizard has learned, drawn from the spells he knows."""
    w = wiz(world)
    size = max(1, int(w["weave_size"]) or 3)
    pool = sorted(w["spells"]) or palette()
    return {"id": "player", "display_name": "You", "archetype": "player", "kind": "player", "weave_size": size, "ward_size": size,
            "attack_pool": list(pool), "ward_pool": list(pool), "allow_repeats": True, "max_casts": int(max_casts),
            "min_cast_seconds": 5.0, "max_cast_seconds": 60.0}

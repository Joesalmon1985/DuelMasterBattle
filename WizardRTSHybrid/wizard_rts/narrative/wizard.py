"""The wizard's own progress: spells known, weave size, lessons done, duel record (`world.narrative["wizard"]`, plan section 2.5).

Spell ids are the retained palette's: 0 Flame, 1 Frost, 6 Vine (`tutorial.palette`, configurable). Everything here is narrative state that
crosses a cycle reset with the wizard and is saved with the world.
"""

from __future__ import annotations

from typing import Any

from wizard_rts.narrative import config

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


def combatant(world: Any, max_casts: int = 8) -> dict[str, Any]:
    """The player's duel combatant: ward and weave of the size the wizard has learned, drawn from the spells he knows."""
    w = wiz(world)
    size = max(1, int(w["weave_size"]) or 3)
    pool = sorted(w["spells"]) or palette()
    return {"id": "player", "display_name": "You", "archetype": "player", "kind": "player", "weave_size": size, "ward_size": size,
            "attack_pool": list(pool), "ward_pool": list(pool), "allow_repeats": True, "max_casts": int(max_casts),
            "min_cast_seconds": 5.0, "max_cast_seconds": 60.0}

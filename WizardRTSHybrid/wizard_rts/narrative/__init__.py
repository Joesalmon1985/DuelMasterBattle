"""Wizard Mode's narrative layer: state that exists only when `server.py` (or a wizard environment) asks for it.

`world.narrative` is created by `enable(world)`, never by `HybridWorld.__init__` or `HybridEnv`, so a training or headless world runs exactly the
code it ran before this package existed. The simulation reaches the layer through one wizard-owned hook, `story.story_quantum`, which calls
`tick(world)` only when the attribute is present (`world.py` is not changed). Narrative code uses sorted iteration, seeded `random.Random`
(never `world.rng`) and game time (never the wall clock); see `docs/EXECUTION_PLAN_WIZARD_SETTLEMENT_STORIES.md` section 0.
"""

from __future__ import annotations

import copy
from typing import Any

from wizard_rts.narrative import config, perf


def _wizard_default() -> dict[str, Any]:
    return {"spells": [], "weave_size": 0, "lessons": {}, "duels": {"won": 0, "lost": 0, "attempts": []},
            "worldview": {}, "journal_notes": [], "visited": [], "version": 1}


def _fresh() -> dict[str, Any]:
    return {"version": config.version(), "wizard": _wizard_default(), "links": {}, "residents": {}, "conversations": {},
            "quests": {}, "settlements": {}, "watch": {"events_seen": 0}, "log": []}


def enabled(world: Any) -> bool:
    return "narrative" in world.__dict__


def state(world: Any) -> dict[str, Any]:
    """The narrative dict of a world that has been enabled (KeyError-free: it enables on first use only through `enable`)."""
    return world.narrative


def enable(world: Any) -> dict[str, Any]:
    """Create `world.narrative` if absent. Idempotent; the only place the attribute is born."""
    if "narrative" not in world.__dict__:
        world.narrative = _fresh()
    return world.narrative


def carry_over(old: Any, new: Any) -> dict[str, Any]:
    """After `history.cycle_reset`: the new world gets a fresh narrative state, and the wizard (spells, lessons, duels, worldview) crosses over (D11)."""
    n = enable(new)
    if enabled(old):
        n["wizard"] = copy.deepcopy(old.narrative["wizard"])
    return n


def tick(world: Any) -> None:
    """Once per game second, from `story.story_quantum`, only when the state exists: the link watcher, then characters for the bodies the
    wizard has come near. Later milestones hang residents, the tutorial and the director here."""
    from wizard_rts.narrative import characters, tutorial

    with perf.timed("tick"):
        characters.watch(world)
        characters.link_nearby(world)
        tutorial.tick(world)

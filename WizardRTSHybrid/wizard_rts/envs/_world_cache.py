"""Prepared real worlds for the environments: built once per (seed, scenario) through the developer fixtures, pickled in memory, cloned
in about 40 ms. Nothing here is a mock: each clone is a full HybridWorld in the state a long campaign would have reached."""

from __future__ import annotations

import math
import pickle
from typing import Any

_CACHE: dict[tuple, bytes] = {}


def prepared(seed: int, scenario: str = "story") -> tuple[Any, dict[str, Any]]:
    from wizard_rts.world import HybridWorld

    key = (seed, scenario)
    if key not in _CACHE:
        w = HybridWorld(seed, profile="developer")
        w.ai_enabled = False
        ids: dict[str, Any] = {}
        if scenario in ("story", "story_outbreak"):
            from wizard_rts import story_fixture

            ids = story_fixture.prepare(w)
        if scenario in ("outbreak", "story_outbreak"):
            from wizard_rts import regions

            w.outbreaks_enabled = False
            ids["outbreak"] = regions.fixture_outbreak(w, cubes=1)
        w.outbreaks_enabled = scenario in ("outbreak", "story_outbreak")
        _CACHE[key] = pickle.dumps((w, ids))
    w, ids = pickle.loads(_CACHE[key])
    return w, ids


def attention_advance(world: Any, seconds: float, economy: bool = False) -> None:
    """Move game time forward by `seconds`. `economy=False` runs only the systems the wizard's choices interact with (story,
    disruptions, outbreaks, VP/eras): the workers, carriers and AI are skipped so that an episode takes milliseconds. `economy=True` is the full world."""
    n = int(math.ceil(seconds))
    for _ in range(n):
        seq = int(world.dmb.clock.get("clock_sequence", 0)) + 1
        if economy:
            world.advance(1000, seq, snapshot=False)
            continue
        if world.dmb.clock.get("pause_tokens"):
            world.dmb.clock["clock_sequence"] = seq
            continue
        from wizard_rts import disruption, history, regions, story, vp

        world.dmb.clock["game_ms"] = int(world.dmb.clock.get("game_ms", 0)) + 1000
        world.dmb.clock["clock_sequence"] = seq
        world.economy_quanta += 10
        disruption.disruption_quantum(world)  # closures and their repairs are part of the story's world (the miner's collapsed gallery)
        story.story_quantum(world)
        vp.vp_quantum(world)
        history.history_quantum(world)
        regions.regions_quantum(world)

"""What the apprentice has done to the world with fire, counted so that people can react (plan `docs/PLAN_PLAYER_STRESS_AND_PROGRESSION.md`,
section 3: Stanley Parable's rule that the world has seen what you did and says so).

Every successful `fire` op is counted here by the class of thing burned (`burned_trees`, `burned_rocks`, `burned_buildings`, `burned_people` for workers
and carriers, `burned_soldiers`, `burned_animals`; the rats are `pests_burned`, counted by pests.py), per seat and world-wide, in the behaviour ledger,
which every conversation reads as facts (`my_burned_people`, ...). A home-settlement building burned is also `burned_home_buildings`, and the
warehouse with the rats in it keeps its own account (`pests.note_fire`). The inner voice (`voice.py`) and the villagers' banks read these.
"""

from __future__ import annotations

from typing import Any

from wizard_rts.narrative import events, ledger

KEYS = {"tree": "burned_trees", "rock": "burned_rocks", "building": "burned_buildings", "worker": "burned_people", "carrier": "burned_people",
        "unit": "burned_soldiers", "animal": "burned_animals"}


def note_fire(world: Any, seat: str, cls: str, target: str) -> None:
    key = KEYS.get(cls)
    if key:
        ledger.bump(world, key, seat=seat)
        ledger.bump(world, "burned_things", seat=seat)
    if cls == "building":
        from wizard_rts.narrative import pests, tutorial

        pests.note_fire(world, seat, target)
        sid = tutorial.state(world).get("settlement", "")
        rec = world.dmb.settlements.get(sid) if sid else None
        b = world.buildings.get(target)
        if rec is not None and b is not None and b.get("faction_name") == rec.get("faction"):
            ledger.bump(world, "burned_home_buildings", seat=seat)
    events.log(world, "deed_fire", seat=seat, cls=cls, target=target)

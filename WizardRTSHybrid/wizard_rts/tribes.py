"""Which Widelands tribe each faction plays, and what that means for its economy.

Six colours, five Widelands tribes: Orange shares Barbarians with Red. A
faction's tribe decides which imported buildings its AI builds and what a
soldier costs (the consume line of its barracks), for both the tribe's own
barracks (a Widelands soldier) and the OpenRA barracks (a rifleman).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from wizard_rts import wl_defs
from wizard_rts.programs_data import BUILDING_OUTPUTS

FACTION_TRIBES = {
    "Red": "barbarians", "Blue": "empire", "Green": "frisians",
    "Yellow": "atlanteans", "Purple": "amazons", "Orange": "barbarians",
}
BASE_STOCK = {"log": 24, "plank": 12, "granite": 10, "ration": 12}
STARTER_PER_WARE = 8  # every ware that appears in the tribe's build costs


@lru_cache(maxsize=None)
def tribe_buildings(tribe: str) -> dict[str, dict[str, Any]]:
    out = {}
    for name in wl_defs.runnable_names():
        spec = wl_defs.building_spec(name)
        if spec and spec["tribe"] == tribe:
            out[name] = spec
    return out


@lru_cache(maxsize=None)
def starter_stock(tribe: str) -> dict[str, int]:
    """A headquarters start: building materials of the tribe, plus the base wares."""
    stock = dict(BASE_STOCK)
    for spec in tribe_buildings(tribe).values():
        for ware in spec["cost"]:
            stock.setdefault(ware, STARTER_PER_WARE)
    stock.setdefault("ax", 0)
    return {k: v for k, v in stock.items() if v > 0}


@lru_cache(maxsize=None)
def producers(tribe: str) -> dict[str, list[str]]:
    """ware -> runnable building names of the tribe that make it, cheapest first."""
    table: dict[str, list[str]] = {}
    for name, spec in tribe_buildings(tribe).items():
        if any(cmd == "recruit" for acts in spec["programs"].values() for cmd, _a in acts):
            continue  # barracks make soldiers, not wares
        for ware in spec["outputs"]:
            table.setdefault(ware, []).append(name)
    for ware, names in table.items():
        names.sort(key=lambda n: (len(tribe_buildings(tribe)[n]["inputs"]), sum(tribe_buildings(tribe)[n]["cost"].values()), n))
    return table


def barracks_of(tribe: str) -> str | None:
    for name in tribe_buildings(tribe):
        if wl_defs.is_soldier_site(wl_defs.defs()["buildings"][name]):
            return name
    return None


def legacy_outputs() -> set[str]:
    return {g for goods in BUILDING_OUTPUTS.values() for g in goods}


def inputs_for(tribe: str, building: str, ware: str) -> list[str]:
    """Wares consumed by the programmes of a building that produce `ware` (not every input it can hold)."""
    spec = tribe_buildings(tribe)[building]
    out: list[str] = []
    for actions in spec["programs"].values():
        if any(cmd == "produce" and ware in a for cmd, a in actions):
            for cmd, a in actions:
                if cmd == "consume":
                    out += [g for g in a if g not in out]
                elif cmd == "consume_groups":
                    for alts, _n in a["groups"]:
                        if alts[0] not in out:
                            out.append(alts[0])
        # createware via a worker needs no inputs
    return out

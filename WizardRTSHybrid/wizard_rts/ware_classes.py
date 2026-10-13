"""Ware classes (owner decision C, 13 Oct 2026): the tribe wares that no Widelands building consumes feed the OpenRA army.

Widelands smithies, armourers and stables make weapons, armour, tools and pack animals that nothing in the hybrid used (no training sites, workers
need no tools). A unit recipe now asks for one ware of a class on top of its raw cost, and any ware of the class the tribe holds will do:
- armour: infantry specialists (grenadier, rocket soldier, shock trooper, flamethrower, commando) wear the tribe's armour, helmets or shields;
- tool: tanks and artillery are built with the tribe's smithing tools;
- animal: transports and light vehicles (jeep, APC, V2 launcher, trucks) need the tribe's pack animal.
A barracks or factory that waits for its class ware for CLASS_PATIENCE_MS drops the requirement (recorded as an event), so a tribe whose smithy chain
is not running can still field an army. The first ware listed for a class is the one logistics fetches; the others are accepted if they are in stock.
"""

from __future__ import annotations

from typing import Any

CLASS_WARES: dict[str, dict[str, list[str]]] = {
    "barbarians": {"armour": ["helmet", "helmet_mask", "helmet_warhelm"], "tool": ["hammer", "pick", "shovel"], "animal": ["ox"]},
    "empire": {"armour": ["armor", "armor_chain", "armor_gilded"], "tool": ["hammer", "saw", "pick"], "animal": ["donkey"]},
    "atlanteans": {"armour": ["shield_advanced", "shield_steel", "tabard_golden"], "tool": ["hammer", "saw", "pick"], "animal": ["horse"]},
    "frisians": {"armour": ["helmet", "helmet_golden", "fur_garment_studded", "fur_garment_golden"], "tool": ["hammer", "pick"], "animal": ["reindeer"]},
    "amazons": {"armour": ["armor_wooden", "helmet_wooden", "vest_padded", "protector_padded"], "tool": ["hammer", "chisel", "pick"], "animal": ["tapir"]},
}
UNIT_CLASS: dict[str, str] = {
    "grenadier": "armour", "rocket_soldier": "armour", "shock_trooper": "armour", "flamethrower": "armour", "commando": "armour",
    "tank": "tool", "light_tank": "tool", "medium_tank": "tool", "artillery": "tool", "mammoth": "tool", "tesla_tank": "tool", "phase_tank": "tool",
    "chrono_tank": "tool", "mad_tank": "tool",
    "jeep": "animal", "apc": "animal", "v2_launcher": "animal", "supply_truck": "animal", "flak_truck": "animal", "minelayer": "animal",
}
CLASS_PATIENCE_MS = 20 * 60_000


def class_of(unit_kind: str) -> str | None:
    return UNIT_CLASS.get(unit_kind)


def wares_for(tribe: str, cls: str) -> list[str]:
    return list(CLASS_WARES.get(tribe, {}).get(cls, []))


def with_class(recipe: dict[str, Any], unit_kind: str, tribe: str) -> dict[str, Any]:
    """The recipe plus its class ware (primary), and `class_alts` listing the wares that may stand in for it."""
    cls = class_of(unit_kind)
    ws = wares_for(tribe, cls) if cls else []
    if not ws:
        return recipe
    out = dict(recipe)
    out["cost"] = {**recipe["cost"], ws[0]: recipe["cost"].get(ws[0], 0) + 1}
    out["class_alts"] = {ws[0]: ws[1:]}
    return out


def resolve(recipe: dict[str, Any], stock: dict[str, int]) -> dict[str, int]:
    """The cost to pay now: a class ware the stock lacks is replaced by an alternate of the class that it holds."""
    cost = dict(recipe["cost"])
    for primary, alts in (recipe.get("class_alts") or {}).items():
        if int(stock.get(primary, 0)) >= cost[primary]:
            continue
        for alt in alts:
            if int(stock.get(alt, 0)) >= 1:
                cost[primary] -= 1
                if cost[primary] <= 0:
                    del cost[primary]
                cost[alt] = cost.get(alt, 0) + 1
                break
    return cost

"""Ware classes (owner decision C, 13 Oct 2026): the tribe wares that no Widelands building consumes feed the OpenRA army.

Widelands smithies, armourers and stables make weapons, armour, tools and pack animals that nothing in the hybrid used (no training sites, workers
need no tools). A unit recipe may now be paid with one of those wares in place of one unit of a raw ware:
- armour (grenadier, rocket soldier, shock trooper, flamethrower, commando): a piece of the tribe's armour, helmet or shield stands in for one iron;
- tool (tanks, artillery): one of the tribe's smithing tools stands in for one iron;
- animal (jeep, APC, V2 launcher, trucks): the tribe's pack animal stands in for one plank (the cart).
Nothing blocks: without the wares the recipe costs what it always did. When a faction's warehouses hold a class ware, the building asks for it instead of
the raw ware, so dead-end wares are used up before raw metal is. At the start of a build the building pays a missing raw ware with an alternate it holds.
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
RAW_FOR_CLASS = {"armour": "iron", "tool": "iron", "animal": "plank"}


def class_of(unit_kind: str) -> str | None:
    return UNIT_CLASS.get(unit_kind)


def wares_for(tribe: str, cls: str) -> list[str]:
    return list(CLASS_WARES.get(tribe, {}).get(cls, []))


def with_class(recipe: dict[str, Any], unit_kind: str, tribe: str) -> dict[str, Any]:
    """The recipe plus `class_subst`: {raw ware: class wares that may stand in for one unit of it}."""
    cls = class_of(unit_kind)
    ws = wares_for(tribe, cls) if cls else []
    raw = RAW_FOR_CLASS.get(cls or "")
    if not ws or raw not in recipe["cost"]:
        return recipe
    out = dict(recipe)
    out["class_subst"] = {raw: ws}
    return out


def request_cost(recipe: dict[str, Any], held: dict[str, int]) -> dict[str, int]:
    """What the building asks logistics for: one raw ware is swapped for a class ware the faction's warehouses hold."""
    cost = dict(recipe["cost"])
    for raw, alts in (recipe.get("class_subst") or {}).items():
        pick = next((a for a in alts if int(held.get(a, 0)) >= 1), None)
        if pick is not None and cost.get(raw, 0) >= 1:
            cost[raw] -= 1
            if cost[raw] <= 0:
                del cost[raw]
            cost[pick] = cost.get(pick, 0) + 1
    return cost


def resolve(recipe: dict[str, Any], stock: dict[str, int]) -> dict[str, int]:
    """The cost to pay now: a raw ware the stock lacks is replaced, one unit at a time, by a class ware it holds."""
    cost = dict(recipe["cost"])
    left = {k: int(v) for k, v in stock.items()}
    for raw, alts in (recipe.get("class_subst") or {}).items():
        short = cost.get(raw, 0) - left.get(raw, 0)
        for alt in alts:
            while short > 0 and left.get(alt, 0) - cost.get(alt, 0) >= 1:
                cost[raw] -= 1
                if cost[raw] <= 0:
                    del cost[raw]
                cost[alt] = cost.get(alt, 0) + 1
                short -= 1
    return cost

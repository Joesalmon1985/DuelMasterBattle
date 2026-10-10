"""Source-derived OpenRA damage.

Adapted from OpenRA bleed e7e9e4ad270221d7fb9725b348c75504d48c1ebd:

- OpenRA.Mods.Common/Util.cs ApplyPercentageModifiers
- OpenRA.Mods.Common/Warheads/DamageWarhead.cs InflictDamage
- OpenRA.Mods.Common/Traits/Health.cs InflictDamage HP clamp

The C# methods do not execute. Percentage modifiers use decimal multiply-then-truncate,
matching `(int)decimal`. Armor versus values are percentage modifiers. Hit-shape search,
actor validity, and the OpenRA world are not included. GPL-3, OpenRA Developers.
"""

from __future__ import annotations

from decimal import Decimal

SOURCE = {
    "repository": "https://github.com/OpenRA/OpenRA",
    "commit": "e7e9e4ad270221d7fb9725b348c75504d48c1ebd",
    "symbols": [
        "OpenRA.Mods.Common.Util.ApplyPercentageModifiers",
        "OpenRA.Mods.Common.Warheads.DamageWarhead.InflictDamage",
        "OpenRA.Mods.Common.Traits.Health.InflictDamage",
    ],
    "status": "source-derived-adapted",
}


def apply_percentage_modifiers(number: int, percentages: list[int]) -> int:
    """Port of Util.ApplyPercentageModifiers. Truncates toward zero."""
    amount = Decimal(int(number))
    for percentage in percentages:
        amount *= Decimal(int(percentage)) / Decimal(100)
    return int(amount)


def damage_versus(versus: dict[str, int], armor_types: list[str]) -> int:
    """Port of DamageWarhead.DamageVersus without actor traits.

    Empty versus, or no matching armor, returns 100. Otherwise the matching
    versus percentages are applied to 100, as DamageWarhead does.
    """
    if not versus:
        return 100
    matched = [int(versus[name]) for name in armor_types if name in versus]
    if not matched:
        return 100
    return apply_percentage_modifiers(100, matched)


def warhead_damage(raw_damage: int, damage_modifiers: list[int], versus_percent: int) -> int:
    """Port of DamageWarhead.InflictDamage's modifier chain."""
    return apply_percentage_modifiers(int(raw_damage), [*damage_modifiers, int(versus_percent)])


def inflict_damage(hp: int, max_hp: int, applied: int) -> int:
    """Port of Health.InflictDamage's HP write. Dead actors take no further damage."""
    if int(hp) <= 0:
        return 0
    return max(0, min(int(max_hp), int(hp) - int(applied)))

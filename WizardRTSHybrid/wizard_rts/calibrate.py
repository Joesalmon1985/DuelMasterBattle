"""Military recipes from OpenRA cost classes (plan v2 6.1): a unit's physical cost is derived by a transparent rule, not guessed.

value(unit) = OpenRA credits / CREDITS_PER_VALUE, spread over the wares of the unit's class template, rounded to whole wares (at least 1 of
the main ware). WARE_VALUE is the one price list (the same weights the plus AI uses to compare costs). CREDITS_PER_VALUE (75) is the median
ratio of credits to ware value over the hand-written recipes that existed on 12 Oct 2026, so new units sit on the same scale as old ones
(`python3 scripts/calibrate_report.py` prints the comparison). Build time grows with credits.
Only units added after that date use this rule; the earlier recipes keep their hand-set costs.
"""

from __future__ import annotations

from typing import Any

WARE_VALUE = {"log": 0.5, "plank": 1.0, "granite": 0.8, "ration": 1.5, "coal": 1.5, "iron": 3.0, "gold": 5.0}
CREDITS_PER_VALUE = 75.0
TEMPLATES = {
    "infantry": {"ration": 0.3, "iron": 0.4, "coal": 0.3},
    "special_infantry": {"ration": 0.3, "iron": 0.3, "coal": 0.2, "gold": 0.2},
    "light_infantry": {"ration": 0.7, "coal": 0.3},
    "vehicle": {"plank": 0.2, "granite": 0.2, "iron": 0.4, "coal": 0.2},
    "ship": {"plank": 0.35, "iron": 0.4, "coal": 0.15, "ration": 0.1},
}
# (producer building, unit kind, OpenRA actor, label, template): new roster entries (combat units with a weapon in the imported rules)
NEW_UNITS = [
    ("barracks", "flamethrower", "e4", "Flamethrower", "infantry"),
    ("barracks", "commando", "e7", "Commando", "special_infantry"),
    ("barracks", "attack_dog", "dog", "Attack dog", "light_infantry"),
    ("naval_yard", "destroyer", "dd", "Destroyer", "ship"),
    ("naval_yard", "cruiser", "ca", "Cruiser", "ship"),
    ("sub_pen", "missile_sub", "msub", "Missile submarine", "ship"),
]
CARD_ONLY = set(u for _b, u, *_ in NEW_UNITS)  # openra_content.install adds the rest of the roster


def recipe(credits: int, template: str) -> dict[str, Any]:
    value = credits / CREDITS_PER_VALUE
    cost = {ware: max(1, round(share * value / WARE_VALUE[ware])) for ware, share in TEMPLATES[template].items()}
    return {"cost": cost, "ms": int(min(70_000, max(20_000, 20_000 + credits * 12))), "value": round(sum(WARE_VALUE[w] * n for w, n in cost.items()), 2)}


def new_recipes(rules_actor) -> dict[str, dict[str, dict[str, Any]]]:
    """producer building -> unit kind -> recipe, for NEW_UNITS (rules_actor(definition) reads the imported OpenRA rules)."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for building, unit, actor, label, template in NEW_UNITS:
        a = rules_actor(f"openra.{actor}")
        r = recipe(int(a["cost"]), template)
        out.setdefault(building, {})[unit] = {"label": label, "definition": f"openra.{actor}", "cost": r["cost"], "ms": r["ms"],
                                              "cost_source": f"calibrated from {int(a['cost'])} OpenRA credits ({template} template, value {r['value']})"}
    return out

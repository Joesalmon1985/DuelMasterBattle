"""Advanced extraction on the EXISTING Widelands resource sites (owner clarification of 11 Oct 2026).

There is no second geology. A drill covers terrain tiles; each tile's canonical reserve is the Widelands `res_kind`/`res_amt`
layer, the same one the Widelands mine programme digs (resources.production_mine). Extraction technology only decides which ware
comes out per reserve unit (data/mindustry_overrides.json `extraction`):

- deposit rules: reserve kind -> output item, minimum drill tier, reserve units consumed per output item;
- floor rules: sand comes from existing desert/beach terrain (an infinite floor drop, no reserve).

Reserve units are taken from the covered tile with the most left (ties by position), so changing extractor never double-counts.
"""

from __future__ import annotations

from typing import Any

from wizard_rts import terrain as T
from wizard_rts.industry import registry as R


def _item_hardness(item: str) -> int:
    return int(R.item_info(item)["hardness"])


def tile_sources(world: Any, x: int, y: int) -> list[dict[str, Any]]:
    """Everything one tile can yield to *some* tier: [{item, kind, min_tier, units_per_item}]."""
    t = world.terrain
    if t is None or not t.in_bounds(x, y):
        return []
    ex = R.extraction()
    out: list[dict[str, Any]] = []
    res, amount = t.resource(x, y)
    if res and amount > 0:
        for rule in ex["deposit_rules"].get(res, []):
            out.append({"item": rule["item"], "source": "deposit", "deposit": res, "min_tier": int(rule["min_tier"]),
                        "units_per_item": int(rule["units_per_item"])})
    name = t.terrain_name(x, y)
    for fname, rule in ex["floor_rules"].items():
        if t.cls[y * t.w + x] in (T.WALKABLE, T.ARABLE) and any(s in name for s in rule["terrain_name_contains"]):
            out.append({"item": rule["item"], "source": "floor", "deposit": "", "min_tier": int(rule["min_tier"]), "units_per_item": 0})
    return out


def options(world: Any, tiles: list[tuple[int, int]], tier: int) -> dict[str, dict[str, Any]]:
    """What a drill of this tier over `tiles` can produce: item -> {tiles, units_per_item, source, hardness}."""
    found: dict[str, dict[str, Any]] = {}
    for (x, y) in tiles:
        for s in tile_sources(world, x, y):
            if s["min_tier"] > tier or _item_hardness(s["item"]) > tier:
                continue
            o = found.setdefault(s["item"], {"tiles": [], "units_per_item": s["units_per_item"], "source": s["source"],
                                             "deposit": s["deposit"], "hardness": _item_hardness(s["item"])})
            o["tiles"].append((x, y))
    return found


def choose_item(opts: dict[str, dict[str, Any]], target: str | None) -> str | None:
    """The configured target if the drill can make it, else the item with the most covered tiles (Mindustry's dominant item),
    ties by item name."""
    if target and target in opts:
        return target
    if not opts:
        return None
    return sorted(opts, key=lambda i: (-len(opts[i]["tiles"]), i))[0]


def take_reserve(world: Any, o: dict[str, Any]) -> bool:
    """Remove one output item's worth of reserve from the covered tile with most left. Floor drops take nothing.
    False when the reserve cannot pay (a non-mineral deposit used up; minerals are inexhaustible, D22)."""
    units = int(o["units_per_item"])
    if o["source"] == "floor" or units == 0:
        return True
    t = world.terrain
    kind = o["deposit"]
    if kind in T.MINERALS:  # D22: a drill on a mineral site never exhausts it; logged as an inexhaustible-source inflow
        from wizard_rts.resources import note_inexhaustible

        if not any(t.res_kind[y * t.w + x] == T.RES_CODE[kind] for x, y in o["tiles"]):
            return False
        note_inexhaustible(world, kind, 1)
        world.stats["extracted_units_" + kind] = world.stats.get("extracted_units_" + kind, 0) + units
        return True
    cells = sorted(((t.amount(x, y, kind), -x, -y) for x, y in o["tiles"]), reverse=True)
    if sum(c[0] for c in cells) < units:
        return False
    left = units
    for amount, nx, ny in cells:
        if left == 0:
            break
        left -= t.take(-nx, -ny, kind, min(left, amount))
    world.stats["extracted_units_" + kind] = world.stats.get("extracted_units_" + kind, 0) + units
    return True


def reserve_left(world: Any, o: dict[str, Any]) -> int:
    """-1 means unlimited: a floor drop, or (D22) a mineral deposit."""
    if o["source"] == "floor" or o["deposit"] in T.MINERALS:
        return -1
    return sum(world.terrain.amount(x, y, o["deposit"]) for x, y in o["tiles"])

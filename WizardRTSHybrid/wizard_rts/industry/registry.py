"""Canonical registry: pinned-source defs + explicit hybrid overrides -> block / item / unit specs the simulation reads.

Pipeline (D06, ARCHITECTURE_CONTRACT): external/mindustry (pinned) -> scripts/import_mindustry_defs.py -> data/mindustry_defs.json
(original numbers) -> data/mindustry_overrides.json (hybrid adaptation, labelled) -> this module. Nothing in the simulation reads
the Java tree or the raw JSON directly.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[1] / "data"
PREFIX = "mdy:"
TICKS = 60


SYNTHETIC_ITEMS = {  # Widelands wares a drill can win from the existing deposits (owner programme 13 Oct 2026): not Mindustry items, but the same drill rules apply
    "granite": {"hardness": 1, "cost": 1.0, "flammability": 0.0, "explosiveness": 0.0, "radioactivity": 0.0, "buildable": False},
    "iron_ore": {"hardness": 2, "cost": 1.0, "flammability": 0.0, "explosiveness": 0.0, "radioactivity": 0.0, "buildable": False},
    "gold_ore": {"hardness": 2, "cost": 1.0, "flammability": 0.0, "explosiveness": 0.0, "radioactivity": 0.0, "buildable": False},
}


@lru_cache(maxsize=1)
def defs() -> dict[str, Any]:
    d = json.loads((DATA / "mindustry_defs.json").read_text())
    for k, v in SYNTHETIC_ITEMS.items():
        d["items"].setdefault(k, v)
    return d


@lru_cache(maxsize=1)
def overrides() -> dict[str, Any]:
    return json.loads((DATA / "mindustry_overrides.json").read_text())


def ware(item: str) -> str:
    """Inventory ware id of a Mindustry item."""
    m = overrides()["ware_map"]
    if item in m:
        return m[item]
    if item in SYNTHETIC_ITEMS:
        return item
    from wizard_rts.industry import blocks as B

    return B.ware_of_item(item)


def item_of(ware_id: str) -> str | None:
    for k, v in overrides()["ware_map"].items():
        if k != "_doc" and v == ware_id:
            return k
    from wizard_rts.industry import blocks as B

    if ware_id in SYNTHETIC_ITEMS:
        return ware_id
    return B.item_of_ware(ware_id)


@lru_cache(maxsize=None)
def _blocks() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    d = defs()["blocks"]
    for src_id, o in overrides()["blocks"].items():
        b = d[src_id]
        spec: dict[str, Any] = {
            "id": src_id, "kind": o["kind"], "label": o["label"], "role": o["role"], "class": b["class"], "size": int(b["size"]),
            "definition": "mindustry." + src_id, "game": "mindustry", "card": o["card"], "upgrade_from": list(o.get("upgrade_from", [])),
            "source_cost": dict(b["requirements"]),
            "consume_items": {ware(i): n for i, n in b.get("consume_items", {}).items()},
            "output_item": {ware(i): n for i, n in b.get("output_item", {}).items()},
            "power_use_per_s": float(b.get("consume_power_per_second", 0.0)),
            "power_production_per_s": float(b.get("power_production_per_second", 0.0)),
            "power_buffer": float(b.get("power_buffer", 0.0)),
            "craft_ticks": int(b["fields"].get("craftTime", 0)),
            "cost_source": "hybrid adaptation of Mindustry v146 requirements (mindustry_overrides.json cost_note)",
        }
        if "hybrid_cost" in o:
            spec["cost"] = dict(o["hybrid_cost"])
        if "hybrid_cost_per_tiles" in o:  # a belt run pays `cost` for every `tiles` tiles (rounded up)
            spec["cost_per_tiles"] = {"tiles": int(o["hybrid_cost_per_tiles"]["tiles"]), "cost": dict(o["hybrid_cost_per_tiles"]["cost"])}
            spec["cost"] = dict(o["hybrid_cost_per_tiles"]["cost"])
        if o["role"] == "drill":
            spec["tier"] = int(b["fields"].get("tier", 2))
            spec["drill_ticks"] = float(b["fields"].get("drillTime", 600))
            spec["hardness_multiplier"] = 50.0
        if o["role"] == "belt":
            spec["belt"] = dict(b["conveyor"])
        if o["role"] == "node":
            spec["laser_range"] = int(b["power_node"]["laser_range"])
            spec["max_nodes"] = int(b["power_node"]["max_nodes"])
        if o["role"] == "generator":
            spec["item_duration_ticks"] = float(b["fields"].get("itemDuration", 120))
            spec["fuel_min_flammability"] = 0.2  # ConsumeItemFlammable default
            spec["solar"] = b["class"] == "SolarGenerator"  # no fuel: produces whenever it exists
        if o["role"] == "unit_factory":
            spec["plans"] = [{"unit": p["unit"], "ticks": int(p["time_ticks"]),
                              "requirements": {ware(i): n for i, n in p["requirements"].items()}} for p in b["plans"]]
        from wizard_rts.industry import blocks as B

        g = B.spec(o["kind"]) or {}
        for k in ("consume_liquids", "boost_liquids", "boost_items", "output_liquid", "heat_in", "heat_out", "results", "liquid_capacity", "item_capacity", "attribute",
                  "ammo", "shoot_type", "coolant", "flammable", "optional_consumers", "refs", "era", "health", "category", "upgrades", "assembler_plans", "filter"):
            if k in g:
                spec.setdefault(k, g[k])
        for k, v in (("consume_liquids", {}), ("boost_liquids", {}), ("boost_items", {}), ("output_liquid", {}), ("heat_in", 0.0), ("heat_out", 0.0), ("results", {}),
                     ("liquid_capacity", 10.0), ("item_capacity", 10), ("attribute", ""), ("ammo", None), ("shoot_type", None), ("coolant", None),
                     ("flammable", False), ("optional_consumers", []), ("refs", {}), ("sandbox", False), ("era", 2), ("health", None), ("category", ""),
                     ("upgrades", None), ("assembler_plans", None), ("filter", None)):
            spec.setdefault(k, v)
        spec["fields"] = dict(b["fields"])
        spec["id"] = src_id
        out[o["kind"]] = spec
    return out


IMPLEMENTED_ROLES: set[str] = set()  # roles engine.py can simulate; a generic block is offered (cards, menu) only when its role is here


@lru_cache(maxsize=None)
def _generic(kind: str) -> dict[str, Any] | None:
    """A block of mindustry_full.json that has no hand-tuned override: the original slice's spec shape plus the generic fields."""
    from wizard_rts.industry import blocks as B

    g = B.spec(kind)
    if g is None:
        return None
    spec = dict(g)
    spec["card"] = "dmb.card.industry"
    spec["upgrade_from"] = []
    spec["cost_source"] = "hybrid conversion of Mindustry v146 requirements (industry/blocks.py hybrid_cost)"
    f = g["fields"]
    if g["role"] == "drill":
        spec["tier"] = int(f.get("tier", 2))
        spec["drill_ticks"] = float(f.get("drillTime", 600))
        spec["hardness_multiplier"] = 50.0
    if g["role"] == "belt":
        spec["belt"] = {"speed": float(f.get("speed", 0.03)), "tiles_per_second": round(float(f.get("speed", 0.03)) * TICKS, 4), "item_space": 0.4, "capacity": 3}
    if g["role"] == "node":
        spec["laser_range"] = int(f.get("laserRange", f.get("range", 6)))
        spec["max_nodes"] = int(f.get("maxNodes", 10))
    if g["role"] == "generator":
        spec["item_duration_ticks"] = float(f.get("itemDuration", 120))
        spec["fuel_min_flammability"] = 0.2
        spec["solar"] = g["class"] in ("SolarGenerator", "PowerSource")
    if g["role"] == "unit_factory":
        spec["plans"] = [{"unit": p["unit"], "ticks": int(p["time_ticks"] or 0), "requirements": {B.ware_of_item(i): int(n) for i, n in p["requirements"].items()}}
                         for p in (g.get("plans") or [])]
    spec["power_buffer"] = g["power_buffer"]
    return spec


def kinds() -> list[str]:
    from wizard_rts.industry import blocks as B
    from wizard_rts.industry import engine  # noqa: F401  (registers IMPLEMENTED_ROLES)

    extra = [k for k in B.functional_kinds() if k not in _blocks() and B.spec(k)["role"] in IMPLEMENTED_ROLES]
    return sorted(set(_blocks()) | set(extra))


def block(kind: str) -> dict[str, Any] | None:
    b = _blocks().get(kind)
    if b is not None:
        return b
    return _generic(kind) if kind.startswith(PREFIX) else None


def build_spec(kind: str) -> dict[str, Any] | None:
    """The construction-menu entry (same shape as construction.BUILD_MENU values)."""
    b = block(kind)
    if b is None:
        return None
    return {"size": "", "label": b["label"], "definition": b["definition"], "game": "mindustry", "cost": dict(b["cost"]),
            "cost_source": b["cost_source"], "source_cost": dict(b["source_cost"]), "role": b["role"], "footprint": b["size"]}


def is_kind(kind: str) -> bool:
    return kind.startswith(PREFIX) and kind in _blocks()


def item_info(item: str) -> dict[str, Any]:
    return defs()["items"][item]


def extraction() -> dict[str, Any]:
    return overrides()["extraction"]


def ground_unit(name: str) -> dict[str, Any] | None:
    u = overrides()["units"]["ground_units"].get(name)
    return u


def unit_rules() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """(actors, weapons) in rules.py's schema, derived from the imported unit stats and the override scales. Keys are `mdy_<unit>`."""
    ov = overrides()["units"]
    hp_scale, dmg_scale = float(ov["hp_scale"]), float(ov["damage_scale"])
    actors: dict[str, dict[str, Any]] = {}
    weapons: dict[str, dict[str, Any]] = {}
    for name, o in ov["ground_units"].items():
        src = defs()["units"][name]
        w = src["weapons"][0]
        wname = f"MDY_{name}_gun"
        reload_s = float(o.get("reload_ticks", w["reload_ticks"])) / TICKS / int(o.get("mirrored_weapons", 1))  # mirrored mounts fire alternately
        weapons[wname] = {
            "range": float(o["range_cells"]), "min_range": 0.0, "reload": max(1, round(reload_s * 1000 / 40)), "burst": 1, "burst_delay": 5,
            "projectile": "InstantHit", "projectile_speed": 0, "valid_targets": ["Ground", "GroundActor"], "invalid_targets": [],
            "warheads": [{"type": "SpreadDamage", "damage": int(round(float(o.get("damage", w["damage"])) * dmg_scale)), "spread": 0.0, "versus": {},
                          "valid_targets": ["GroundActor"]}],
            "source": f"Mindustry v146 UnitTypes.{name}: damage {w['damage']}, reload {w['reload_ticks']} ticks, x{dmg_scale:g} damage scale",
        }
        actors["mdy_" + name] = {
            "name": o["label"], "hp": int(round(float(src["health"]) * hp_scale)), "armor": o["armor"], "speed": int(o["speed"]), "cost": 0,
            "queue": "", "prerequisites": "", "armaments": [wname], "target_types": list(o["target_types"]), "mobile": True,
            "is_building": False, "locomotor": o["locomotor"],
            "source": f"Mindustry v146 UnitTypes.{name}: health {src['health']}, x{hp_scale:g} hp scale",
        }
    from wizard_rts.industry import units as U

    all_a, all_w = U.all_rules()  # every other unit from the statement-level import; the hand-tuned three keep their entries
    all_a, all_w = dict(all_a), dict(all_w)
    all_a.update(actors)
    all_w.update(weapons)
    return all_a, all_w

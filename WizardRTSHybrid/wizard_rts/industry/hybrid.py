"""The industrial replacement of Widelands production (owner programme 13 Oct 2026, section 6: the Industrial Revolution).

Modern does not delete the old economy. It offers machines that make the same wares several times faster and in bulk, run on electricity and liquids, and leave
the hand-worked buildings economically obsolete. Where Mindustry has a direct equivalent (drills, smelting, pumps, presses) the Mindustry block does it
(`extraction.deposit_rules` now lets drills yield granite, iron ore and gold ore). Where it has none, this module defines hybrid industrial blocks
(`mdy:hy_*`, class HybridCrafter) with configurable recipes:

    tree harvester          trees in reach -> logs                   automated sawmill   logs -> planks
    arc smelter             iron ore + coal -> iron                  gold refinery       gold ore + coal -> gold
    water bottler           liquid water -> the water ware           hydroponic farm     liquid water -> any crop
    protein vat             fish / meat                              food plant          bread, rations, meals, drinks, smoked food, ...
    material press          bricks, grout, blackwood, marble, cloth, rope, reed, quartz, ... from industrial raw materials
    tool foundry            every Widelands tool from iron and planks

`ware_sources()` maps each Widelands ware to its industrial source; tests/test_industrial_revolution.py checks that every ware the civilian economy and the
OpenRA recipes consume has one, and that each industrial block makes its ware many times faster than the Widelands building that made it. `convert` turns a
standing Widelands building into the industrial block that replaces it (the S08 upgrade price), which is the dismantling/replacement mechanic.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

TICKS = 60.0
SPORE = "mdy.spore_pod"
SAND = "mdy.sand"

# product -> (inputs, output count, craft ticks, liquid water per tick, power per tick)
FOOD_CROPS = {"wheat": 4, "barley": 4, "corn": 4, "cassavaroot": 4, "cocoa_beans": 3, "grape": 4, "fruit": 4, "blackroot": 3, "honey": 2, "liana": 3}
PLANT_FIBRE = {"cloth": ({SPORE: 2}, 2), "rope": ({SPORE: 2}, 1), "reed": ({SPORE: 2}, 2), "spidercloth": ({SPORE: 3}, 1), "spider_silk": ({SPORE: 2}, 1), "fur": ({SPORE: 3}, 2),
               "wool": ({SPORE: 2}, 2), "gold_thread": ({"gold": 1}, 2), "rubber": ({SPORE: 2}, 2)}
MATERIALS = {"brick": ({"granite": 2}, 2, 0.2), "grout": ({"granite": 2, "coal": 1}, 2, 0.2), "blackwood": ({"log": 2}, 2, 0.1), "marble": ({"granite": 3}, 2, 0.0),
             "marble_column": ({"marble": 2}, 1, 0.0), "quartz": ({SAND: 3}, 1, 0.0), "diamond": ({SAND: 4, "coal": 1}, 1, 0.0), "clay": ({"granite": 1}, 2, 0.3),
             "balsa": ({"log": 2}, 2, 0.1), "ironwood": ({"log": 2}, 2, 0.1), "gold_dust": ({"gold_ore": 1}, 2, 0.0)}
PROCESSED = {"flour": ({"wheat": 2}, 2, 0.0), "bread": ({"wheat": 2}, 2, 0.2), "ration": ({"wheat": 1, "fish": 1}, 2, 0.0), "meal": ({"bread": 1, "meat": 1}, 2, 0.0),
             "snack": ({"bread": 1, "fish": 1}, 2, 0.0), "beer": ({"wheat": 2}, 2, 0.3), "beer_strong": ({"wheat": 3}, 2, 0.3), "wine": ({"grape": 2}, 2, 0.0), "mead": ({"honey": 2}, 2, 0.0),
             "chocolate": ({"cocoa_beans": 2}, 2, 0.0), "smoked_fish": ({"fish": 2, "coal": 1}, 2, 0.0), "smoked_meat": ({"meat": 2, "coal": 1}, 2, 0.0), "honey_bread": ({"bread": 1, "honey": 1}, 2, 0.0),
             "cornmeal": ({"corn": 2}, 2, 0.0), "blackroot_flour": ({"blackroot": 2}, 2, 0.0), "bread_frisians": ({"wheat": 2}, 2, 0.2)}
TOOLS = ("pick", "hammer", "shovel", "saw", "scythe", "felling_ax", "fire_tongs", "fishing_rod", "fishing_net", "hunting_spear", "hunting_bow", "bread_paddle", "kitchen_tools", "basket",
         "needles", "chisel", "milking_tongs", "buckets", "machete", "stone_bowl", "hook_pole", "firestones")

UNMADE = {  # Widelands wares with no industrial source, each with the reason
    "ax": "hand weapons are replaced by the OpenRA military (D05); the barracks recipe pays rifleman costs in other wares",
    "carrier": "a worker, created by warehouses", "recruit": "a worker, created by warehouses", "scrap_iron": "dismantling by-product, not an input", "scrap_metal_mixed": "dismantling by-product, not an input",
    "fur_garment_old": "dismantling by-product, not an input",
    "ox": "a draft animal (trade carriers); bred by farms", "donkey": "a draft animal", "horse": "a draft animal", "tapir": "a draft animal", "reindeer": "a draft animal",
}
for _w in ("armor", "armor_chain", "armor_gilded", "armor_helmet", "armor_wooden", "ax_battle", "ax_broad", "ax_bronze", "ax_sharp", "ax_warriors", "boots_hero", "boots_sturdy", "boots_swift",
           "fur_garment", "fur_garment_golden", "fur_garment_studded", "helmet", "helmet_golden", "helmet_mask", "helmet_warhelm", "helmet_wooden", "protector_padded", "shield_advanced",
           "shield_steel", "spear", "spear_advanced", "spear_hardened", "spear_heavy", "spear_stone_tipped", "spear_war", "spear_wooden", "sword_broad", "sword_double", "sword_long",
           "sword_short", "tabard", "tabard_golden", "trident_double", "trident_heavy_double", "trident_light", "trident_long", "trident_steel", "tunic", "vest_padded", "warriors_coat"):
    UNMADE[_w] = "soldier equipment of the Widelands tribes: replaced by the OpenRA military roster (D05)"


def _block(bid: str, label: str, size: int, cost: dict[str, int], recipes: dict[str, dict[str, Any]], role: str = "crafter", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    first = next(iter(recipes.values()))
    spec = {
        "id": bid, "kind": "mdy:" + bid.replace("-", "_"), "label": label, "role": role, "class": "HybridCrafter", "size": size, "game": "hybrid", "definition": "dmb.industry." + bid.replace("-", "_"),
        "era": 2, "sandbox": False, "category": "crafting", "source_cost": {}, "cost": dict(cost), "health": None,
        "consume_items": dict(first.get("consume_items", {})), "consume_liquids": dict(first.get("liquids", {})), "boost_liquids": {}, "boost_items": {}, "coolant": None, "flammable": False,
        "optional_consumers": [], "power_use_per_s": round(float(first.get("power", 0.5)) * TICKS, 4), "power_buffer": 0.0, "power_production_per_s": 0.0,
        "output_item": dict(first["output"]), "output_liquid": {}, "heat_out": 0.0, "heat_in": 0.0, "craft_ticks": int(first["ticks"]), "fields": {"size": size},
        "results": {}, "liquid_capacity": 30.0, "item_capacity": 20, "ammo": None, "shoot_type": None, "plans": None, "upgrades": None, "assembler_plans": None, "filter": None,
        "java_name": "", "attribute": "", "refs": {}, "recipes": recipes, "default_recipe": next(iter(recipes)),
    }
    if extra:
        spec.update(extra)
    return spec


def _recipes_from(table: dict[str, tuple], power: float, ticks: int, liquid: bool = False) -> dict[str, dict[str, Any]]:
    out = {}
    for product, v in table.items():
        ins, n = v[0], v[1]
        wl = float(v[2]) if len(v) > 2 else 0.0
        out[product] = {"consume_items": dict(ins), "output": {product: n}, "ticks": ticks, "power": power, "liquids": ({"water": wl} if wl > 0 else {})}
    return out


@lru_cache(maxsize=1)
def specs() -> dict[str, dict[str, Any]]:
    blocks = [
        _block("hy-tree-harvester", "Tree harvester", 2, {"iron": 3, "plank": 6, "mdy.silicon": 4},
               {"log": {"consume_items": {}, "output": {"log": 2}, "ticks": 110, "power": 1.0}}, role="harvester", extra={"harvest_radius": 9}),
        _block("hy-sawmill-line", "Automated sawmill", 2, {"iron": 3, "plank": 4, "granite": 3}, {"plank": {"consume_items": {"log": 2}, "output": {"plank": 3}, "ticks": 50, "power": 0.5}}),
        _block("hy-arc-smelter", "Arc smelter", 2, {"iron": 4, "granite": 4, "mdy.graphite": 4},
               {"iron": {"consume_items": {"iron_ore": 1, "coal": 1}, "output": {"iron": 2}, "ticks": 40, "power": 1.0}}),
        _block("hy-gold-refinery", "Gold refinery", 2, {"iron": 4, "granite": 4, "mdy.graphite": 4},
               {"gold": {"consume_items": {"gold_ore": 1, "coal": 1}, "output": {"gold": 1}, "ticks": 60, "power": 1.0}}),
        _block("hy-water-bottler", "Water bottler", 1, {"iron": 2, "plank": 2, "mdy.metaglass": 3},
               {"water": {"consume_items": {}, "liquids": {"water": 0.6}, "output": {"water": 2}, "ticks": 30, "power": 0.3}}),
        _block("hy-hydroponic-farm", "Hydroponic farm", 3, {"iron": 5, "plank": 6, "mdy.metaglass": 8, "mdy.silicon": 6},
               {c: {"consume_items": {}, "liquids": {"water": 0.3}, "output": {c: n}, "ticks": 110, "power": 1.0} for c, n in FOOD_CROPS.items()}),
        _block("hy-protein-vat", "Protein vat", 2, {"iron": 4, "plank": 4, "mdy.metaglass": 6},
               {"fish": {"consume_items": {}, "liquids": {"water": 0.2}, "output": {"fish": 2}, "ticks": 100, "power": 0.6},
                "meat": {"consume_items": {SPORE: 1}, "liquids": {"water": 0.2}, "output": {"meat": 2}, "ticks": 100, "power": 0.8}}),
        _block("hy-food-plant", "Food plant", 3, {"iron": 5, "plank": 6, "granite": 4, "mdy.silicon": 5}, _recipes_from(PROCESSED, 0.9, 80)),
        _block("hy-material-press", "Material press", 2, {"iron": 4, "plank": 4, "granite": 4, "mdy.graphite": 4}, _recipes_from(MATERIALS, 0.8, 70)),
        _block("hy-fibre-loom", "Industrial loom", 2, {"iron": 4, "plank": 4, "mdy.silicon": 4},
               {p: {"consume_items": dict(ins), "output": {p: n}, "ticks": 70, "power": 0.6} for p, (ins, n) in PLANT_FIBRE.items()}),
        _block("hy-tool-foundry", "Tool foundry", 2, {"iron": 6, "plank": 4, "granite": 4, "mdy.graphite": 4},
               {t: {"consume_items": {"iron": 1, "plank": 1}, "output": {t: 2}, "ticks": 60, "power": 0.7} for t in TOOLS}),
    ]
    blocks += _assembly_lines()
    return {b["kind"]: b for b in blocks}


def _assembly_lines() -> list[dict[str, Any]]:
    """Modern assembly lines: electric, item-fed factories that make an enhanced (Mk2) version of every Red Alert combat unit."""
    import json
    from pathlib import Path

    ra = json.loads((Path(__file__).resolve().parents[1] / "data" / "openra_rules.json").read_text())["actors"]
    lines = {"hy-assembly-barracks": ("Assembly barracks", ("Infantry",), 3), "hy-assembly-vehicle-plant": ("Assembly vehicle plant", ("Vehicle",), 4),
             "hy-assembly-shipyard": ("Assembly shipyard", ("Ship",), 4), "hy-assembly-airfield": ("Assembly airfield", ("Aircraft",), 4)}
    out = []
    for bid, (label, queues, size) in lines.items():
        plans = []
        for key, a in sorted(ra.items()):
            if a.get("queue") in queues and a.get("armaments") and a.get("mobile") and not key.startswith(("mk2_",)) and key not in ("harv",) and "~disabled" not in a.get("prerequisites", ""):
                c = int(a["cost"])
                req = {"mdy.silicon": max(2, c // 120), "mdy.titanium": max(1, c // 250), "mdy.graphite": max(1, c // 400)}
                if c >= 1500:
                    req["mdy.plastanium"] = max(1, c // 600)
                plans.append({"unit": "mk2_" + key, "ticks": 480 + c * 2, "requirements": req})
        spec = _block(bid, label, size, {"iron": 8, "plank": 8, "granite": 6, "mdy.silicon": 12, "mdy.titanium": 8},
                      {"mk2": {"consume_items": {}, "output": {"mk2": 1}, "ticks": 60, "power": 2.0}}, role="unit_factory",
                      extra={"class": "UnitFactory", "plans": plans, "fields": {"size": size}, "default_recipe": "mk2"})
        spec.pop("recipes", None)
        spec["default_recipe"] = ""
        out.append(spec)
    return out


def effective(spec: dict[str, Any], m: dict[str, Any]) -> dict[str, Any]:
    """The spec with the machine's chosen recipe applied (a copy when it has recipes; the spec itself otherwise)."""
    rec = spec.get("recipes")
    if not rec:
        return spec
    r = rec.get(m.get("recipe") or spec["default_recipe"]) or rec[spec["default_recipe"]]
    out = dict(spec)
    out.update(consume_items=dict(r.get("consume_items", {})), consume_liquids=dict(r.get("liquids", {})), output_item=dict(r["output"]), craft_ticks=int(r["ticks"]),
               power_use_per_s=round(float(r.get("power", 0.5)) * TICKS, 4))
    return out


@lru_cache(maxsize=1)
def ware_sources() -> dict[str, list[str]]:
    """Widelands ware -> the industrial block kinds that make it (drills for raw ore and stone, hybrid blocks for the rest)."""
    out: dict[str, list[str]] = {}
    for kind, s in specs().items():
        for recipe in s.get("recipes", {}):
            out.setdefault(recipe, []).append(kind)
    out["granite"] = out.get("granite", []) + ["drill:stones"]
    out["iron_ore"] = ["drill:iron"]
    out["gold_ore"] = ["drill:gold"]
    out["coal"] = ["drill:coal"]
    return out


# Widelands building -> the hybrid industrial block that replaces it (the old building keeps working; `convert` swaps them)
REPLACES = {
    "lumberjacks_hut": "mdy:hy_tree_harvester", "lumberjacks_house": "mdy:hy_tree_harvester", "woodcutters_house": "mdy:hy_tree_harvester", "woodcutters_hut": "mdy:hy_tree_harvester",
    "sawmill": "mdy:hy_sawmill_line", "smelting_works": "mdy:hy_arc_smelter", "furnace": "mdy:hy_arc_smelter", "farm": "mdy:hy_hydroponic_farm", "well": "mdy:hy_water_bottler",
    "bakery": "mdy:hy_food_plant", "tavern": "mdy:hy_food_plant", "inn": "mdy:hy_food_plant", "brewery": "mdy:hy_food_plant", "weaving_mill": "mdy:hy_fibre_loom",
    "fishers_house": "mdy:hy_protein_vat", "fishers_hut": "mdy:hy_protein_vat", "hunters_house": "mdy:hy_protein_vat", "hunters_hut": "mdy:hy_protein_vat",
    "toolsmithy": "mdy:hy_tool_foundry", "metal_workshop": "mdy:hy_tool_foundry", "lime_kiln": "mdy:hy_material_press", "brick_kiln": "mdy:hy_material_press",
    "wood_hardener": "mdy:hy_material_press", "stonemasons_house": "mdy:hy_material_press",
}

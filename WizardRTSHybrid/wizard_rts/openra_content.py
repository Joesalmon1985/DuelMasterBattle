"""The rest of the Red Alert roster as hybrid buildings and recipes (owner programme 13 Oct 2026, scope: OpenRA `ra` mod, pinned commit).

`data/openra_rules.json` holds every actor. This module decides, once and visibly, how each one enters the game:
  * building -> a build-menu kind (`construction.BUILD_MENU`) paid in wares by a template scaled from its credits (`calibrate`), its footprint
    from OpenRA's Dimensions, its prerequisites mapped to hybrid kinds;
  * unit -> a recipe at the producing building (`construction.RECIPES`), same cost rule, with prerequisite buildings;
  * excluded -> a written reason (power, the credit economy, mission-only actors, the construction yard the hybrid replaces with settlers).
Hand-set entries that existed before (barracks, vehicle factory, naval yards, turrets...) are left untouched.
"""

from __future__ import annotations

from typing import Any

from wizard_rts import calibrate

# actor -> hybrid kind of a building that already exists
EXISTING_BUILDING = {"barr": "barracks", "tent": "barracks", "weap": "vehicle_factory", "gun": "defense", "ftur": "flame_tower", "tsla": "tesla_coil", "syrd": "naval_yard", "spen": "sub_pen"}
EXCLUDED_BUILDING = {
    "powr": "power plants: power comes from the Mindustry industry in Modern (roster rule 4.2)", "apwr": "advanced power plant: same", "proc": "ore refinery: the credit economy is replaced by wares",
    "silo": "ore silo: resource storage of the credit economy", "fact": "construction yard: disabled in the RA rules; settlers and MCVs found settlements",
    "spef": "disabled in the RA rules (prerequisite ~disabled)",
    "atef": "decoy building (D27): OpenRA fakes only fool an enemy that cannot see the player; with per-faction visibility they would need a full disguise system, so they are excluded",
    "domf": "decoy building (D27): OpenRA fakes only fool an enemy that cannot see the player; with per-faction visibility they would need a full disguise system, so they are excluded",
    "facf": "decoy building (D27): OpenRA fakes only fool an enemy that cannot see the player; with per-faction visibility they would need a full disguise system, so they are excluded",
    "fapw": "decoy building (D27): OpenRA fakes only fool an enemy that cannot see the player; with per-faction visibility they would need a full disguise system, so they are excluded",
    "fixf": "decoy building (D27): OpenRA fakes only fool an enemy that cannot see the player; with per-faction visibility they would need a full disguise system, so they are excluded",
    "fpwr": "decoy building (D27): OpenRA fakes only fool an enemy that cannot see the player; with per-faction visibility they would need a full disguise system, so they are excluded",
    "mslf": "decoy building (D27): OpenRA fakes only fool an enemy that cannot see the player; with per-faction visibility they would need a full disguise system, so they are excluded",
    "pdof": "decoy building (D27): OpenRA fakes only fool an enemy that cannot see the player; with per-faction visibility they would need a full disguise system, so they are excluded",
    "syrf": "decoy building (D27): OpenRA fakes only fool an enemy that cannot see the player; with per-faction visibility they would need a full disguise system, so they are excluded",
    "tenf": "decoy building (D27): OpenRA fakes only fool an enemy that cannot see the player; with per-faction visibility they would need a full disguise system, so they are excluded",
    "weaf": "decoy building (D27): OpenRA fakes only fool an enemy that cannot see the player; with per-faction visibility they would need a full disguise system, so they are excluded",
}
# actor -> (kind, label, template, size class); templates come from calibrate.TEMPLATES
BUILDING_TEMPLATE = {"building": {"plank": 0.35, "granite": 0.3, "iron": 0.25, "coal": 0.1}, "defense": {"plank": 0.3, "granite": 0.3, "iron": 0.3, "coal": 0.1},
                     "tech": {"plank": 0.25, "granite": 0.2, "iron": 0.35, "gold": 0.2}, "wall": {"granite": 0.8, "plank": 0.2}, "fake": {"plank": 0.6, "granite": 0.4}}
NEW_BUILDINGS: dict[str, tuple[str, str, str]] = {  # actor: (label, template, role)
    "afld": ("Airfield", "building", "plane_yard"), "hpad": ("Helipad", "building", "heli_yard"), "dome": ("Radar dome", "tech", "radar"), "fix": ("Service depot", "building", "depot"),
    "atek": ("Allied tech center", "tech", "tech"), "stek": ("Soviet tech center", "tech", "tech"), "kenn": ("Kennel", "building", "kennel"), "agun": ("AA gun", "defense", "defense"),
    "sam": ("SAM site", "defense", "defense"), "pbox": ("Pillbox", "defense", "defense"), "hbox": ("Camo pillbox", "defense", "defense"), "gap": ("Gap generator", "tech", "gap"),
    "brik": ("Concrete wall", "wall", "wall"), "sbag": ("Sandbags", "wall", "wall"), "fenc": ("Barbed wire", "wall", "wall"), "iron": ("Iron curtain", "tech", "power"),
    "pdox": ("Chronosphere", "tech", "power"), "mslo": ("Missile silo", "tech", "power"),
}
# actor -> (kind, label, producing building kind, template)
NEW_UNITS: dict[str, tuple[str, str, str, str]] = {
    "e6": ("engineer", "Engineer", "barracks", "infantry"), "medi": ("medic", "Medic", "barracks", "light_infantry"), "mech": ("mechanic", "Mechanic", "barracks", "special_infantry"),
    "spy": ("spy", "Spy", "barracks", "special_infantry"), "thf": ("thief", "Thief", "barracks", "special_infantry"),
    "dtrk": ("demo_truck", "Demolition truck", "vehicle_factory", "vehicle"), "ftrk": ("flak_truck", "Flak truck", "vehicle_factory", "vehicle"),
    "mgg": ("gap_vehicle", "Mobile gap generator", "vehicle_factory", "vehicle"), "mnly": ("minelayer", "Minelayer", "vehicle_factory", "vehicle"),
    "mrj": ("radar_jammer", "Mobile radar jammer", "vehicle_factory", "vehicle"), "qtnk": ("mad_tank", "MAD tank", "vehicle_factory", "vehicle"),
    "truk": ("supply_truck", "Supply truck", "vehicle_factory", "vehicle"), "lst": ("landing_ship", "Landing ship", "naval_yard", "ship"),
    "yak": ("yak", "Yak attack plane", "afld", "aircraft"), "mig": ("mig", "MiG attack plane", "afld", "aircraft"),
    "heli": ("longbow", "Longbow helicopter", "hpad", "aircraft"), "mh60": ("black_hawk", "Black Hawk", "hpad", "aircraft"), "tran": ("chinook", "Chinook transport", "hpad", "aircraft"),
}
EXCLUDED_UNIT = {"hind": "disabled in the RA rules (prerequisite ~disabled)", "ant": "mission-only creature", "zombie": "mission-only creature", "fireant": "mission-only creature",
                 "scoutant": "mission-only creature", "warriorant": "mission-only creature", "harv": "harvester: the credit economy is replaced by wares (roster rule 4.2)"}
PREREQ_KIND = {"barr": "barracks", "tent": "barracks", "weap": "vehicle_factory", "dome": "dome", "atek": "atek", "stek": "stek", "fix": "fix", "afld": "afld", "hpad": "hpad",
               "syrd": "naval_yard", "spen": "sub_pen", "kenn": "kenn", "gap": "gap", "iron": "iron", "pdox": "pdox", "mslo": "mslo"}
UNIT_PREREQ_OVERRIDE = {"e6": ["barracks"], "medi": ["barracks"], "mech": ["barracks", "fix"], "spy": ["barracks", "dome"], "thf": ["barracks", "dome"], "dtrk": ["vehicle_factory", "stek"],
                        "ftrk": ["vehicle_factory"], "mgg": ["vehicle_factory", "atek"], "mnly": ["vehicle_factory", "fix"], "mrj": ["vehicle_factory", "atek"], "qtnk": ["vehicle_factory", "fix", "stek"],
                        "truk": ["vehicle_factory"], "lst": ["naval_yard"], "yak": ["afld"], "mig": ["afld", "stek"], "heli": ["hpad", "atek"], "mh60": ["hpad"], "tran": ["hpad"]}
BUILDING_PREREQ = {"dome": ["vehicle_factory"], "fix": ["vehicle_factory"], "atek": ["vehicle_factory", "dome"], "stek": ["vehicle_factory", "dome"], "afld": ["dome"], "hpad": ["dome"],
                   "kenn": ["barracks"], "agun": ["dome"], "sam": ["dome"], "pbox": ["barracks"], "hbox": ["barracks"], "gap": ["atek"], "iron": ["stek"], "pdox": ["atek"], "mslo": ["stek"],
                   "brik": ["vehicle_factory"], "sbag": ["barracks"], "fenc": ["barracks"]}
HYBRID_ARMAMENTS = {"pbox": ["M1Carbine"], "hbox": ["M1Carbine"]}  # the garrison's rifle (OpenRA: Cargo with an initial rifleman)
SIZE_CLASS = {(1, 1): "small", (2, 1): "small", (1, 2): "small", (2, 2): "medium", (2, 3): "medium", (3, 2): "medium", (3, 3): "big", (3, 4): "big", (4, 3): "big"}


def building_cost(credits: int, template: str) -> dict[str, int]:
    value = credits / calibrate.CREDITS_PER_VALUE
    shares = BUILDING_TEMPLATE[template]
    return {w: max(1, round(share * value / calibrate.WARE_VALUE[w])) for w, share in shares.items()}


def footprint(dims: str) -> list[tuple[int, int]]:
    """Extra ground tiles relative to the door tile (bottom middle): an OpenRA Dimensions of w,h covers w x h cells."""
    w, h = (int(x) for x in dims.split(","))
    out = []
    for dy in range(-(h - 1), 1):
        for dx in range(-(w // 2), w - w // 2):
            if (dx, dy) != (0, 0):
                out.append((dx, dy))
    return out


def install(menu: dict, recipes: dict, sizes: dict, ground: dict, rules_actor) -> None:
    """Add the generated buildings and recipes to the construction tables (called once at the end of construction.py)."""
    for actor, (label, template, role) in NEW_BUILDINGS.items():
        a = rules_actor(f"openra.{actor}")
        if a is None:
            continue
        dims = (a.get("building") or {}).get("dimensions", "1,1")
        w, h = (int(x) for x in dims.split(","))
        kind = actor
        cost = building_cost(int(a["cost"]), template)
        menu[kind] = {"label": label, "definition": f"openra.{actor}", "game": "openra", "cost": cost, "cost_source": f"calibrated from {int(a['cost'])} OpenRA credits ({template} template)",
                      "role": role, "requires": list(BUILDING_PREREQ.get(actor, [])), "size": ""}
        sizes[kind] = SIZE_CLASS.get((w, h), "medium" if w * h <= 6 else "big")
        if w * h > 1:
            ground[kind] = footprint(dims)
    for actor, (kind, label, producer, template) in NEW_UNITS.items():
        a = rules_actor(f"openra.{actor}")
        if a is None:
            continue
        tpl = "special_infantry" if template == "aircraft" else template
        if template == "aircraft":
            r = calibrate.recipe(int(a["cost"]), "vehicle")
            r = {**r, "cost": {"plank": r["cost"].get("plank", 1) + 1, "iron": r["cost"].get("iron", 1) + 1, "coal": r["cost"].get("coal", 1)}}
        else:
            r = calibrate.recipe(int(a["cost"]), tpl if tpl in calibrate.TEMPLATES else "vehicle")
        recipes.setdefault(producer, {})[kind] = {"label": label, "definition": f"openra.{actor}", "cost": r["cost"], "ms": r["ms"],
                                                  "cost_source": f"calibrated from {int(a['cost'])} OpenRA credits ({template})", "requires": list(UNIT_PREREQ_OVERRIDE.get(actor, []))}
    # kennel: the dog comes out of the kennel as well as the barracks
    recipes.setdefault("kenn", {})["attack_dog"] = {"label": "Attack dog", "definition": "openra.dog", "cost": dict(recipes.get("barracks", {}).get("attack_dog", {}).get("cost", {"ration": 1})),
                                                    "ms": 20_000, "requires": []}


def card_only_units() -> set[str]:
    return {k for k, *_ in NEW_UNITS.values()}


def prerequisites_met(world: Any, faction: str, requires: list[str]) -> str | None:
    """None, or the first missing prerequisite building kind (a standing, finished, healthy building of the faction)."""
    if not requires:
        return None
    for kind in requires:
        if not any(b["faction_name"] == faction and b["kind"] == kind and b.get("operational") and not b.get("constructing") and int(b.get("hp", 1)) > 0
                   for b in world.buildings.values()):
            return kind
    return None

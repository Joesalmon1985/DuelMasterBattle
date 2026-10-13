"""Every Mindustry unit as an actor/weapon pair in the shared combat rules (owner programme 13 Oct 2026).

`mindustry_full.json` (statement-level import of UnitTypes.java) gives health, armor, speed, hit size, weapons with their bullets and the
entity class (mech, legs, air, naval, tank, hover, crawl). This module scales them to the shared rules (hp x50, damage x25, range 0.4 cell per
tile, speed 115 per px/tick) with Mindustry's own flat armor. The three hand-tuned units of mindustry_overrides.json (dagger, crawler, nova)
keep their entries. Tier is derived from the reconstructor upgrade chains (T1 = factory unit, T2.. = successive reconstructors).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from wizard_rts.industry import blocks as B

HP_SCALE = 50
DMG_SCALE = 25
CELLS_PER_WORLD = 0.4 / 8.0
SPEED_SCALE = 115.0
MS_PER_TICK = 1000.0 / 60.0
INTERNAL = {"block", "anthicus-missile", "disrupt-missile", "quell-missile", "assembly-drone", "manifold", "latum", "renale"}  # drones, missiles and two types no block of v146 produces
CORE_UNITS = {"alpha", "beta", "gamma", "evoke", "incite", "emanate"}  # spawned by cores for the player; not producible
LOCO = {"mech": "foot", "legs": "legs", "crawl": "foot", "tank": "tracked", "naval": "naval", "air": "fly", "hover": "hover", "tether": "fly"}
SUPPORT = {"mono", "poly", "mega", "quad", "oct", "nova", "pulsar", "quasar", "retusa", "oxynoe", "cyerce", "aegires", "navanax", "evoke", "incite", "emanate"}


def _n(v: Any, default: float = 0.0) -> float:
    """A number from the importer, or `default` when the source wrote an expression we could not evaluate."""
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else default


def label_of(name: str) -> str:
    return name.replace("-", " ").capitalize()


@lru_cache(maxsize=1)
def chains() -> dict[str, int]:
    """unit -> tier (1..5) from the factory plans and the reconstructor upgrade pairs."""
    tier: dict[str, int] = {}
    blocks = B.full()["blocks"]
    for b in blocks.values():
        for p in b.get("plans") or []:
            tier[p["unit"]] = 1
    for b in blocks.values():
        for k, p in enumerate(b.get("assembler_plans") or []):  # Erekir assemblers make the fourth and fifth tier of each line
            tier[p["unit"]] = 4 + k
    for _ in range(6):
        for b in blocks.values():
            for pair in b.get("upgrades") or []:
                a, c = pair[0], pair[1] if len(pair) > 1 else None
                if c and a in tier and c not in tier:
                    tier[c] = tier[a] + 1
    return tier


def upgrade_of(unit: str) -> str | None:
    for b in B.full()["blocks"].values():
        for pair in b.get("upgrades") or []:
            if len(pair) > 1 and pair[0] == unit:
                return pair[1]
    return None


def armor_class(armor: float) -> str:
    return "None" if armor <= 0 else ("Light" if armor <= 3 else ("Heavy" if armor <= 10 else "Concrete"))


def unit_list() -> list[str]:
    u = B.full()["units"]
    return sorted(n for n in u if n not in INTERNAL)


def is_producible(name: str) -> bool:
    return name not in INTERNAL and name not in CORE_UNITS and name in chains()


def _weapon_range_units(u: dict) -> float:
    best = 0.0
    for w in u["weapons"]:
        bl = w.get("bullet") or {}
        if bl.get("speed") and bl.get("lifetime"):
            best = max(best, _n(bl["speed"]) * _n(bl["lifetime"]))
        elif bl.get("length"):
            best = max(best, _n(bl["length"]))
    return best


def unit_range_units(u: dict) -> float:
    return _n(u.get("range")) or _n(u.get("max_range")) or _weapon_range_units(u) or 60.0


def rules_for(name: str) -> tuple[dict, dict] | None:
    """(actor, {weapon name: weapon}) of one unit in the shared schema."""
    u = B.full()["units"].get(name)
    if u is None or name in INTERNAL:
        return None
    kind = u["constructor"]
    base = kind.split("+")[0]
    loco = LOCO.get(base, "foot")
    flying = base == "air"
    naval = base == "naval"
    hit = _n(u.get("hit_size"), 8.0) or 8.0
    armor = _n(u.get("armor"))
    rng_units = unit_range_units(u)
    weapons: dict[str, dict] = {}
    names: list[str] = []
    fields = u.get("fields", {})
    for i, w in enumerate(u["weapons"]):
        bl = w.get("bullet") or {}
        direct = _n(bl.get("damage"))
        splash = _n(bl.get("splashDamage"))
        radius = _n(bl.get("splashDamageRadius"))
        if direct <= 0 and splash <= 0:
            continue
        reload = _n(w.get("reload"), 30.0) or 30.0
        mirrored = 2 if w.get("mirror", True) and (w.get("x") or 0) != 0 else 1
        reload_ticks = reload / mirrored  # mirrored mounts fire alternately: twice the rate of one mount
        wr = rng_units
        if bl.get("speed") and bl.get("lifetime"):
            wr = min(rng_units, _n(bl["speed"]) * _n(bl["lifetime"])) if rng_units else _n(bl["speed"]) * _n(bl["lifetime"])
        coll_air = bl.get("collidesAir", True) is not False and w.get("targetAir", True) is not False and fields.get("targetAir", True) is not False
        coll_gnd = bl.get("collidesGround", True) is not False and fields.get("targetGround", True) is not False
        targets = (["Ground", "GroundActor", "Water", "WaterActor"] if coll_gnd else []) + (["AirborneActor"] if coll_air else [])
        if not targets:
            continue
        wname = f"MDY_{name}_{i}"
        weapons[wname] = {
            "range": max(1.2, round(wr * CELLS_PER_WORLD, 3)), "min_range": 0.0, "reload": max(1, round(reload_ticks * MS_PER_TICK / 40.0)),
            "burst": max(1, int(_n(w.get("shots"), 1.0) or 1)), "burst_delay": 2, "projectile": bl.get("class", ""),
            "projectile_speed": int(_n(bl.get("speed")) * 123) if bl.get("class") not in ("LaserBulletType", "LightningBulletType", "SapBulletType") else 0,
            "valid_targets": targets, "invalid_targets": [],
            "warheads": [{"type": "SpreadDamage", "damage": max(1, int(round((direct + splash) * DMG_SCALE))), "spread": round(radius * CELLS_PER_WORLD, 3), "versus": {},
                          "valid_targets": ["GroundActor", "WaterActor", "AirborneActor", "Structure"]}],
            "source": f"Mindustry v146 UnitTypes.{u['java_name']} weapon {w.get('name') or i}",
        }
        names.append(wname)
    if flying:
        ttypes = ["AirborneActor"]
    elif naval:
        ttypes = ["WaterActor", "Ship"]
    else:
        ttypes = ["GroundActor", "Infantry" if hit < 12 else "Vehicle"]
    speed = min(220, max(30, int(_n(u.get("speed"), 0.5) * SPEED_SCALE)))
    actor = {
        "name": label_of(name), "hp": int(round(_n(u.get("health"), 100.0) * HP_SCALE)), "armor": armor_class(armor), "flat_armor": int(round(armor * DMG_SCALE)),
        "speed": speed, "cost": 0, "queue": "", "prerequisites": "", "armaments": names, "target_types": ttypes, "mobile": True, "is_building": False,
        "locomotor": loco, "flying": flying, "naval": naval, "tier": chains().get(name, 0), "payload": "payload" in kind,
        "source": f"Mindustry v146 UnitTypes.{u['java_name']}: health {u.get('health')}, armor {armor}",
    }
    if flying:
        actor["targetable"] = {"Targetable@AIR": {"types": ["AirborneActor"], "requires": ""}}
    return actor, weapons


@lru_cache(maxsize=1)
def all_rules() -> tuple[dict[str, dict], dict[str, dict]]:
    actors: dict[str, dict] = {}
    weapons: dict[str, dict] = {}
    for n in unit_list():
        r = rules_for(n)
        if r:
            actors["mdy_" + n] = r[0]
            weapons.update(r[1])
    return actors, weapons

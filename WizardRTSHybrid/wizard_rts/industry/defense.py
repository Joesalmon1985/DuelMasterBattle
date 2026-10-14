"""Mindustry defence: turrets, walls, doors, menders, overdrive and force projectors, mines, point defence (owner programme 13 Oct 2026).

Turrets are ordinary `world.buildings` that fight through military.py: `turret_weapon` builds the OpenRA-schema weapon of the ammunition they
hold right now, `on_fire` takes the ammunition, liquid and charge a shot costs. Scales (data/mindustry_overrides.json `units`, shared with the
unit rules): hp x50, damage x25 (OpenRA's internal scale), range 0.4 cell per 8 world units, bullet speed 123 units/tick per px/tick.
Armor is Mindustry's own flat rule (damage - armor, at least a quarter), applied in military._apply_warheads through `flat_armor`.
"""

from __future__ import annotations

import math
from typing import Any

from wizard_rts.industry import registry as R

HP_SCALE = 50
DMG_SCALE = 25
CELLS_PER_WORLD = 0.4 / 8.0  # a Mindustry range of 8 world units (one tile) is 0.4 hybrid cells
MS_PER_TICK = 1000.0 / 60.0
AMMO_MAX = 30
GROUND_TARGETS = ["Ground", "GroundActor", "Water", "WaterActor"]
AIR_TARGETS = ["AirborneActor"]
WALL_HEALTH = {"copper": 80, "titanium": 110, "plastanium": 125, "thorium": 200, "phase": 150, "surge": 230, "scrap": 60, "beryllium": 130, "tungsten": 180,
               "carbide": 270, "reinforced-surge": 250, "shielded": 130}
_WEAPONS: dict[tuple, dict] = {}


def block_hp(spec: dict) -> int:
    """Hit points in the shared scale (Mindustry health x50). Blocks without an explicit health use scaledHealth x size^2 (Block.init)."""
    bid = spec["id"]
    health = spec.get("health")
    if spec["role"] in ("wall", "door") and not health:
        base = next((v for k, v in WALL_HEALTH.items() if bid.startswith(k + "-wall") or bid.startswith(k)), 80)
        health = base * 4 * (spec["size"] ** 2)
    if not health:
        health = float(spec["fields"].get("scaledHealth", 40)) * spec["size"] ** 2
    return int(health * HP_SCALE)


def armor_type(spec: dict) -> str:
    return "Concrete" if spec["role"] in ("wall", "door") else ("Heavy" if spec["role"] in ("turret", "core", "store") else "Wood")


# ------------------------------------------------------------------ weapons from bullets

def _cells(world_units: float) -> float:
    return round(world_units * CELLS_PER_WORLD, 3)


def bullet_damage(bullet: dict) -> tuple[int, int, float]:
    """(direct damage, splash damage, splash radius in cells) on the shared scale."""
    d = float(bullet.get("damage") or 0)
    sd = float(bullet.get("splashDamage") or 0)
    sr = float(bullet.get("splashDamageRadius") or 0)
    return int(round(d * DMG_SCALE)), int(round(sd * DMG_SCALE)), _cells(sr)


def make_weapon(name: str, bullet: dict, rng_units: float, reload_ticks: float, shots: int, targets: list[str], reload_mult: float = 1.0,
                min_range: float = 0.0, extra: float = 0.0) -> dict:
    direct, splash, radius = bullet_damage(bullet)
    dmg = max(direct, 0) + max(splash, 0) + int(extra)
    speed = float(bullet.get("speed") or 0)
    ticks = max(1.0, reload_ticks / max(0.05, reload_mult))
    cls = bullet.get("class", "")
    return {
        "range": max(1.5, _cells(rng_units)), "min_range": _cells(min_range), "reload": max(1, round(ticks * MS_PER_TICK / 40.0)), "burst": max(1, int(shots)),
        "burst_delay": 2, "projectile": cls, "projectile_speed": int(speed * 123) if speed and cls not in ("LaserBulletType", "LightningBulletType", "RailBulletType") else 0,
        "valid_targets": list(targets), "invalid_targets": [],
        "warheads": [{"type": "SpreadDamage", "damage": max(1, dmg), "spread": radius, "versus": {}, "valid_targets": ["GroundActor", "WaterActor", "AirborneActor", "Structure"]}],
        "source": f"Mindustry v146 {name}",
    }


def turret_targets(spec: dict) -> list[str]:
    f = spec["fields"]
    ta, tg = f.get("targetAir", True), f.get("targetGround", True)
    out: list[str] = []
    if tg is not False:
        out += GROUND_TARGETS
    if ta is not False:
        out += AIR_TARGETS
    return out


# ------------------------------------------------------------------ turrets: state

def init_turret(world: Any, b: dict, m: dict, spec: dict) -> None:
    m.update(ammo=[], target=None, charge=0, liq_used=0.0, kills=0, shots=0, od=1.0, timer=0)


def _bullets(spec: dict) -> dict[str, dict]:
    return spec.get("ammo") or {}


def ammo_wares(spec: dict) -> dict[str, dict]:
    """ware -> bullet for an item turret (the ammo table is keyed by item name)."""
    from wizard_rts.industry import blocks as B

    if spec["class"] != "ItemTurret":
        return {}
    return {B.ware_of_item(i): bl for i, bl in _bullets(spec).items()}


def total_ammo(m: dict) -> int:
    return sum(n for _w, n in m["ammo"])


def turret_accepts(world: Any, b: dict, ware: str) -> bool:
    spec = R.block(b["kind"])
    bl = ammo_wares(spec).get(ware)
    if bl is None:
        return False
    return total_ammo(b["mdy"]) + int(bl.get("ammoMultiplier", 2)) <= int(spec["fields"].get("maxAmmo", AMMO_MAX))


def turret_take(world: Any, b: dict, ware: str) -> bool:
    spec = R.block(b["kind"])
    bl = ammo_wares(spec).get(ware)
    if bl is None:
        return False
    m = b["mdy"]
    mult = int(bl.get("ammoMultiplier", 2))
    for entry in m["ammo"]:
        if entry[0] == ware:
            entry[1] += mult
            m["ammo"].remove(entry)
            m["ammo"].append(entry)  # the newest ammunition is fired first (ItemTurret.handleItem)
            return True
    m["ammo"].append([ware, mult])
    return True


def active_bullet(world: Any, b: dict) -> tuple[str, dict] | None:
    spec = R.block(b["kind"])
    m = b["mdy"]
    cls = spec["class"]
    if cls == "ItemTurret":
        if not m["ammo"]:
            return None
        ware = m["ammo"][-1][0]
        return ware, ammo_wares(spec)[ware]
    if cls in ("LiquidTurret", "ContinuousLiquidTurret"):
        from wizard_rts.industry import fluids as F

        for liquid, bl in _bullets(spec).items():
            if m["liq"].get(liquid, 0.0) >= 1.0 / max(1, int(spec["fields"].get("ammoPerShot", 1))) * 0.2:
                return liquid, bl
        return None
    st = spec.get("shoot_type")
    if st:
        return "power", st
    if cls == "TractorBeamTurret":
        return "power", {"class": "LaserBulletType", "damage": 0.3}
    return None


def turret_weapon(world: Any, b: dict) -> dict | None:
    """The weapon this turret can fire now, or None (no ammunition, no power, closed, unbuilt)."""
    m = b.get("mdy")
    if m is None or b.get("constructing") or int(b.get("hp", 1)) <= 0 or b.get("disrupted") or b.get("unpowered"):
        return None
    spec = R.block(b["kind"])
    cls = spec["class"]
    if cls == "PowerTurret" and m.get("sat", 1.0) <= 0.01:
        return None
    pick = active_bullet(world, b)
    if pick is None:
        return None
    key, bl = pick
    ck = (b["kind"], key)
    w = _WEAPONS.get(ck)
    if w is None:
        f = spec["fields"]
        shots = 1
        raw = spec.get("fields", {})
        reload = float(f.get("reload", 60))
        rng = float(f.get("range", 110)) + float(bl.get("rangeChange", 0) or 0)
        if cls in ("ContinuousTurret", "ContinuousLiquidTurret", "LaserTurret"):
            dps_hits = max(1.0, 30.0 / float(bl.get("damageInterval", 5) or 5))
            bl = dict(bl)
            bl["damage"] = float(bl.get("damage") or 0) * dps_hits
            reload = 30.0
        if cls == "LiquidTurret" or cls == "ContinuousLiquidTurret":
            bl = dict(bl)
            bl["damage"] = max(float(bl.get("damage") or 0), 0.3)
        if cls == "TractorBeamTurret":
            bl = {"class": "LaserBulletType", "damage": float(f.get("damage", 0.3)) * 20}
            reload = 20.0
        if cls == "PointDefenseTurret":
            bl = {"class": "BulletType", "damage": 0.0}
        shots = int(f.get("shots", 1))
        if spec["id"] in ("salvo", "swarmer", "ripple", "cyclone", "spectre", "fuse", "disperse", "diffuse", "scatter", "hail", "duo"):
            shots = {"salvo": 4, "swarmer": 4, "ripple": 4, "cyclone": 1, "spectre": 1, "fuse": 3, "disperse": 4, "diffuse": 3, "scatter": 1, "hail": 1, "duo": 1}[spec["id"]]
        w = make_weapon(spec["id"], bl, rng, reload, shots, turret_targets(spec), float(bl.get("reloadMultiplier", 1.0) or 1.0),
                        min_range=float(f.get("minRange", 0) or 0))
        if cls in ("ItemTurret",) and spec["id"] in ("hail", "ripple", "scathe", "foreshadow"):
            w["valid_targets"] = list(GROUND_TARGETS)
        _WEAPONS[ck] = w
    return w


def reload_ms(world: Any, b: dict, w: dict) -> int:
    """Reload scaled by power satisfaction, overdrive and coolant (Turret.baseReloadSpeed / coolant)."""
    from wizard_rts import rules

    m = b["mdy"]
    spec = R.block(b["kind"])
    speed = 1.0
    if spec["power_use_per_s"] > 0 and spec["class"] in ("PowerTurret", "LaserTurret"):
        speed *= max(0.05, m.get("sat", 1.0))
    speed *= float(m.get("od", 1.0))
    if spec.get("coolant"):
        for liquid, cap in (("cryofluid", 0.9), ("water", 0.4)):
            if m["liq"].get(liquid, 0.0) >= spec["coolant"] * 6:
                speed *= 1.0 + cap * 5.0 * float(spec["coolant"])
                m["cooling"] = liquid
                break
        else:
            m["cooling"] = ""
    return max(100, int(rules.reload_ms(w) / speed))


def on_fire(world: Any, b: dict, w: dict) -> None:
    """A shot: consume ammunition (one round per shot, `ammoPerShot`), liquid for liquid turrets, count it."""
    m = b["mdy"]
    spec = R.block(b["kind"])
    cls = spec["class"]
    m["shots"] += 1
    if cls == "ItemTurret" and m["ammo"]:
        per = int(spec["fields"].get("ammoPerShot", 1))
        m["ammo"][-1][1] -= per
        if m["ammo"][-1][1] <= 0:
            ware = m["ammo"][-1][0]
            m["ammo"].pop()
            world.stats["consumed_" + ware] = world.stats.get("consumed_" + ware, 0) + 1
    elif cls in ("LiquidTurret", "ContinuousLiquidTurret"):
        from wizard_rts.industry import fluids as F

        pick = active_bullet(world, b)
        if pick:
            F.consume(world, b, pick[0], 0.5)
    m["target"] = True


# ------------------------------------------------------------------ explosions

def explode(world: Any, b: dict, radius: float, damage: int) -> None:
    """A destroyed reactor or an overloaded block: damage everything around it, itself first."""
    from wizard_rts import military

    cx, cy = b["tx"], b["ty"]
    world.damage_building(b["id"], 10**9, ["structure"], {}, by="explosion")
    for o in list(world.buildings.values()):
        if o["id"] != b["id"] and "hp" in o and int(o["hp"]) > 0 and math.hypot(o["tx"] - cx, o["ty"] - cy) <= radius:
            world.damage_building(o["id"], damage * HP_SCALE // 5, ["structure"], {}, by="explosion")
    for u in list(world.units.values()):
        if u.get("alive", True) and math.hypot(u["tx"] - cx, u["ty"] - cy) <= radius:
            u["hp"] = max(0, int(u["hp"]) - damage * DMG_SCALE)
            if u["hp"] <= 0:
                military.kill_unit(world, u, "explosion")
    world.effects.append({"t": "explosion", "x1": cx, "y1": cy, "x2": cx, "y2": cy, "ttl_ms": 1200, "keep": 3, "p": ""})


# ------------------------------------------------------------------ support blocks

def init_support(world: Any, b: dict, m: dict, spec: dict) -> None:
    m.update(timer=0, shield=0.0, broken=0, od=1.0, target=None, sat=1.0)
    if spec["role"] == "shield":
        m["shield"] = shield_health(spec)
    if spec["role"] == "logic":
        from wizard_rts.industry import logic

        logic.init_logic(world, b, m, spec)


def shield_health(spec: dict) -> float:
    return float(spec["fields"].get("shieldHealth", spec["fields"].get("shieldHealth", 750))) * DMG_SCALE


def support_accepts(world: Any, b: dict, ware: str) -> bool:
    spec = R.block(b["kind"])
    if spec["role"] == "logic":
        return False
    return ware in spec["consume_items"] or ware in spec["boost_items"] or (spec["role"] == "mender" and ware == "mdy.silicon") or (
        spec["role"] in ("overdrive", "shield") and ware == "mdy.phase_fabric")


def support_take(world: Any, b: dict, ware: str) -> bool:
    m = b["mdy"]
    spec = R.block(b["kind"])
    cap = 10
    if m["buf"].get(ware, 0) >= cap:
        return False
    m["buf"][ware] = m["buf"].get(ware, 0) + 1
    return True


def _in_range(b: dict, o: dict, r_cells: float) -> bool:
    return math.hypot(b["tx"] - o["tx"], b["ty"] - o["ty"]) <= r_cells


def _friendly_buildings(world: Any, b: dict) -> list[dict]:
    return [o for o in world.buildings.values() if o["faction"] == b["faction"] and "hp" in o and int(o["hp"]) > 0 and not o.get("constructing")]


def step(world: Any, st: Any, machines: list[dict], sat: dict[str, float]) -> None:
    from wizard_rts import military

    ods = [b for b in machines if b["mdy"]["role"] == "overdrive"]
    for b in machines:
        m = b["mdy"]
        role = m["role"]
        spec = R.block(b["kind"])
        s = sat.get(b["id"], 1.0)
        m["sat"] = s
        if b.get("disrupted"):
            continue
        if role == "turret":
            _turret_step(world, st, b, m, spec, s)
        elif role == "mender":
            _mender_step(world, b, m, spec, s)
        elif role == "overdrive":
            m["state"] = "boosting" if s > 0 or spec["power_use_per_s"] <= 0 else "no power"
        elif role == "shield":
            _shield_step(world, b, m, spec, s)
        elif role == "repair":
            _repair_step(world, b, m, spec, s)
        elif role == "mine":
            _mine_step(world, b, m, spec)
        elif role == "build_turret":
            _build_turret_step(world, b, m, spec, s)
        elif role == "incinerator":
            m["state"] = "burning" if s > 0 or spec["power_use_per_s"] <= 0 else "no power"
        elif role == "radar":
            _radar_step(world, b, m, spec, s)
        elif role == "door":
            _door_step(world, b, m)
        elif role == "logic":
            from wizard_rts.industry import logic

            logic.step(world, st, b, m, spec, s)
    # overdrive: every machine in range of a powered projector runs faster (the best boost wins, OverdriveProjector.applyBoost)
    for b in machines:
        b["mdy"]["od"] = 1.0
    for p in ods:
        if p["mdy"]["state"] != "boosting":
            continue
        spec = R.block(p["kind"])
        boost = float(spec["fields"].get("speedBoost", 1.5))
        if p["mdy"]["buf"].get("mdy.phase_fabric", 0) > 0:
            boost += float(spec["fields"].get("speedBoostPhase", 0.75))
        rng = float(spec["fields"].get("range", 80)) * 0.4 / 8.0 * 2.5
        for o in machines:
            if o["faction"] == p["faction"] and o["id"] != p["id"] and _in_range(p, o, rng):
                o["mdy"]["od"] = max(o["mdy"]["od"], boost)


def _door_step(world: Any, b: dict, m: dict) -> None:
    """Doors (Mindustry Door/AutoDoor): closed they block every unit like a wall; a unit of the door's own faction beside or on it opens it, and it closes again
    when nobody of that faction is near and nothing stands in the gap. `m['forced']` (set by logic `control enabled`) holds it open or shut."""
    from wizard_rts.industry import sim as S

    fp = [tuple(t) for t in S.footprint(b)]
    near = any(u.get("alive", True) and u["faction_name"] == b["faction_name"] and not u.get("inside") and u.get("loco") != "fly"
               and any(max(abs(u["tx"] - x), abs(u["ty"] - y)) <= 1 for x, y in fp) for u in world.units.values())
    standing = any(u.get("alive", True) and not u.get("inside") and u.get("loco") != "fly" and (u["tx"], u["ty"]) in fp for u in world.units.values())
    forced = m.get("forced")
    want_open = near or standing if forced is None else bool(forced)
    if want_open:
        for t in fp:
            world.blocked.discard(t)
        m["open"], m["state"] = True, "open"
    elif not standing:
        world.blocked.update(fp)
        m["open"], m["state"] = False, "closed"


def _turret_step(world: Any, st: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    cls = spec["class"]
    m["state"] = "ready" if turret_weapon(world, b) is not None else ("no power" if spec["power_use_per_s"] > 0 and s <= 0.01 else "no ammo")
    if cls == "PointDefenseTurret":
        _point_defense(world, b, m, spec, s)
    elif cls == "ShockwaveTower":
        _shockwave(world, b, m, spec, s)
    elif cls == "TractorBeamTurret":
        pass


def _point_defense(world: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    """PointDefenseTurret: shoots down an enemy bullet in range every `reload` ticks (the bullet is removed before it lands)."""
    if spec["power_use_per_s"] > 0 and s <= 0:
        return
    m["timer"] += 6 * s * m.get("od", 1.0)
    if m["timer"] < float(spec["fields"].get("reload", 8)):
        return
    rng = float(spec["fields"].get("range", 180)) * CELLS_PER_WORLD
    for p in list(world.projectiles):
        sh = world.units.get(p["shooter"]) or world.buildings.get(p["shooter"])
        if sh is None or sh["faction"] == b["faction"]:
            continue
        tp = p["target"]
        te = world.units.get(tp["id"]) if tp["kind"] == "unit" else world.buildings.get(tp["id"])
        if te is None or te["faction"] != b["faction"] or math.hypot(te["tx"] - b["tx"], te["ty"] - b["ty"]) > rng:
            continue
        world.projectiles.remove(p)
        m["timer"] = 0
        m["shots"] = m.get("shots", 0) + 1
        world.stats["bullets_downed"] = world.stats.get("bullets_downed", 0) + 1
        world.effects.append({"t": "shot", "x1": b["tx"], "y1": b["ty"], "x2": te["tx"], "y2": te["ty"], "ttl_ms": 300, "keep": 2, "p": "point_defense"})
        break


def _shockwave(world: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    from wizard_rts import military

    if spec["power_use_per_s"] > 0 and s <= 0:
        return
    m["timer"] += 6 * s
    if m["timer"] < float(spec["fields"].get("reload", 80)):
        return
    rng = float(spec["fields"].get("range", 170)) * CELLS_PER_WORLD
    hit = False
    for u in list(world.units.values()):
        if u.get("alive", True) and u["faction"] != b["faction"] and math.hypot(u["tx"] - b["tx"], u["ty"] - b["ty"]) <= rng:
            u["hp"] = max(0, int(u["hp"]) - int(float(spec["fields"].get("damage", 50)) * DMG_SCALE))
            hit = True
            if u["hp"] <= 0:
                military.kill_unit(world, u, b["id"])
    kept = []
    for p in world.projectiles:
        sh = world.units.get(p["shooter"]) or world.buildings.get(p["shooter"])
        if sh is not None and sh["faction"] != b["faction"] and math.hypot(sh["tx"] - b["tx"], sh["ty"] - b["ty"]) <= rng * 1.5:
            hit = True
            continue
        kept.append(p)
    world.projectiles[:] = kept
    if hit:
        m["timer"] = 0
        world.effects.append({"t": "explosion", "x1": b["tx"], "y1": b["ty"], "x2": b["tx"], "y2": b["ty"], "ttl_ms": 500, "keep": 2, "p": "shockwave"})


def _mender_step(world: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    """MendProjector / RegenProjector: every `reload` ticks heal buildings in range by healPercent of their maximum."""
    f = spec["fields"]
    if spec["power_use_per_s"] > 0 and s <= 0:
        m["state"] = "no power"
        return
    reload = float(f.get("reload", 200))
    boost = 1.0
    phase = False
    if spec["boost_items"] and any(m["buf"].get(w, 0) > 0 for w in spec["boost_items"]):
        phase = True
    if spec["consume_items"] and not all(m["buf"].get(w, 0) >= 1 for w in spec["consume_items"]) and spec["id"] != "mender":
        m["state"] = "needs items"
        return
    m["timer"] += 6 * s * m.get("od", 1.0)
    cont = spec["class"] == "RegenProjector"
    if cont:
        reload = 6.0
    if m["timer"] < reload:
        m["state"] = "idle"
        return
    m["timer"] = 0
    pct = float(f.get("healPercent", 12)) + (float(f.get("phaseBoost", 0)) if phase else 0.0)
    rng = (float(f.get("range", 60)) + (float(f.get("phaseRangeBoost", 0)) if phase else 0.0)) * CELLS_PER_WORLD * 2.0
    healed = False
    for o in _friendly_buildings(world, b):
        if o["id"] != b["id"] or True:
            if int(o["hp"]) < int(o["max_hp"]) and _in_range(b, o, max(rng, 2.0)):
                o["hp"] = min(int(o["max_hp"]), int(o["hp"]) + int(int(o["max_hp"]) * pct / 100.0))
                healed = True
    m["state"] = "mending" if healed else "idle"
    if healed and phase and spec["id"] == "mender":
        pass
    if healed and spec["consume_items"]:
        for w in spec["consume_items"]:
            if m["buf"].get(w, 0) > 0:
                m["buf"][w] -= 1
                world.stats["consumed_" + w] = world.stats.get("consumed_" + w, 0) + 1
                break
    if healed and phase:
        for w in spec["boost_items"]:
            if m["buf"].get(w, 0) > 0:
                m["buf"][w] -= 1
                world.stats["consumed_" + w] = world.stats.get("consumed_" + w, 0) + 1
                break


def _repair_step(world: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    """RepairTurret / RepairTower: heal friendly units in range."""
    f = spec["fields"]
    if spec["power_use_per_s"] > 0 and s <= 0:
        m["state"] = "no power"
        return
    m["timer"] += 6 * s
    if m["timer"] < 30:
        return
    m["timer"] = 0
    rng = float(f.get("range", 80)) * CELLS_PER_WORLD * 2.0
    rate = float(f.get("repairSpeed", 0.3)) * 30 / 60.0
    done = False
    for u in world.units.values():
        if u.get("alive", True) and u["faction"] == b["faction"] and int(u["hp"]) < int(u["max_hp"]) and math.hypot(u["tx"] - b["tx"], u["ty"] - b["ty"]) <= max(rng, 3.0):
            u["hp"] = min(int(u["max_hp"]), int(u["hp"]) + max(1, int(int(u["max_hp"]) * 0.04 * (rate * 20 + 1))))
            done = True
    m["state"] = "repairing" if done else "idle"


def _mine_step(world: Any, b: dict, m: dict, spec: dict) -> None:
    from wizard_rts import military

    m["timer"] = max(0, m.get("timer", 0) - 6)
    if m["timer"] > 0:
        return
    for u in list(world.units.values()):
        if u.get("alive", True) and u["faction"] != b["faction"] and (u["tx"], u["ty"]) == (b["tx"], b["ty"]) and u.get("loco") != "fly":
            u["hp"] = max(0, int(u["hp"]) - int(float(spec["fields"].get("damage", 13)) * float(spec["fields"].get("tendrils", 6)) * DMG_SCALE))
            m["timer"] = float(spec["fields"].get("cooldown", 80))
            world.effects.append({"t": "explosion", "x1": b["tx"], "y1": b["ty"], "x2": b["tx"], "y2": b["ty"], "ttl_ms": 400, "keep": 2, "p": "mine"})
            if u["hp"] <= 0:
                military.kill_unit(world, u, b["id"])
            break


def _build_turret_step(world: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    """BuildTurret: construction sites of the same faction in range progress faster while it has power and nitrogen."""
    if spec["power_use_per_s"] > 0 and s <= 0:
        m["state"] = "no power"
        return
    rng = float(spec["fields"].get("range", 200)) * CELLS_PER_WORLD * 2.0
    n = 0
    for o in world.buildings.values():
        if o["faction"] == b["faction"] and o.get("constructing") and _in_range(b, o, rng):
            o["constructing"]["progress_ms"] += int(100 * float(spec["fields"].get("buildSpeed", 1.5)) * s)
            n += 1
    m["state"] = "building" if n else "idle"


def _radar_step(world: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    if spec["power_use_per_s"] > 0 and s <= 0:
        m["state"] = "no power"
        return
    m["state"] = "scanning"
    seen = world.__dict__.setdefault("explored", {}).setdefault(b["faction_name"], set())
    r = int(float(spec["fields"].get("fogRadius", 20)))
    if world.economy_quanta % 50 == 0:
        for dy in range(-r, r + 1, 2):
            for dx in range(-r, r + 1, 2):
                if dx * dx + dy * dy <= r * r:
                    seen.add((b["tx"] + dx, b["ty"] + dy))


def _shield_step(world: Any, b: dict, m: dict, spec: dict, s: float) -> None:
    """ForceProjector: a bubble that absorbs hostile bullets heading for blocks inside it, breaks at zero and recovers after a cooldown."""
    f = spec["fields"]
    full = shield_health(spec)
    if spec["power_use_per_s"] > 0 and s <= 0:
        m["state"] = "no power"
        return
    if m["broken"] > 0:
        m["broken"] -= 6
        if m["broken"] <= 0:
            m["shield"] = full * 0.3
        m["state"] = "broken"
        return
    m["shield"] = min(full, m["shield"] + float(f.get("cooldownNormal", 1.75)) * 6 * DMG_SCALE * 0.1)
    radius = float(f.get("radius", 101.7)) * CELLS_PER_WORLD * 2.0
    m["state"] = "shielding"
    for p in list(world.projectiles):
        sh = world.units.get(p["shooter"]) or world.buildings.get(p["shooter"])
        if sh is None or sh["faction"] == b["faction"]:
            continue
        tp = p["target"]
        te = world.units.get(tp["id"]) if tp["kind"] == "unit" else world.buildings.get(tp["id"])
        if te is None or te["faction"] != b["faction"] or math.hypot(te["tx"] - b["tx"], te["ty"] - b["ty"]) > radius:
            continue
        dmg = sum(int(w["damage"]) for w in p["warheads"])
        world.projectiles.remove(p)
        m["shield"] -= dmg
        world.stats["shield_absorbed"] = world.stats.get("shield_absorbed", 0) + dmg
        if m["shield"] <= 0:
            m["broken"] = float(f.get("cooldownBrokenBase", 0.35)) * 60 * 60 / 6 * 6
            m["shield"] = 0.0
            m["state"] = "broken"
            break

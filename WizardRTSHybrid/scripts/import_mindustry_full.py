#!/usr/bin/env python3
"""Pinned Mindustry source -> data/mindustry_full.json (statement-level importer, plan v2 P9/P11).

The first importer (import_mindustry_defs.py) used regexes and lost everything written as an expression (`pumpAmount = 7f / 60f`),
every ammo table, every drill/crafter liquid, every reconstructor upgrade. This one splits each `{{ ... }}` initialiser into
statements, evaluates the numeric expressions, and keeps the calls (`consumeLiquid(..)`, `ammo(..)`, `plans = ..`) in a structured form.

Output (original numbers; ticks are 1/60 s; the hybrid adaptation stays in mindustry_overrides.json / industry/blocks.py):
  blocks[name] = {class, category, size, requirements, fields{all evaluated scalars}, consume{items,liquids,power,power_buffered,coolant,flammable},
                  output{items,liquid,heat}, ammo{item|liquid: bullet}, shoot_type, plans[], upgrades[], results{}, ...}
  units[name]  = {class, constructor, speed, health, armor, flying, weapons[{name,reload,x,y,mirror,bullet{...}}], abilities[], ...}
Usage: python3 scripts/import_mindustry_full.py [--check]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "external" / "mindustry" / "core" / "src" / "mindustry" / "content"
OUT = ROOT / "wizard_rts" / "data" / "mindustry_full.json"
TICKS = 60.0
CONST = {"tilesize": 8.0, "size": None, "Mathf.PI": 3.14159265, "Mathf.pi": 3.14159265, "Mathf.sqrt2": 1.41421356}


def kebab(name: str) -> str:
    return re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), name)


def split_top(text: str, sep: str = ",") -> list[str]:
    """Split on `sep` outside (), {}, [] and string literals."""
    out, depth, cur, i, q = [], 0, [], 0, ""
    while i < len(text):
        c = text[i]
        if q:
            cur.append(c)
            if c == "\\":
                cur.append(text[i + 1])
                i += 1
            elif c == q:
                q = ""
        elif c in "\"'":
            q = c
            cur.append(c)
        elif c in "({[":
            depth += 1
            cur.append(c)
        elif c in ")}]":
            depth -= 1
            cur.append(c)
        elif c == sep and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    tail = "".join(cur)
    if tail.strip():
        out.append(tail)
    return out


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", "", text)


def matching(text: str, i: int) -> int:
    """Index of the bracket closing the one at text[i]."""
    pairs = {"(": ")", "{": "}", "[": "]"}
    stack, q, j = [], "", i
    while j < len(text):
        c = text[j]
        if q:
            if c == "\\":
                j += 1
            elif c == q:
                q = ""
        elif c in "\"'":
            q = c
        elif c in pairs:
            stack.append(pairs[c])
        elif stack and c == stack[-1]:
            stack.pop()
            if not stack:
                return j
        j += 1
    raise ValueError("unbalanced")


def num(expr: str, env: dict | None = None):
    """Evaluate a Java numeric expression (`7f / 60f`, `60f * 3`, `size * tilesize`); None when it is not purely numeric."""
    s = expr.strip()
    s = re.sub(r"\(\s*(?:float|int|long)\s*\)", "", s)
    s = re.sub(r"(?<![\w.])(\d+(?:\.\d+)?)[fFdDlL]\b", r"\1", s)
    s = re.sub(r"\bMathf\.(PI|pi)\b", "3.14159265", s)
    for k, v in {**CONST, **(env or {})}.items():
        if v is not None and re.search(r"\b" + re.escape(k) + r"\b", s):
            s = re.sub(r"(?<![\w.])" + re.escape(k) + r"\b", repr(float(v)), s)
    if not re.fullmatch(r"[\d\s.+\-*/()eE]+", s):
        return None
    try:
        v = eval(s, {"__builtins__": {}}, {})
    except Exception:
        return None
    return int(v) if isinstance(v, float) and v == int(v) and abs(v) < 1e9 and "." not in expr and "f" not in expr.lower() else v


def value(expr: str, env: dict):
    e = expr.strip()
    if e in ("true", "false"):
        return e == "true"
    v = num(e, env)
    if v is not None:
        return v
    m = re.fullmatch(r"(?:Items|Liquids|UnitTypes|Blocks|Category|StatusEffects)\.(\w+)", e)
    if m:
        return {"ref": kebab(m.group(1)) if e.startswith(("Items", "Liquids")) else m.group(1)}
    if re.fullmatch(r'"[^"]*"', e):
        return e[1:-1]
    return {"expr": e[:200]}


def statements(body: str) -> list[str]:
    return [s.strip() for s in split_top(strip_comments(body), ";") if s.strip()]


def parse_body(body: str) -> tuple[dict, dict[str, list[str]]]:
    """(scalar fields, calls name -> [raw args...]) of an initialiser body."""
    fields: dict = {}
    calls: dict[str, list[str]] = {}
    for st in statements(body):
        m = re.match(r"^(?:final\s+\w+\s+)?([A-Za-z_]\w*)\s*(?:\+|-)?=\s*(.+)$", st, re.S)
        if m and not st.startswith(("for", "if")):
            fields[m.group(1)] = value(m.group(2), {**{k: v for k, v in fields.items() if isinstance(v, (int, float))}})
            fields.setdefault("_raw", {})[m.group(1)] = m.group(2).strip()[:60000]
            continue
        c = re.match(r"^([A-Za-z_]\w*)\s*\(", st)
        if c:
            j = matching(st, st.index("("))
            tail = st[j + 1:]
            key = c.group(1) + ("#boost" if ".boost()" in tail else "#optional" if ".optional(" in tail else "")
            calls.setdefault(key, []).append(st[st.index("(") + 1:j])
    return fields, calls


def stacks(expr: str, kind: str = "Items") -> dict:
    """with(Items.copper, 12, ...) or LiquidStack.with(Liquids.water, 0.1f)."""
    out = {}
    for m in re.finditer(kind + r"\.(\w+)\s*,\s*([^,)]+)", expr):
        v = num(m.group(2))
        out[kebab(m.group(1))] = v if v is not None else m.group(2).strip()
    return out


def bullet(text: str, env: dict) -> dict:
    """`new BasicBulletType(2.5f, 9){{ width = 7f; ... }}` -> flat dict of the numbers that matter in combat."""
    m = re.match(r"\s*new\s+(\w+)\s*(\()?", text)
    if not m:
        return {"expr": text[:120]}
    d: dict = {"class": m.group(1)}
    if m.group(2):
        j = matching(text, text.index("(", m.start()))
        args = [num(a) for a in split_top(text[text.index("(", m.start()) + 1:j])]
        names = {"BasicBulletType": ("speed", "damage"), "ArtilleryBulletType": ("speed", "damage"), "MissileBulletType": ("speed", "damage"),
                 "LaserBoltBulletType": ("speed", "damage"), "LiquidBulletType": ("liquid",), "ContinuousLaserBulletType": ("damage",),
                 "LaserBulletType": ("damage",), "LightningBulletType": (), "SapBulletType": (), "RailBulletType": (), "PointBulletType": (),
                 "ShrapnelBulletType": (), "FlakBulletType": ("speed", "damage"), "BulletType": ("speed", "damage"), "EmpBulletType": (),
                 "ContinuousFlameBulletType": ("damage",), "PointDefenseBulletType": ()}.get(d["class"], ("speed", "damage"))
        for n, a in zip(names, args):
            if a is not None:
                d[n] = a
    if "{{" in text:
        i = text.index("{{")
        j = matching(text, i + 1) if False else matching(text, i)
        f, calls = parse_body(text[i + 2:j - 1] if text[j - 1] == "}" else text[i + 2:j])
        f.pop("_raw", None)
        for k in ("damage", "speed", "lifetime", "splashDamage", "splashDamageRadius", "ammoMultiplier", "reloadMultiplier", "pierce", "pierceCap",
                  "homingPower", "homingRange", "knockback", "width", "height", "length", "buildingDamageMultiplier", "collidesAir", "collidesGround",
                  "collides", "collidesTiles", "hittable", "absorbable", "pierceBuilding", "lightning", "lightningDamage", "lightningLength", "healPercent",
                  "healAmount", "fragBullets", "status", "statusDuration", "rangeChange", "minRange", "maxRange", "scaleLife", "targetMissiles",
                  "drag", "gravity", "recoil", "trailLength", "incendChance", "makeFire", "healPercent", "sapStrength", "sprite"):
            if k in f and not isinstance(f[k], dict):
                d[k] = f[k]
            elif k in f and isinstance(f[k], dict) and "ref" in f[k]:
                d[k] = f[k]["ref"]
        if "status" in f and isinstance(f["status"], dict):
            d["status"] = f["status"].get("ref", "")
        if "damage" not in d and "damage" in f and isinstance(f["damage"], (int, float)):
            d["damage"] = f["damage"]
    return d


def parse_ammo(args: str) -> dict:
    parts = split_top(args)
    out = {}
    for k in range(0, len(parts) - 1, 2):
        key = parts[k].strip()
        m = re.fullmatch(r"(?:Items|Liquids)\.(\w+)", key)
        if m:
            out[kebab(m.group(1))] = bullet(parts[k + 1], {})
    return out


def common(cls: str, name: str, fields: dict, calls: dict[str, list[str]]) -> dict:
    """What every block class shares: consumption and outputs."""
    d: dict = {"class": cls, "id": name}
    cons: dict = {"items": {}, "liquids": {}, "power_per_tick": 0.0, "power_buffered": 0.0, "coolant": None, "flammable": False, "optional": []}
    for a in calls.get("consumeItems", []):
        cons["items"].update(stacks(a))
    for a in calls.get("consumeItem", []):
        m = re.match(r"\s*Items\.(\w+)(?:\s*,\s*(\d+))?", a)
        if m:
            cons["items"][kebab(m.group(1))] = int(m.group(2) or 1)
    for a in calls.get("consumeLiquid", []):
        m = re.match(r"\s*Liquids\.(\w+)\s*,\s*([^)]+)", a)
        if m:
            cons["liquids"][kebab(m.group(1))] = num(m.group(2))
    for a in calls.get("consumeLiquids", []):
        cons["liquids"].update(stacks(a, "Liquids"))
    for a in calls.get("consumePower", []):
        cons["power_per_tick"] = float(num(a) or 0.0)
    for a in calls.get("consumePowerBuffered", []):
        cons["power_buffered"] = float(num(a) or 0.0)
    for a in calls.get("consumeCoolant", []):
        cons["coolant"] = float(num(a.split(",")[0]) or 0.0)
    cons["boost"] = {"items": {}, "liquids": {}}
    for a in calls.get("consumeLiquid#boost", []):
        m = re.match(r"\s*Liquids\.(\w+)\s*,\s*([^)]+)", a)
        if m:
            cons["boost"]["liquids"][kebab(m.group(1))] = num(m.group(2))
    for a in calls.get("consumeLiquids#boost", []):
        cons["boost"]["liquids"].update(stacks(a, "Liquids"))
    for a in calls.get("consumeItem#boost", []) + calls.get("consumeItem#optional", []):
        m = re.match(r"\s*Items\.(\w+)(?:\s*,\s*(\d+))?", a)
        if m:
            cons["boost"]["items"][kebab(m.group(1))] = int(m.group(2) or 1)
    if any("ConsumeItemFlammable" in a or "ConsumeItemExplosive" in a for a in calls.get("consume", [])):
        cons["flammable"] = True
    for a in calls.get("consume", []):
        for m in re.finditer(r"new Consume(Item|Liquid|Power)\w*\(", a):
            cons["optional"].append(a[:120])
    for a in calls.get("consumeItemFilter", []):
        cons["flammable"] = True
    d["consume"] = cons
    out: dict = {"items": {}, "liquid": {}, "heat": 0.0}
    r = fields.get("_raw", {})
    if "outputItem" in r:
        m = re.search(r"Items\.(\w+)\s*,\s*(\d+)", r["outputItem"])
        if m:
            out["items"][kebab(m.group(1))] = int(m.group(2))
    if "outputItems" in r:
        out["items"].update(stacks(r["outputItems"]))
    if "outputLiquid" in r:
        m = re.search(r"Liquids\.(\w+)\s*,\s*([^)]+)", r["outputLiquid"])
        if m:
            out["liquid"][kebab(m.group(1))] = num(m.group(2))
    if "outputLiquids" in r:
        out["liquid"].update(stacks(r["outputLiquids"], "Liquids"))
    for k in ("heatOutput", "warmupRate"):
        if isinstance(fields.get(k), (int, float)):
            out["heat"] = float(fields["heatOutput"]) if k == "heatOutput" else out["heat"]
    d["output"] = out
    return d


def parse_blocks(text: str) -> dict:
    text = strip_comments(text)
    blocks: dict = {}
    by_java: dict[str, dict] = {}
    for m in re.finditer(r"(\w+)\s*=\s*new (\w+)\(\"([\w-]+)\"\)\s*\{\{", text):
        i = text.index("{{", m.start())
        j = matching(text, i)
        body = text[i + 2:j - 1]
        fields, calls = parse_body(body)
        d = common(m.group(2), m.group(3), fields, calls)
        d["java_name"] = m.group(1)
        d["category"], d["requirements"] = "", {}
        for a in calls.get("requirements", []):
            parts = split_top(a)
            d["category"] = parts[0].split(".")[-1].strip()
            rest = ",".join(parts[1:])
            wm = re.search(r"with\(([^)]*)\)", rest)
            mm = re.search(r"ItemStack\.mult\((\w+)\.requirements,\s*(\d+)\)", rest)
            if wm:
                d["requirements"] = {k: int(v) for k, v in stacks(wm.group(1)).items()}
            elif mm:
                d["mult_of"] = (mm.group(1), int(mm.group(2)))
        fl = {k: v for k, v in fields.items() if k != "_raw" and isinstance(v, (int, float, bool))}
        d["fields"] = fl
        d["refs"] = {k: v["ref"] for k, v in fields.items() if k != "_raw" and isinstance(v, dict) and "ref" in v}
        d["size"] = int(fl.get("size", 1))
        d["health"] = fl.get("health")
        for a in calls.get("ammo", []):
            d["ammo"] = parse_ammo(a)
        r = fields.get("_raw", {})
        if "shootType" in r:
            d["shoot_type"] = bullet(r["shootType"], {})
        if "plans" in r:
            d["plans"] = [{"unit": u.group(1), "time_ticks": num(u.group(2)), "requirements": stacks(u.group(3))}
                          for u in re.finditer(r"new UnitPlan\(UnitTypes\.(\w+),\s*([^,]+?),\s*with\(([^)]*)\)\)", r["plans"])]
        for a in calls.get("upgrades.addAll", []) + calls.get("upgrades", []):
            pass
        ups = re.findall(r"new UnitType\[\]\{([^}]*)\}", body)
        if ups:
            d["upgrades"] = [[u.strip().split(".")[-1] for u in pair.split(",") if u.strip()] for pair in ups]
        if "results" in r:
            d["results"] = stacks(r["results"])
        if m.group(2) == "Wall" or "Wall" in m.group(2):
            d["wall"] = True
        for k in ("pumpAmount", "liquidCapacity", "itemCapacity", "range", "laserRange", "maxNodes", "speed", "displayedSpeed", "transportTime", "reload",
                  "powerProduction", "itemDuration", "drillTime", "tier", "healPercent", "reload", "phaseBoost", "craftTime", "healthRaw"):
            pass
        if "heatOutput" in fl:
            d["output"]["heat"] = float(fl["heatOutput"])
        if "heatRequirement" in fl:
            d["heat_requirement"] = float(fl["heatRequirement"])
        if "attribute" in d["refs"] or "attribute" in r:
            d["attribute"] = r.get("attribute", "")
        blocks[m.group(3)] = d
        by_java[m.group(1)] = d
    for d in blocks.values():
        if "mult_of" in d and d["mult_of"][0] in by_java:
            d["requirements"] = {i: n * d["mult_of"][1] for i, n in by_java[d["mult_of"][0]]["requirements"].items()}
    return blocks


UNIT_CTORS = {"MechUnit": "mech", "LegsUnit": "legs", "UnitEntity": "air", "UnitWaterMove": "naval", "PayloadUnit": "payload", "TankUnit": "tank",
              "ElevationMoveUnit": "hover", "CrawlUnit": "crawl", "BuildingTetherPayloadUnit": "tether", "TimedKillUnit": "timed"}


def parse_weapons(body: str) -> list[dict]:
    out = []
    pos = 0
    while True:
        m = re.search(r"new (?:\w*Weapon)\(([^)]*)\)\s*\{\{", body[pos:])
        if not m:
            return out
        i = pos + m.end() - 2
        j = matching(body, i)
        wb = body[i + 2:j - 1]
        f, calls = parse_body(wb)
        raw = f.get("_raw", {})
        w = {"name": re.sub(r'^"|"$', "", m.group(1).strip()), "reload": f.get("reload"), "x": f.get("x", 0), "y": f.get("y", 0), "mirror": f.get("mirror", True),
             "rotate": f.get("rotate", False), "shootCone": f.get("shootCone"), "inaccuracy": f.get("inaccuracy"), "shots": f.get("shots", 1),
             "alternate": f.get("alternate", True), "targetAir": f.get("ignoreRotation") is None, "range": None}
        if "bullet" in raw:
            w["bullet"] = bullet(raw["bullet"], {})
        out.append(w)
        pos = j


def entity_classes(text: str) -> dict[str, str]:
    """`@EntityDef({Unitc.class, Mechc.class}) UnitType mace, dagger;` -> movement class per unit name (the annotation is what picks the entity)."""
    out: dict[str, str] = {}
    for m in re.finditer(r"@EntityDef\((.*?)\)\s*UnitType\s+([^;]+);", text, re.S):
        comps = re.findall(r"(\w+)c\.class", m.group(1))
        kind = ("mech" if "Mech" in comps else "legs" if "Legs" in comps else "hover" if "ElevationMove" in comps else "naval" if "WaterMove" in comps
                else "tank" if "Tank" in comps else "crawl" if "Crawl" in comps else "block" if "BlockUnit" in comps else "tether" if "BuildingTetherPayload" in comps
                else "air")
        payload = "Payload" in comps
        for n in re.split(r"[,\s]+", m.group(2).strip()):
            if n:
                out[n] = kind + ("+payload" if payload else "")
    return out


def parse_units(text: str) -> dict:
    text = strip_comments(text)
    classes = entity_classes(text)
    units: dict = {}
    for m in re.finditer(r"(\w+)\s*=\s*new (\w*UnitType)\(\"([\w-]+)\"\)\s*\{\{", text):
        i = text.index("{{", m.start())
        j = matching(text, i)
        body = text[i + 2:j - 1]
        fields, calls = parse_body(body)
        fl = {k: v for k, v in fields.items() if k != "_raw" and isinstance(v, (int, float, bool))}
        r = fields.get("_raw", {})
        ctor = classes.get(m.group(1), "mech")
        base = ctor.split("+")[0]
        flying = base == "air"
        u = {"java_name": m.group(1), "constructor": ctor, "flying": flying, "naval": base == "naval", "legs": base == "legs", "payload": "payload" in ctor, "class": m.group(2),
             "speed": fl.get("speed"), "health": fl.get("health"), "armor": fl.get("armor", 0), "hit_size": fl.get("hitSize"), "range": fl.get("range"),
             "max_range": fl.get("maxRange"), "fields": {k: v for k, v in fl.items() if k in (
                 "buildSpeed", "mineTier", "mineSpeed", "itemCapacity", "payloadCapacity", "canBoost", "lowAltitude", "faceTarget", "rotateSpeed", "drag",
                 "accel", "engineOffset", "boostMultiplier", "ammoCapacity", "buildRange", "abilityCooldown", "mineWalls", "mineFloor", "targetAir",
                 "targetGround", "circleTarget", "omniMovement", "fallSpeed", "crashDamageMultiplier", "researchCostMultiplier", "legCount", "hovering",
                 "allowLegStep", "legLength", "legSpeed", "baseRotateSpeed", "mechStepParticles", "canAttack", "isEnemy", "range", "singleTarget")},
             "weapons": parse_weapons(body), "abilities": re.findall(r"new (\w+Ability)\(", body), "tier_hint": None}
        if u["range"] is None and r.get("range"):
            u["range"] = num(r["range"])
        units[m.group(3)] = u
    return units


def build() -> dict:
    blocks = parse_blocks((CONTENT / "Blocks.java").read_text())
    units = parse_units((CONTENT / "UnitTypes.java").read_text())
    return {"_provenance": {"source": "https://github.com/Anuken/Mindustry", "file": "core/src/mindustry/content/{Blocks,UnitTypes}.java",
                            "importer": "scripts/import_mindustry_full.py", "license": "GPL-3.0", "units": "ticks (1/60 s), tiles*8 world units"},
            "blocks": blocks, "units": units}


def main() -> int:
    if not CONTENT.exists():
        print("external/mindustry missing", file=sys.stderr)
        return 2
    data = build()
    text = json.dumps(data, indent=1, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        ok = OUT.exists() and OUT.read_text() == text
        print("mindustry_full.json", "up to date" if ok else "OUT OF DATE")
        return 0 if ok else 1
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(data['blocks'])} blocks, {len(data['units'])} units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

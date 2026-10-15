#!/usr/bin/env python3
"""Pinned Mindustry source -> versioned JSON (stage 1 of the pipeline).

Reads Items.java, Liquids.java, Blocks.java and UnitTypes.java from external/mindustry (pinned in
sources/manifest.json) and writes wizard_rts/data/mindustry_defs.json with the ORIGINAL numbers. Nothing
here is a hybrid adaptation: terrain mapping, costs in Widelands goods and era strength live in
wizard_rts/data/mindustry_overrides.json and are merged by wizard_rts/industry/registry.py.

Usage: python3 scripts/import_mindustry_defs.py [--check]   (--check fails if the JSON is out of date)
"""
from __future__ import annotations
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from wizard_rts import freeze_guard  # noqa: E402  (content is frozen: D33)
freeze_guard.require_unfreeze(__file__)

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "external" / "mindustry"
CONTENT = SRC / "core" / "src" / "mindustry" / "content"
OUT = ROOT / "wizard_rts" / "data" / "mindustry_defs.json"
# Items that exist as drillable ore/floor drops upstream (Blocks.java ores + sand floors + scrap walls); other items have default hardness 0 but are not drillable.
DRILLABLE = ("sand", "scrap", "copper", "lead", "coal", "titanium", "thorium", "beryllium", "tungsten")
TICKS = 60.0  # Mindustry runs 60 ticks per second; durations/rates below are converted per second.


def pinned_sha() -> str:
    manifest = json.loads((ROOT / "sources" / "manifest.json").read_text())
    return next(s["commit"] for s in manifest["sources"] if s["id"] == "mindustry")


def find_body(text: str, start: int) -> tuple[str, int]:
    """Return the text inside the double-brace initialiser opening at/after `start`, and its end index."""
    i = text.index("{{", start)
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i + 2:j - 1], j
        j += 1
    raise ValueError("unbalanced braces")


def stacks(expr: str) -> dict[str, int]:
    """`Items.copper, 12, Items.lead, 3` -> {copper: 12, lead: 3}"""
    out = {}
    for m in re.finditer(r"Items\.(\w+)\s*,\s*(\d+)", expr):
        out[kebab(m.group(1))] = int(m.group(2))
    return out


def kebab(name: str) -> str:
    return re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), name)


def num(s: str) -> float:
    s = s.strip().rstrip("f")
    m = re.fullmatch(r"60f?\s*\*\s*([\d.]+)f?", s)
    if m:
        return 60.0 * float(m.group(1))
    return float(s)


def scalar_fields(body: str) -> dict:
    """Top-level `name = number;` assignments only (nested braces are blanked first)."""
    flat, depth = [], 0
    for ch in body:
        if ch == "{":
            depth += 1
        if depth == 0:
            flat.append(ch)
        if ch == "}":
            depth -= 1
    flat = "".join(flat)
    out = {}
    for m in re.finditer(r"^\s*(\w+)\s*=\s*([-\d.]+f?|true|false)\s*;", flat, re.M):
        v = m.group(2)
        out[m.group(1)] = (v == "true") if v in ("true", "false") else (int(v) if re.fullmatch(r"-?\d+", v) else float(v.rstrip("f")))
    return out


def parse_items(text: str) -> dict:
    items = {}
    for m in re.finditer(r"(\w+)\s*=\s*new Item\(\"([\w-]+)\"(?:,[^)]*\))?\)\s*\{\{", text):
        body, _ = find_body(text, m.start())
        f = scalar_fields(body)
        items[m.group(2)] = {"hardness": f.get("hardness", 0), "cost": f.get("cost", 1.0), "flammability": f.get("flammability", 0.0),
                             "explosiveness": f.get("explosiveness", 0.0), "radioactivity": f.get("radioactivity", 0.0),
                             "buildable": f.get("buildable", True)}
    return items


def parse_liquids(text: str) -> dict:
    out = {}
    for m in re.finditer(r"(\w+)\s*=\s*new \w*Liquid\(\"([\w-]+)\"[^{]*\{\{", text):
        body, _ = find_body(text, m.start())
        f = scalar_fields(body)
        out[m.group(2)] = {k: f[k] for k in ("temperature", "viscosity", "heatCapacity", "flammability", "explosiveness") if k in f}
    return out


def parse_blocks(text: str) -> dict:
    blocks = {}
    by_java: dict[str, dict] = {}
    deferred: list[tuple[str, str, int]] = []  # (block name, base java name, multiplier): `ItemStack.mult(copperWall.requirements, 4)` (large walls)
    for m in re.finditer(r"(\w+)\s*=\s*new (\w+)\(\"([\w-]+)\"\)\s*\{\{", text):
        body, _ = find_body(text, m.start())
        req = re.search(r"requirements\(Category\.(\w+),\s*(?:BuildVisibility\.\w+,\s*)?with\(([^)]*)\)", body)
        mult = None if req else re.search(r"requirements\(Category\.(\w+),\s*(?:BuildVisibility\.\w+,\s*)?ItemStack\.mult\((\w+)\.requirements,\s*(\d+)\)", body)
        if not req and not mult:
            continue
        f = scalar_fields(body)
        d = {"java_name": m.group(1), "class": m.group(2), "category": (req or mult).group(1), "requirements": stacks(req.group(2)) if req else {},
             "size": f.get("size", 1), "health": f.get("health"), "fields": f}
        ci = re.search(r"consumeItems\(with\(([^)]*)\)\)", body)
        if ci:
            d["consume_items"] = stacks(ci.group(1))
        c1 = re.search(r"consumeItem\(Items\.(\w+)(?:,\s*(\d+))?\)", body)
        if c1:
            d["consume_items"] = {kebab(c1.group(1)): int(c1.group(2) or 1)}
        cp = re.search(r"consumePower\(([\d.]+)f?\)", body)
        if cp:
            d["consume_power_per_tick"] = float(cp.group(1))
            d["consume_power_per_second"] = round(float(cp.group(1)) * TICKS, 4)
        cl = re.search(r"consumeLiquid\(Liquids\.(\w+),\s*([\d.]+)f?\)", body)
        if cl:
            d["consume_liquid"] = {"liquid": cl.group(1), "per_tick": float(cl.group(2))}
        oi = re.search(r"outputItem\s*=\s*new ItemStack\(Items\.(\w+),\s*(\d+)\)", body)
        if oi:
            d["output_item"] = {kebab(oi.group(1)): int(oi.group(2))}
        ol = re.search(r"outputLiquid\s*=\s*new LiquidStack\(Liquids\.(\w+),\s*([\d.]+)f?\)", body)
        if ol:
            d["output_liquid"] = {"liquid": ol.group(1), "per_tick": float(ol.group(2))}
        plans = [{"unit": u.group(1), "time_ticks": num(u.group(2)), "time_seconds": round(num(u.group(2)) / TICKS, 3),
                  "requirements": stacks(u.group(3))}
                 for u in re.finditer(r"new UnitPlan\(UnitTypes\.(\w+),\s*([^,]+?),\s*with\(([^)]*)\)\)", body)]
        if plans:
            d["plans"] = plans
        pb = re.search(r"consumePowerBuffered\(([\d.]+)f?\)", body)
        if pb:
            d["power_buffer"] = float(pb.group(1))
        if "powerProduction" in f:
            d["power_production_per_second"] = round(f["powerProduction"] * TICKS, 4)
        blocks[m.group(3)] = d
        by_java[m.group(1)] = d
        if mult:
            deferred.append((m.group(3), mult.group(2), int(mult.group(3))))
    for name, base_java, k in deferred:
        if base_java in by_java:
            blocks[name]["requirements"] = {i: n * k for i, n in by_java[base_java]["requirements"].items()}
    return blocks


def derive(blocks: dict, items: dict) -> None:
    """Add the per-second rates the sim needs, computed with Mindustry's own formulas (Drill.getDrillTime)."""
    for b in blocks.values():
        f = b["fields"]
        if b["class"] == "Drill":
            dt, hm = f.get("drillTime", 300), 50.0
            area = b["size"] ** 2
            b["drill"] = {"tier": f.get("tier", 0), "drill_time": dt, "hardness_multiplier": hm,
                          "items_per_second": {i: round(TICKS * area / (dt + hm * v["hardness"]), 4)
                                               for i, v in items.items() if i in DRILLABLE and v["hardness"] <= f.get("tier", 0)}}
        if b["class"] in ("GenericCrafter", "AttributeCrafter") and "craftTime" in f:
            b["craft_seconds"] = round(f["craftTime"] / TICKS, 4)
        if b["class"] == "Conveyor":
            # Conveyor.java: itemSpace 0.4, capacity 3, an item moves `speed` of a tile per tick (read from the pinned source)
            b["conveyor"] = {"speed": f.get("speed"), "displayed_items_per_second": f.get("displayedSpeed"),
                             "tiles_per_second": round(f.get("speed", 0) * TICKS, 4), "item_space": 0.4, "capacity": 3}
        if b["class"] == "PowerNode":
            b["power_node"] = {"laser_range": f.get("laserRange"), "max_nodes": f.get("maxNodes")}


def parse_units(text: str) -> dict:
    out = {}
    for m in re.finditer(r"(\w+)\s*=\s*new \w*UnitType\(\"([\w-]+)\"\)\s*\{\{", text):
        body, _ = find_body(text, m.start())
        f = scalar_fields(body)
        weapons = []
        for w in re.finditer(r"new Weapon\(([^)]*)\)\s*\{\{", body):
            wb, _ = find_body(body, w.start())
            wf = scalar_fields(wb)
            bl = re.search(r"new (?:\w*Bullet\w*)\(([\d.]+)f?,\s*([\d.]+)f?\)", wb)
            weapons.append({"reload_ticks": wf.get("reload"), "bullet_speed": float(bl.group(1)) if bl else None,
                            "damage": float(bl.group(2)) if bl else None,
                            "lifetime": float(re.search(r"lifetime\s*=\s*([\d.]+)", wb).group(1)) if re.search(r"lifetime\s*=\s*([\d.]+)", wb) else None})
        flying = bool(re.search(r"flying\s*=\s*true", body)) or "constructor = UnitEntity::create" in body
        out[m.group(2)] = {"java_name": m.group(1), "speed": f.get("speed"), "health": f.get("health"), "armor": f.get("armor", 0),
                           "hit_size": f.get("hitSize"), "range": f.get("range"), "flying": flying, "weapons": weapons}
    return out


def build() -> dict:
    items = parse_items((CONTENT / "Items.java").read_text())
    liquids = parse_liquids((CONTENT / "Liquids.java").read_text())
    blocks = parse_blocks((CONTENT / "Blocks.java").read_text())
    units = parse_units((CONTENT / "UnitTypes.java").read_text())
    derive(blocks, items)
    head = subprocess.run(["git", "-C", str(SRC), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return {"_provenance": {"source": "https://github.com/Anuken/Mindustry", "commit": pinned_sha(), "checked_out_commit": head,
                            "license": "GPL-3.0", "files": ["Items.java", "Liquids.java", "Blocks.java", "UnitTypes.java"],
                            "units": "ticks/60 = seconds; power in power-units per second; sizes in tiles",
                            "note": "Original numbers only; hybrid adaptation is in mindustry_overrides.json"},
            "items": items, "liquids": liquids, "blocks": blocks, "units": units}


def main() -> int:
    if not CONTENT.exists():
        print("external/mindustry missing: run scripts/setup_external.sh mindustry", file=sys.stderr)
        return 2
    data = build()
    text = json.dumps(data, indent=1, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        ok = OUT.exists() and OUT.read_text() == text
        print("mindustry_defs.json", "up to date" if ok else "OUT OF DATE")
        return 0 if ok else 1
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(data['items'])} items, {len(data['liquids'])} liquids, "
          f"{len(data['blocks'])} blocks, {len(data['units'])} units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

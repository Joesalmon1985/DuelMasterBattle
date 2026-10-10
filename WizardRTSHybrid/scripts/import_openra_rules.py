"""Extract OpenRA RA actor and weapon rules into wizard_rts/data/openra_rules.json.

Reads the pinned checkout's MiniYaml (mods/ra/rules and weapons), resolves
Inherits, removals (-Key) and trait overrides, then keeps the numbers the hybrid
needs: health, armor, speed, cost, build queue, armaments, and each weapon's
range, reload, burst, projectile speed and damage warheads with Versus.

The hybrid does not read the OpenRA tree at runtime; it reads this JSON.
Source: OpenRA bleed e7e9e4ad. GPL-3.0-or-later, OpenRA Developers.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HYBRID = Path(__file__).resolve().parents[1]
RA = HYBRID / "external" / "openra" / "mods" / "ra"
OUT = HYBRID / "wizard_rts" / "data" / "openra_rules.json"


class Node:
    __slots__ = ("key", "value", "children")

    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value
        self.children: list[Node] = []


def parse(text: str) -> list[Node]:
    root = Node("", "")
    stack = [(-1, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        depth = len(raw) - len(raw.lstrip("\t"))
        line = raw.strip()
        line = re.sub(r"\s+#.*$", "", line)
        key, _sep, value = line.partition(":")
        node = Node(key.strip(), value.strip())
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack[-1][1].children.append(node)
        stack.append((depth, node))
    return root.children


def load(directory: Path) -> dict[str, list[Node]]:
    table: dict[str, list[Node]] = {}
    for path in sorted(directory.glob("*.yaml")):
        for node in parse(path.read_text(encoding="utf-8", errors="replace")):
            table.setdefault(node.key, []).extend(node.children)
    return table


def merge(into: dict, nodes: list[Node]) -> None:
    for n in nodes:
        if n.key.startswith("-"):
            into.pop(n.key[1:], None)
            continue
        slot = into.setdefault(n.key, {"_v": "", "_c": {}})
        if n.value != "":
            slot["_v"] = n.value
        merge(slot["_c"], n.children)


def resolve(table: dict[str, list[Node]], name: str, seen: tuple = ()) -> dict:
    out: dict = {}
    if name in seen or name not in table:
        return out
    nodes = table[name]
    # inheritance first (in order), then own traits
    merged: dict = {}
    for n in nodes:
        if n.key == "Inherits" or n.key.startswith("Inherits@"):
            parent = resolve(table, n.value, seen + (name,))
            for k, v in parent.items():
                merged.setdefault(k, {"_v": "", "_c": {}})
                merged[k]["_v"] = v["_v"] or merged[k]["_v"]
                _deep(merged[k]["_c"], v["_c"])
    own = [n for n in nodes if not (n.key == "Inherits" or n.key.startswith("Inherits@"))]
    merge(merged, own)
    return merged


def _deep(a: dict, b: dict) -> None:
    for k, v in b.items():
        slot = a.setdefault(k, {"_v": "", "_c": {}})
        if v["_v"]:
            slot["_v"] = v["_v"]
        _deep(slot["_c"], v["_c"])


def val(d: dict, *path: str, default=None):
    cur = d
    for i, key in enumerate(path):
        cur = cur.get(key)
        if cur is None:
            return default
        if i == len(path) - 1:
            return cur["_v"] if cur["_v"] != "" else default
        cur = cur["_c"]
    return default


def cells(text: str | None) -> float:
    """OpenRA WDist: '5c512' is five cells and 512/1024."""
    if not text:
        return 0.0
    m = re.match(r"(-?\d+)c(-?\d+)", text.strip())
    if m:
        return int(m.group(1)) + int(m.group(2)) / 1024.0
    return float(text) / 1024.0


def to_int(text, default=0) -> int:
    try:
        return int(str(text).split(",")[0])
    except (TypeError, ValueError):
        return default


def weapon_info(table: dict, name: str) -> dict:
    w = resolve(table, name)
    warheads = []
    for key, slot in w.items():
        if key.startswith("Warhead") and slot["_v"] in ("SpreadDamage", "TargetDamage", "HealthPercentageDamage"):
            c = slot["_c"]
            versus = {k: to_int(v["_v"]) for k, v in c.get("Versus", {"_c": {}})["_c"].items()} if "Versus" in c else {}
            warheads.append(
                {
                    "type": slot["_v"],
                    "damage": to_int(val(c, "Damage"), 0),
                    "spread": cells(val(c, "Spread")),
                    "versus": versus,
                    "valid_targets": [t.strip() for t in str(val(c, "ValidTargets", default="")).split(",") if t.strip()],
                }
            )
    proj = w.get("Projectile", {"_v": "", "_c": {}})
    return {
        "range": cells(val(w, "Range")),
        "min_range": cells(val(w, "MinRange")),
        "reload": to_int(val(w, "ReloadDelay"), 1),
        "burst": to_int(val(w, "Burst"), 1),
        "burst_delay": to_int(val(w, "BurstDelays"), 5),
        "projectile": proj["_v"],
        "projectile_speed": to_int(val(proj["_c"], "Speed"), 0) if proj["_c"] else 0,
        "valid_targets": [t.strip() for t in str(val(w, "ValidTargets", default="Ground, Water")).split(",") if t.strip()],
        "invalid_targets": [t.strip() for t in str(val(w, "InvalidTargets", default="")).split(",") if t.strip()],
        "warheads": warheads,
    }


def main() -> None:
    actors = load(RA / "rules")
    weapons = load(RA / "weapons")
    out_actors = {}
    wanted_weapons: set[str] = set()
    for name in actors:
        if name.startswith("^") or name.endswith((".Husk", "Husk")) or "." in name:
            continue
        a = resolve(actors, name)
        if not a or "Health" not in a or "Buildable" not in a:
            continue
        hp = to_int(val(a, "Health", "HP"), 0)
        if hp <= 0:
            continue
        arms = []
        for key, slot in a.items():
            if key.startswith("Armament"):
                wn = val({"x": slot}, "x", "Weapon") if False else slot["_c"].get("Weapon", {}).get("_v")
                if wn and "garrison" not in key.lower():
                    arms.append(wn)
                    wanted_weapons.add(wn)
        speed = to_int(val(a, "Mobile", "Speed"), 0)
        out_actors[name.lower()] = {
            "name": name,
            "hp": hp,
            "armor": val(a, "Armor", "Type", default="None"),
            "speed": speed,
            "cost": to_int(val(a, "Valued", "Cost"), 0),
            "queue": val(a, "Buildable", "Queue", default=""),
            "prerequisites": val(a, "Buildable", "Prerequisites", default=""),
            "armaments": arms,
            "target_types": [t.strip() for t in str(val(a, "Targetable", "TargetTypes", default="")).split(",") if t.strip()],
            "mobile": "Mobile" in a,
            "is_building": "Building" in a,
            "locomotor": val(a, "Mobile", "Locomotor", default=""),
        }
    out_weapons = {w: weapon_info(weapons, w) for w in sorted(wanted_weapons) if w in weapons}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": "OpenRA bleed e7e9e4ad mods/ra rules + weapons", "actors": out_actors, "weapons": out_weapons}, indent=1), encoding="utf-8")
    print(f"OPENRA_RULES actors={len(out_actors)} weapons={len(out_weapons)}")
    for n in ("e1", "3tnk", "gun", "barr", "weap", "e3"):
        a = out_actors.get(n)
        if a:
            print(n, a["hp"], a["armor"], a["speed"], a["armaments"], [out_weapons.get(w, {}).get("range") for w in a["armaments"]])


if __name__ == "__main__":
    main()

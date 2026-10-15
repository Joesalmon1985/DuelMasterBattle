"""Extract OpenRA RA actor and weapon rules into wizard_rts/data/openra_rules.json.

Reads the pinned checkout's MiniYaml (mods/ra/rules and weapons), resolves
Inherits, removals (-Key) and trait overrides, then keeps the numbers the hybrid
needs: health, armor, speed, cost, build queue, armaments, and each weapon's
range, reload, burst, projectile speed and damage warheads with Versus.

The hybrid does not read the OpenRA tree at runtime; it reads this JSON.
Source: OpenRA bleed e7e9e4ad. GPL-3.0-or-later, OpenRA Developers.
"""

from __future__ import annotations
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from wizard_rts import freeze_guard  # noqa: E402  (content is frozen: D33)
freeze_guard.require_unfreeze(__file__)

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


def naval_traits(a: dict) -> dict:
    """Footprint, production, exits, cloak and detection: what ships and naval yards need."""
    out: dict = {}
    b = a.get("Building")
    if b is not None:
        c = b["_c"]
        out["building"] = {
            "footprint": val(c, "Footprint", default="x"),
            "dimensions": val(c, "Dimensions", default="1,1"),
            "terrain_types": [t.strip() for t in str(val(c, "TerrainTypes", default="")).split(",") if t.strip()],
            "requires_buildable_adjacent": to_int(val(a, "RequiresBuildableArea", "Adjacent"), 0),
        }
    prod = a.get("Production")
    if prod is not None:
        out["produces"] = [t.strip() for t in str(val(prod["_c"], "Produces", default=prod["_v"] or "")).split(",") if t.strip()]
        exits = []
        for key, slot in a.items():
            if key == "Exit" or key.startswith("Exit@"):
                c = slot["_c"]
                exits.append({
                    "exit_cell": [int(x) for x in str(val(c, "ExitCell", default="0,0")).split(",")[:2]],
                    "spawn_offset": [int(x) for x in str(val(c, "SpawnOffset", default="0,0,0")).split(",")[:3]],
                    "facing": to_int(val(c, "Facing"), 0),
                })
        out["exits"] = exits
    bap = val(a, "Buildable", "BuildAtProductionType", default="")
    if bap:
        out["build_at"] = bap
    cloak = a.get("Cloak")
    if cloak is not None:
        out["cloak"] = {
            "delay_ticks": to_int(val(cloak["_c"], "CloakDelay"), 30),
            "detection_types": [t.strip() for t in str(val(cloak["_c"], "DetectionTypes", default="")).split(",") if t.strip()],
        }
    det = a.get("DetectCloaked")
    if det is not None:
        out["detect"] = {"range": cells(val(det["_c"], "Range", default="5c0")), "types": [t.strip() for t in str(val(det["_c"], "DetectionTypes", default="Cloak")).split(",") if t.strip()]}
    targ = {}
    for key, slot in a.items():
        if key == "Targetable" or key.startswith("Targetable@"):
            targ[key] = {"types": [t.strip() for t in str(val(slot["_c"], "TargetTypes", default="")).split(",") if t.strip()],
                         "requires": val(slot["_c"], "RequiresCondition", default="")}
    if targ:
        out["targetable"] = targ
    return out


ABILITY_TRAITS = ("Aircraft", "AmmoPool", "Cargo", "Passenger", "Repairable", "RepairableNear", "RepairsUnits", "Captures", "Capturable", "ExternalCapturable", "Infiltrates",
                  "Infiltrable", "InfiltrateForCash", "InfiltrateForSupportPower", "InfiltrateForExploration", "InfiltrateForPowerOutage", "Minelayer", "Mine", "Demolition", "Demolishable",
                  "NukePower", "GrantExternalConditionPower", "ChronoshiftPower", "ParatroopersPower", "AirstrikePower", "SpawnActorPower", "ProduceActorPower", "GivesBuildableArea",
                  "Power", "ProvidesPrerequisite", "Transforms", "ProductionAirdrop", "Reservable", "Selfheal", "Wall", "Crushable", "GainsExperience", "WithBuildingRepairIcon",
                  "RepairsBridges", "Disguise", "IgnoresDisguise", "Sellable", "HealthPercentageDamage", "ChangesHealth", "ChronoshiftDeploy", "TeleportNetwork", "AttackAircraft",
                  "AttackFrontal", "AttackTurreted", "AttackGarrisoned", "ParatroopersPower", "Hovers", "HoversNote", "ReturnOnIdle", "FallsToEarth", "JamsMissiles", "AutoTarget",
                  "ProximityCaptor", "ProximityCapturable", "RevealsShroud", "CreatesShroud", "GpsPower", "SupportPowerManager", "ScaredyCat", "TakeCover", "MadTank", "DeployToUpgrade",
                  "GrantConditionOnDeploy", "AirstrikePowerInfo", "SelfHealing", "RepairableBuilding", "WithSpriteBody", "WithMakeAnimation", "EngineerRepair", "DamagedByTerrain")


def ability_traits(a: dict) -> dict:
    """The scalar settings of the traits that give an actor its special functions (aircraft, cargo, repair, capture, infiltration, mines, support powers...)."""
    out: dict = {}
    for key, slot in a.items():
        base = key.split("@")[0]
        if base in ABILITY_TRAITS:
            kids = {k: v["_v"] for k, v in slot["_c"].items() if v["_v"] != ""}
            if slot["_v"]:
                kids["_value"] = slot["_v"]
            out[key] = kids
    return out


def locomotors() -> dict:
    """TerrainSpeeds per locomotor from mods/ra/rules/world.yaml (percent of base speed by terrain type)."""
    table = load(RA / "rules")
    world = resolve(table, "World")
    out = {}
    for key, slot in world.items():
        if key.startswith("Locomotor"):
            c = slot["_c"]
            speeds = {k: to_int(v["_v"]) for k, v in c.get("TerrainSpeeds", {"_c": {}})["_c"].items()}
            out[val(c, "Name", default=key)] = {"speeds": speeds, "crushes": [t.strip() for t in str(val(c, "Crushes", default="")).split(",") if t.strip()]}
    return out


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
        speed = to_int(val(a, "Mobile", "Speed"), 0) or to_int(val(a, "Aircraft", "Speed"), 0)
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
            "mobile": "Mobile" in a or "Aircraft" in a,
            "is_building": "Building" in a,
            "locomotor": val(a, "Mobile", "Locomotor", default="") or ("fly" if "Aircraft" in a else ""),
        }
        extra = naval_traits(a)
        if extra:
            out_actors[name.lower()].update(extra)
        ab = ability_traits(a)
        if ab:
            out_actors[name.lower()]["abilities"] = ab
    out_weapons = {w: weapon_info(weapons, w) for w in sorted(wanted_weapons) if w in weapons}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": "OpenRA bleed e7e9e4ad mods/ra rules + weapons", "locomotors": locomotors(), "actors": out_actors, "weapons": out_weapons}, indent=1), encoding="utf-8")
    print(f"OPENRA_RULES actors={len(out_actors)} weapons={len(out_weapons)}")
    for n in ("e1", "3tnk", "gun", "barr", "weap", "e3"):
        a = out_actors.get(n)
        if a:
            print(n, a["hp"], a["armor"], a["speed"], a["armaments"], [out_weapons.get(w, {}).get("range") for w in a["armaments"]])


if __name__ == "__main__":
    main()

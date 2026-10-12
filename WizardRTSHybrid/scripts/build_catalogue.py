"""Build the machine-readable feature catalogue from the original sources.

Discovery: every Widelands tribe building / worker / ware definition and every
OpenRA RA actor definition. Status comes from docs/feature_status.json, a hand
kept map of id -> {status, evidence}. Anything not listed there is `missing`.

Statuses, in order: missing, scaffolded, adapted, integrated, tested, verified.
A sprite alone never raises a status above `missing`.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

HYBRID = Path(__file__).resolve().parents[1]
WL = HYBRID / "external" / "widelands" / "data"
RA = HYBRID / "external" / "openra" / "mods" / "ra" / "rules"
OUT = HYBRID / "docs" / "feature_catalogue.json"
STATUS = HYBRID / "docs" / "feature_status.json"
ORDER = ["missing", "scaffolded", "adapted", "integrated", "tested", "verified"]

WL_KINDS = {
    "productionsite": "building", "warehouse": "building", "militarysite": "building",
    "trainingsite": "building", "worker": "worker", "ware": "ware", "soldier": "worker", "carrier": "worker",
}
NAME_RE = re.compile(r"new_(\w+?)_type\s*\{[^}]*?name\s*=\s*\"([^\"]+)\"", re.S)
RA_FILES = {
    "infantry.yaml": "unit", "vehicles.yaml": "unit", "aircraft.yaml": "unit", "ships.yaml": "unit",
    "structures.yaml": "building",
}


def discover() -> list[dict]:
    items: list[dict] = []
    for path in sorted((WL / "tribes").rglob("init.lua")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for kind, name in NAME_RE.findall(text):
            if kind in WL_KINDS:
                rel = path.relative_to(WL).as_posix()
                items.append({"id": f"widelands.{name}", "game": "widelands", "category": WL_KINDS[kind],
                              "subtype": kind, "source": rel})
    for fname, category in RA_FILES.items():
        path = RA / fname
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"^([A-Za-z0-9_]+):\s*(?:#.*)?$", line)
            if m:
                items.append({"id": f"openra.{m.group(1).lower()}", "game": "openra", "category": category,
                              "subtype": fname[:-5], "source": f"mods/ra/rules/{fname}"})
    items.extend(discover_mindustry())
    return items


def discover_mindustry() -> list[dict]:
    """Every block, unit, item and liquid of the pinned Mindustry import (wizard_rts/data/mindustry_defs.json). Imported data alone is
    `missing` here by the catalogue's own rule: only a status entry with evidence raises it."""
    path = HYBRID / "wizard_rts" / "data" / "mindustry_defs.json"
    if not path.is_file():
        return []
    d = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for bid, b in sorted(d["blocks"].items()):
        out.append({"id": f"mindustry.{bid}", "game": "mindustry", "category": "block", "subtype": b["category"], "source": "Blocks.java"})
    for uid in sorted(d["units"]):
        out.append({"id": f"mindustry.{uid}", "game": "mindustry", "category": "unit", "subtype": "ground" if not d["units"][uid]["flying"] else "air", "source": "UnitTypes.java"})
    for iid in sorted(d["items"]):
        out.append({"id": f"mindustry.item.{iid}", "game": "mindustry", "category": "item", "subtype": "item", "source": "Items.java"})
    for lid in sorted(d["liquids"]):
        out.append({"id": f"mindustry.liquid.{lid}", "game": "mindustry", "category": "liquid", "subtype": "liquid", "source": "Liquids.java"})
    return out


def generic_status() -> dict[str, dict]:
    """Statuses earned by the data-driven path: `adapted` when the definition is imported and runnable on
    the generic interpreter, `tested` when the isolated bench made one of its wares from it."""
    out: dict[str, dict] = {}
    defs_path = HYBRID / "wizard_rts" / "data" / "widelands_defs.json"
    if not defs_path.is_file():
        return out
    defs = json.loads(defs_path.read_text(encoding="utf-8"))
    results = {}
    res_path = HYBRID / "docs" / "generic_building_results.json"
    if res_path.is_file():
        results = {r["name"]: r for r in json.loads(res_path.read_text(encoding="utf-8"))}
    made_wares: set[str] = set()
    for name, b in defs["buildings"].items():
        if not b.get("runnable"):
            continue
        r = results.get(name)
        if r and r.get("passed"):
            out[f"widelands.{name}"] = {"status": "tested", "evidence": "isolated bench: scripts/verify_generic_buildings.py"}
            made_wares.update(g for g, n in r.get("made", {}).items() if n)
        else:
            out[f"widelands.{name}"] = {"status": "adapted", "evidence": "imported and runnable on the generic interpreter; bench not passed"}
    for w, info in defs["workers"].items():
        if info.get("executable") and info["programs"]:
            out[f"widelands.{w}"] = {"status": "adapted", "evidence": "worker programmes convert to interpreter commands"}
    for g in made_wares:
        out[f"widelands.{g}"] = {"status": "tested", "evidence": "made by a bench-passed building"}
    return out


def main() -> None:
    status = generic_status()
    hand = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.is_file() else {}
    for k, v in hand.items():  # hand-kept entries win when they are higher or add evidence
        cur = status.get(k)
        if cur is None or ORDER.index(v["status"]) >= ORDER.index(cur["status"]):
            status[k] = v
    items = discover()
    seen = set()
    unique = []
    for it in items:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        st = status.get(it["id"], {})
        it["status"] = st.get("status", "missing")
        it["evidence"] = st.get("evidence", "")
        it["ai_usable"] = bool(st.get("ai_usable", False))
        unique.append(it)
    totals: dict = {}
    for game in ("widelands", "openra", "mindustry"):
        for cat in sorted({i["category"] for i in unique if i["game"] == game}):
            rows = [i for i in unique if i["game"] == game and i["category"] == cat]
            counts = Counter(r["status"] for r in rows)
            totals[f"{game}.{cat}"] = {"discovered": len(rows), **{s: counts.get(s, 0) for s in ORDER}}
    unknown = sorted(k for k in status if k not in seen)
    OUT.write_text(json.dumps({"statuses": ORDER, "totals": totals, "unknown_status_keys": unknown,
                               "items": unique}, indent=1), encoding="utf-8")
    for key, row in totals.items():
        print(key, row)
    if unknown:
        print("STATUS_KEYS_NOT_IN_SOURCE", unknown)


if __name__ == "__main__":
    main()

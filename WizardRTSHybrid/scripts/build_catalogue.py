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
    return items


def main() -> None:
    status = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.is_file() else {}
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
        unique.append(it)
    totals: dict = {}
    for game in ("widelands", "openra"):
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

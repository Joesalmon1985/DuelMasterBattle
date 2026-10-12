"""Catalogue audit (plan v2 section 3.1): upstream definitions in the pinned external/ trees versus the imported JSON.

    python3 scripts/audit_catalogues.py [--json out.json] [--list]

Prints one row per source with upstream count, imported count and the names missing. --list prints every missing name.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
DATA = HYB / "wizard_rts" / "data"
EXT = HYB / "external"
MIND = EXT / "mindustry" / "core" / "src" / "mindustry" / "content"
DECL = re.compile(r'\b[A-Za-z0-9_]+\s*=\s*new\s+[A-Za-z0-9_<>]+\s*\(\s*"([a-z0-9\-]+)"')


def java_names(fname: str, class_filter: str | None = None) -> set[str]:
    text = (MIND / fname).read_text(errors="replace")
    pat = re.compile(r'\b[A-Za-z0-9_]+\s*=\s*new\s+(' + (class_filter or "[A-Za-z0-9_<>]+") + r')\s*\(\s*"([a-z0-9\-]+)"')
    return {m.group(2) for m in pat.finditer(text)}


TRIBES = {"amazons", "atlanteans", "barbarians", "empire", "frisians"}


def widelands_dirs() -> dict[str, set[str]]:
    """Names as the importer keys them: <tribe>_<dir> for buildings and workers, <dir> for wares."""
    base = EXT / "widelands" / "data" / "tribes"
    out: dict[str, set[str]] = {"buildings": set(), "workers": set(), "wares": set()}
    for kind in out:
        for f in (base / kind).rglob("init.lua"):
            d = f.parent
            tribe = d.parent.name
            out[kind].add(d.name if kind == "wares" or tribe not in TRIBES else f"{tribe}_{d.name}")
    return out


def openra_names() -> set[str]:
    names: set[str] = set()
    for f in (EXT / "openra" / "mods" / "ra" / "rules").glob("*.yaml"):
        for line in f.read_text(errors="replace").splitlines():
            m = re.match(r"^([A-Za-z0-9_]+):\s*$", line)
            if m and not m.group(1).startswith(("^", "Inherits")):
                names.add(m.group(1).lower())
    return names


def row(label: str, upstream: set[str], imported: set[str]) -> dict:
    return {"source": label, "upstream": len(upstream), "imported": len(imported), "missing": sorted(upstream - imported),
            "extra": sorted(imported - upstream)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    wl = json.loads((DATA / "widelands_defs.json").read_text())
    md = json.loads((DATA / "mindustry_defs.json").read_text())
    ra = json.loads((DATA / "openra_rules.json").read_text())
    strip = lambda ks, p: {k.split(".", 1)[1] if k.startswith(p) else k for k in ks}  # noqa: E731
    up = widelands_dirs()
    rows = []
    for kind in ("buildings", "workers", "wares"):
        imp = set(wl[kind])
        rows.append(row(f"widelands {kind}", up[kind], imp))
    rows.append(row("mindustry units", java_names("UnitTypes.java", "[A-Za-z]*UnitType[A-Za-z]*"), strip(md["units"], "mindustry.")))
    rows.append(row("mindustry items", java_names("Items.java", "Item"), strip(md["items"], "mindustry.")))
    rows.append(row("mindustry liquids", java_names("Liquids.java", "[A-Za-z]*Liquid"), strip(md["liquids"], "mindustry.")))
    blocks = java_names("Blocks.java")
    rows.append(row("mindustry blocks (all declarations incl. floors/props)", blocks, strip(md["blocks"], "mindustry.")))
    rows.append(row("openra ra rule names (all, incl. abstract/civilian)", openra_names(), {k.split(".")[-1].lower() for k in ra["actors"]}))
    print(f"{'source':58} {'upstream':>8} {'imported':>8} {'missing':>8}")
    for r in rows:
        print(f"{r['source']:58} {r['upstream']:8} {r['imported']:8} {len(r['missing']):8}")
        if a.list and r["missing"]:
            print("   missing:", ", ".join(r["missing"]))
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Asset audit: every image and data file the Godot client reads at run time must exist in the repository and, for an
exported build, inside the APK.

    python3 scripts/android/asset_audit.py                                  # repository only
    python3 scripts/android/asset_audit.py build/android/DuelMasterBattle-debug.apk   # repository + the package

Why it exists. A Godot export does not ship source PNG files. It ships the imported textures (`.godot/imported/*.ctex`) and a
`<name>.png.import` remap beside each name; `Image.load("res://x.png")` therefore works from the editor on the PC and fails on a
phone. The client now loads every picture through `client/scripts/asset_loader.gd` (ResourceLoader first). This audit is the
other half: it enumerates what the client will ask for (the art catalogue exactly as `hybrid_art.gd` registers it, plus every
literal `res://` image/data path in the client scripts) and fails if any of it is not in the package in a form the loader can
read. Nothing here imports content: it only checks the roster that already exists, and a catalogue item that never had
artwork is reported (`missing_required`) rather than replaced."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

HYB = Path(__file__).resolve().parents[2]
ROOT = HYB.parent
PROJECT = ROOT / "godot_project"
CATALOGUE = PROJECT / "client" / "hybrid" / "art" / "catalogue.json"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
# Data the client reads with FileAccess/load at run time: it must travel as a plain file in the package.
DATA_EXT = {".json", ".cfg", ".csv", ".txt", ".tres", ".res", ".ogg", ".wav", ".mp3", ".ttf", ".otf"}
SCENE_EXT = {".tscn", ".scn"}
SKIP_DIRS = ("client/tests/", "client/tools/", "sim/tools/", "sim/tests/", "tests/")


def res_to_rel(path: str) -> str:
    return path[len("res://"):] if path.startswith("res://") else path


def catalogue_paths(catalogue: Path = CATALOGUE) -> dict[str, set[str]]:
    """The res:// paths `hybrid_art.gd` registers or draws, grouped by what asked for them (mirrors load_catalogue,
    _item_for/_sequence_index, layer_textures and state_texture)."""
    data = json.loads(catalogue.read_text(encoding="utf-8"))
    out: dict[str, set[str]] = {}
    base = "res://client/hybrid/art/openra/%s-%04d.png"
    for item in data["items"]:
        iid = item["id"]
        paths: set[str] = set()
        mode = item.get("mode")
        if mode == "sheet" and item.get("godot"):
            paths.add(item["godot"])
        for p in item.get("frames_godot", []):
            paths.add(p)
        layers = item.get("layers")
        if layers:
            for f in range(int(layers.get("facings", 32))):
                for key in ("body_prefix", "turret_prefix"):
                    paths.add(base % (layers[key], f))
        for state in item.get("states", {}).values():
            for p in state.get("files", []):
                paths.add(p)
        if item.get("overlay_prefix"):
            for i in range(int(item.get("overlay_length", 1))):
                paths.add(base % (item["overlay_prefix"], i))
        out[iid] = {p for p in paths if p}
    return out


def literal_paths(project: Path = PROJECT) -> dict[str, set[str]]:
    """Literal res:// image/data paths in the client scripts (tests and tools excluded), keyed by the file naming them."""
    pat = re.compile(r'"(res://[^"%\s{}*]+\.[A-Za-z0-9]+)"')
    out: dict[str, set[str]] = {}
    for gd in list((project / "client").rglob("*.gd")) + list((project / "sim").rglob("*.gd")):
        rel = gd.relative_to(project).as_posix()
        if any(rel.startswith(s) for s in SKIP_DIRS) or "/tests/" in rel or "/tools/" in rel:
            continue
        text = gd.read_text(encoding="utf-8", errors="replace")
        for m in pat.finditer(text):
            ext = "." + m.group(1).rsplit(".", 1)[-1].lower()
            if ext in IMAGE_EXT or ext in DATA_EXT or ext in SCENE_EXT:
                out.setdefault(rel, set()).add(m.group(1))
    return out


def in_repo(path: str, project: Path = PROJECT) -> bool:
    return (project / res_to_rel(path)).is_file()


def in_apk(path: str, names: set[str], files: dict[str, bytes] | None = None) -> str | None:
    """None if the loader can read `path` from the package, else the reason it cannot."""
    rel = res_to_rel(path)
    ext = "." + rel.rsplit(".", 1)[-1].lower()
    if ext in IMAGE_EXT:
        imp = "assets/" + rel + ".import"
        if imp not in names:
            return "no import remap (%s) - the image would not load on the phone" % imp
        if files is not None:
            text = files.get(imp, b"").decode("utf-8", "replace")
            m = re.search(r'^path="res://([^"]+)"', text, re.M)
            if not m:
                return "import remap names no imported resource"
            if "assets/" + m.group(1) not in names:
                return "imported texture %s is not in the package" % m.group(1)
        return None
    if ext in SCENE_EXT:
        if "assets/" + rel + ".remap" in names or "assets/" + rel in names:
            return None
        return "scene not in the package"
    return None if "assets/" + rel in names else "data file not in the package (check export filters)"


def audit(apk: Path | None) -> tuple[list[str], dict[str, int]]:
    problems: list[str] = []
    stats: dict[str, int] = {}
    cat = catalogue_paths()
    required = {p for paths in cat.values() for p in paths}
    lit = literal_paths()
    literal_all = {p for paths in lit.values() for p in paths}
    stats["catalogue_items"] = len(cat)
    stats["catalogue_files"] = len(required)
    stats["literal_paths"] = len(literal_all)
    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    if data.get("missing_required"):
        problems.append("catalogue.missing_required is not empty: %s" % data["missing_required"])
    for item_id, paths in sorted(cat.items()):
        for p in sorted(paths):
            if not in_repo(p):
                problems.append("catalogue %s: %s is not in the repository" % (item_id, p))
    for owner, paths in sorted(lit.items()):
        for p in sorted(paths):
            if not in_repo(p) and not (PROJECT / res_to_rel(p + ".remap")).exists():
                problems.append("%s names %s which is not in the repository" % (owner, p))
    if apk is not None:
        with zipfile.ZipFile(apk) as z:
            names = set(z.namelist())
            imports = {n: z.read(n) for n in names if n.startswith("assets/") and n.endswith(".import") and n.count("/") > 1}
        stats["apk_import_remaps"] = len(imports)
        stats["apk_ctex"] = sum(1 for n in names if n.endswith(".ctex"))
        bad = 0
        for item_id, paths in sorted(cat.items()):
            for p in sorted(paths):
                if not in_repo(p):
                    continue
                why = in_apk(p, names, imports)
                if why:
                    bad += 1
                    if bad <= 40:
                        problems.append("APK: catalogue %s: %s: %s" % (item_id, p, why))
        if bad > 40:
            problems.append("APK: ... and %d more catalogue files" % (bad - 40))
        for owner, paths in sorted(lit.items()):
            for p in sorted(paths):
                if not in_repo(p):
                    continue
                why = in_apk(p, names, imports)
                if why:
                    problems.append("APK: %s names %s: %s" % (owner, p, why))
        if "assets/client/hybrid/art/catalogue.json" not in names:
            problems.append("APK: the art catalogue itself is not packaged")
        # A phone that has to fall back to source PNGs cannot: the export must carry imported textures, not a handful of PNGs.
        raw_png = [n for n in names if n.startswith("assets/") and n.lower().endswith(".png")]
        stats["apk_raw_png"] = len(raw_png)
        if stats["apk_ctex"] < stats["catalogue_files"]:
            problems.append("APK: only %d imported textures for %d catalogue files" % (stats["apk_ctex"], stats["catalogue_files"]))
    return problems, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("apk", nargs="?", help="an exported APK to check as well as the repository")
    args = ap.parse_args(argv)
    problems, stats = audit(Path(args.apk) if args.apk else None)
    print("ASSET_AUDIT", json.dumps(stats, sort_keys=True))
    for p in problems:
        print("ASSET_PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

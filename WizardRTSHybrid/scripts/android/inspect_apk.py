#!/usr/bin/env python3
"""Print what an exported DuelMasterBattle APK contains and fail if it is not what a phone needs.

    python3 scripts/android/inspect_apk.py build/android/DuelMasterBattle-debug.apk [--client-only] [--skip-assets] [--expect-version 0.2.0]

Checks:
* arm64-v8a only, the Godot library;
* unless --client-only: the Chaquopy CPython runtime and the packed `wizard_rts` sources (`assets/chaquopy/app.imy`) with every file the stager listed
  (`STAGED.json`: data files as files, Python as `.pyc` or `.py`), so a Wizard World host that imports a module or reads a data file the package lacks is caught here;
* the art: every picture the client will draw (the art catalogue exactly as `hybrid_art.gd` registers it, plus every literal `res://` image/data path in the client scripts)
  exists in the repository and is in the package in the form the exported game can load (an imported texture and its `.import` remap; a source PNG is not enough,
  Godot does not ship it). See `asset_audit.py`;
* the app version in the manifest, when --expect-version is given.

Signing is checked by the caller with apksigner (v2 signatures live in the APK signing block, not in META-INF)."""

from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asset_audit  # noqa: E402


def packed_python_problems(z: zipfile.ZipFile) -> list[str]:
    """Every file the stager listed is in the packed sources (Python compiled to .pyc is fine)."""
    problems: list[str] = []
    try:
        imy = zipfile.ZipFile(io.BytesIO(z.read("assets/chaquopy/app.imy")))
    except (KeyError, zipfile.BadZipFile):
        return ["assets/chaquopy/app.imy cannot be read"]
    names = set(imy.namelist())
    if "STAGED.json" not in names:
        return ["the packed sources carry no STAGED.json (stage_python.py did not run)"]
    staged = json.loads(imy.read("STAGED.json"))["sha1"]
    missing = []
    for rel in staged:
        rel = rel.replace("\\", "/")
        if rel.startswith("source/"):  # the content tree is keyed by its folder name in STAGED.json and sits under godot_project/content in the package
            rel = "godot_project/content/" + rel
        if rel.endswith(".py"):
            if rel not in names and rel + "c" not in names and rel[:-3] + ".pyc" not in names:
                missing.append(rel)
        elif rel not in names:
            missing.append(rel)
    if missing:
        problems.append("%d staged files are not in the packed sources, e.g. %s" % (len(missing), missing[:6]))
    for must in ("wizard_rts/data/ai_wizards.json", "wizard_rts/narrative/party.py", "wizard_rts/net/ai_wizard.py", "wizard_rts/net/pvp.py", "wizard_rts/data/narrative/config.json"):
        if must not in staged and must.replace("\\", "/") not in {k.replace("\\", "/") for k in staged}:
            problems.append("the Wizard World file %s was not staged" % must)
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("apk")
    ap.add_argument("--client-only", action="store_true", help="a plain Godot export: no Python runtime expected")
    ap.add_argument("--skip-assets", action="store_true", help="skip the art/data audit (it needs the repository next to the script)")
    ap.add_argument("--expect-version", default="", help="the version name the manifest must carry (a UTF-16 string search in the binary manifest)")
    args = ap.parse_args(argv)
    with zipfile.ZipFile(args.apk) as z:
        names = z.namelist()
        manifest = z.read("AndroidManifest.xml") if "AndroidManifest.xml" in names else b""
        problems = []
        if not args.client_only:
            problems += packed_python_problems(z)
    py = [n for n in names if n.startswith("assets/chaquopy/")]
    libs = [n for n in names if n.startswith("lib/")]
    abis = sorted({n.split("/")[1] for n in libs})
    python_libs = [n for n in libs if "libpython3" in n]
    godot = [n for n in libs if "libgodot" in n]
    print("APK entries:", len(names), "chaquopy assets:", len(py), "native libs:", len(libs), "abis:", abis)
    print("python runtime:", python_libs[:3])
    print("godot:", godot[:2])
    print("packed sources:", "assets/chaquopy/app.imy" in names)
    if abis != ["arm64-v8a"]:
        problems.append("expected only arm64-v8a, got %s" % abis)
    if not godot:
        problems.append("no Godot library")
    if not args.client_only:
        if not python_libs:
            problems.append("no CPython runtime (Chaquopy did not run)")
        if "assets/chaquopy/app.imy" not in names:
            problems.append("the Python sources are not packed (stage_python.py / chaquopy sourceSets)")
    if args.expect_version:
        needle = args.expect_version.encode("utf-16-le")
        print("manifest version %s:" % args.expect_version, needle in manifest)
        if needle not in manifest:
            problems.append("the manifest does not carry version %s" % args.expect_version)
    if not args.skip_assets:
        asset_problems, stats = asset_audit.audit(Path(args.apk))
        print("ASSET_AUDIT", json.dumps(stats, sort_keys=True))
        problems += asset_problems
    for p in problems:
        print("APK_PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Print what an exported DuelMasterBattle APK contains and fail if it is not what a phone needs.

    python3 scripts/android/inspect_apk.py build/android/DuelMasterBattle-debug.apk [--client-only]

Checks: arm64-v8a only, the Godot library, and (unless --client-only) the Chaquopy CPython runtime plus the packed
`wizard_rts` sources (`assets/chaquopy/app.imy`). Signing is checked by the caller with apksigner (v2 signatures live in the
APK signing block, not in META-INF)."""

from __future__ import annotations

import argparse
import sys
import zipfile


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("apk")
    ap.add_argument("--client-only", action="store_true", help="a plain Godot export: no Python runtime expected")
    args = ap.parse_args(argv)
    with zipfile.ZipFile(args.apk) as z:
        names = z.namelist()
    py = [n for n in names if n.startswith("assets/chaquopy/")]
    libs = [n for n in names if n.startswith("lib/")]
    abis = sorted({n.split("/")[1] for n in libs})
    python_libs = [n for n in libs if "libpython3" in n]
    godot = [n for n in libs if "libgodot" in n]
    print("APK entries:", len(names), "chaquopy assets:", len(py), "native libs:", len(libs), "abis:", abis)
    print("python runtime:", python_libs[:3])
    print("godot:", godot[:2])
    print("packed sources:", "assets/chaquopy/app.imy" in names)
    problems = []
    if abis != ["arm64-v8a"]:
        problems.append("expected only arm64-v8a, got %s" % abis)
    if not godot:
        problems.append("no Godot library")
    if not args.client_only:
        if not python_libs:
            problems.append("no CPython runtime (Chaquopy did not run)")
        if "assets/chaquopy/app.imy" not in names:
            problems.append("the Python sources are not packed (stage_python.py / chaquopy sourceSets)")
    for p in problems:
        print("APK_PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

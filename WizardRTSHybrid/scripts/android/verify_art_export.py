#!/usr/bin/env python3
"""Prove that art chosen from the catalogue at run time loads from an EXPORTED game, not just from the editor.

    python3 scripts/android/verify_art_export.py [--godot PATH] [--keep]

It exports the project to a `.pck` (the same resource packing an Android export does: imported textures only, no source PNGs), then runs
`client/tests/run_art_export_probe.gd` from that pack in an empty working directory, so `res://` can only resolve to what the package holds.
The probe loads every catalogue image through `hybrid_art.gd` (lazily, as the game does), plays an animated sheet and state frames, loads the duel art through
`art.gd`, and prints `ART_PROBE_OK`. A control line shows that the source PNG is unreadable in that environment (which is why `Image.load` drew nothing on
the phones). Exit 0 only on ART_PROBE_OK. Takes a few minutes (a full export)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "godot_project"


def find_godot(explicit: str) -> str:
    if explicit:
        return explicit
    if os.environ.get("GODOT"):
        return os.environ["GODOT"]
    local = ROOT / ".dmb_windows_local.json"
    if local.exists():
        exe = json.loads(local.read_text(encoding="utf-8")).get("godot", "")
        console = exe.replace("_win64.exe", "_win64_console.exe")
        for cand in (console, exe):
            if cand and Path(cand).exists():
                return cand
    for cand in (Path.home() / "godot451" / "Godot_v4.5.1-stable_linux.x86_64",):
        if cand.exists():
            return str(cand)
    raise SystemExit("Godot not found: pass --godot or set GODOT")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--godot", default="")
    ap.add_argument("--keep", action="store_true", help="keep the exported pack")
    ap.add_argument("--preset", default="Android Client", help="the export preset to pack (any preset exercises the same resource export)")
    args = ap.parse_args(argv)
    godot = find_godot(args.godot)
    out_dir = ROOT / "build" / "probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    pck = out_dir / "art_probe.pck"
    if pck.exists():
        pck.unlink()
    exp = subprocess.run([godot, "--headless", "--path", str(PROJECT), "--export-pack", args.preset, str(pck)], capture_output=True, text=True, timeout=1800)
    if not pck.exists():
        print((exp.stdout + exp.stderr)[-1500:])
        print("ART_EXPORT_FAIL: the pack was not written")
        return 1
    with tempfile.TemporaryDirectory() as empty:  # nothing of the repository is visible from here
        run = subprocess.run([godot, "--headless", "--main-pack", str(pck), "--script", "res://client/tests/run_art_export_probe.gd"],
                             capture_output=True, text=True, timeout=900, cwd=empty)
    lines = [l for l in (run.stdout + run.stderr).splitlines() if l.startswith("ART_PROBE")]
    print("\n".join(lines))
    if not args.keep:
        pck.unlink(missing_ok=True)
    if "ART_PROBE_OK" not in lines:
        print("ART_EXPORT_FAIL: the exported pack did not load the catalogue art")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

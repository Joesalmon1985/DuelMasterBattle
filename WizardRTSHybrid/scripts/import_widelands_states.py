#!/usr/bin/env python3
"""Import the building state animations the first Widelands import left out: working, build, unoccupied, empty (plan v2 8.2/8.3).

The first importer (import_assets.generic_items) kept only `idle`. The Lua of each building declares more animations; this script adds
every one whose frames exist as `widelands.<building>.<state>` sheets (spritesheet `<state>_1.png`, or numbered frames
`<state>_00.png ...` stitched into a strip) and records, per building, which declared animations still have no files at all.

Art source: the installed Widelands data (default /usr/share/games/widelands/data, package 1.3.1) because the pinned `external/widelands`
checkout holds only Lua and maps. Run: python3 scripts/import_widelands_states.py [path/to/widelands/data]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

HYB = Path(__file__).resolve().parents[1]
ART = HYB.parent / "godot_project" / "client" / "hybrid" / "art"
CAT = ART / "catalogue.json"
DEFS = HYB / "wizard_rts" / "data" / "widelands_defs.json"
STATES = ("working", "build", "unoccupied", "empty")
LICENSE = "Widelands artwork, GPL-2.0-or-later (data/tribes). Copied from the installed Widelands package; Widelands copyright holders credited in its data/txts/AUTHORS."


def frames_of(base: Path, state: str) -> list[Path]:
    return sorted(p for p in base.glob(f"{state}_[0-9][0-9].png") if not p.stem.endswith("_pc"))


def fill_idle(by_id: dict) -> int:
    """Sites that only declare working/build/unoccupied sheets (ferry yard, clay pit...) get a still idle item: the first frame of their working (or unoccupied) sheet."""
    n = 0
    for key in sorted(by_id):
        if not key.endswith(".working"):
            continue
        base = key[: -len(".working")]
        if base in by_id:
            continue
        src = dict(by_id.get(base + ".unoccupied") or by_id[key])
        src.update(id=base, state="idle", frames=1, fps=0, source_note=f"{base} idle: first frame of its {src.get('state', 'working')} sheet (fill_idle)")
        by_id[base] = src
        n += 1
    return n


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/usr/share/games/widelands/data")
    if not root.is_dir():
        print("no Widelands data at", root)
        return 2
    defs = json.loads(DEFS.read_text())["buildings"]
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in cat["items"]}
    added, no_files = 0, {}
    for name, b in sorted(defs.items()):
        if not b.get("runnable"):
            continue
        base = root / b["dir"]
        for state in STATES:
            meta = b["spritesheets"].get(state) or b["animations"].get(state)
            if meta is None:
                continue
            dest_rel = f"widelands/gen/{name}_{state}.png"
            sheet_file = base / f"{state}_1.png"
            seq = frames_of(base, state)
            if b["spritesheets"].get(state) and sheet_file.is_file():
                cols, rows, n = int(meta.get("columns", 1)), int(meta.get("rows", 1)), int(meta.get("frames", 1))
                im = Image.open(sheet_file).convert("RGBA")
            elif seq:
                frames = [Image.open(p).convert("RGBA") for p in seq]
                w, h = frames[0].size
                im = Image.new("RGBA", (w * len(frames), h))
                for k, f in enumerate(frames):
                    im.paste(f, (k * w, 0))
                cols, rows, n = len(frames), 1, len(frames)
            else:
                no_files.setdefault(name, []).append(state)
                continue
            (ART / dest_rel).parent.mkdir(parents=True, exist_ok=True)
            im.save(ART / dest_rel)
            idle = b["animations"].get("idle") or b["spritesheets"].get("idle") or {}
            by_id[f"widelands.{name}.{state}"] = {
                "id": f"widelands.{name}.{state}", "status": "imported", "game": "widelands", "license": LICENSE, "source": f"{b['dir']}/{state}",
                "source_note": f"{name} {state} animation (import_widelands_states.py)", "godot": f"res://client/hybrid/art/{dest_rel}", "mode": "sheet",
                "width": im.width, "height": im.height, "columns": cols, "rows": rows, "frames": n, "hotspot": list(meta.get("hotspot") or idle.get("hotspot") or [0, 0]),
                "scale": 2, "fps": int(meta.get("fps", 10)) if n > 1 else 0, "state": state}
            added += 1
    fill_idle(by_id)
    cat["items"] = sorted(by_id.values(), key=lambda i: i["id"])
    CAT.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    out = HYB / "docs" / "evidence" / "assets"
    out.mkdir(parents=True, exist_ok=True)
    (out / "widelands_state_gaps.json").write_text(json.dumps({"declared_without_files": no_files}, indent=1, sort_keys=True))
    print(f"added {added} state sheets; {len(no_files)} buildings declare an animation with no image files (they draw idle)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

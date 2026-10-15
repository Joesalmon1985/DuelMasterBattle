"""Extract the OpenRA MCV (mcv.shp, 32 facings) and Construction Yard (fact.shp frame 0 idle, 26 damaged-idle) art.

Source: the player's own Red Alert content (conquer.mix, from OpenRA's content installer), read with scripts/mix_read.py and decoded
with scripts/shp_td.py using the temperat palette of the earlier extraction. Output goes to godot_project/client/hybrid/art/openra and
the catalogue, the same way the other OpenRA items were imported. Use of the artwork was permitted for this project (docs/LICENSES.md).
Run: python3 scripts/import_openra_mcv.py [path/to/conquer.mix]
"""
from __future__ import annotations
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from wizard_rts import freeze_guard  # noqa: E402  (content is frozen: D33)
freeze_guard.require_unfreeze(__file__)

import json
import sys
from pathlib import Path

from PIL import Image

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB / "scripts"))
import mix_read  # noqa: E402
import shp_td  # noqa: E402

ART = HYB.parent / "godot_project" / "client" / "hybrid" / "art"
CAT = ART / "catalogue.json"
MIX = "/home/joe/Videos/.config/openra/Content/ra/v2/conquer.mix"
LICENSE = "Extracted from the player's own Red Alert content with the OpenRA package format. Use was permitted for this project. The OpenRA engine is GPL-3.0-or-later. The original Red Alert artwork is not relicensed by this copy."
CELL = 64.0 / 24.0


def png(raw: bytes, w: int, h: int, palette: list[int], path: Path) -> None:
    im = Image.frombytes("P", (w, h), raw)
    im.putpalette(palette)
    rgba = im.convert("RGBA")
    px = rgba.load()
    for y in range(h):
        for x in range(w):
            if raw[y * w + x] == 0:
                px[x, y] = (0, 0, 0, 0)
    rgba.save(path)


def main() -> None:
    mix = mix_read.Mix(sys.argv[1] if len(sys.argv) > 1 else MIX)
    palette = Image.open(ART / "openra" / "weap-0000.png").getpalette()
    items = []
    w, h, frames = shp_td.read_shp(mix.read("MCV.SHP"))
    paths = []
    for i, raw in enumerate(frames):
        png(raw, w, h, palette, ART / "openra" / f"mcv-{i:04d}.png")
        paths.append(f"res://client/hybrid/art/openra/mcv-{i:04d}.png")
    items.append({
        "id": "openra.mcv", "status": "imported", "game": "openra", "license": LICENSE, "source": "mcv.shp sequence idle Facings 32 (classic)",
        "source_note": "mods/ra sequence, decoded from conquer.mix with the temperat palette", "godot": paths[0], "frames_godot": paths,
        "mode": "sequence", "frame_indexes": list(range(32)), "facings": 32, "facing_count": 32, "length": 1, "hotspot": [w // 2, h // 2],
        "scale": CELL, "fps": 0, "prefix": "mcv",
    })
    w, h, frames = shp_td.read_shp(mix.read("FACT.SHP"))
    paths = []
    for i in (0, 26):
        png(frames[i], w, h, palette, ART / "openra" / f"fact-{i:04d}.png")
        paths.append(f"res://client/hybrid/art/openra/fact-{i:04d}.png")
    items.append({
        "id": "openra.fact", "status": "imported", "game": "openra", "license": LICENSE, "source": "fact.shp sequence idle (0) and damaged-idle (26)",
        "source_note": "mods/ra sequence, decoded from conquer.mix with the temperat palette", "godot": paths[0], "frames_godot": paths,
        "mode": "sequence", "frame_indexes": [0, 26], "facings": 1, "length": 1, "hotspot": [0, 0], "scale": CELL, "fps": 0, "prefix": "fact",
        "footprint_cells": [3, 3], "damaged_frame": 26,
    })
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    ids = {i["id"] for i in items}
    cat["items"] = [i for i in cat["items"] if i["id"] not in ids] + items
    CAT.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    print("MCV 32 facings and Construction Yard (2 frames) merged")


if __name__ == "__main__":
    main()

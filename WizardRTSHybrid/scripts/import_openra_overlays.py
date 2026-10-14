"""War factory art repair: add the roll-up door overlay (weap3.shp, sequence `build-top`) and fit the buildings to the grid.

Why: OpenRA draws a WEAP as the `idle` frame of weap.shp (the base, with the bay left open and black) plus the
WithProductionDoorOverlay `build-top` frames of weap3.shp laid exactly over it. The first import kept only the base, so the
war factory showed a black rectangle. weap3.shp is a loose file in mods/ra/bits (GPL OpenRA repository); it is decoded here with
scripts/shp_td.py using the palette of the already extracted frames. Also sets each OpenRA land building to one OpenRA cell
(24 px) per grid tile (TPX 64 / 24) and records its footprint in cells.
Run: python3 scripts/import_openra_overlays.py
"""
from __future__ import annotations
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from wizard_rts import freeze_guard  # noqa: E402  (content is frozen: D33)
freeze_guard.require_unfreeze(__file__)

import glob
import json
import sys
from pathlib import Path

from PIL import Image

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB / "scripts"))
import shp_td  # noqa: E402

ART = HYB.parent / "godot_project" / "client" / "hybrid" / "art"
CAT = ART / "catalogue.json"
CELL_SCALE = 64.0 / 24.0
SOURCES = [
    str(HYB / "external/openra/mods/ra/bits/weap3.shp"),
    "/var/lib/flatpak/app/net.openra.OpenRA/x86_64/stable/*/files/lib/openra/mods/ra/bits/weap3.shp",
]


def find_weap3() -> bytes:
    for pattern in SOURCES:
        for path in glob.glob(pattern):
            return Path(path).read_bytes()
    raise SystemExit("weap3.shp not found: check out OpenRA mods/ra/bits or install the OpenRA flatpak")


def main() -> None:
    w, h, frames = shp_td.read_shp(find_weap3())
    palette = Image.open(ART / "openra" / "weap-0000.png").getpalette()
    for i, raw in enumerate(frames):
        im = Image.frombytes("P", (w, h), raw)
        im.putpalette(palette)
        rgba = im.convert("RGBA")
        px = rgba.load()
        for y in range(h):
            for x in range(w):
                if raw[y * w + x] == 0:
                    px[x, y] = (0, 0, 0, 0)
        rgba.save(ART / "openra" / f"weap-top-{i:04d}.png")
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    for item in cat["items"]:
        if item["id"] == "openra.weap":
            item.update(
                scale=CELL_SCALE, footprint_cells=[3, 2], hotspot=[0, 0], overlay_prefix="weap-top", overlay_length=len(frames),
                overlay_fps=8, frames_godot=[f for f in item["frames_godot"] if "weap-top" not in f]
                + [f"res://client/hybrid/art/openra/weap-top-{i:04d}.png" for i in range(len(frames))],
                source="weap.shp idle + damaged-idle; build-top from mods/ra/bits/weap3.shp",
            )
        elif item["id"] == "openra.barracks":
            item.update(scale=CELL_SCALE, footprint_cells=[2, 2], hotspot=[0, 0])
        elif item["id"] == "openra.gun":
            item.update(scale=CELL_SCALE)
    CAT.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    print(f"weap overlay: {len(frames)} frames of {w}x{h}; weap, barracks and gun fitted to the grid")


if __name__ == "__main__":
    main()

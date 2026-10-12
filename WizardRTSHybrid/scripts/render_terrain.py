"""Render a generated terrain to a PNG (one pixel per node, scaled) for inspection.
Usage: python3 scripts/render_terrain.py [seed] [size] [out.png]"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

from wizard_rts import mapgen, terrain as T  # noqa: E402

COLORS = {
    "water": (40, 90, 170), "beach": (222, 205, 140), "meadow": (86, 160, 70), "steppe": (150, 160, 80),
    "barren": (170, 150, 100), "mountain_meadow": (110, 150, 100), "mountain": (120, 110, 100),
    "snow": (240, 245, 250), "swamp": (70, 90, 60),
}
RES_COLORS = {"coal": (20, 20, 20), "iron": (200, 90, 60), "gold": (250, 210, 40), "stones": (200, 200, 210)}


def color(g: T.TerrainGrid, i: int, show_res: bool):
    name = g.palette[g.terrain[i]].replace("summer_", "")
    if show_res and g.res_kind[i] in (1, 2, 3, 4):
        return RES_COLORS[T.RES_NAMES[g.res_kind[i]]]
    for key in ("meadow", "steppe_barren", "steppe", "mountain_meadow", "forested_mountain", "mountain", "snow", "swamp", "beach", "water"):
        if name.startswith(key):
            base = {"steppe_barren": "barren", "forested_mountain": "mountain"}.get(key, key)
            c = COLORS[base]
            shade = (g.height[i] - 40) // 4 if base != "water" else 0
            return tuple(max(0, min(255, v + shade)) for v in c)
    return (255, 0, 255)


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 507
    size = sys.argv[2] if len(sys.argv) > 2 else "standard"
    out = sys.argv[3] if len(sys.argv) > 3 else f"terrain_{seed}_{size}.png"
    g = mapgen.generate(seed, size)
    img = Image.new("RGB", (g.w, g.h))
    img.putdata([color(g, i, True) for i in range(g.w * g.h)])
    px = img.load()
    for t in g.features["trees"]:
        px[t[0], t[1]] = (20, 70, 30)
    for s in g.starts:
        for d in range(-3, 4):
            px[s[0] + d, s[1]] = (255, 0, 0)
            px[s[0], s[1] + d] = (255, 0, 0)
    img.save(out)
    print(out, g.summary()["classes"])


if __name__ == "__main__":
    main()

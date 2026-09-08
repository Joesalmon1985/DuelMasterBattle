#!/usr/bin/env python3
"""Generate essence (spell) icons with a unique silhouette per essence.

Each icon is a coloured disc with a bold white glyph so the spell type is
distinguishable by shape as well as colour. Output: godot_project/assets/icons/magic_<slug>.png

Run: python tools/generate_essence_icons.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "godot_project" / "assets" / "icons"
SIZE = 128
SS = 4  # supersampling factor

# Keep in sync with godot_project/client/scripts/colour_data.gd
ESSENCES = [
    ("flame", (232, 69, 69)),
    ("frost", (63, 169, 245)),
    ("storm", (143, 163, 184)),
    ("stone", (224, 138, 46)),
    ("light", (245, 212, 66)),
    ("shadow", (91, 74, 122)),
    ("vine", (62, 207, 106)),
    ("metal", (184, 196, 204)),
    ("spirit", (242, 162, 217)),
    ("arcane", (155, 93, 229)),
]


def _poly(cx, cy, r, n, rot=-math.pi / 2):
    return [(cx + r * math.cos(rot + 2 * math.pi * i / n), cy + r * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]


def _star(cx, cy, r_out, r_in, n, rot=-math.pi / 2):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + math.pi * i / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def draw_glyph(d: ImageDraw.ImageDraw, slug: str, cx: float, cy: float, r: float, fill) -> None:
    w = r * 0.22
    if slug == "flame":
        # triangle
        d.polygon(_poly(cx, cy + r * 0.08, r, 3), fill=fill)
    elif slug == "frost":
        # six-arm snowflake
        for i in range(3):
            a = math.pi * i / 3
            x1, y1 = cx + r * math.cos(a), cy + r * math.sin(a)
            x2, y2 = cx - r * math.cos(a), cy - r * math.sin(a)
            d.line([(x1, y1), (x2, y2)], fill=fill, width=int(w))
        d.ellipse([cx - w, cy - w, cx + w, cy + w], fill=fill)
    elif slug == "storm":
        # lightning bolt
        pts = [
            (cx + r * 0.15, cy - r), (cx - r * 0.45, cy + r * 0.1), (cx - r * 0.02, cy + r * 0.1),
            (cx - r * 0.2, cy + r), (cx + r * 0.5, cy - r * 0.15), (cx + r * 0.05, cy - r * 0.15),
        ]
        d.polygon(pts, fill=fill)
    elif slug == "stone":
        # square
        s = r * 0.8
        d.rectangle([cx - s, cy - s, cx + s, cy + s], fill=fill)
    elif slug == "light":
        # sun: disc with eight short rays
        d.ellipse([cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.5], fill=fill)
        for i in range(8):
            a = math.pi * i / 4
            x1, y1 = cx + r * 0.68 * math.cos(a), cy + r * 0.68 * math.sin(a)
            x2, y2 = cx + r * 1.02 * math.cos(a), cy + r * 1.02 * math.sin(a)
            d.line([(x1, y1), (x2, y2)], fill=fill, width=int(r * 0.2))
    elif slug == "shadow":
        # crescent: full disc minus an offset disc (drawn as a polygon so it
        # composites cleanly onto other layers)
        pts = []
        steps = 96
        off = r * 0.62
        for i in range(steps + 1):
            t = math.pi * 0.5 + math.pi * 1.35 * (i / steps) - math.pi * 0.175
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
        for i in range(steps, -1, -1):
            t = math.pi * 0.5 + math.pi * 1.35 * (i / steps) - math.pi * 0.175
            pts.append((cx + off * 0.55 + r * 0.82 * math.cos(t), cy + r * 0.82 * math.sin(t)))
        d.polygon(pts, fill=fill)
    elif slug == "vine":
        # leaf: rotated ellipse made from two arcs
        pts = []
        for i in range(64):
            t = 2 * math.pi * i / 64
            x = r * 1.0 * math.cos(t)
            y = r * 0.55 * math.sin(t)
            rot = -math.pi / 4
            pts.append((cx + x * math.cos(rot) - y * math.sin(rot), cy + x * math.sin(rot) + y * math.cos(rot)))
        d.polygon(pts, fill=fill)
    elif slug == "metal":
        # hexagon
        d.polygon(_poly(cx, cy, r, 6, rot=0), fill=fill)
    elif slug == "spirit":
        # teardrop
        d.ellipse([cx - r * 0.7, cy - r * 0.2, cx + r * 0.7, cy + r * 1.0], fill=fill)
        d.polygon([(cx - r * 0.66, cy + r * 0.05), (cx, cy - r * 1.05), (cx + r * 0.66, cy + r * 0.05)], fill=fill)
    elif slug == "arcane":
        # five-point star
        d.polygon(_star(cx, cy, r * 1.05, r * 0.45, 5), fill=fill)


def _layer(big: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    return layer, ImageDraw.Draw(layer)


def make_icon(slug: str, rgb) -> Image.Image:
    # ImageDraw overwrites pixels rather than blending, so every translucent
    # element is drawn on its own layer and alpha-composited.
    big = SIZE * SS
    img, d = _layer(big)
    cx = cy = big / 2
    outer = big * 0.47
    d.ellipse([cx - outer, cy - outer, cx + outer, cy + outer], fill=(20, 16, 36, 255))
    inner = outer - big * 0.035
    d.ellipse([cx - inner, cy - inner, cx + inner, cy + inner], fill=rgb + (255,))
    # subtle top highlight
    hl_layer, hd = _layer(big)
    hl = inner * 0.86
    light = tuple(min(255, int(c * 0.35 + 255 * 0.65)) for c in rgb)
    hd.ellipse([cx - hl, cy - hl - inner * 0.12, cx + hl, cy + hl - inner * 0.12], fill=light + (60,))
    img.alpha_composite(hl_layer)
    # glyph shadow, then glyph
    glyph_r = inner * 0.52
    sh_layer, sd = _layer(big)
    draw_glyph(sd, slug, cx + big * 0.012, cy + big * 0.018, glyph_r, (0, 0, 0, 255))
    sh_layer.putalpha(sh_layer.getchannel("A").point(lambda a: a * 110 // 255))
    img.alpha_composite(sh_layer)
    g_layer, gd = _layer(big)
    draw_glyph(gd, slug, cx, cy, glyph_r, (255, 255, 255, 255))
    img.alpha_composite(g_layer)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, rgb in ESSENCES:
        make_icon(slug, rgb).save(OUT / f"magic_{slug}.png")
        print("wrote", OUT / f"magic_{slug}.png")


if __name__ == "__main__":
    main()

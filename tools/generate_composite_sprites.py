#!/usr/bin/env python3
"""Generate vector-composite cutout PNG assets at 2x resolution. See docs/ART_BIBLE.md."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "godot_project" / "assets" / "generated" / "composite"
SCALE = 2

ESSENCE_SLUGS = [
    "flame", "frost", "storm", "stone", "light",
    "shadow", "vine", "metal", "spirit", "arcane",
]
ESSENCE_COLORS = [
    (230, 25, 75), (79, 195, 247), (158, 158, 158), (121, 85, 72), (255, 241, 118),
    (66, 66, 66), (102, 187, 106), (176, 190, 197), (206, 147, 216), (126, 87, 194),
]
LOCUS_SLUGS = ["roach", "uzag", "lieana", "gyse", "vorr", "mael", "oshen", "keth"]

WIZARD_ARCHETYPES = {
    "player": (107, 140, 255),
    "blue_apprentice": (94, 179, 255),
    "thorn_adept": (107, 191, 89),
    "mirror_mage": (180, 160, 255),
    "archmage": (255, 213, 79),
    "eightfold_warden": (126, 87, 194),
}

WIZARD_PARTS = [
    "shadow", "back_aura", "back_cloak", "torso", "head", "face", "eyes",
    "hair_or_hat", "left_upper_arm", "left_forearm", "left_hand",
    "right_upper_arm", "right_forearm", "right_hand", "front_cloak",
    "chest_gem", "floating_runes", "cast_glow",
]

PART_SPECS = [
    {"name": "shadow", "z_index": 0, "offset": [0, 58]},
    {"name": "back_aura", "z_index": 1, "offset": [0, 0]},
    {"name": "back_cloak", "z_index": 2, "offset": [0, 8]},
    {"name": "torso", "z_index": 3, "offset": [0, 20]},
    {"name": "head", "z_index": 4, "offset": [0, -18]},
    {"name": "face", "z_index": 5, "offset": [0, -16]},
    {"name": "eyes", "z_index": 6, "offset": [0, -20]},
    {"name": "hair_or_hat", "z_index": 7, "offset": [0, -28]},
    {"name": "left_upper_arm", "z_index": 8, "offset": [-28, 12]},
    {"name": "left_forearm", "z_index": 9, "offset": [-36, 32]},
    {"name": "left_hand", "z_index": 10, "offset": [-40, 48]},
    {"name": "right_upper_arm", "z_index": 8, "offset": [28, 12]},
    {"name": "right_forearm", "z_index": 9, "offset": [36, 32]},
    {"name": "right_hand", "z_index": 10, "offset": [40, 48]},
    {"name": "front_cloak", "z_index": 11, "offset": [0, 24]},
    {"name": "chest_gem", "z_index": 12, "offset": [0, 22]},
    {"name": "floating_runes", "z_index": 13, "offset": [0, -40]},
    {"name": "cast_glow", "z_index": 14, "offset": [0, 10], "tint": [1.0, 0.9, 0.5, 0.7]},
]


def s(v: int) -> int:
    return v * SCALE


def new_canvas(w: int, h: int) -> Image.Image:
    return Image.new("RGBA", (s(w), s(h)), (0, 0, 0, 0))


def add_glow(img: Image.Image, color: tuple, radius: int = 8) -> Image.Image:
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    glow.paste(color + (120,), (0, 0), img.split()[-1])
    glow = glow.filter(ImageFilter.GaussianBlur(s(radius)))
    return Image.alpha_composite(glow, img)


def add_outline(img: Image.Image, width: int = 2, color: tuple = (26, 16, 48, 200)) -> Image.Image:
    w, h = img.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    alpha = img.split()[-1]
    for dx in range(-s(width), s(width) + 1):
        for dy in range(-s(width), s(width) + 1):
            if dx * dx + dy * dy > s(width) * s(width):
                continue
            shifted = ImageChops.offset(alpha, dx, dy)
            layer = Image.new("RGBA", (w, h), color)
            layer.putalpha(shifted)
            out = Image.alpha_composite(out, layer)
    return Image.alpha_composite(out, img)


def save_part(path: Path, img: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    outlined = add_outline(img)
    outlined.save(path)


def draw_gradient_ellipse(draw: ImageDraw.ImageDraw, box: tuple, c1: tuple, c2: tuple) -> None:
    draw.ellipse(box, fill=c1 + (255,))
    inner = (box[0] + s(4), box[1] + s(4), box[2] - s(4), box[3] - s(4))
    draw.ellipse(inner, fill=c2 + (200,))


def gen_wizard_part(part: str, accent: tuple) -> Image.Image:
    img = new_canvas(96, 96)
    draw = ImageDraw.Draw(img)
    dark = tuple(max(0, c - 60) for c in accent)
    light = tuple(min(255, c + 40) for c in accent)
    if part == "shadow":
        draw.ellipse((s(18), s(70), s(78), s(88)), fill=(0, 0, 0, 90))
    elif part == "back_aura":
        draw_gradient_ellipse(draw, (s(8), s(8), s(88), s(88)), accent, (255, 255, 255))
    elif part in ("back_cloak", "front_cloak"):
        draw.polygon([(s(48), s(10)), (s(12), s(85)), (s(84), s(85))], fill=dark + (220,))
        draw.line([(s(48), s(10)), (s(48), s(85))], fill=light + (180,), width=s(2))
    elif part == "torso":
        draw.rounded_rectangle((s(30), s(20), s(66), s(70)), radius=s(10), fill=accent + (255,))
    elif part == "head":
        draw.ellipse((s(32), s(8), s(64), s(40)), fill=light + (255,))
    elif part == "face":
        draw.ellipse((s(36), s(16), s(60), s(36)), fill=(240, 220, 200, 255))
    elif part == "eyes":
        draw.ellipse((s(40), s(22), s(46), s(28)), fill=(30, 20, 50, 255))
        draw.ellipse((s(50), s(22), s(56), s(28)), fill=(30, 20, 50, 255))
    elif part == "hair_or_hat":
        draw.pieslice((s(28), s(0), s(68), s(36)), 180, 360, fill=dark + (255,))
    elif "arm" in part or "hand" in part:
        draw.rounded_rectangle((s(36), s(36), s(60), s(56)), radius=s(6), fill=light + (255,))
    elif part == "chest_gem":
        draw.polygon([(s(48), s(40)), (s(42), s(52)), (s(54), s(52))], fill=(255, 220, 100, 255))
    elif part == "floating_runes":
        for i, ang in enumerate([0, 90, 180, 270]):
            x = s(48) + int(math.cos(math.radians(ang)) * s(28))
            y = s(48) + int(math.sin(math.radians(ang)) * s(20))
            draw.ellipse((x - s(4), y - s(4), x + s(4), y + s(4)), fill=accent + (200,))
    elif part == "cast_glow":
        draw_gradient_ellipse(draw, (s(20), s(20), s(76), s(76)), (255, 230, 120), accent)
    return add_glow(img, accent, 6)


def gen_wizards() -> None:
    for arch, accent in WIZARD_ARCHETYPES.items():
        folder = OUT / "wizards" / arch
        folder.mkdir(parents=True, exist_ok=True)
        for part in WIZARD_PARTS:
            save_part(folder / f"{part}.png", gen_wizard_part(part, accent))
        manifest = {"archetype": arch, "parts": PART_SPECS}
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))


def gen_essence_layer(slug: str, color: tuple, layer: str) -> Image.Image:
    img = new_canvas(64, 64)
    draw = ImageDraw.Draw(img)
    light = tuple(min(255, c + 50) for c in color)
    if layer == "core_glyph":
        if slug == "flame":
            draw.polygon([(s(32), s(8)), (s(48), s(48)), (s(16), s(48))], fill=light + (255,))
        elif slug == "frost":
            draw.polygon([(s(32), s(10)), (s(44), s(30)), (s(32), s(54)), (s(20), s(30))], fill=light + (255,))
        elif slug == "storm":
            draw.line([(s(28), s(12)), (s(40), s(32)), (s(30), s(32)), (s(38), s(52))], fill=light + (255,), width=s(3))
        else:
            draw.ellipse((s(16), s(16), s(48), s(48)), fill=light + (255,))
    elif layer == "inner_glow":
        draw_gradient_ellipse(draw, (s(12), s(12), s(52), s(52)), color, (255, 255, 255))
    elif layer == "outer_aura":
        draw.ellipse((s(4), s(4), s(60), s(60)), outline=color + (120,), width=s(3))
    elif layer == "trail":
        for i in range(4):
            draw.ellipse((s(40 + i * 4), s(28), s(48 + i * 4), s(36)), fill=color + (80 - i * 15,))
    elif layer == "spark":
        draw.ellipse((s(26), s(26), s(38), s(38)), fill=(255, 255, 255, 180))
    return img


def gen_essences() -> None:
    for slug, color in zip(ESSENCE_SLUGS, ESSENCE_COLORS):
        folder = OUT / "essences" / slug
        folder.mkdir(parents=True, exist_ok=True)
        for layer in ["core_glyph", "inner_glow", "outer_aura", "trail", "spark"]:
            save_part(folder / f"{layer}.png", gen_essence_layer(slug, color, layer))


def gen_wards() -> None:
    folder = OUT / "wards"
    folder.mkdir(parents=True, exist_ok=True)
    for part, fn in [
        ("outer_ring", lambda d: d.ellipse((s(4), s(4), s(124), s(84)), outline=(107, 92, 231, 255), width=s(4))),
        ("inner_ring", lambda d: d.ellipse((s(16), s(12), s(112), s(76)), outline=(79, 195, 247, 200), width=s(2))),
        ("runes", lambda d: [d.arc((s(20), s(16), s(108), s(72)), i, i + 40, fill=(255, 201, 71, 180), width=s(2)) for i in range(0, 360, 45)]),
        ("surface", lambda d: draw_gradient_ellipse(d, (s(20), s(16), s(108), s(72)), (45, 38, 80), (30, 26, 53))),
        ("cracks", lambda d: d.line([(s(30), s(20)), (s(50), s(50)), (s(70), s(30))], fill=(102, 255, 153, 220), width=s(3))),
        ("instability", lambda d: d.ellipse((s(24), s(20), s(104), s(68)), outline=(255, 100, 120, 180), width=s(2))),
    ]:
        img = new_canvas(128, 88)
        draw = ImageDraw.Draw(img)
        result = fn(draw)
        if result is None:
            pass
        save_part(folder / f"{part}.png", add_glow(img, (107, 92, 231), 8))


def gen_effects() -> None:
    folder = OUT / "effects"
    folder.mkdir(parents=True, exist_ok=True)
    specs = {
        "impact_flash": ((255, 240, 200), lambda d: d.ellipse((s(20), s(20), s(76), s(76)), fill=(255, 240, 200, 200))),
        "shockwave_ring": ((79, 195, 247), lambda d: d.ellipse((s(8), s(8), s(88), s(88)), outline=(79, 195, 247, 220), width=s(4))),
        "ward_ripple": ((126, 87, 194), lambda d: d.ellipse((s(16), s(16), s(80), s(80)), outline=(126, 87, 194, 160), width=s(2))),
        "fracture_glyph": ((102, 255, 153), lambda d: d.line([(s(20), s(20)), (s(60), s(60))], fill=(102, 255, 153, 255), width=s(4))),
        "echo_ring": ((255, 184, 77), lambda d: d.ellipse((s(16), s(16), s(64), s(64)), outline=(255, 184, 77, 255), width=s(3))),
        "fade_mote": ((168, 168, 184), lambda d: d.ellipse((s(28), s(28), s(52), s(52)), fill=(168, 168, 184, 180))),
    }
    for name, (accent, draw_fn) in specs.items():
        img = new_canvas(96, 96)
        draw = ImageDraw.Draw(img)
        draw_fn(draw)
        save_part(folder / f"{name}.png", add_glow(img, accent, 6))


def gen_ui() -> None:
    folder = OUT / "ui"
    folder.mkdir(parents=True, exist_ok=True)
    for name, pressed in [("button_gem", False), ("button_gem_pressed", True)]:
        img = new_canvas(96, 96)
        draw = ImageDraw.Draw(img)
        c1 = (61, 53, 128) if not pressed else (42, 36, 96)
        c2 = (107, 92, 231)
        draw.rounded_rectangle((s(8), s(8), s(88), s(88)), radius=s(20), fill=c1 + (255,))
        draw.rounded_rectangle((s(12), s(12), s(84), s(84)), radius=s(16), outline=(255, 201, 71, 255), width=s(3))
        draw.ellipse((s(28), s(20), s(68), s(40)), fill=(255, 255, 255, 60))
        save_part(folder / f"{name}.png", add_glow(img, c2, 8))
    img = new_canvas(72, 72)
    draw = ImageDraw.Draw(img)
    draw.ellipse((s(4), s(4), s(68), s(68)), outline=(255, 201, 71, 255), width=s(4))
    save_part(folder / "timer_ring.png", img)


def gen_loci() -> None:
    for i, slug in enumerate(LOCUS_SLUGS):
        folder = OUT / "loci" / slug
        folder.mkdir(parents=True, exist_ok=True)
        color = ESSENCE_COLORS[i % len(ESSENCE_COLORS)]
        for state, alpha in [("rune_empty", 120), ("rune_filled", 255)]:
            img = new_canvas(48, 48)
            draw = ImageDraw.Draw(img)
            draw.ellipse((s(6), s(6), s(42), s(42)), outline=color + (alpha,), width=s(3))
            draw.line([(s(24), s(12)), (s(24), s(36))], fill=color + (alpha,), width=s(2))
            save_part(folder / f"{state}.png", img)


def main() -> None:
    gen_wizards()
    gen_essences()
    gen_wards()
    gen_effects()
    gen_ui()
    gen_loci()
    print(f"Generated composite assets under {OUT}")


if __name__ == "__main__":
    main()

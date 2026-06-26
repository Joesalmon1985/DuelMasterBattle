#!/usr/bin/env python3
"""Generate draft wizard-duel placeholder PNG sprites."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "godot_project" / "assets" / "sprites"
ICONS = ROOT / "godot_project" / "assets" / "icons"

MAGIC = [
    ("flame", "#e6194b", "Fr", "Flame"),
    ("frost", "#4fc3f7", "Fs", "Frost"),
    ("storm", "#9e9e9e", "St", "Storm"),
    ("stone", "#795548", "Sn", "Stone"),
    ("light", "#fff176", "Li", "Light"),
    ("shadow", "#424242", "Sh", "Shadow"),
    ("vine", "#66bb6a", "Vi", "Vine"),
    ("metal", "#b0bec5", "Me", "Metal"),
    ("spirit", "#ce93d8", "Sp", "Spirit"),
    ("arcane", "#7e57c2", "Ar", "Arcane"),
]

LOCI = [
    ("roach", "#546e7a", "Ro", "Roach"),
    ("uzag", "#8d6e63", "Uz", "Uzag"),
    ("lieana", "#6d4c41", "Li", "Lieana"),
    ("gyse", "#5e35b1", "Gy", "Gyse"),
    ("vorr", "#37474f", "Vo", "Vorr"),
    ("mael", "#00838f", "Ma", "Mael"),
    ("oshen", "#1565c0", "Os", "Oshen"),
    ("keth", "#6a1b9a", "Ke", "Keth"),
]

FEEDBACK = [
    ("hit", "#212121", "Fc", "Fracture"),
    ("weakness", "#757575", "Ec", "Echo"),
    ("unaffected", "#bdbdbd", "Fd", "Fade"),
    ("clash", "#ff6f00", "Cl", "Clash"),
    ("stalemate", "#9e9e9e", "St", "Stalemate"),
    ("last_stand", "#d32f2f", "LS", "LastStand"),
]

ENEMIES = [
    ("enemy_blue_apprentice.png", "#3949ab", "Blue"),
    ("enemy_thorn_adept.png", "#2e7d32", "Thorn"),
    ("enemy_mirror_mage.png", "#7b1fa2", "Mirror"),
    ("enemy_archmage.png", "#c62828", "Arch"),
    ("enemy_eightfold_warden.png", "#4527a0", "Warden"),
]


def _hex(c: str) -> tuple:
    c = c.lstrip("#")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))


def _draw_icon(path: Path, bg: str, sym: str, label: str, size: int = 64) -> None:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([2, 2, size - 3, size - 3], radius=8, fill=_hex(bg) + (255,))
    draw.text((8, 8), sym, fill=(255, 255, 255, 255))
    draw.text((8, size - 18), label[:6], fill=(255, 255, 255, 200))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def _draw_wizard(path: Path, bg: str, label: str, size: tuple = (96, 128)) -> None:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([8, 8, w - 8, h - 8], radius=12, fill=_hex(bg) + (255,))
    draw.ellipse([w // 2 - 16, 20, w // 2 + 16, 52], fill=(255, 220, 180, 255))
    draw.polygon([(w // 2, 8), (w // 2 - 20, 28), (w // 2 + 20, 28)], fill=(100, 50, 150, 255))
    draw.text((12, h - 28), label, fill=(255, 255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def _draw_background(path: Path) -> None:
    img = Image.new("RGBA", (320, 480), (30, 30, 50, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([4, 4, 316, 476], radius=10, outline=(120, 100, 180, 255), width=3)
    draw.text((12, 12), "Ward Duel", fill=(200, 200, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def main() -> None:
    for slug, bg, sym, label in MAGIC:
        _draw_icon(ICONS / f"magic_{slug}.png", bg, sym, label)
    for slug, bg, sym, label in LOCI:
        _draw_icon(ICONS / f"locus_{slug}.png", bg, sym, label)
        if slug in ("roach", "uzag", "lieana", "gyse"):
            _draw_icon(ICONS / f"point_{'shield' if slug=='roach' else 'body' if slug=='uzag' else 'staff' if slug=='lieana' else 'mind'}.png", bg, sym, label)
    for slug, bg, sym, label in FEEDBACK:
        _draw_icon(ICONS / f"feedback_{slug}.png", bg, sym, label)
    _draw_wizard(SPRITES / "player_wizard.png", "#3949ab", "You")
    _draw_wizard(SPRITES / "enemy_wizard.png", "#c62828", "Rival")
    for fname, bg, label in ENEMIES:
        _draw_wizard(SPRITES / fname, bg, label)
    _draw_background(SPRITES / "duel_background.png")
    print(f"Generated sprites in {SPRITES} and {ICONS}")


if __name__ == "__main__":
    main()

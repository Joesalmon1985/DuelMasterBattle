#!/usr/bin/env python3
"""Import and downscale dark-fantasy sprites from 'Spare Sprites' into the project,
and generate pixel-art placeholders for everything the pack lacks (John, creatures,
overworld tiles, props).

Everything lands under godot_project/assets/pixel/. Deterministic; safe to re-run.

  python tools/build_pixel_assets.py
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Spare Sprites" / "dark-fantasy-adventure-sprites"
OUT = ROOT / "godot_project" / "assets" / "pixel"

TILE = 16  # native tile size; the game renders at 4x

# ---------------------------------------------------------------- palettes
INK = (16, 12, 24)
PAL = {
    "grass_a": (52, 84, 46), "grass_b": (60, 96, 52), "grass_c": (44, 72, 40),
    "path_a": (120, 100, 72), "path_b": (108, 90, 64),
    "dirt": (74, 58, 44), "ash": (58, 52, 60), "ash_b": (48, 44, 52),
    "water_a": (36, 64, 112), "water_b": (48, 84, 136),
    "wall": (86, 74, 66), "wall_b": (70, 60, 54), "roof": (110, 48, 42), "roof_b": (92, 40, 36),
    "wood": (94, 66, 40), "wood_b": (76, 52, 32),
    "trunk": (70, 48, 30), "leaf_a": (34, 70, 40), "leaf_b": (46, 92, 52), "leaf_c": (26, 54, 32),
    "stone": (120, 118, 124), "stone_b": (92, 90, 98),
    "fire_a": (255, 200, 60), "fire_b": (240, 120, 40), "fire_c": (200, 60, 30),
    "skin": (222, 178, 140), "shirt": (150, 60, 50), "trouser": (60, 58, 80), "boot": (50, 36, 28), "hair": (80, 50, 30),
    "steel": (190, 196, 210),
}


def px(d: ImageDraw.ImageDraw, x, y, c):
    d.point((x, y), c)


def new(w=TILE, h=TILE, bg=(0, 0, 0, 0)):
    im = Image.new("RGBA", (w, h), bg)
    return im, ImageDraw.Draw(im)


def save(im: Image.Image, rel: str):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    im.save(p)


# ---------------------------------------------------------------- tiles
def tile_noise(base, alt, density, seed):
    rnd = random.Random(seed)
    im, d = new(bg=base + (255,))
    for _ in range(int(TILE * TILE * density)):
        px(d, rnd.randrange(TILE), rnd.randrange(TILE), alt + (255,))
    return im


def make_tiles():
    save(tile_noise(PAL["grass_a"], PAL["grass_b"], 0.18, 1), "tiles/grass.png")
    save(tile_noise(PAL["grass_a"], PAL["grass_c"], 0.22, 2), "tiles/grass_dark.png")
    save(tile_noise(PAL["path_a"], PAL["path_b"], 0.25, 3), "tiles/path.png")
    save(tile_noise(PAL["dirt"], PAL["ash_b"], 0.2, 4), "tiles/dirt.png")
    save(tile_noise(PAL["ash"], PAL["ash_b"], 0.3, 5), "tiles/ash.png")
    # water with two highlight lines
    im, d = new(bg=PAL["water_a"] + (255,))
    for y in (4, 11):
        d.line([(1, y), (6, y)], PAL["water_b"] + (255,))
        d.line([(9, y + 1), (14, y + 1)], PAL["water_b"] + (255,))
    save(im, "tiles/water.png")
    # stone wall
    im, d = new(bg=PAL["wall"] + (255,))
    for y in range(0, TILE, 4):
        d.line([(0, y), (TILE, y)], PAL["wall_b"] + (255,))
        off = 0 if (y // 4) % 2 == 0 else 4
        for x in range(off, TILE, 8):
            d.line([(x, y), (x, y + 3)], PAL["wall_b"] + (255,))
    save(im, "tiles/wall.png")
    # roof
    im, d = new(bg=PAL["roof"] + (255,))
    for y in range(0, TILE, 3):
        d.line([(0, y), (TILE, y)], PAL["roof_b"] + (255,))
    save(im, "tiles/roof.png")
    # wood floor / door
    im, d = new(bg=PAL["wood"] + (255,))
    for x in range(0, TILE, 4):
        d.line([(x, 0), (x, TILE)], PAL["wood_b"] + (255,))
    save(im, "tiles/wood.png")
    im, d = new(bg=PAL["wood_b"] + (255,))
    d.rectangle([3, 1, 12, 15], PAL["wood"] + (255,), outline=INK + (255,))
    px(d, 10, 8, PAL["fire_a"] + (255,))
    save(im, "tiles/door.png")
    # fence
    im, d = new()
    d.rectangle([0, 6, 15, 7], PAL["wood"] + (255,))
    d.rectangle([0, 10, 15, 11], PAL["wood"] + (255,))
    for x in (2, 8, 14):
        d.rectangle([x, 3, x + 1, 14], PAL["wood_b"] + (255,))
    save(im, "tiles/fence.png")
    # bridge
    im, d = new(bg=PAL["water_a"] + (255,))
    d.rectangle([0, 2, 15, 13], PAL["wood"] + (255,))
    for y in range(3, 13, 3):
        d.line([(0, y), (15, y)], PAL["wood_b"] + (255,))
    d.line([(0, 2), (15, 2)], INK + (255,))
    d.line([(0, 13), (15, 13)], INK + (255,))
    save(im, "tiles/bridge.png")


# ---------------------------------------------------------------- props (32x32)
def make_tree(seed, burnt=False):
    rnd = random.Random(seed)
    im, d = new(32, 32)
    trunk = PAL["trunk"] if not burnt else PAL["ash_b"]
    d.rectangle([14, 20, 17, 31], trunk + (255,))
    if burnt:
        # bare charred branches
        d.line([(15, 20), (9, 12)], trunk + (255,), 2)
        d.line([(16, 20), (22, 10)], trunk + (255,), 2)
        d.line([(15, 16), (12, 8)], trunk + (255,), 1)
        d.line([(19, 14), (24, 16)], trunk + (255,), 1)
        for _ in range(10):
            px(d, rnd.randrange(8, 24), rnd.randrange(6, 20), PAL["ash"] + (255,))
        return im
    # dark-fantasy conifer: layered triangles
    for i, (w, y, col) in enumerate([(26, 22, "leaf_c"), (22, 16, "leaf_a"), (18, 10, "leaf_b"), (12, 5, "leaf_a")]):
        cx = 16
        d.polygon([(cx - w // 2, y), (cx + w // 2, y), (cx, y - 8)], PAL[col] + (255,))
    for _ in range(14):
        x, y = rnd.randrange(8, 24), rnd.randrange(2, 22)
        if im.getpixel((x, y))[3]:
            px(d, x, y, PAL["leaf_c"] + (255,))
    return im


def make_fire(frame):
    im, d = new(TILE, TILE)
    rnd = random.Random(100 + frame)
    base_y = 15
    pts = [(2, base_y), (14, base_y), (12, 9 + (frame % 2)), (9, 3 + frame % 3), (7, 6), (5, 1 + (frame + 1) % 3), (3, 8)]
    d.polygon(pts, PAL["fire_c"] + (255,))
    d.polygon([(4, base_y), (12, base_y), (10, 9), (8, 5 + frame % 2), (6, 9)], PAL["fire_b"] + (255,))
    d.polygon([(6, base_y), (10, base_y), (9, 11), (8, 8 + frame % 2), (7, 11)], PAL["fire_a"] + (255,))
    for _ in range(3):
        px(d, rnd.randrange(3, 13), rnd.randrange(0, 6), PAL["fire_a"] + (200,))
    return im


def make_rock():
    im, d = new(TILE, TILE)
    d.ellipse([1, 5, 14, 15], PAL["stone_b"] + (255,))
    d.ellipse([3, 4, 12, 12], PAL["stone"] + (255,))
    d.line([(4, 12), (11, 12)], INK + (255,))
    return im


def make_log_pile():
    im, d = new(TILE, TILE)
    for (x, y) in [(2, 9), (8, 9), (5, 4)]:
        d.ellipse([x, y, x + 6, y + 6], PAL["wood"] + (255,), outline=PAL["wood_b"] + (255,))
        px(d, x + 3, y + 3, PAL["wood_b"] + (255,))
    return im


def make_pendant():
    im, d = new(TILE, TILE)
    d.polygon([(8, 2), (13, 8), (8, 14), (3, 8)], PAL["fire_b"] + (255,))
    d.polygon([(8, 4), (11, 8), (8, 12), (5, 8)], PAL["fire_a"] + (255,))
    d.line([(8, 0), (8, 2)], PAL["steel"] + (255,))
    return im


def make_stone_shard():
    im, d = new(TILE, TILE)
    d.polygon([(8, 1), (13, 6), (11, 14), (5, 14), (3, 6)], PAL["stone"] + (255,))
    d.polygon([(8, 3), (11, 6), (10, 12), (6, 12), (5, 6)], PAL["stone_b"] + (255,))
    px(d, 7, 5, (230, 230, 240, 255))
    return im


def make_seed():
    im, d = new(TILE, TILE)
    d.ellipse([4, 3, 12, 13], PAL["leaf_b"] + (255,))
    d.line([(8, 3), (8, 13)], PAL["leaf_c"] + (255,))
    d.line([(8, 3), (11, 0)], PAL["trunk"] + (255,))
    return im


def make_staff_pickup():
    im, d = new(TILE, TILE)
    d.line([(4, 15), (11, 2)], PAL["trunk"] + (255,), 2)
    d.ellipse([9, 0, 14, 5], PAL["water_b"] + (255,))
    px(d, 11, 2, (200, 230, 255, 255))
    return im


def make_sign():
    im, d = new(TILE, TILE)
    d.rectangle([7, 8, 8, 15], PAL["wood_b"] + (255,))
    d.rectangle([2, 2, 13, 8], PAL["wood"] + (255,), outline=INK + (255,))
    d.line([(4, 4), (11, 4)], INK + (255,))
    d.line([(4, 6), (9, 6)], INK + (255,))
    return im


def make_box():
    # Sukumvit's aid box: small chest with a seal.
    im, d = new(TILE, TILE)
    d.rectangle([2, 6, 13, 14], PAL["wood_b"] + (255,), outline=INK + (255,))
    d.rectangle([2, 6, 13, 9], PAL["wood"] + (255,))
    d.rectangle([7, 8, 8, 12], PAL["fire_a"] + (255,))
    return im


def make_book(red=True):
    # Leather-bound book, red or black.
    im, d = new(TILE, TILE)
    cover = (150, 40, 36) if red else (30, 28, 40)
    spine = (100, 26, 24) if red else (16, 14, 22)
    d.polygon([(3, 2), (12, 4), (12, 13), (3, 11)], cover + (255,), outline=INK + (255,))
    d.line([(3, 2), (3, 11)], spine + (255,), 2)
    d.line([(5, 5), (10, 6)], (220, 210, 190, 255,))
    d.line([(5, 8), (10, 9)], (220, 210, 190, 255,))
    return im


def make_ring():
    # Druidic bone ring.
    im, d = new(TILE, TILE)
    d.ellipse([3, 3, 12, 12], (225, 215, 190, 255))
    d.ellipse([6, 6, 9, 9], (0, 0, 0, 0))
    px(d, 5, 4, PAL["leaf_b"] + (255,))
    px(d, 10, 9, PAL["leaf_b"] + (255,))
    return im


def make_props():
    for i in range(4):
        save(make_tree(i), f"props/tree_{i}.png")
    for i in range(2):
        save(make_tree(10 + i, burnt=True), f"props/tree_burnt_{i}.png")
    for f in range(3):
        save(make_fire(f), f"props/fire_{f}.png")
    save(make_rock(), "props/rock.png")
    save(make_log_pile(), "props/logs.png")
    save(make_pendant(), "props/pendant.png")
    save(make_stone_shard(), "props/stone_shard.png")
    save(make_seed(), "props/seed.png")
    save(make_staff_pickup(), "props/staff.png")
    save(make_sign(), "props/sign.png")
    save(make_box(), "props/box.png")
    save(make_book(True), "props/book_red.png")
    save(make_book(False), "props/book_black.png")
    save(make_ring(), "props/ring.png")


# ---------------------------------------------------------------- characters (16x24, 4 dirs x 2 frames)
def draw_human(d, facing, frame, shirt, hat=None, tool=None, skin=PAL["skin"], hair=PAL["hair"]):
    # body
    d.rectangle([5, 9, 10, 16], shirt + (255,))
    # legs
    step = frame % 2
    d.rectangle([5, 17, 7, 21 + step], PAL["trouser"] + (255,))
    d.rectangle([8, 17, 10, 22 - step], PAL["trouser"] + (255,))
    d.rectangle([5, 22 + step, 7, 23], PAL["boot"] + (255,))
    d.rectangle([8, 23 - step, 10, 23], PAL["boot"] + (255,))
    # head
    d.rectangle([5, 3, 10, 8], skin + (255,))
    if facing == "down":
        d.rectangle([5, 2, 10, 4], hair + (255,))
        px(d, 6, 6, INK + (255,)); px(d, 9, 6, INK + (255,))
    elif facing == "up":
        d.rectangle([5, 2, 10, 7], hair + (255,))
    elif facing == "left":
        d.rectangle([5, 2, 10, 4], hair + (255,)); d.rectangle([9, 4, 10, 7], hair + (255,))
        px(d, 6, 6, INK + (255,))
    else:
        d.rectangle([5, 2, 10, 4], hair + (255,)); d.rectangle([5, 4, 6, 7], hair + (255,))
        px(d, 9, 6, INK + (255,))
    if hat:
        d.polygon([(4, 3), (11, 3), (8, -2)], hat + (255,))
        d.rectangle([3, 3, 12, 4], hat + (255,))
    # arms
    d.rectangle([3, 9, 4, 15], skin + (255,))
    d.rectangle([11, 9, 12, 15], skin + (255,))
    if tool == "axe":
        d.line([(12, 15), (12, 6)], PAL["wood_b"] + (255,))
        d.rectangle([12, 5, 14, 8], PAL["steel"] + (255,))
    elif tool == "staff":
        d.line([(12, 16), (12, 2)], PAL["trunk"] + (255,))
        d.ellipse([11, 0, 14, 3], PAL["water_b"] + (255,))


def make_character(name, shirt, hat=None, tool=None, hair=PAL["hair"], skin=PAL["skin"]):
    for facing in ("down", "up", "left", "right"):
        for frame in range(2):
            im, d = new(16, 24)
            draw_human(d, facing, frame, shirt, hat, tool, skin=skin, hair=hair)
            save(im, f"chars/{name}_{facing}_{frame}.png")


def make_characters():
    make_character("john", PAL["shirt"], tool="axe")
    make_character("john_staff", PAL["shirt"], tool="staff")
    make_character("villager_a", (90, 110, 140))
    make_character("villager_b", (130, 100, 60), hair=(200, 200, 200))
    make_character("elder", (70, 90, 60), hat=(60, 80, 50), tool="staff", hair=(220, 220, 220))
    make_character("child", (170, 120, 80))
    # Trial-gate contestants (P1 placeholders; refined in the P7 art pass).
    make_character("knight", (170, 178, 195), hat=(120, 128, 145), hair=(90, 90, 100))
    make_character("elf", (60, 140, 90), hair=(225, 205, 150))
    make_character("assassin", (40, 36, 52), hair=(25, 22, 30))
    make_character("throm", (200, 150, 110), hair=(120, 70, 35))
    make_character("official", (105, 90, 165), hat=(80, 65, 130), hair=(200, 200, 200))


# ---------------------------------------------------------------- creatures (battle portraits 64x64 + overworld 16x16)
def make_wisp(size, frame=0, col_a=PAL["fire_a"], col_b=PAL["fire_b"], col_c=PAL["fire_c"], eye=INK, horns=False):
    im, d = new(size, size)
    s = size
    cx = s // 2
    base = int(s * 0.9)
    wob = (frame % 2) * max(1, s // 16)
    d.polygon([(int(s * 0.15), base), (int(s * 0.85), base), (int(s * 0.75), int(s * 0.5)), (cx + s // 8, int(s * 0.15) + wob), (cx, int(s * 0.3)), (cx - s // 6, int(s * 0.05) + wob), (int(s * 0.2), int(s * 0.5))], col_c + (255,))
    d.polygon([(int(s * 0.28), base), (int(s * 0.72), base), (int(s * 0.62), int(s * 0.55)), (cx, int(s * 0.28) + wob), (int(s * 0.38), int(s * 0.55))], col_b + (255,))
    d.polygon([(int(s * 0.4), base), (int(s * 0.6), base), (cx, int(s * 0.55) + wob)], col_a + (255,))
    ey = int(s * 0.62)
    d.rectangle([int(s * 0.36), ey, int(s * 0.42), ey + max(1, s // 16)], eye + (255,))
    d.rectangle([int(s * 0.56), ey, int(s * 0.62), ey + max(1, s // 16)], eye + (255,))
    if horns:
        d.polygon([(int(s * 0.3), int(s * 0.5)), (int(s * 0.36), int(s * 0.5)), (int(s * 0.24), int(s * 0.3))], INK + (255,))
        d.polygon([(int(s * 0.64), int(s * 0.5)), (int(s * 0.7), int(s * 0.5)), (int(s * 0.76), int(s * 0.3))], INK + (255,))
        d.polygon([(int(s * 0.44), int(s * 0.74)), (int(s * 0.56), int(s * 0.74)), (int(s * 0.5), int(s * 0.8))], INK + (255,))
    return im


def make_steam(size, frame=0, big=False):
    im, d = new(size, size)
    rnd = random.Random(7 + frame)
    s = size
    col = (200, 205, 215)
    col2 = (150, 160, 180)
    blobs = 7 if big else 4
    for i in range(blobs):
        r = int(s * (0.22 if big else 0.2)) + rnd.randrange(0, max(1, s // 10))
        x = int(s * 0.5 + math.cos(i * 2.2 + frame) * s * 0.2)
        y = int(s * 0.55 + math.sin(i * 1.7 + frame) * s * 0.18)
        d.ellipse([x - r, y - r, x + r, y + r], col2 + (255,))
    for i in range(blobs):
        r = int(s * (0.17 if big else 0.15))
        x = int(s * 0.5 + math.cos(i * 2.2 + frame + 0.4) * s * 0.17)
        y = int(s * 0.52 + math.sin(i * 1.7 + frame + 0.4) * s * 0.15)
        d.ellipse([x - r, y - r, x + r, y + r], col + (255,))
    ey = int(s * 0.5)
    d.rectangle([int(s * 0.38), ey, int(s * 0.44), ey + max(1, s // 14)], (60, 90, 150, 255))
    d.rectangle([int(s * 0.56), ey, int(s * 0.62), ey + max(1, s // 14)], (60, 90, 150, 255))
    if big:
        d.rectangle([int(s * 0.42), int(s * 0.66), int(s * 0.58), int(s * 0.7)], (60, 90, 150, 255))
        # heavy fists
        r = int(s * 0.14)
        for x in (0.14, 0.86):
            d.ellipse([int(s * x) - r, int(s * 0.7) - r, int(s * x) + r, int(s * 0.7) + r], col2 + (255,))
            d.ellipse([int(s * x) - r + 2, int(s * 0.7) - r + 2, int(s * x) + r - 2, int(s * 0.7) + r - 2], col + (255,))
        # angry brow
        d.line([(int(s * 0.36), int(s * 0.45)), (int(s * 0.46), int(s * 0.48))], (60, 90, 150, 255), max(1, s // 20))
        d.line([(int(s * 0.64), int(s * 0.45)), (int(s * 0.54), int(s * 0.48))], (60, 90, 150, 255), max(1, s // 20))
    return im


def make_golem(size, frame=0):
    im, d = new(size, size)
    s = size
    st, stb, dk = PAL["stone"], PAL["stone_b"], (58, 56, 64)
    def blk(x0, y0, x1, y1, c):
        d.rectangle([int(s * x0), int(s * y0), int(s * x1), int(s * y1)], c + (255,))
    # legs
    blk(0.28, 0.78, 0.44, 0.98, stb); blk(0.56, 0.78, 0.72, 0.98, stb)
    # torso (cracked boulder)
    blk(0.22, 0.34, 0.78, 0.8, dk); blk(0.26, 0.38, 0.74, 0.76, st)
    # shoulders / arms hanging low
    blk(0.06, 0.36, 0.24, 0.5, stb); blk(0.76, 0.36, 0.94, 0.5, stb)
    blk(0.04, 0.5, 0.18, 0.82, stb); blk(0.82, 0.5, 0.96, 0.82, stb)
    blk(0.02, 0.8, 0.2, 0.9, dk); blk(0.8, 0.8, 0.98, 0.9, dk)
    # head
    blk(0.34, 0.1, 0.66, 0.36, stb); blk(0.38, 0.14, 0.62, 0.32, st)
    # cracks
    d.line([(int(s * 0.5), int(s * 0.4)), (int(s * 0.42), int(s * 0.58)), (int(s * 0.5), int(s * 0.72))], dk + (255,), max(1, s // 32))
    d.line([(int(s * 0.62), int(s * 0.44)), (int(s * 0.68), int(s * 0.6))], dk + (255,), max(1, s // 32))
    # ember eyes + core
    glow = PAL["fire_a"] if frame % 2 == 0 else PAL["fire_b"]
    r = max(1, s // 16)
    for (x, y) in [(0.43, 0.22), (0.57, 0.22)]:
        d.rectangle([int(s * x) - r, int(s * y) - r // 2, int(s * x) + r, int(s * y) + r // 2], glow + (255,))
    d.rectangle([int(s * 0.46), int(s * 0.5), int(s * 0.54), int(s * 0.6)], glow + (255,))
    return im


def make_shade(size, frame=0):
    im, d = new(size, size)
    s = size
    body, body2 = (24, 36, 30), (40, 60, 44)
    # hunched hooded silhouette with trailing roots
    d.polygon([(int(s * 0.15), int(s * 0.98)), (int(s * 0.85), int(s * 0.98)), (int(s * 0.8), int(s * 0.55)), (int(s * 0.62), int(s * 0.28)), (int(s * 0.5), int(s * 0.1)), (int(s * 0.38), int(s * 0.28)), (int(s * 0.2), int(s * 0.55))], body + (255,))
    d.polygon([(int(s * 0.28), int(s * 0.9)), (int(s * 0.72), int(s * 0.9)), (int(s * 0.68), int(s * 0.58)), (int(s * 0.5), int(s * 0.3)), (int(s * 0.32), int(s * 0.58))], body2 + (255,))
    # hood shadow
    d.polygon([(int(s * 0.38), int(s * 0.36)), (int(s * 0.62), int(s * 0.36)), (int(s * 0.58), int(s * 0.52)), (int(s * 0.42), int(s * 0.52))], INK + (255,))
    # roots/tendrils at base
    w = max(1, s // 24)
    for i, dx in enumerate((-0.32, -0.16, 0.16, 0.32)):
        x0 = int(s * (0.5 + dx * 0.5)); y0 = int(s * 0.9)
        x1 = int(s * (0.5 + dx)); y1 = int(s * (0.98 if (i + frame) % 2 == 0 else 0.94))
        d.line([(x0, y0), (x1, y1)], body + (255,), w)
    # moss speckles and leaves
    rnd = random.Random(3 + frame)
    for _ in range(int(s * 0.5)):
        x, y = rnd.randrange(int(s * 0.3), int(s * 0.7)), rnd.randrange(int(s * 0.5), int(s * 0.9))
        px(d, x, y, PAL["leaf_b"] + (255,))
    for (x, y) in [(0.3, 0.6), (0.7, 0.62), (0.5, 0.2)]:
        r = max(1, s // 20)
        d.ellipse([int(s * x) - r, int(s * y) - r, int(s * x) + r, int(s * y) + r], PAL["leaf_a"] + (255,))
    # glowing eyes in hood
    ey = int(s * 0.44)
    e = max(1, s // 16)
    d.rectangle([int(s * 0.42), ey, int(s * 0.42) + e, ey + e // 2 + 1], (180, 240, 120, 255))
    d.rectangle([int(s * 0.56), ey, int(s * 0.56) + e, ey + e // 2 + 1], (180, 240, 120, 255))
    return im


def make_dog(size, frame=0):
    # Trialmastiff: low quadruped silhouette, pale eyes. Distinct from wisps/fly.
    im, d = new(size, size)
    s = size
    fur, dark = (96, 84, 72), (52, 44, 38)
    leg = 0 if frame % 2 == 0 else max(1, s // 16)
    # body
    d.ellipse([int(s * 0.18), int(s * 0.48), int(s * 0.82), int(s * 0.78)], fur + (255,))
    d.ellipse([int(s * 0.24), int(s * 0.52), int(s * 0.76), int(s * 0.72)], dark + (255,))
    # head (right), raised
    d.ellipse([int(s * 0.66), int(s * 0.22), int(s * 0.94), int(s * 0.52)], fur + (255,))
    # ears
    d.polygon([(int(s * 0.70), int(s * 0.26)), (int(s * 0.76), int(s * 0.26)), (int(s * 0.73), int(s * 0.12))], dark + (255,))
    d.polygon([(int(s * 0.82), int(s * 0.26)), (int(s * 0.88), int(s * 0.26)), (int(s * 0.85), int(s * 0.12))], dark + (255,))
    # jaw + eye
    d.rectangle([int(s * 0.78), int(s * 0.44), int(s * 0.94), int(s * 0.50)], dark + (255,))
    e = max(1, s // 16)
    d.rectangle([int(s * 0.74), int(s * 0.32), int(s * 0.74) + e, int(s * 0.32) + e], (230, 220, 150, 255))
    # tail (left, up)
    d.line([(int(s * 0.18), int(s * 0.55)), (int(s * 0.06), int(s * 0.35))], fur + (255,), max(1, s // 24))
    # legs
    w = max(1, s // 28)
    for i, dx in enumerate((0.28, 0.44, 0.60, 0.74)):
        lift = leg if i % 2 == 0 else 0
        d.line([(int(s * dx), int(s * 0.72)), (int(s * dx), int(s * 0.96) - lift)], dark + (255,), w)
    return im


def make_troll(size, frame=0):
    # Cave troll: hulking grey-green brute with a club. Biggest silhouette yet.
    im, d = new(size, size)
    s = size
    hide, dark = (110, 128, 104), (58, 68, 58)
    sway = 0 if frame % 2 == 0 else max(1, s // 20)
    # legs
    d.rectangle([int(s * 0.30), int(s * 0.74), int(s * 0.44), int(s * 0.98)], dark + (255,))
    d.rectangle([int(s * 0.56), int(s * 0.74), int(s * 0.70), int(s * 0.98)], dark + (255,))
    # torso
    d.ellipse([int(s * 0.20), int(s * 0.34) + sway, int(s * 0.80), int(s * 0.80) + sway], hide + (255,))
    d.ellipse([int(s * 0.30), int(s * 0.42) + sway, int(s * 0.70), int(s * 0.72) + sway], dark + (255,))
    # head: low brow, underbite tusks
    d.ellipse([int(s * 0.32), int(s * 0.10), int(s * 0.68), int(s * 0.36)], hide + (255,))
    d.line([(int(s * 0.34), int(s * 0.22)), (int(s * 0.48), int(s * 0.24))], dark + (255,), max(1, s // 24))
    d.line([(int(s * 0.66), int(s * 0.22)), (int(s * 0.52), int(s * 0.24))], dark + (255,), max(1, s // 24))
    e = max(1, s // 18)
    d.rectangle([int(s * 0.40), int(s * 0.26), int(s * 0.40) + e, int(s * 0.26) + e], (240, 200, 80, 255))
    d.rectangle([int(s * 0.58), int(s * 0.26), int(s * 0.58) + e, int(s * 0.26) + e], (240, 200, 80, 255))
    d.polygon([(int(s * 0.42), int(s * 0.34)), (int(s * 0.46), int(s * 0.34)), (int(s * 0.44), int(s * 0.28))], (230, 225, 210, 255))
    d.polygon([(int(s * 0.54), int(s * 0.34)), (int(s * 0.58), int(s * 0.34)), (int(s * 0.56), int(s * 0.28))], (230, 225, 210, 255))
    # club in right fist
    d.line([(int(s * 0.84), int(s * 0.90)), (int(s * 0.90), int(s * 0.30) + sway)], PAL["wood_b"] + (255,), max(2, s // 14))
    d.ellipse([int(s * 0.78), int(s * 0.62) + sway, int(s * 0.94), int(s * 0.76) + sway], hide + (255,))
    return im


def make_fly(size, frame=0):
    # Giant horsefly: winged silhouette (distinct from flame wisps), red eyes.
    im, d = new(size, size)
    s = size
    wing, vein = (205, 215, 228), (150, 160, 180)
    body, dark = (74, 62, 96), (42, 34, 58)
    lift = 0 if frame % 2 == 0 else max(1, s // 16)
    d.ellipse([int(s * 0.06), int(s * 0.10) + lift, int(s * 0.44), int(s * 0.42) + lift], wing + (255,))
    d.ellipse([int(s * 0.56), int(s * 0.10) + lift, int(s * 0.94), int(s * 0.42) + lift], wing + (255,))
    d.line([(int(s * 0.12), int(s * 0.26) + lift), (int(s * 0.38), int(s * 0.26) + lift)], vein + (255,))
    d.line([(int(s * 0.62), int(s * 0.26) + lift), (int(s * 0.88), int(s * 0.26) + lift)], vein + (255,))
    d.ellipse([int(s * 0.32), int(s * 0.34), int(s * 0.68), int(s * 0.92)], body + (255,))
    d.line([(int(s * 0.5), int(s * 0.36)), (int(s * 0.5), int(s * 0.9))], dark + (255,), max(1, s // 32))
    d.ellipse([int(s * 0.36), int(s * 0.22), int(s * 0.64), int(s * 0.44)], dark + (255,))
    e = max(1, s // 12)
    for ex in (0.40, 0.60):
        d.ellipse([int(s * ex) - e, int(s * 0.30) - e, int(s * ex) + e, int(s * 0.30) + e], (200, 40, 40, 255))
    w = max(1, s // 32)
    for dx in (-0.2, -0.07, 0.07, 0.2):
        d.line([(int(s * (0.5 + dx * 0.5)), int(s * 0.7)), (int(s * (0.5 + dx)), int(s * 0.94))], dark + (255,), w)
    return im


def make_creatures():
    gens = {
        "flame_wisp": lambda s, f: make_wisp(s, f),
        "flame_imp": lambda s, f: make_wisp(s, f, PAL["fire_b"], PAL["fire_c"], (120, 30, 20), (255, 240, 120), True),
        "steam_sprite": lambda s, f: make_steam(s, f, False),
        "steam_brute": lambda s, f: make_steam(s, f, True),
        "cinder_golem": make_golem,
        "moss_shade": make_shade,
        "giant_fly": make_fly,
        "guard_dog": make_dog,
        "cave_troll": make_troll,
    }
    for name, g in gens.items():
        for f in range(2):
            save(g(64, f), f"creatures/{name}_portrait_{f}.png")
            save(g(16, f), f"creatures/{name}_world_{f}.png")


# ---------------------------------------------------------------- imported pack sprites
def import_pack():
    if not SRC.exists():
        print("Spare Sprites not found; skipping pack import")
        return
    # Wizard portraits (500x500 transparent) -> 96x96 nearest-neighbour keeps pixels crisp
    wiz = {
        "arcanist": "Arcanist", "wizard": "Wizard", "pyroclast": "Pyroclast", "druid": "Druid",
        "apprentice": "Apprentice", "mage": "Mage", "archon": "Archon", "savant": "Savant", "warlock": "Warlock",
    }
    for key, name in wiz.items():
        p = SRC / "Characters" / "NPC" / "EnemyNPC" / f"{name}Sprites" / f"{name}.png"
        if p.exists():
            im = Image.open(p).convert("RGBA")
            bbox = im.getbbox()
            if bbox:
                im = im.crop(bbox)
            im.thumbnail((96, 96), Image.NEAREST)
            canvas = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
            canvas.paste(im, ((96 - im.width) // 2, 96 - im.height), im)
            save(canvas, f"portraits/{key}.png")
    # 8-direction mages -> overworld 16x24-ish cutscene sprites (4 dirs)
    for key, name in (("red_mage", "FireMage"), ("blue_mage", "IceMage")):
        for facing, src in (("down", "Front"), ("up", "Back"), ("left", "Left"), ("right", "Right")):
            p = SRC / "Characters" / "NPC" / "EnemyNPC" / f"{name}Sprites" / f"{src}.png"
            if p.exists():
                im = Image.open(p).convert("RGBA")
                bbox = im.getbbox()
                if bbox:
                    im = im.crop(bbox)
                im.thumbnail((18, 26), Image.NEAREST)
                canvas = Image.new("RGBA", (18, 26), (0, 0, 0, 0))
                canvas.paste(im, ((18 - im.width) // 2, 26 - im.height), im)
                for f in range(2):
                    save(canvas, f"chars/{key}_{facing}_{f}.png")
    # Hedge wizard (Ashby): recolour the fire mage towards moss green.
    for facing in ("down", "up", "left", "right"):
        src = OUT / "chars" / f"red_mage_{facing}_0.png"
        if src.exists():
            im = Image.open(src).convert("RGBA")
            px = im.load()
            for y in range(im.height):
                for x in range(im.width):
                    r, g, bch, a = px[x, y]
                    if a and r > g + 30 and r > bch + 30:
                        px[x, y] = (int(g * 0.9), int(r * 0.75), int(bch * 0.6), a)
            for f in range(2):
                save(im, f"chars/hedge_mage_{facing}_{f}.png")
    # Panorama left third -> title backdrop
    pan = SRC / "World" / "GameWorld3D" / "Panorama" / "bigpan1.png"
    if pan.exists():
        im = Image.open(pan).convert("RGB")
        w, h = im.size
        crop = im.crop((0, 0, int(w * 0.27), h))
        crop = crop.resize((360, int(360 * h / (w * 0.27))), Image.LANCZOS)
        # pixelate for style consistency
        crop = crop.resize((90, crop.height // 4), Image.BOX).resize((360, crop.height // 4 * 4), Image.NEAREST)
        save(crop, "backdrops/title_panorama.png")
    # John portrait for the title screen: upscale his 16x24 down-facing sprite.
    john = OUT / "chars" / "john_down_0.png"
    if john.exists():
        im = Image.open(john).convert("RGBA")
        big = im.resize((im.width * 4, im.height * 4), Image.NEAREST)
        canvas = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        canvas.paste(big, ((96 - big.width) // 2, 96 - big.height), big)
        save(canvas, "portraits/john.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    make_tiles()
    make_props()
    make_characters()
    make_creatures()
    import_pack()
    n = sum(1 for _ in OUT.rglob("*.png"))
    print(f"wrote {n} files under {OUT}")


if __name__ == "__main__":
    main()

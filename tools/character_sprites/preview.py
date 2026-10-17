"""python -m tools.character_sprites.preview <outfit>: contact sheet of an outfit for visual inspection."""
from __future__ import annotations

import sys

import numpy as np
from PIL import Image

from . import build as B
from . import clips as clipmod
from .tint import compose


def contact(outfit_spec, tints, out_path, body="adult", hair=None, beard=None, scale=3, clips=("idle", "walk", "talk"), bg=(86, 116, 78)):
    cs = list(clipmod.CLIPS_FULL)
    sheet = B.build_outfit(outfit_spec, body, cs)
    cols = B.frame_list(cs)
    hair_sheet = B.build_hair("hair", hair, body, cs) if hair else None
    beard_sheet = B.build_hair("beard", beard, body, cs) if beard else None
    rows = []
    sel = [ci for ci, (c, i) in enumerate(cols) if c in clips]
    W = len(sel) * B.CELL_W
    out = Image.new("RGBA", (W, B.CELL_H * 3), bg + (255,))
    for k, ci in enumerate(sel):
        for ri in range(3):
            cell = compose(sheet, hair_sheet, beard_sheet, ci, ri, tints)
            out.alpha_composite(cell, (k * B.CELL_W, ri * B.CELL_H))
    out = out.resize((out.width * scale, out.height * scale), Image.NEAREST)
    out.save(out_path)
    return out


def default_tints(oid, tribe="empire", variant=0):
    from . import palettes as P
    from .outfits_db import OUTFITS
    o = OUTFITS[oid]
    tri = P.TRIBES[tribe][variant % 4]
    ws = P.WIZARD_SETS[variant % len(P.WIZARD_SETS)]
    t = dict(skin=P.SKIN[1 + variant % 3], hair=P.HAIR[1 + variant % 5])
    for k in ("a", "b", "c"):
        v = o["pal"].get(k, (160, 160, 160))
        if isinstance(v, str):
            v = tri[int(v[1])] if v[0] == "T" else ws[int(v[1])]
        t[k] = v
    t = {k: tuple(min(255, int(c / 0.9)) for c in v) for k, v in t.items()}
    return t


def gallery(ids, out_path, scale=2, cols_frames=(("idle", 0), ("walk", 1), ("walk", 4), ("talk", 2)), tribe="empire", variant=0, per_row=6):
    from .outfits_db import OUTFITS
    from . import hair as hairmod
    cs = list(clipmod.CLIPS_FULL)
    colsl = B.frame_list(cs)
    tiles = []
    for oid in ids:
        o = OUTFITS[oid]
        body = o["body"]
        sheet = B.build_outfit(o["spec"], body, cs if o["clips"] == "full" else clipmod.CLIPS_CIVIL)
        hs = o["hairs"][variant % len(o["hairs"])]
        bs = o["beards"][variant % len(o["beards"])]
        hsheet = B.build_hair("hair", hs, body, cs) if hs != "bald" else None
        bsheet = B.build_hair("beard", bs, "adult", cs) if bs != "none" else None
        t = default_tints(oid, tribe, variant)
        strip = Image.new("RGBA", (B.CELL_W * len(cols_frames), B.CELL_H * 3), (86, 116, 78, 255))
        for k, (clip, fi) in enumerate(cols_frames):
            ci = colsl.index((clip, fi))
            for ri in range(3):
                strip.alpha_composite(compose(sheet, hsheet, bsheet, ci, ri, t), (k * B.CELL_W, ri * B.CELL_H))
        tiles.append((oid, strip))
    from PIL import ImageDraw
    w, h = tiles[0][1].size
    rows = (len(tiles) + per_row - 1) // per_row
    img = Image.new("RGBA", (per_row * (w + 6), rows * (h + 14)), (60, 80, 56, 255))
    d = ImageDraw.Draw(img)
    for i, (oid, st) in enumerate(tiles):
        x, y = (i % per_row) * (w + 6), (i // per_row) * (h + 14)
        img.alpha_composite(st, (x, y + 12))
        d.text((x + 2, y + 1), oid, fill=(255, 255, 255, 255))
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    img.save(out_path)

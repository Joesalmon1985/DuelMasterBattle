"""Render outfit / hair / beard sheets and the manifest.

Sheet layout: columns are the frames of every clip in CLIPS order; each layer is a band of three rows (down, side, up);
the bands are stacked top to bottom in LAYER_BANDS order.  Draw order at runtime: line, skin, hair, a, b, c, detail, beard.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from . import clips as clipmod
from . import hair as hairmod
from .outfits import draw_outfit
from .raster import Frame, render
from .rig import CELL_H, CELL_W, CX, Figure

LAYER_BANDS = ["line", "skin", "a", "b", "c", "detail"]
PORTRAIT = 64
PORTRAIT_SCALE = 2.5
PORTRAIT_POSES = [  # name -> pose overrides (front view)
    ("neutral", dict(mouth="closed", eyes="open", brows="neutral")),
    ("blink", dict(mouth="closed", eyes="blink", brows="neutral")),
    ("talk_a", dict(mouth="open_s", eyes="open", brows="neutral")),
    ("talk_b", dict(mouth="open_m", eyes="open", brows="up", head_dy=-1.0)),
    ("talk_c", dict(mouth="open_l", eyes="open", brows="up", head_dy=-1.0)),
    ("smile", dict(mouth="smile", eyes="open", brows="neutral", blush=True)),
    ("worried", dict(mouth="frown", eyes="open", brows="worried")),
    ("surprised", dict(mouth="o", eyes="wide", brows="up")),
    ("angry", dict(mouth="frown", eyes="half", brows="down")),
]


def fig_for(clip: str, i: int, view: str, body: str, mod=None) -> Figure:
    p = clipmod.pose_for(clip, i, view, mod)
    v = "side" if p.get("_side") else view
    return Figure(v, p, body)


def frame_list(clip_set: list[str]):
    cols = []
    for c in clip_set:
        for i in range(clipmod.FRAMES[c]):
            cols.append((c, i))
    return cols


def build_outfit(spec: dict, body: str, clip_set: list[str]) -> Image.Image:
    cols = frame_list(clip_set)
    W, H = CELL_W * len(cols), CELL_H * 3 * len(LAYER_BANDS)
    sheet = np.zeros((H, W, 4), dtype=np.uint8)
    for ci, (clip, i) in enumerate(cols):
        for ri, view in enumerate(clipmod.VIEWS):
            f = fig_for(clip, i, view, body, spec.get("pose_mod"))
            draw_outfit(f, spec)
            out = render(f.prims, Frame(CELL_W, CELL_H))
            for bi, name in enumerate(LAYER_BANDS):
                arr = out[name]
                y0 = (bi * 3 + ri) * CELL_H
                sheet[y0:y0 + CELL_H, ci * CELL_W:(ci + 1) * CELL_W] = arr
    return Image.fromarray(sheet, "RGBA")


def build_portrait(spec: dict, body: str) -> Image.Image:
    n = len(PORTRAIT_POSES)
    W, H = PORTRAIT * n, PORTRAIT * len(LAYER_BANDS)
    sheet = np.zeros((H, W, 4), dtype=np.uint8)
    ox = PORTRAIT / 2 - CX * PORTRAIT_SCALE
    oy = PORTRAIT * 0.52 - (15.0 if body == "adult" else 22.5) * PORTRAIT_SCALE
    for ci, (name, over) in enumerate(PORTRAIT_POSES):
        p = clipmod.pose_for("idle", 0, "down")
        p.update(over)
        f = Figure("down", p, body)
        draw_outfit(f, spec, detail=PORTRAIT_SCALE)
        out = render(f.prims, Frame(PORTRAIT, PORTRAIT, PORTRAIT_SCALE, ox, oy))
        for bi, lname in enumerate(LAYER_BANDS):
            sheet[bi * PORTRAIT:(bi + 1) * PORTRAIT, ci * PORTRAIT:(ci + 1) * PORTRAIT] = out[lname]
    return Image.fromarray(sheet, "RGBA")


def build_hair(kind: str, style: str, body: str, clip_set: list[str]) -> Image.Image:
    """kind 'hair' or 'beard'.  One band, three rows."""
    cols = frame_list(clip_set)
    sheet = np.zeros((CELL_H * 3, CELL_W * len(cols), 4), dtype=np.uint8)
    for ci, (clip, i) in enumerate(cols):
        for ri, view in enumerate(clipmod.VIEWS):
            f = fig_for(clip, i, view, body)
            from .rig import Figure as _F
            body_fig = fig_for(clip, i, view, body)
            body_fig.body()
            occ = render(body_fig.prims, Frame(CELL_W, CELL_H), outline=False)["_solid"]
            (hairmod.hair if kind == "hair" else hairmod.beard)(f, style)
            if not f.prims:
                continue
            out = render(f.prims, Frame(CELL_W, CELL_H), outline=False)
            arr = out["hair"].copy()
            solid = out["_solid"]
            # darken the hair's own outer rim so it reads against the background / clothes
            empty = ~(solid | occ)
            rim = np.zeros_like(solid)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                sh = np.zeros_like(empty)
                h, w = empty.shape
                ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
                xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
                sh[yd, xd] = empty[ys, xs]
                rim |= sh
            rim &= solid
            v = int(0.40 * 255)
            arr[rim, 0] = arr[rim, 1] = arr[rim, 2] = v
            sheet[ri * CELL_H:(ri + 1) * CELL_H, ci * CELL_W:(ci + 1) * CELL_W] = arr
    return Image.fromarray(sheet, "RGBA")


def clip_table(clip_set: list[str]) -> dict:
    out, col = {}, 0
    for c in clip_set:
        out[c] = {"start": col, "frames": clipmod.FRAMES[c]}
        col += clipmod.FRAMES[c]
    return out


def build_hair_portrait(kind: str, style: str, body: str) -> Image.Image:
    n = len(PORTRAIT_POSES)
    sheet = np.zeros((PORTRAIT, PORTRAIT * n, 4), dtype=np.uint8)
    ox = PORTRAIT / 2 - CX * PORTRAIT_SCALE
    oy = PORTRAIT * 0.52 - (15.0 if body == "adult" else 22.5) * PORTRAIT_SCALE
    for ci, (name, over) in enumerate(PORTRAIT_POSES):
        p = clipmod.pose_for("idle", 0, "down")
        p.update(over)
        f = Figure("down", p, body)
        b = Figure("down", p, body)
        b.body()
        occ = render(b.prims, Frame(PORTRAIT, PORTRAIT, PORTRAIT_SCALE, ox, oy), outline=False)["_solid"]
        (hairmod.hair if kind == "hair" else hairmod.beard)(f, style)
        if not f.prims:
            continue
        out = render(f.prims, Frame(PORTRAIT, PORTRAIT, PORTRAIT_SCALE, ox, oy), outline=False)
        arr = out["hair"].copy()
        solid = out["_solid"]
        empty = ~(solid | occ)
        rim = np.zeros_like(solid)
        h, w = empty.shape
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.zeros_like(empty)
            ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
            xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
            sh[yd, xd] = empty[ys, xs]
            rim |= sh
        rim &= solid
        v = int(0.40 * 255)
        arr[rim, 0] = arr[rim, 1] = arr[rim, 2] = v
        sheet[:, ci * PORTRAIT:(ci + 1) * PORTRAIT] = arr
    return Image.fromarray(sheet, "RGBA")

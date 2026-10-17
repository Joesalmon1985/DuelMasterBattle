"""Python mirror of the runtime compositor (client/characters/character_renderer.gd): tints luminance layers and stacks them."""
from __future__ import annotations

import numpy as np
from PIL import Image

from . import build as B


def _tint(img: Image.Image, rgb) -> Image.Image:
    a = np.asarray(img).astype(np.float32)
    k = np.array(rgb, dtype=np.float32) / 255.0
    a[..., :3] *= k[None, None, :]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def _band(sheet: Image.Image, band: int, col: int, row: int) -> Image.Image:
    x, y = col * B.CELL_W, (band * 3 + row) * B.CELL_H
    return sheet.crop((x, y, x + B.CELL_W, y + B.CELL_H))


def _hband(sheet, col, row):
    x, y = col * B.CELL_W, row * B.CELL_H
    return sheet.crop((x, y, x + B.CELL_W, y + B.CELL_H))


def compose(sheet, hair_sheet, beard_sheet, col, row, tints) -> Image.Image:
    out = Image.new("RGBA", (B.CELL_W, B.CELL_H), (0, 0, 0, 0))
    names = B.LAYER_BANDS
    order = ["line", "skin"]
    out.alpha_composite(_band(sheet, 0, col, row))
    out.alpha_composite(_tint(_band(sheet, 1, col, row), tints["skin"]))
    if hair_sheet is not None:
        out.alpha_composite(_tint(_hband(hair_sheet, col, row), tints["hair"]))
    for nm in ("a", "b", "c"):
        out.alpha_composite(_tint(_band(sheet, names.index(nm), col, row), tints[nm]))
    out.alpha_composite(_band(sheet, 5, col, row))
    if beard_sheet is not None:
        out.alpha_composite(_tint(_hband(beard_sheet, col, row), tints["hair"]))
    return out

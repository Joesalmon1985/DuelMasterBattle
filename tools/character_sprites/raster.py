"""Shape rasteriser: primitives -> pixel masks -> shaded, layer-split sprite frames.

Pixel art is made by drawing every primitive 4x oversampled, thresholding the coverage and then shading the resulting
silhouette with a fixed light from the upper left (highlight rim, shade rim, deep shade rim).  Every pixel ends up owned
by exactly one primitive (painter's order), so the finished frame can be split into tintable layers without overlaps:
drawing all layers at the same position re-creates the composite exactly.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw

SS = 4
OUTLINE = (38, 24, 44)

# luminance ramp for tinted layers (multiplied by the layer tint at runtime; tints are pre-brightened by 1/0.9)
L_HI, L_BASE, L_SHADE, L_DEEP, L_LINE = 1.0, 0.9, 0.74, 0.6, 0.42


@dataclass
class Prim:
    kind: str                      # poly | ell | cap | line | rect
    pts: tuple                     # geometry (see mask())
    layer: str                     # skin | a | b | c | hair | detail
    z: float = 0.0
    grp: str = ""                  # primitives of one group never draw inner outlines on each other
    color: tuple | None = None     # detail layer colour (r, g, b)
    shade: bool = True
    thr: float = 0.5               # coverage threshold (thin lines use less)
    lum: float | None = None       # flat luminance override for tinted layers
    outline_ok: bool = True        # may receive an inner outline from a part in front of it
    nodark: bool = False


class Frame:
    """Rasterisation target for one frame: canvas size, and the figure->canvas transform."""

    def __init__(self, w: int, h: int, scale: float = 1.0, ox: float = 0.0, oy: float = 0.0):
        self.w, self.h, self.scale, self.ox, self.oy = w, h, scale, ox, oy

    def xf(self, x: float, y: float) -> tuple[float, float]:
        return x * self.scale + self.ox, y * self.scale + self.oy


def mask(p: Prim, fr: Frame) -> np.ndarray:
    W, H = fr.w * SS, fr.h * SS
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    k = SS

    def T(pt):
        x, y = fr.xf(pt[0], pt[1])
        return (x * k, y * k)

    s = fr.scale
    if p.kind == "poly":
        d.polygon([T(q) for q in p.pts], fill=255)
    elif p.kind == "ell":
        cx, cy, rx, ry = p.pts
        x0, y0 = T((cx - rx, cy - ry))
        x1, y1 = T((cx + rx, cy + ry))
        d.ellipse([x0, y0, x1, y1], fill=255)
    elif p.kind == "rect":
        x0, y0, x1, y1 = p.pts
        a = T((x0, y0))
        b = T((x1, y1))
        d.rectangle([a[0], a[1], b[0] - 1, b[1] - 1], fill=255)
    elif p.kind == "cap":  # capsule: (x0, y0, x1, y1, r0, r1)
        x0, y0, x1, y1, r0, r1 = p.pts
        a, b = T((x0, y0)), T((x1, y1))
        for (c, r) in ((a, r0), (b, r1)):
            rr = r * s * k
            d.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr], fill=255)
        ang = math.atan2(y1 - y0, x1 - x0) + math.pi / 2
        nx, ny = math.cos(ang), math.sin(ang)
        q = [(a[0] + nx * r0 * s * k, a[1] + ny * r0 * s * k), (b[0] + nx * r1 * s * k, b[1] + ny * r1 * s * k),
             (b[0] - nx * r1 * s * k, b[1] - ny * r1 * s * k), (a[0] - nx * r0 * s * k, a[1] - ny * r0 * s * k)]
        d.polygon(q, fill=255)
    elif p.kind == "line":  # (x0, y0, x1, y1, width)
        x0, y0, x1, y1, wd = p.pts
        d.line([T((x0, y0)), T((x1, y1))], fill=255, width=max(1, int(round(wd * s * k))))
    else:
        raise ValueError(p.kind)
    a = np.asarray(im, dtype=np.float32).reshape(fr.h, SS, fr.w, SS).mean((1, 3)) / 255.0
    return a >= p.thr


def _sh(m: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(m)
    h, w = m.shape
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = m[ys, xs]
    return out


def shade_lum(m: np.ndarray) -> np.ndarray:
    lum = np.full(m.shape, L_BASE, dtype=np.float32)
    lit = m & ~_sh(m, 1, 1)
    d1 = m & ~_sh(m, -1, -1)
    area = int(m.sum())
    if area > 26:
        d2 = m & ~_sh(m, -2, -2) & ~d1
        lum[d2] = L_SHADE
        lum[d1] = L_DEEP
    else:
        lum[d1] = L_SHADE
    lum[lit & ~d1] = L_HI
    return lum


LAYERS = ("skin", "a", "b", "c", "hair", "detail")


def render(prims: list[Prim], fr: Frame, occupancy: np.ndarray | None = None, outline: bool = True) -> dict[str, np.ndarray]:
    """Return RGBA arrays (h, w, 4 uint8) per layer plus 'line' (the outer outline), pixels split by owner."""
    h, w = fr.h, fr.w
    own = np.full((h, w), -1, dtype=np.int32)
    lum = np.zeros((h, w), dtype=np.float32)
    col = np.zeros((h, w, 3), dtype=np.float32)
    order = sorted(range(len(prims)), key=lambda i: prims[i].z)
    masks: dict[int, np.ndarray] = {}
    for i in order:
        p = prims[i]
        m = mask(p, fr)
        if not m.any():
            continue
        masks[i] = m
        if p.layer == "detail":
            base = np.array(p.color or (255, 255, 255), dtype=np.float32)
            if p.shade:
                lv = shade_lum(m) / L_BASE
                col[m] = base[None, :] * lv[m][:, None]
            else:
                col[m] = base
        else:
            if p.lum is not None:
                lum[m] = p.lum
            elif p.shade:
                lum[m] = shade_lum(m)[m]
            else:
                lum[m] = L_BASE
        own[m] = i
    # inner outlines: a pixel next to a part in front of it (different group) is darkened
    n = len(prims)
    zs = np.array([prims[i].z for i in range(n)] + [-1e9], dtype=np.float32)
    gids = {}
    gid = np.array([gids.setdefault(prims[i].grp or f"#{i}", len(gids)) for i in range(n)] + [-1], dtype=np.int32)
    okf = np.array([prims[i].outline_ok and not prims[i].nodark for i in range(n)] + [False])
    dark = np.zeros((h, w), dtype=bool)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = _shift_int(own, dx, dy)
        sel = (own >= 0) & (nb >= 0) & (nb != own) & (zs[nb] > zs[own]) & (gid[nb] != gid[own]) & okf[own]
        dark |= sel
    out = {k: np.zeros((h, w, 4), dtype=np.uint8) for k in LAYERS}
    for i in set(own[own >= 0].tolist()):
        p = prims[i]
        sel = own == i
        if p.layer == "detail":
            c = col.copy()
            c[sel & dark] *= 0.55
            out["detail"][sel, :3] = np.clip(c[sel], 0, 255).astype(np.uint8)
            out["detail"][sel, 3] = 255
        else:
            l = np.where(dark, L_LINE, lum)
            v = np.clip(l[sel] * 255, 0, 255).astype(np.uint8)
            out[p.layer][sel, 0] = v
            out[p.layer][sel, 1] = v
            out[p.layer][sel, 2] = v
            out[p.layer][sel, 3] = 255
    solid = own >= 0
    if occupancy is not None:
        union = solid | occupancy
    else:
        union = solid
    ring = np.zeros_like(union)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ring |= _sh(union, dx, dy)
    ring &= ~union
    line = np.zeros((h, w, 4), dtype=np.uint8)
    if outline:
        line[ring, 0], line[ring, 1], line[ring, 2], line[ring, 3] = OUTLINE[0], OUTLINE[1], OUTLINE[2], 255
    out["line"] = line
    out["_solid"] = solid
    return out


def _shift_int(a: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.full_like(a, -1)
    h, w = a.shape
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = a[ys, xs]
    return out

"""Eyes, brows, mouth and cheeks.  Drawn into the untinted detail layer; snapped to whole pixels so the face never shimmers."""
from __future__ import annotations

from .rig import Figure

INK = (38, 26, 48)
LIP = (150, 66, 70)
MOUTH_IN = (92, 28, 40)
TONGUE = (226, 108, 120)
BLUSH = (238, 150, 140)
WHITE = (250, 246, 240)
BROW = (66, 44, 44)


def draw(fig: Figure, detail: float = 1.0, eye_color=INK, iris=(70, 110, 170), brow_color=BROW, hidden: bool = False, glow=None) -> None:
    if fig.view == "up" or hidden:
        if hidden and glow is not None and fig.view != "up":
            _glow_eyes(fig, glow)
        return
    p, sk = fig.p, fig.sk
    hcx, hcy = sk["head"]
    cx, cy = round(hcx), round(hcy)
    side = fig.view == "side"
    z = 56
    hi = detail >= 1.8
    eyes, mouth, brows = p["eyes"], p["mouth"], p["brows"]
    ey = cy + 1
    if side:
        xs = [cx + 3]
    else:
        xs = [cx - 4, cx + 2]
    for x in xs:
        _eye(fig, x, ey, eyes, eye_color, iris, hi, z, side)
        _brow(fig, x, ey, brows, brow_color, z, side, xs.index(x) if not side else 1)
        if p["blush"]:
            fig.rect(x - (0 if side else 0), ey + 3, x + 2, ey + 4, "detail", z, "face", color=BLUSH, shade=False)
    mx = cx + (4 if side else 0)
    my = cy + 5
    _mouth(fig, mx, my, mouth, z, side, hi)


def _eye(fig, x, y, state, col, iris, hi, z, side):
    if hi:
        # portrait quality eye (coordinates are in rig units; the frame scale makes them bigger)
        w, h = 2.0, 3.0
        if state in ("blink", "closed"):
            fig.line((x - 0.2, y + 1.2), (x + w + 0.2, y + 1.2), 0.45, "detail", z, "face", color=col, shade=False)
            fig.line((x - 0.2, y + 1.2), (x - 0.7, y + 0.8), 0.3, "detail", z, "face", color=col, shade=False)
            return
        hh = h + (0.8 if state == "wide" else (-0.9 if state == "half" else 0.0))
        fig.ell(x + w / 2, y + 1.0, w / 2 + 0.25, hh / 2 + 0.2, "detail", z, "face", color=WHITE, shade=False)
        fig.ell(x + w / 2, y + 1.2, w / 2 - 0.1, hh / 2 - 0.1, "detail", z + .1, "face", color=iris, shade=False)
        fig.ell(x + w / 2, y + 1.2, w / 4 + 0.08, hh / 4 + 0.15, "detail", z + .2, "face", color=col, shade=False)
        fig.ell(x + w / 2 - 0.35, y + 0.6, 0.28, 0.28, "detail", z + .3, "face", color=WHITE, shade=False)
        if state == "half":
            fig.rect(x - 0.4, y - 0.6, x + w + 0.4, y + 0.5, "skin", z + .4, "face", shade=False, lum=0.82)
        fig.line((x - 0.3, y - 0.1), (x + w + 0.3, y - 0.3), 0.35, "detail", z + .5, "face", color=col, shade=False)
        return
    if state in ("blink", "closed"):
        fig.rect(x, y + 1, x + 2, y + 2, "detail", z, "face", color=col, shade=False)
    elif state == "half":
        fig.rect(x, y, x + 2, y + 2, "detail", z, "face", color=col, shade=False)
        fig.rect(x, y, x + 1, y + 1, "detail", z + .1, "face", color=WHITE, shade=False)
    elif state == "wide":
        fig.rect(x - (1 if not side else 0), y - 1, x + 2 + (0 if not side else 1), y + 3, "detail", z, "face", color=WHITE, shade=False)
        fig.rect(x, y, x + 2, y + 2, "detail", z + .1, "face", color=col, shade=False)
    elif state == "dead":
        fig.line((x, y), (x + 2, y + 2), 1.0, "detail", z, "face", color=col, shade=False)
        fig.line((x + 2, y), (x, y + 2), 1.0, "detail", z, "face", color=col, shade=False)
    else:
        fig.rect(x, y - 1, x + 2, y + 2, "detail", z, "face", color=col, shade=False)
        fig.rect(x, y - 1, x + 1, y, "detail", z + .1, "face", color=WHITE, shade=False)


def _brow(fig, x, y, state, col, z, side, idx):
    if state == "none":
        return
    by = y - 2.0
    x0, x1 = x - 0.3, x + 2.3
    if state == "up":
        by -= 1
    y0 = y1 = by
    if state == "down":  # angry: inner end lower
        if idx == 0 or side:
            y1 = by + 1
        else:
            y0 = by + 1
    elif state == "worried":
        if idx == 0 or side:
            y0 = by + 1
        else:
            y1 = by + 1
    fig.line((x0, y0 + .5), (x1, y1 + .5), 1.0, "detail", z, "face", color=col, shade=False, thr=0.3)


def _mouth(fig, x, y, m, z, side, hi):
    if m == "closed":
        fig.rect(x - 1, y, x + 1, y + 1, "detail", z, "face", color=LIP, shade=False)
    elif m == "smile":
        fig.rect(x - 1, y, x + 1, y + 1, "detail", z, "face", color=LIP, shade=False)
        fig.rect(x - 2, y - 1, x - 1, y, "detail", z, "face", color=LIP, shade=False)
        fig.rect(x + 1, y - 1, x + 2, y, "detail", z, "face", color=LIP, shade=False)
    elif m == "frown":
        fig.rect(x - 1, y, x + 1, y + 1, "detail", z, "face", color=LIP, shade=False)
        fig.rect(x - 2, y + 1, x - 1, y + 2, "detail", z, "face", color=LIP, shade=False)
        fig.rect(x + 1, y + 1, x + 2, y + 2, "detail", z, "face", color=LIP, shade=False)
    elif m == "open_s":
        fig.rect(x - 1, y, x + 1, y + 2, "detail", z, "face", color=MOUTH_IN, shade=False)
    elif m == "open_m":
        fig.rect(x - 1, y, x + 2, y + 2, "detail", z, "face", color=MOUTH_IN, shade=False)
        fig.rect(x, y + 1, x + 1, y + 2, "detail", z + .1, "face", color=TONGUE, shade=False)
    elif m == "open_l":
        fig.rect(x - 2, y - 1, x + 2, y + 2, "detail", z, "face", color=MOUTH_IN, shade=False)
        fig.rect(x - 1, y + 1, x + 1, y + 2, "detail", z + .1, "face", color=TONGUE, shade=False)
    elif m == "o":
        fig.rect(x - 1, y, x + 1, y + 2, "detail", z, "face", color=MOUTH_IN, shade=False)
    elif m == "grin":
        fig.rect(x - 2, y - 1, x + 2, y + 1, "detail", z, "face", color=MOUTH_IN, shade=False)
        fig.rect(x - 2, y - 1, x + 2, y, "detail", z + .1, "face", color=WHITE, shade=False)
    else:
        fig.rect(x - 1, y, x + 1, y + 1, "detail", z, "face", color=LIP, shade=False)


def _glow_eyes(fig, col):
    sk = fig.sk
    hcx, hcy = sk["head"]
    cx, cy = round(hcx), round(hcy)
    xs = [cx + 3] if fig.view == "side" else [cx - 3, cx + 2]
    for x in xs:
        fig.rect(x, cy + 1, x + 1, cy + 2, "detail", 60, "face", color=col, shade=False)

"""Hair and beards: separate tintable sheets so any hairstyle can be combined with any outfit (a hat simply covers it)."""
from __future__ import annotations

import math

from .rig import Figure

HAIR_STYLES = ["bald", "short", "swept", "long", "ponytail", "bun", "spiky", "curly", "bob", "balding", "braid"]
BEARD_STYLES = ["none", "stubble", "short", "mustache", "long", "braided", "goatee"]


def arc(cx, cy, rx, ry, a0, a1, n=12):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def hair(f: Figure, style: str) -> None:
    if style == "bald":
        return
    hx, hy = f.sk["head"]
    hx, hy = round(hx), round(hy)
    D = f.D
    rx, ry = D["hrx"], D["hry"]
    v = f.view
    L = "hair"
    g = "hair"
    top = hy - ry
    if v == "side":
        cx = hx - 0.4
        rxs = rx - 0.6
        back = arc(cx, hy - 0.3, rxs + 0.9, ry + 0.9, 20, -100, 14)  # forehead over the crown (screen angles, y down)
        back = arc(cx, hy - 0.3, rxs + 0.9, ry + 0.8, -35, -250, 16)   # from the forehead (upper right) round the crown to the nape
        pts = list(back)
        # fringe line returning along the hairline
        if style in ("short", "bun", "ponytail", "braid", "long", "bob", "curly", "swept", "spiky"):
            fr = [(cx - 1.5, hy + 1.8), (cx + 0.5, hy - 1.0), (cx + 3.3, hy - 2.4), (cx + rxs - 0.4, hy - 2.6)]
            if style == "swept":
                fr = [(cx - 1.5, hy + 1.8), (cx + 1.5, hy - 0.5), (cx + 4.6, hy - 1.6), (cx + rxs + 1.0, hy - 1.0)]
            pts = pts + fr
        elif style == "balding":
            pts = arc(cx, hy + 0.3, rxs + 0.6, ry - 2.2, 215, 140, 6) + [(cx - 2.5, hy + 4.0), (cx - 2.0, hy + 1.0)]
        f.poly(pts, L, 60, g)
        if style in ("long", "bob"):
            n = 6 if style == "long" else 3.5
            f.poly([(cx - rxs - 0.7, hy), (cx - rxs - 0.5, hy + ry + n), (cx - 1.0, hy + ry + n - 0.5), (cx + 0.4, hy + 3.0), (cx - 1.5, hy + 0.5)], L, 59, g)
        if style == "ponytail":
            f.poly([(cx - rxs - 0.4, hy - 1.5), (cx - rxs - 3.8, hy + 1.5), (cx - rxs - 3.4, hy + 7.0), (cx - rxs - 1.2, hy + 4.0), (cx - rxs, hy + 2.0)], L, 58, g)
        if style == "braid":
            f.cap((cx - rxs - 0.8, hy + 1.0), (cx - rxs - 2.4, hy + 9.0), 1.7, 1.3, L, 58, g)
        if style == "bun":
            f.ell(cx - 2.0, top - 1.5, 3.0, 2.6, L, 61, g)
        if style == "spiky":
            for i, (dx, h) in enumerate(((-4, 3.5), (-1, 4.5), (2, 3.8), (4.5, 2.5))):
                f.poly([(cx + dx - 1.8, top + 1.6), (cx + dx + 0.2, top - h), (cx + dx + 1.8, top + 1.6)], L, 61, g)
        if style == "curly":
            for dx, dy, r in ((-5, 1.0, 2.8), (-3.5, -4.5, 3.0), (0, -6.5, 3.2), (3.5, -5, 2.8), (-6, 4.5, 2.4)):
                f.ell(cx + dx, hy + dy, r, r, L, 60.5, g)
        return
    # front / back
    if v == "up":
        base = arc(hx, hy - 0.3, rx + 0.9, ry + 0.8, 180, 360, 14) + arc(hx, hy + 1.8, rx + 0.5, ry - 2.2, 0, 180, 10)
        if style == "balding":
            base = arc(hx, hy + 2.0, rx + 0.7, ry - 1.8, 10, 170, 10) + arc(hx, hy + 1.4, rx - 1.2, ry - 4.0, 170, 10, 8)
        f.poly(base, L, 60, g)
        if style in ("long", "bob"):
            n = 8.0 if style == "long" else 3.5
            f.poly([(hx - rx - 0.6, hy), (hx - rx - 0.2, hy + ry + n), (hx + rx + 0.2, hy + ry + n), (hx + rx + 0.6, hy)], L, 59.5, g)
        if style == "ponytail":
            f.poly([(hx - 1.7, hy - 2.5), (hx + 1.7, hy - 2.5), (hx + 2.7, hy + 6.5), (hx, hy + 9.5), (hx - 2.7, hy + 6.5)], L, 61, g)
        if style == "braid":
            f.cap((hx, hy - 1.0), (hx + 0.5, hy + 10.0), 2.0, 1.4, L, 61, g)
    else:
        top_arc = arc(hx, hy - 0.2, rx + 0.9, ry + 0.8, 180, 360, 16)
        if style == "balding":
            pts = arc(hx, hy + 0.2, rx + 0.5, ry - 1.5, 200, 160, 1)
            f.poly([(hx - rx - 0.5, hy - 0.5), (hx - rx + 0.6, hy - 2.5), (hx - rx + 1.6, hy + 2.0), (hx - rx - 0.3, hy + 3.5)], L, 60, g)
            f.poly([(hx + rx + 0.5, hy - 0.5), (hx + rx - 0.6, hy - 2.5), (hx + rx - 1.6, hy + 2.0), (hx + rx + 0.3, hy + 3.5)], L, 60, g)
            return
        fr = {
            "swept": [(hx + rx - 0.3, hy - 1.8), (hx + 4.0, hy - 3.6), (hx - 0.5, hy - 2.6), (hx - 3.5, hy - 4.2), (hx - rx + 1.4, hy - 1.0)],
        }.get(style, [(hx + rx - 0.9, hy - 1.6), (hx + 3.6, hy - 3.4), (hx + 1.2, hy - 2.2), (hx - 1.5, hy - 3.6), (hx - 4.0, hy - 2.4), (hx - rx + 0.9, hy - 1.8)])
        f.poly(top_arc + fr, L, 60, g)
        if style in ("long", "bob"):
            n = 7.0 if style == "long" else 3.5
            f.poly([(hx - rx - 0.7, hy - 1.0), (hx - rx + 2.6, hy - 1.5), (hx - rx + 2.2, hy + ry + n - 1), (hx - rx - 0.4, hy + ry + n)], L, 59.5, g)
            f.poly([(hx + rx + 0.7, hy - 1.0), (hx + rx - 2.6, hy - 1.5), (hx + rx - 2.2, hy + ry + n - 1), (hx + rx + 0.4, hy + ry + n)], L, 59.5, g)
        elif style in ("ponytail", "short", "swept", "braid", "bun", "spiky", "curly"):
            f.rect(hx - rx - 0.6, hy - 1.2, hx - rx + 1.2, hy + 2.6, L, 59.5, g)
            f.rect(hx + rx - 1.2, hy - 1.2, hx + rx + 0.6, hy + 2.6, L, 59.5, g)
        if style == "braid":
            f.cap((hx - rx - 0.3, hy + 1.0), (hx - rx - 1.0, hy + 9.5), 1.6, 1.2, L, 59, g)
    top = hy - ry
    if style == "bun":
        f.ell(hx, top - 1.2, 3.2, 2.8, L, 61, g)
    if style == "spiky":
        for dx, h in ((-5, 2.5), (-2.5, 4.0), (0.2, 4.8), (2.8, 4.0), (5.3, 2.4)):
            f.poly([(hx + dx - 1.7, top + 2.0), (hx + dx, top - h), (hx + dx + 1.7, top + 2.0)], L, 61, g)
    if style == "curly":
        for dx, dy, r in ((-6.5, 0.0, 2.6), (6.5, 0.0, 2.6), (-5.5, -4.2, 3.0), (5.5, -4.2, 3.0), (-2.5, -6.6, 3.1), (2.5, -6.6, 3.1), (0, -5, 3.0)):
            f.ell(hx + dx, hy + dy, r, r, L, 60.5, g)


def beard(f: Figure, style: str) -> None:
    if style == "none" or f.view == "up":
        return
    hx, hy = f.sk["head"]
    hx, hy = round(hx), round(hy)
    D = f.D
    rx, ry = D["hrx"], D["hry"]
    L, g = "hair", "beard"
    chin = hy + ry
    if f.view == "side":
        cx = hx - 0.4
        fx = cx + rx - 1.0
        if style == "mustache":
            f.poly([(fx - 1.5, hy + 3.5), (fx + 1.4, hy + 3.8), (fx + 0.4, hy + 5.0), (fx - 1.8, hy + 4.6)], L, 62, g)
        elif style == "stubble":
            f.poly([(cx - 2.5, hy + 1.5), (fx + 0.2, hy + 4.5), (fx - 1.0, chin + 0.5), (cx - 2.0, chin + 0.3)], L, 62, g, lum=0.7)
        else:
            ln = {"short": 1.5, "goatee": 2.0, "long": 8.0, "braided": 9.0}.get(style, 1.5)
            f.poly([(cx - 2.8, hy + 0.5), (cx + 0.5, hy + 3.2), (fx + 0.6, hy + 5.8), (fx + 0.8, chin + ln * 0.6), (fx - 2.2, chin + ln), (cx - 2.4, chin + 1.0)], L, 62, g)
            if style == "braided":
                f.cap((fx - 0.8, chin + 1), (fx - 0.8, chin + ln), 1.4, 1.1, L, 62.1, g)
        return
    if style == "mustache":
        f.poly([(hx - 4.5, hy + 3.8), (hx - 1, hy + 3.4), (hx, hy + 4.2), (hx + 1, hy + 3.4), (hx + 4.5, hy + 3.8), (hx + 3.2, hy + 5.0), (hx, hy + 4.4), (hx - 3.2, hy + 5.0)], L, 62, g)
        return
    if style == "stubble":
        f.poly([(hx - rx + 0.6, hy + 1.0), (hx - 3, hy + 5.8), (hx + 3, hy + 5.8), (hx + rx - 0.6, hy + 1.0), (hx + rx - 1.4, hy + ry - 0.8), (hx, chin + 0.4), (hx - rx + 1.4, hy + ry - 0.8)], L, 62, g, lum=0.7)
        return
    ln = {"short": 1.5, "goatee": 2.5, "long": 8.5, "braided": 8.0}.get(style, 1.5)
    if style == "goatee":
        f.poly([(hx - 3.2, hy + 6.6), (hx + 3.2, hy + 6.6), (hx + 2.4, chin + ln), (hx, chin + ln + 1.0), (hx - 2.4, chin + ln)], L, 62, g)
        return
    f.poly([(hx - rx + 0.2, hy + 0.5), (hx - rx + 1.8, hy + 0.5), (hx - 3.6, hy + 6.7), (hx + 3.6, hy + 6.7), (hx + rx - 1.8, hy + 0.5), (hx + rx - 0.2, hy + 0.5),
            (hx + rx - 0.4, hy + ry - 0.5), (hx + 3.5, chin + ln * 0.6), (hx, chin + ln + 0.8), (hx - 3.5, chin + ln * 0.6), (hx - rx + 0.4, hy + ry - 0.5)], L, 62, g)
    if style == "braided":
        f.cap((hx - 1.6, chin), (hx - 1.6, chin + ln + 1), 1.5, 1.2, L, 62.2, g)
        f.cap((hx + 1.6, chin), (hx + 1.6, chin + ln + 1), 1.5, 1.2, L, 62.2, g)

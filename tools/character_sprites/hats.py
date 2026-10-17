"""Headgear.  All hats are drawn above the hair sheet (the hair sheet is composited under cloth/hat layers)."""
from __future__ import annotations

import math

from .garments import GOLD, IRON, IRON_D, WOOD
from .hair import arc
from .rig import Figure

RED = (200, 52, 52)
BONE = (238, 228, 200)
FEATHER = (86, 170, 120)
LAMP = (255, 232, 130)


def _head(f: Figure):
    hx, hy = f.sk["head"]
    hx, hy = round(hx), round(hy)
    if f.view == "side":
        hx -= 0.4
    return hx, hy, f.D["hrx"] - (0.6 if f.view == "side" else 0), f.D["hry"]


def dome(f: Figure, cx, cy, rx, ry, cut, layer, z, grp="hat", **kw):
    """The part of an ellipse above y=cut."""
    pts = []
    n = 16
    for i in range(n + 1):
        a = math.pi + math.pi * i / n
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        pts.append((x, min(y, cut)))
    f.poly(pts, layer, z, grp, **kw)


def draw(f: Figure, kind: str, spec: dict) -> None:
    fn = HATS.get(kind)
    if fn is None:
        raise KeyError(kind)
    fn(f, spec)


def _layer(spec, default="c"):
    return spec.get("hat_layer", default)


def cap(f, spec):
    hx, hy, rx, ry = _head(f)
    L = _layer(spec)
    dome(f, hx, hy - 0.3, rx + 0.7, ry + 0.5, hy - 2.2, L, 60)
    if f.view == "side":
        f.poly([(hx + rx - 2.5, hy - 2.7), (hx + rx + 3.0, hy - 2.2), (hx + rx + 3.0, hy - 1.0), (hx + rx - 2.5, hy - 1.2)], L, 60.2, "hat", lum=0.8, shade=False)
    elif f.view == "down":
        f.poly([(hx - rx + 1, hy - 2.8), (hx + rx - 1, hy - 2.8), (hx + rx - 0.4, hy - 1.0), (hx - rx + 0.4, hy - 1.0)], L, 60.2, "hat", lum=0.8, shade=False)


def beanie(f, spec):
    hx, hy, rx, ry = _head(f)
    L = _layer(spec)
    dome(f, hx, hy - 0.5, rx + 0.8, ry + 0.8, hy - 1.8, L, 60)
    f.rect(hx - rx - 0.6, hy - 3.4, hx + rx + 0.6, hy - 1.4, spec.get("trim_layer2", "a"), 60.3, "hat", shade=False, lum=0.9)
    f.ell(hx - (1 if f.view == "side" else 0), hy - ry - 1.8, 2.0, 2.0, "a", 60.6, "hat")


def straw(f, spec):
    hx, hy, rx, ry = _head(f)
    L = _layer(spec, "c")
    f.ell(hx, hy - 4.2, rx + 3.6, 2.0, L, 59.9, "hatb")
    dome(f, hx, hy - 3.4, rx - 0.8, ry - 2.6, hy - 4.0, L, 60.4, "hat")
    f.rect(hx - rx + 1.0, hy - 5.8, hx + rx - 1.0, hy - 4.5, spec.get("band_layer", "a"), 60.6, "hat", shade=False, lum=0.9)


def toque(f, spec):
    hx, hy, rx, ry = _head(f)
    L = _layer(spec, "c")
    f.rect(hx - rx + 1.2, hy - ry - 3.5, hx + rx - 1.2, hy - 1.6, L, 60, "hat")
    f.ell(hx, hy - ry - 4.2, rx - 0.2, 3.2, L, 60.1, "hat")
    f.ell(hx - 4.2, hy - ry - 2.6, 2.6, 2.4, L, 60.2, "hat")
    f.ell(hx + 4.2, hy - ry - 2.6, 2.6, 2.4, L, 60.2, "hat")
    f.rect(hx - rx + 1.0, hy - 3.2, hx + rx - 1.0, hy - 1.4, "a", 60.5, "hat", shade=False, lum=0.8)


def hardhat(f, spec):
    hx, hy, rx, ry = _head(f)
    L = _layer(spec, "c")
    dome(f, hx, hy - 0.5, rx + 0.8, ry + 0.6, hy - 2.0, L, 60)
    f.rect(hx - rx - 1.4, hy - 2.6, hx + rx + 1.4, hy - 1.2, L, 60.3, "hat", shade=False, lum=0.78)
    if f.view != "up":
        off = 3.2 if f.view == "side" else 0
        f.ell(hx + off, hy - 4.6, 1.8, 1.6, "detail", 61, "hat", color=LAMP, shade=False)
        f.ell(hx + off, hy - 4.6, 2.6, 2.4, "detail", 60.9, "hat", color=IRON_D, shade=False)


def hood(f, spec):
    hx, hy, rx, ry = _head(f)
    L = _layer(spec, "a")
    back = f.view == "up"
    f.ell(hx - (1.0 if f.view == "side" else 0), hy + 0.2, rx + 1.8, ry + 1.5, L, 49.5, "hood")  # cowl behind the face
    if back:
        f.ell(hx, hy + 0.4, rx + 1.6, ry + 1.4, L, 60, "hood")
    elif f.view == "down":
        pts = arc(hx, hy, rx + 1.9, ry + 1.6, 180, 360, 14) + [(hx + rx - 0.8, hy - 1.2), (hx + 3.2, hy - 3.4), (hx - 3.2, hy - 3.4), (hx - rx + 0.8, hy - 1.2)]
        f.poly(pts, L, 60, "hood")
        f.poly([(hx - rx - 1.6, hy), (hx - rx + 1.0, hy - 1), (hx - rx + 1.0, hy + 5), (hx - rx - 0.6, hy + ry + 1)], L, 60.1, "hood")
        f.poly([(hx + rx + 1.6, hy), (hx + rx - 1.0, hy - 1), (hx + rx - 1.0, hy + 5), (hx + rx + 0.6, hy + ry + 1)], L, 60.1, "hood")
    else:
        pts = arc(hx - 1.0, hy, rx + 1.8, ry + 1.4, 300, 140, 14)
        pts = arc(hx - 1.0, hy, rx + 1.8, ry + 1.5, -40, -250, 16) + [(hx - 1.5, hy + 4.0), (hx, hy - 0.5), (hx + 3.2, hy - 2.8)]
        f.poly(pts, L, 60, "hood")
    f.ell(hx, hy + ry + 1.2, 5.6, 2.2, L, 49.4, "hood")


def wizard(f, spec):
    hx, hy, rx, ry = _head(f)
    L = _layer(spec, "a")
    cut = hy - 3.4
    tip = spec.get("hat_tip", 6.5)
    bend = spec.get("hat_bend", 3.0) * (1 if f.view != "side" else 1)
    top = hy - ry
    f.ell(hx, cut + 0.3, rx + 3.4, 2.0, L, 59.9, "hatb")
    base_w = rx + 0.4
    mid = (hx + bend * 0.2, top - tip * 0.55)
    pts = [(hx - base_w, cut), (hx - base_w + 1.2, top - 1.2), (mid[0] - 3.0, mid[1]), (hx + bend * 0.8, top - tip), (mid[0] + 3.2, mid[1]), (hx + base_w - 1.2, top - 1.2), (hx + base_w, cut)]
    f.poly(pts, L, 60.3, "hat")
    f.poly([(hx - base_w - 0.4, cut - 0.2), (hx + base_w + 0.4, cut - 0.2), (hx + base_w, cut - 2.2), (hx - base_w, cut - 2.2)], spec.get("band_layer", "c"), 60.6, "hat", shade=False, lum=0.9)
    if spec.get("hat_star", True) and f.view != "up":
        f.rect(hx - 0.5, cut - 6.0, hx + 1.0, cut - 4.4, "detail", 60.8, "hat", color=GOLD, shade=False)
        f.rect(hx - 1.2, cut - 5.4, hx + 1.7, cut - 5.0, "detail", 60.8, "hat", color=GOLD, shade=False)


def bandana(f, spec):
    hx, hy, rx, ry = _head(f)
    L = _layer(spec, "c")
    dome(f, hx, hy - 0.2, rx + 0.6, ry + 0.4, hy - 2.0, L, 60)
    if f.view == "side":
        f.poly([(hx - rx - 0.4, hy - 2.0), (hx - rx - 3.5, hy - 0.5), (hx - rx - 2.5, hy + 2), (hx - rx - 0.2, hy - 0.5)], L, 59, "hat")
    elif f.view == "up":
        f.poly([(hx - 1.5, hy - 2.0), (hx + 1.5, hy - 2.0), (hx + 2.5, hy + 2), (hx - 2.5, hy + 2)], L, 61, "hat")


def headband(f, spec):
    hx, hy, rx, ry = _head(f)
    f.rect(hx - rx - 0.5, hy - 3.0, hx + rx + 0.5, hy - 1.3, _layer(spec, "c"), 60, "hat", shade=False, lum=0.86)
    if f.view == "down":
        f.rect(hx - 1.0, hy - 3.2, hx + 1.0, hy - 1.1, "detail", 60.1, "hat", color=GOLD, shade=False)


def helmet_horned(f, spec):
    hx, hy, rx, ry = _head(f)
    dome(f, hx, hy - 0.3, rx + 0.7, ry + 0.4, hy - 1.8, "detail", 60, "hat", color=IRON, shade=True)
    f.rect(hx - rx - 0.5, hy - 2.5, hx + rx + 0.5, hy - 1.2, "detail", 60.2, "hat", color=IRON_D, shade=False)
    if f.view == "side":
        f.poly([(hx - 1.5, hy - ry), (hx + 0.5, hy - ry - 0.5), (hx + 2.5, hy - ry - 4.5), (hx + 0.6, hy - ry - 5.5), (hx - 1.0, hy - ry - 2)], "detail", 60.4, "hat", color=BONE)
        return
    for s in (-1, 1):
        f.poly([(hx + s * (rx - 0.5), hy - 2.4), (hx + s * (rx + 1.5), hy - 3.0), (hx + s * (rx + 3.5), hy - ry - 3.0), (hx + s * (rx + 1.0), hy - ry - 1.6), (hx + s * (rx - 1.8), hy - ry + 1.5)], "detail", 60.4, "hat", color=BONE)


def helmet_crest(f, spec):
    hx, hy, rx, ry = _head(f)
    dome(f, hx, hy - 0.3, rx + 0.7, ry + 0.4, hy - 1.6, "detail", 60, "hat", color=GOLD)
    f.rect(hx - rx - 0.5, hy - 2.4, hx + rx + 0.5, hy - 1.0, "detail", 60.2, "hat", color=(176, 130, 50), shade=False)
    if f.view == "side":
        f.poly([(hx - 4, hy - ry + 1), (hx - 3.0, hy - ry - 4.5), (hx + 3.2, hy - ry - 4.5), (hx + 4, hy - ry + 1.0)], spec.get("crest_layer", "a"), 60.4, "hat")
        f.poly([(hx + rx - 2, hy - 1.0), (hx + rx - 0.4, hy - 1.0), (hx + rx - 0.4, hy + 5), (hx + rx - 2.0, hy + 5)], "detail", 60.3, "hat", color=GOLD)
    else:
        f.poly([(hx - 1.2, hy - ry + 0.6), (hx - 2.5, hy - ry - 4.0), (hx + 2.5, hy - ry - 4.0), (hx + 1.2, hy - ry + 0.6)], spec.get("crest_layer", "a"), 60.4, "hat")
        if f.view == "down":
            f.rect(hx - rx - 0.3, hy - 1.0, hx - rx + 1.6, hy + 4.5, "detail", 60.3, "hat", color=GOLD)
            f.rect(hx + rx - 1.6, hy - 1.0, hx + rx + 0.3, hy + 4.5, "detail", 60.3, "hat", color=GOLD)


def helmet_round(f, spec):
    hx, hy, rx, ry = _head(f)
    dome(f, hx, hy - 0.3, rx + 0.8, ry + 0.4, hy - 1.8, "detail", 60, "hat", color=IRON)
    f.rect(hx - rx - 0.6, hy - 2.6, hx + rx + 0.6, hy - 1.2, "detail", 60.2, "hat", color=IRON_D, shade=False)
    if f.view == "down":
        f.rect(hx - 0.7, hy - 2.2, hx + 0.8, hy + 2.4, "detail", 60.3, "hat", color=IRON_D, shade=False)
    if f.view == "side":
        f.rect(hx + rx - 1.5, hy - 2.0, hx + rx + 0.1, hy + 2.0, "detail", 60.3, "hat", color=IRON_D, shade=False)


def kettle(f, spec):
    hx, hy, rx, ry = _head(f)
    f.ell(hx, hy - 2.6, rx + 3.6, 2.1, "detail", 59.9, "hatb", color=IRON_D)
    dome(f, hx, hy - 1.5, rx + 0.2, ry - 0.8, hy - 2.6, "detail", 60.2, "hat", color=IRON)


def headdress(f, spec):
    hx, hy, rx, ry = _head(f)
    f.rect(hx - rx - 0.5, hy - 3.2, hx + rx + 0.5, hy - 1.6, _layer(spec, "c"), 60, "hat", shade=False, lum=0.86)
    cols = [(220, 70, 60), (240, 190, 70), (70, 170, 130), (60, 130, 200), (220, 70, 60)]
    for i, c in enumerate(cols):
        ang = math.radians(-80 + i * 40) if f.view != "side" else math.radians(-130 + i * 25)
        bx, by = hx + (i - 2) * 2.6 if f.view != "side" else hx - 2 + i * 1.5, hy - 3.0
        f.poly([(bx - 1.2, by), (bx + 1.2, by), (bx + 2.0 * math.sin(ang) * 4 + (i - 2) * 1.2, by - 7.2 - (2 - abs(i - 2)) * 1.4)], "detail", 59.5 + i * 0.01, "hat", color=c, shade=False)


def sailor(f, spec):
    hx, hy, rx, ry = _head(f)
    dome(f, hx, hy - 0.4, rx + 0.5, ry + 0.2, hy - 2.0, "a", 60)
    f.rect(hx - rx - 0.7, hy - 3.0, hx + rx + 0.7, hy - 1.4, "a", 60.2, "hat", shade=False, lum=0.82)
    f.rect(hx - rx - 0.5, hy - 2.6, hx + rx + 0.5, hy - 1.8, "c", 60.3, "hat", shade=False, lum=0.9)


def circlet(f, spec):
    hx, hy, rx, ry = _head(f)
    f.rect(hx - rx - 0.4, hy - 3.0, hx + rx + 0.4, hy - 1.8, "detail", 60, "hat", color=GOLD, shade=False)
    if f.view == "down":
        f.ell(hx, hy - 3.0, 1.3, 1.3, "detail", 60.2, "hat", color=(90, 190, 230), shade=False)


def spyhat(f, spec):  # a brimmed hat pulled low
    hx, hy, rx, ry = _head(f)
    f.ell(hx, hy - 2.0, rx + 3.8, 2.0, "a", 59.9, "hatb")
    dome(f, hx, hy - 1.8, rx - 0.2, ry - 1.4, hy - 2.4, "a", 60.2, "hat")
    f.rect(hx - rx + 0.6, hy - 4.3, hx + rx - 0.6, hy - 3.0, "c", 60.4, "hat", shade=False, lum=0.9)


def crown_laurel(f, spec):
    hx, hy, rx, ry = _head(f)
    for i in range(7):
        a = math.radians(200 + i * 23)
        f.ell(hx + (rx + 0.2) * math.cos(a), hy - 0.5 + (ry - 0.4) * math.sin(a), 1.3, 1.0, "detail", 60.3, "hat", color=(90, 160, 80), shade=True)


HATS = {"cap": cap, "beanie": beanie, "straw": straw, "toque": toque, "hardhat": hardhat, "hood": hood, "wizard": wizard, "bandana": bandana, "headband": headband,
        "helmet_horned": helmet_horned, "helmet_crest": helmet_crest, "helmet_round": helmet_round, "kettle": kettle, "headdress": headdress, "sailor": sailor,
        "circlet": circlet, "spyhat": spyhat, "laurel": crown_laurel}

"""Clothing drawn over the rig: tunics, robes, trousers, boots, belts, aprons, cloaks.  Layers: a = main cloth, b = second cloth,
c = trim / leather / accessory colour, detail = untinted (metal, wood, gems)."""
from __future__ import annotations

import math

from .rig import Figure, rad

GOLD = (236, 186, 70)
IRON = (176, 184, 196)
IRON_D = (110, 118, 134)
WOOD = (136, 92, 56)
WOOD_D = (96, 62, 40)
LEATHER = (112, 72, 46)


def torso(f: Figure, spec: dict) -> None:
    """Tunic / robe / vest / coat body.  spec: hem (px below hip, may be large for robes), flare, layer, sleeve."""
    D, sk, v, p = f.D, f.sk, f.view, f.p
    hx, hip_y = sk["hip"]
    hem = spec.get("hem", 3.0)
    flare = spec.get("flare", 0.8)
    layer = spec.get("layer", "a")
    hem_y = min(hip_y + hem, 44.0 if hem > 8 else hip_y + hem)
    shx, shy = sk["sh_x"], sk["sh_y"]
    tw = D["tw"] / 2 + spec.get("bulk", 0.5)
    sw = spec.get("sway", 0.0)
    if v == "side":
        a_n, a_f = p["legn"][0], p["legf"][0]
        swing = math.sin(rad(max(a_n, a_f, key=abs))) * min(hem, 14) * 0.3
        pts = [(shx - tw + 0.4, shy - 0.2), (shx + tw - 1.4, shy - 0.2), (shx + tw - 0.2, shy + 2.0), (hx + tw - 0.2 + flare + swing * 0.6, hem_y),
               (hx - tw + 0.2 - flare + swing * 0.2, hem_y)]
        if spec.get("skirt_back"):
            pts[-1] = (pts[-1][0] - 1.5, hem_y)
        f.poly(pts, layer, 31, "torso")
        if spec.get("hem_trim"):
            f.poly([(pts[4][0], hem_y), (pts[3][0], hem_y), (pts[3][0] - 0.1, hem_y - 1.5), (pts[4][0] + 0.1, hem_y - 1.5)], spec.get("trim_layer", "c"), 31.2, "torso", shade=False, lum=0.9)
        return
    pts = [(shx - tw, shy + 0.6), (shx - tw + 1.3, shy - 0.4), (shx + tw - 1.3, shy - 0.4), (shx + tw, shy + 0.6), (hx + tw + flare + sw, hem_y),
           (hx - tw - flare + sw, hem_y)]
    if hem > 5:
        pts = [(shx - tw, shy + 0.6), (shx - tw + 1.3, shy - 0.4), (shx + tw - 1.3, shy - 0.4), (shx + tw, shy + 0.6), (hx + tw - 0.4, hip_y + 1),
               (hx + tw + flare + sw + 0.8, hem_y - 1.5), (hx + tw + flare + sw, hem_y), (hx - tw - flare + sw, hem_y), (hx - tw - flare + sw - 0.8, hem_y - 1.5), (hx - tw + 0.4, hip_y + 1)]
    f.poly(pts, layer, 31, "torso")
    if spec.get("hem_trim"):
        Lx, Rx = hx - tw - flare + sw, hx + tw + flare + sw
        f.poly([(Lx - 0.3, hem_y), (Rx + 0.3, hem_y), (Rx + 0.1, hem_y - 1.5), (Lx - 0.1, hem_y - 1.5)], spec.get("trim_layer", "c"), 31.2, "torso", shade=False, lum=0.9)


def sleeves(f: Figure, spec: dict) -> None:
    """spec['sleeve']: 'none' | 'short' | 'long' | 'bell'."""
    mode = spec.get("sleeve", "short")
    if mode == "none":
        return
    D, sk, v = f.D, f.sk, f.view
    layer = spec.get("sleeve_layer", spec.get("layer", "a"))
    names = ("n", "f") if v == "side" else ("l", "r")
    for nm in names:
        z = (45.5 if nm == "n" else 12.5) if v == "side" else 40.5
        r = D["aw"] + 0.5
        sh, el, wr = sk["sh_" + nm], sk["elbow_" + nm], sk["wrist_" + nm]
        f.cap(sh, el, r, r - 0.1, layer, z, "arm" + nm)
        if mode in ("long", "bell"):
            end = (el[0] + (wr[0] - el[0]) * 0.82, el[1] + (wr[1] - el[1]) * 0.82)
            if mode == "bell":
                f.cap(el, end, r - 0.1, r + 1.4, layer, z + .05, "arm" + nm)
            else:
                f.cap(el, end, r - 0.1, r - 0.25, layer, z + .05, "arm" + nm)
        if spec.get("cuff"):
            e2 = (el[0] + (wr[0] - el[0]) * (0.8 if mode != "short" else 0.1), el[1] + (wr[1] - el[1]) * (0.8 if mode != "short" else 0.1))
            f.ell(e2[0], e2[1], r + (0.4 if mode == "bell" else 0.0), 1.2, spec.get("trim_layer", "c"), z + .1, "arm" + nm, shade=False, lum=0.9)


def legs(f: Figure, spec: dict) -> None:
    mode = spec.get("legs", "trousers")
    if mode in ("none", "robe"):
        return
    D, sk, v = f.D, f.sk, f.view
    layer = spec.get("legs_layer", "b")
    lw = D["lw"] + 0.35
    hx, hip_y = sk["hip"]
    names = ("n", "f") if v == "side" else ("l", "r")
    for nm in names:
        z = ((20 if nm == "n" else 14) if v == "side" else 20) + 0.3
        if v == "side":
            top = (hx, hip_y)
            kn, an = sk["knee_" + nm], sk["ankle_" + nm]
            f.cap(top, kn, lw, lw - 0.1, layer, z, "leg" + nm)
            if mode == "shorts":
                continue
            lower_end = (kn[0] + (an[0] - kn[0]) * 0.86, kn[1] + (an[1] - kn[1]) * 0.86)
            f.cap(kn, lower_end, lw - 0.1, lw - 0.35, layer, z + .1, "leg" + nm)
        else:
            top, an = sk["top_" + nm], sk["ankle_" + nm]
            end = top if mode == "shorts" else (top[0] + (an[0] - top[0]) * 0.86, top[1] + (an[1] - top[1]) * 0.86)
            if mode == "shorts":
                end = (top[0] + (an[0] - top[0]) * 0.5, top[1] + (an[1] - top[1]) * 0.5)
            f.cap(top, end, lw, lw - 0.3, layer, z, "leg" + nm)


def boots(f: Figure, spec: dict) -> None:
    mode = spec.get("boots", "boots")
    if mode == "none":
        return
    bare = mode == "bare"
    kw = {} if bare else dict(color=spec.get("boot_color", (98, 68, 48)))
    layer = "skin" if bare else "detail"
    sk, v = f.sk, f.view
    tall = spec.get("boot_h", 3.2)
    names = ("n", "f") if v == "side" else ("l", "r")
    for nm in names:
        an = sk["ankle_" + nm]
        z = ((21 if nm == "n" else 15) if v == "side" else 21)
        if v == "side":
            kn = sk["knee_" + nm]
            dx, dy = an[0] - kn[0], an[1] - kn[1]
            ln = math.hypot(dx, dy) or 1
            ux, uy = dx / ln, dy / ln
            top = (an[0] - ux * tall, an[1] - uy * tall)
            if not bare:
                f.cap(top, an, f.D["lw"] + 0.2, f.D["lw"] + 0.1, layer, z, "leg" + nm, **kw)
            f.poly([(an[0] - 2.0, an[1] - 1.8), (an[0] + 1.4, an[1] - 2.2), (an[0] + 4.6, an[1] + 0.3), (an[0] + 4.4, an[1] + 1.3), (an[0] - 2.2, an[1] + 1.3)], layer, z + .2, "leg" + nm, **kw)
        else:
            top = (an[0], an[1] - tall)
            if not bare:
                f.cap(top, an, f.D["lw"] + 0.2, f.D["lw"] + 0.2, layer, z, "leg" + nm, **kw)
            f.ell(an[0], an[1] + 0.2, 2.9, 1.9, layer, z + .2, "leg" + nm, **kw)


def belt(f: Figure, spec: dict) -> None:
    if not spec.get("belt", True):
        return
    sk, v, D = f.sk, f.view, f.D
    hx, hip_y = sk["hip"]
    tw = D["tw"] / 2 + 0.5
    y = hip_y - 1.6
    if v == "side":
        f.poly([(hx - tw + 0.6, y), (hx + tw - 0.2, y), (hx + tw - 0.2, y + 1.9), (hx - tw + 0.6, y + 1.9)], spec.get("belt_layer", "c"), 32, "torso", shade=False, lum=0.82)
    else:
        f.poly([(hx - tw + 0.1, y), (hx + tw - 0.1, y), (hx + tw - 0.1, y + 1.9), (hx - tw + 0.1, y + 1.9)], spec.get("belt_layer", "c"), 32, "torso", shade=False, lum=0.82)
        if v == "down" and spec.get("buckle", True):
            f.rect(hx - 1.2, y - 0.2, hx + 1.2, y + 2.0, "detail", 32.1, "torso", color=GOLD, shade=False)


def apron(f: Figure, spec: dict) -> None:
    if not spec.get("apron"):
        return
    sk, v, D = f.sk, f.view, f.D
    hx, hip_y = sk["hip"]
    layer = spec.get("apron_layer", "c")
    ln = spec.get("apron_len", 8.5)
    top = sk["sh_y"] + 3.0
    if v == "side":
        f.poly([(hx + 2.0, top), (hx + D["tw"] / 2 + 0.9, top + 0.5), (hx + D["tw"] / 2 + 1.1, hip_y + ln), (hx + 0.4, hip_y + ln)], layer, 33, "apron")
    elif v == "down":
        w = D["tw"] / 2 - 0.6
        f.poly([(hx - w + 1.2, top), (hx + w - 1.2, top), (hx + w + 0.9, hip_y + 1), (hx + w + 1.3, hip_y + ln), (hx - w - 1.3, hip_y + ln), (hx - w - 0.9, hip_y + 1)], layer, 33, "apron")
        f.line((hx - w + 1.2, top), (hx - 2.0, sk["sh_y"] - 0.2), 0.9, layer, 33.1, "apron", shade=False, lum=0.8)
        f.line((hx + w - 1.2, top), (hx + 2.0, sk["sh_y"] - 0.2), 0.9, layer, 33.1, "apron", shade=False, lum=0.8)


def cloak(f: Figure, spec: dict) -> None:
    """A cape / cloak behind (or over, from the back) the figure; flutters with leg swing."""
    if not spec.get("cloak"):
        return
    sk, v, D, p = f.sk, f.view, f.D, f.p
    hx, hip_y = sk["hip"]
    layer = spec.get("cloak_layer", "b")
    ln = spec.get("cloak_len", 13.0)
    shx, shy = sk["sh_x"], sk["sh_y"]
    swing = max(abs(p["legn"][0]), abs(p["legf"][0])) / 30.0 if v == "side" else abs(p["legl"][0] - p["legr"][0]) / 5.0
    hy = min(hip_y + ln, 44.5)
    if v == "side":
        kick = 1.5 + swing * 3.0 + abs(p["lean"]) * 0.5
        f.poly([(shx - 3.5, shy), (shx + 1.0, shy), (hx + 1.0, hy - 2), (hx - 5.5 - kick, hy), (hx - 4.8 - kick, hy - 5), (shx - 4.6, shy + 6)], layer, 8, "cloak")
    elif v == "down":
        w = D["tw"] / 2 + 1.2
        f.poly([(shx - w, shy), (shx + w, shy), (hx + w + 2.6, hy), (hx - w - 2.6, hy)], layer, 8, "cloak")
    else:
        w = D["tw"] / 2 + 1.3
        f.poly([(shx - w, shy - 0.6), (shx + w, shy - 0.6), (hx + w + 2.8, hy), (hx - w - 2.8, hy)], layer, 70, "cloak")
        f.poly([(shx - 2.5, shy - 1.2), (shx + 2.5, shy - 1.2), (hx + 1.5, hy), (hx - 1.5, hy)], layer, 70.1, "cloak", shade=False, lum=0.74)


def collar(f: Figure, spec: dict) -> None:
    if f.view == "up" or not spec.get("collar"):
        return
    sk, D = f.sk, f.D
    hx, hy = sk["head"]
    y = sk["sh_y"]
    layer = spec.get("collar_layer", "c")
    if f.view == "down":
        f.poly([(sk["sh_x"] - 4.6, y - 0.4), (sk["sh_x"] + 4.6, y - 0.4), (sk["sh_x"] + 2.8, y + 2.6), (sk["sh_x"], y + 4.0), (sk["sh_x"] - 2.8, y + 2.6)], layer, 33, "torso", shade=False, lum=0.86)
        f.poly([(sk["sh_x"] - 1.6, y - 0.2), (sk["sh_x"] + 1.6, y - 0.2), (sk["sh_x"], y + 3.0)], "skin", 33.1, "torso", shade=False, lum=0.86)
    else:
        f.poly([(sk["sh_x"] - 3.0, y - 0.4), (sk["sh_x"] + 3.2, y - 0.4), (sk["sh_x"] + 3.4, y + 2.4), (sk["sh_x"] - 2.2, y + 2.4)], layer, 33, "torso", shade=False, lum=0.86)


def draw_clothes(f: Figure, spec: dict) -> None:
    cloak(f, spec)
    legs(f, spec)
    boots(f, spec)
    torso(f, spec)
    belt(f, spec)
    apron(f, spec)
    collar(f, spec)
    sleeves(f, spec)

"""Held tools and carried gear.  Tools are attached to the hand joint of the animated arm, so they swing and tilt with it."""
from __future__ import annotations

import math
from functools import lru_cache

from .garments import GOLD, IRON, IRON_D, LEATHER, WOOD, WOOD_D
from .rig import Figure

STEEL = (206, 214, 226)
PAPER = (240, 228, 196)
BREAD = (214, 150, 76)
BREAD_D = (170, 104, 52)
CYAN = (110, 220, 255)


def _fore(f: Figure, nm: str) -> tuple[float, float]:
    el, wr = f.sk["elbow_" + nm], f.sk["wrist_" + nm]
    return (wr[0] - el[0], wr[1] - el[1])


@lru_cache(maxsize=None)
def _rest_psi(view: str, nm: str, body: str) -> float:
    from .clips import pose_for
    g = Figure(view, pose_for("idle", 0, view), body)
    vx, vy = _fore(g, nm)
    return math.degrees(math.atan2(vx, vy))


def hand(f: Figure, which: str):
    """which: 'main' or 'off'.  Returns (name, wrist, z, rest_psi, current_psi)."""
    side = f.view == "side"
    nm = {"main": "n" if side else "r", "off": "f" if side else "l"}[which]
    if f.view == "up":
        nm = {"main": "l", "off": "r"}[which]
    vx, vy = _fore(f, nm)
    psi = math.degrees(math.atan2(vx, vy))
    z = (45.8 if nm == "n" else 12.8) if side else 41.0
    return nm, f.sk["wrist_" + nm], z, _rest_psi(f.view, nm, f.body_type), psi


def frame(up_deg: float):
    """unit vectors for a tool whose 'up' points up_deg clockwise from straight up (screen space, y down)."""
    a = math.radians(up_deg)
    u = (math.sin(a), -math.cos(a))
    n = (math.cos(a), math.sin(a))  # to the right of u
    return u, n


def P(g, u, n, a, b):
    return (g[0] + u[0] * a + n[0] * b, g[1] + u[1] * a + n[1] * b)


def shaft(f, g, u, n, a0, a1, w, z, color=WOOD, grp="tool"):
    f.cap(P(g, u, n, a0, 0), P(g, u, n, a1, 0), w, w, "detail", z, grp, color=color)


def _setup(f, spec_prop):
    which = spec_prop.get("hand", "main")
    nm, g, z, psi0, psi = hand(f, which)
    ab = spec_prop.get("abs", {})
    base = ab.get(f.view, ab.get("side", 0.0)) if isinstance(ab, dict) else ab
    follow = spec_prop.get("follow", 0.9)
    up = base + follow * (psi - psi0)
    u, n = frame(up)
    return nm, g, z, u, n


def draw(f: Figure, prop, spec: dict) -> None:
    if f.p["rot"] > 45.0:  # a falling figure lets go of what it holds
        return
    kinds = prop if isinstance(prop, list) else [prop]
    for pr in kinds:
        if isinstance(pr, str):
            pr = {"kind": pr}
        fn = TOOLS[pr["kind"]]
        nm, g, z, u, n = _setup(f, pr)
        fn(f, g, u, n, z, pr, spec)


def draw_back(f: Figure, kind, spec: dict) -> None:
    kinds = kind if isinstance(kind, list) else [kind]
    for k in kinds:
        BACK[k](f, spec)


# ---------------------------------------------------------------- tools
def staff(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -11, 12, 0.95, z, pr.get("wood", WOOD))
    top = P(g, u, n, 13.5, 0)
    col = pr.get("magic", spec.get("magic", CYAN))
    style = pr.get("head", "orb")
    glow = f.p["glow"]
    ol = pr.get("orb_layer", "detail")
    if style == "orb":
        kw = dict(color=col) if ol == "detail" else dict()
        f.ell(top[0], top[1], 2.9 + glow * 0.8, 2.9 + glow * 0.8, ol, z + .3, "tool", **kw)
        f.ell(top[0] - 0.7, top[1] - 0.8, 0.9, 0.9, "detail", z + .4, "tool", color=(255, 255, 255), shade=False)
        for s in (-1, 1):
            f.poly([P(g, u, n, 11.0, 0), P(g, u, n, 12.8, s * 2.6), P(g, u, n, 14.2, s * 2.2), P(g, u, n, 12.4, 0)], "detail", z + .2, "tool", color=GOLD, shade=False)
    elif style == "crystal":
        kw = dict(color=col) if ol == "detail" else dict()
        f.poly([P(g, u, n, 12, -1.9), P(g, u, n, 15, -2.6), P(g, u, n, 19.5, 0), P(g, u, n, 15, 2.6), P(g, u, n, 12, 1.9)], ol, z + .3, "tool", **kw)
        f.poly([P(g, u, n, 13, -1.0), P(g, u, n, 16.5, -0.3), P(g, u, n, 18.4, 0), P(g, u, n, 16, 0.4)], "detail", z + .35, "tool", color=(255, 255, 255), shade=False)
    elif style == "crook":
        f.cap(P(g, u, n, 12, 0), P(g, u, n, 15, 2.2), 0.95, 0.95, "detail", z + .2, "tool", color=pr.get("wood", WOOD))
        f.cap(P(g, u, n, 15, 2.2), P(g, u, n, 13.2, 4.6), 0.95, 0.95, "detail", z + .2, "tool", color=pr.get("wood", WOOD))
    elif style == "flame":
        hot = pr.get("flame", ((255, 120, 40), (255, 220, 90)))
        f.ell(top[0], top[1], 2.6, 3.2, "detail", z + .3, "tool", color=hot[0])
        f.ell(top[0], top[1] + 0.5, 1.4, 2.0, "detail", z + .4, "tool", color=hot[1], shade=False)
    elif style == "plain":
        f.ell(top[0], top[1], 1.4, 1.4, "detail", z + .2, "tool", color=WOOD_D)
    elif style == "leaf":
        f.poly([P(g, u, n, 11, 0), P(g, u, n, 14, -3.2), P(g, u, n, 18, 0), P(g, u, n, 14, 3.2)], "detail", z + .3, "tool", color=(110, 200, 90))
    if glow > 0.2:
        for i in range(4):
            a = i * 1.6 + glow * 3
            f.ell(top[0] + math.cos(a) * (4 + glow * 3), top[1] + math.sin(a) * (4 + glow * 3), 0.9, 0.9, "detail", z + .5, "fx", color=col, shade=False)


def axe(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -3.5, 11.0, 0.9, z)
    f.poly([P(g, u, n, 8.2, 0), P(g, u, n, 11.5, 0), P(g, u, n, 12.2, 3.0), P(g, u, n, 13.0, 5.4), P(g, u, n, 9.6, 5.8), P(g, u, n, 7.4, 3.2)], "detail", z + .2, "tool", color=STEEL)


def pickaxe(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -3.5, 11.0, 0.9, z)
    f.poly([P(g, u, n, 9.0, -6.2), P(g, u, n, 11.4, -3.0), P(g, u, n, 11.6, 3.0), P(g, u, n, 9.0, 6.4), P(g, u, n, 10.4, 3.0), P(g, u, n, 10.4, -3.0)], "detail", z + .2, "tool", color=IRON)


def hammer(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -3, 8, 0.9, z)
    f.poly([P(g, u, n, 6.4, -2.8), P(g, u, n, 6.4, 3.0), P(g, u, n, 10.0, 3.0), P(g, u, n, 10.0, -2.8)], "detail", z + .2, "tool", color=IRON)


def mallet(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -3, 7, 0.9, z)
    f.poly([P(g, u, n, 6.0, -2.8), P(g, u, n, 6.0, 2.8), P(g, u, n, 9.6, 2.8), P(g, u, n, 9.6, -2.8)], "detail", z + .2, "tool", color=WOOD_D)


def pitchfork(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -5, 14, 0.85, z)
    for s in (-2.2, 0.0, 2.2):
        f.cap(P(g, u, n, 14, s), P(g, u, n, 18.4, s), 0.5, 0.45, "detail", z + .2, "tool", color=STEEL)
    f.cap(P(g, u, n, 14, -2.2), P(g, u, n, 14, 2.2), 0.6, 0.6, "detail", z + .2, "tool", color=STEEL)


def spade(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -4, 12, 0.85, z)
    f.poly([P(g, u, n, 11.5, -2.2), P(g, u, n, 11.5, 2.2), P(g, u, n, 16.5, 2.0), P(g, u, n, 18.0, 0), P(g, u, n, 16.5, -2.0)], "detail", z + .2, "tool", color=IRON)


def scythe(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -6, 16, 0.85, z, (70, 60, 70))
    f.poly([P(g, u, n, 15.5, 0), P(g, u, n, 17.5, 3.5), P(g, u, n, 17.2, 8.5), P(g, u, n, 15.6, 11.0), P(g, u, n, 15.2, 8.0), P(g, u, n, 15.8, 3.5), P(g, u, n, 14.0, 0.5)], "detail", z + .2, "tool", color=STEEL)


def sword(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -3.5, 0.5, 0.8, z, LEATHER)
    f.cap(P(g, u, n, 0.8, -2.4), P(g, u, n, 0.8, 2.4), 0.7, 0.7, "detail", z + .2, "tool", color=GOLD)
    f.poly([P(g, u, n, 1.2, -0.9), P(g, u, n, 1.2, 0.9), P(g, u, n, 11.5, 0.7), P(g, u, n, 12.8, 0)], "detail", z + .1, "tool", color=STEEL)
    f.line(P(g, u, n, 1.6, 0), P(g, u, n, 11.5, 0), 0.4, "detail", z + .15, "tool", color=(255, 255, 255), shade=False)


def spear(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -9, 18, 0.8, z)
    f.poly([P(g, u, n, 17.5, -1.7), P(g, u, n, 21.5, 0), P(g, u, n, 17.5, 1.7)], "detail", z + .2, "tool", color=STEEL)
    f.poly([P(g, u, n, 16.8, -1.0), P(g, u, n, 17.6, -1.0), P(g, u, n, 17.6, 1.0), P(g, u, n, 16.8, 1.0)], "a", z + .3, "tool", shade=False, lum=0.9)


def shield(f, g, u, n, z, pr, spec):
    c = P(g, u, n, 0.5, 1.0)
    shape = pr.get("shape", "round")
    r = 4.8
    if shape == "kite":
        f.poly([(c[0] - 4, c[1] - 5), (c[0] + 4, c[1] - 5), (c[0] + 4, c[1] + 1.5), (c[0], c[1] + 7), (c[0] - 4, c[1] + 1.5)], "a", z + .5, "shield")
    else:
        f.ell(c[0], c[1], r, r, "a", z + .5, "shield")
    f.ell(c[0], c[1], 1.5, 1.5, "detail", z + .6, "shield", color=GOLD)
    f.ell(c[0], c[1], r, r, "c", z + .45, "shield", shade=False, lum=0.8) if shape != "kite" else None


def bow(f, g, u, n, z, pr, spec):
    f.cap(P(g, u, n, -8, 2.0), P(g, u, n, 0, 4.2), 0.6, 0.8, "detail", z, "tool", color=WOOD)
    f.cap(P(g, u, n, 0, 4.2), P(g, u, n, 8, 2.0), 0.8, 0.6, "detail", z, "tool", color=WOOD)
    f.line(P(g, u, n, -8, 2.0), P(g, u, n, 8, 2.0), 0.4, "detail", z - .1, "tool", color=(235, 230, 215), shade=False)


def rod(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -4, 16, 0.55, z, WOOD_D)
    tip = P(g, u, n, 16, 0)
    f.line(tip, (tip[0] + 1.5, tip[1] + 9), 0.35, "detail", z, "tool", color=(235, 235, 225), shade=False)
    f.ell(tip[0] + 1.5, tip[1] + 9.5, 1.1, 1.1, "detail", z + .1, "tool", color=(230, 60, 60), shade=False)


def mug(f, g, u, n, z, pr, spec):
    c = P(g, u, n, 2.2, 0)
    f.rect(c[0] - 2, c[1] - 2.5, c[0] + 2, c[1] + 2.2, "detail", z + .3, "tool", color=(210, 170, 90))
    f.rect(c[0] - 2.4, c[1] - 3.4, c[0] + 2.4, c[1] - 2.0, "detail", z + .4, "tool", color=(250, 246, 236), shade=False)
    f.cap((c[0] + 2.2, c[1] - 1), (c[0] + 2.2, c[1] + 1), 0.9, 0.9, "detail", z + .2, "tool", color=(180, 140, 70))


def loaf(f, g, u, n, z, pr, spec):
    c = P(g, u, n, 3.0, 0)
    f.ell(c[0], c[1], 4.0, 2.1, "detail", z + .3, "tool", color=BREAD)
    for dx in (-1.6, 0, 1.6):
        f.line((c[0] + dx - 0.5, c[1] - 1.2), (c[0] + dx + 0.5, c[1] + 0.6), 0.5, "detail", z + .4, "tool", color=BREAD_D, shade=False)


def peel(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -4, 12, 0.8, z)
    f.poly([P(g, u, n, 11, -2.6), P(g, u, n, 11, 2.6), P(g, u, n, 17, 2.8), P(g, u, n, 17, -2.8)], "detail", z + .2, "tool", color=(196, 150, 90))
    c = P(g, u, n, 14, 0)
    f.ell(c[0], c[1], 2.2, 1.6, "detail", z + .3, "tool", color=BREAD)


def basket(f, g, u, n, z, pr, spec):
    c = (g[0], g[1] + 3.0)
    f.poly([(c[0] - 4, c[1] - 1), (c[0] + 4, c[1] - 1), (c[0] + 3, c[1] + 3.5), (c[0] - 3, c[1] + 3.5)], "detail", z + .3, "tool", color=(196, 150, 80))
    f.line((c[0] - 4, c[1] + 0.8), (c[0] + 4, c[1] + 0.8), 0.5, "detail", z + .35, "tool", color=(140, 98, 50), shade=False)
    for dx, col in ((-2, (220, 70, 60)), (0.4, (240, 190, 60)), (2.2, (120, 190, 80))):
        f.ell(c[0] + dx, c[1] - 1.6, 1.4, 1.4, "detail", z + .25, "tool", color=col)
    f.line((c[0] - 3.4, c[1] - 1), (g[0], g[1] - 0.5), 0.5, "detail", z + .2, "tool", color=(140, 98, 50), shade=False)


def wrench(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -3, 9, 1.0, z, IRON_D)
    c = P(g, u, n, 10.2, 0)
    f.ell(c[0], c[1], 2.4, 2.4, "detail", z + .2, "tool", color=IRON)


def scroll(f, g, u, n, z, pr, spec):
    c = P(g, u, n, 2.8, 0)
    f.rect(c[0] - 4.2, c[1] - 2.6, c[0] + 4.2, c[1] + 2.6, "detail", z + .3, "tool", color=PAPER)
    f.rect(c[0] - 4.6, c[1] - 3.0, c[0] - 3.0, c[1] + 3.0, "detail", z + .4, "tool", color=(196, 150, 90))
    f.rect(c[0] + 3.0, c[1] - 3.0, c[0] + 4.6, c[1] + 3.0, "detail", z + .4, "tool", color=(196, 150, 90))
    for dy in (-1.2, 0.2, 1.4):
        f.line((c[0] - 2.4, c[1] + dy), (c[0] + 2.4, c[1] + dy), 0.4, "detail", z + .5, "tool", color=(110, 90, 80), shade=False)


def book(f, g, u, n, z, pr, spec):
    c = P(g, u, n, 2.4, 0)
    f.rect(c[0] - 3.2, c[1] - 3.2, c[0] + 3.2, c[1] + 3.2, "detail", z + .3, "tool", color=pr.get("color", (130, 60, 70)))
    f.rect(c[0] - 2.4, c[1] - 2.4, c[0] + 2.8, c[1] + 2.6, "detail", z + .4, "tool", color=PAPER, shade=False) if pr.get("open") else f.rect(c[0] - 1.2, c[1] - 1.6, c[0] + 1.2, c[1] + 1.6, "detail", z + .4, "tool", color=GOLD, shade=False)


def lantern(f, g, u, n, z, pr, spec):
    c = (g[0], g[1] + 4.0)
    f.line((g[0], g[1]), (c[0], c[1] - 2.4), 0.5, "detail", z + .1, "tool", color=IRON_D, shade=False)
    f.rect(c[0] - 2.2, c[1] - 2.6, c[0] + 2.2, c[1] + 2.8, "detail", z + .3, "tool", color=IRON_D)
    f.rect(c[0] - 1.4, c[1] - 1.6, c[0] + 1.4, c[1] + 1.8, "detail", z + .4, "tool", color=(255, 226, 120), shade=False)


def club(f, g, u, n, z, pr, spec):
    f.cap(P(g, u, n, -3, 0), P(g, u, n, 7, 0), 0.9, 0.9, "detail", z, "tool", color=WOOD)
    f.cap(P(g, u, n, 7, 0), P(g, u, n, 12.5, 0), 1.3, 2.6, "detail", z + .1, "tool", color=WOOD_D)


def rifle(f, g, u, n, z, pr, spec):
    f.cap(P(g, u, n, -5, 0.4), P(g, u, n, 12, 0.4), 0.95, 0.8, "detail", z, "tool", color=(70, 74, 86))
    f.cap(P(g, u, n, -6, 0.6), P(g, u, n, -1, 0.6), 1.5, 1.4, "detail", z - .1, "tool", color=WOOD)


def sling(f, g, u, n, z, pr, spec):
    c = P(g, u, n, 4, 0)
    f.line(g, c, 0.4, "detail", z, "tool", color=LEATHER, shade=False)
    f.ell(c[0], c[1], 1.8, 1.4, "detail", z + .2, "tool", color=LEATHER)


def torch(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -3, 9, 0.9, z)
    top = P(g, u, n, 10.5, 0)
    f.ell(top[0], top[1], 2.4, 3.0, "detail", z + .3, "tool", color=(255, 130, 40))
    f.ell(top[0], top[1] + 0.6, 1.2, 1.8, "detail", z + .4, "tool", color=(255, 226, 110), shade=False)


def tongs(f, g, u, n, z, pr, spec):
    f.cap(P(g, u, n, -2, -0.6), P(g, u, n, 10, -0.8), 0.5, 0.5, "detail", z, "tool", color=IRON_D)
    f.cap(P(g, u, n, -2, 0.6), P(g, u, n, 10, 0.8), 0.5, 0.5, "detail", z, "tool", color=IRON_D)
    c = P(g, u, n, 10.5, 0)
    f.ell(c[0], c[1], 1.6, 1.2, "detail", z + .2, "tool", color=(255, 140, 60))


def chisel(f, g, u, n, z, pr, spec):
    f.cap(P(g, u, n, -2, 0), P(g, u, n, 6, 0), 0.9, 0.9, "detail", z, "tool", color=WOOD)
    f.cap(P(g, u, n, 6, 0), P(g, u, n, 10.5, 0), 0.7, 0.4, "detail", z + .1, "tool", color=STEEL)


def saw(f, g, u, n, z, pr, spec):
    f.poly([P(g, u, n, -1, -1.0), P(g, u, n, 12, -2.2), P(g, u, n, 12, 1.4), P(g, u, n, -1, 1.8)], "detail", z + .2, "tool", color=STEEL)
    f.cap(P(g, u, n, -3, 1.0), P(g, u, n, 0, 1.0), 1.2, 1.2, "detail", z + .1, "tool", color=WOOD)


def cleaver(f, g, u, n, z, pr, spec):
    f.cap(P(g, u, n, -2, 0), P(g, u, n, 2, 0), 0.9, 0.9, "detail", z, "tool", color=WOOD)
    f.poly([P(g, u, n, 2, -2.4), P(g, u, n, 9, -2.4), P(g, u, n, 9, 2.0), P(g, u, n, 2, 1.0)], "detail", z + .2, "tool", color=STEEL)


def ladle(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -3, 9, 0.7, z, IRON_D)
    c = P(g, u, n, 10, 0)
    f.ell(c[0], c[1], 2.2, 1.8, "detail", z + .2, "tool", color=IRON)


def pipe_wand(f, g, u, n, z, pr, spec):
    shaft(f, g, u, n, -2, 7, 0.7, z, (70, 60, 90))
    top = P(g, u, n, 8, 0)
    f.ell(top[0], top[1], 1.4, 1.4, "detail", z + .2, "tool", color=spec.get("magic", CYAN))


def syringe_bag(f, g, u, n, z, pr, spec):  # medic's satchel held at the hip
    c = (g[0], g[1] + 2.4)
    f.rect(c[0] - 3.4, c[1] - 2.6, c[0] + 3.4, c[1] + 2.8, "detail", z + .3, "tool", color=(240, 240, 236))
    f.rect(c[0] - 0.8, c[1] - 1.8, c[0] + 0.8, c[1] + 1.8, "detail", z + .4, "tool", color=(210, 50, 50), shade=False)
    f.rect(c[0] - 1.8, c[1] - 0.8, c[0] + 1.8, c[1] + 0.8, "detail", z + .4, "tool", color=(210, 50, 50), shade=False)


def pistols(f, g, u, n, z, pr, spec):
    f.cap(P(g, u, n, -1, 0), P(g, u, n, 6.5, 0), 0.9, 0.7, "detail", z, "tool", color=(60, 64, 76))


def tesla(f, g, u, n, z, pr, spec):
    f.cap(P(g, u, n, -3, 0), P(g, u, n, 9, 0), 1.5, 1.3, "detail", z, "tool", color=(80, 86, 104))
    c = P(g, u, n, 11, 0)
    f.ell(c[0], c[1], 2.6, 2.6, "detail", z + .1, "tool", color=(130, 220, 255))
    f.ell(c[0], c[1], 1.2, 1.2, "detail", z + .2, "tool", color=(255, 255, 255), shade=False)


def flame_thrower(f, g, u, n, z, pr, spec):
    f.cap(P(g, u, n, -4, 0), P(g, u, n, 10, 0), 1.1, 1.0, "detail", z, "tool", color=(130, 70, 60))
    c = P(g, u, n, 12, 0)
    f.ell(c[0], c[1], 2.0, 2.4, "detail", z + .1, "tool", color=(255, 130, 40))


def launcher(f, g, u, n, z, pr, spec):
    f.cap(P(g, u, n, -6, 0), P(g, u, n, 12, 0), 1.9, 2.2, "detail", z, "tool", color=(86, 98, 82))
    f.ell(*P(g, u, n, 12, 0), 2.3, 2.3, "detail", z + .1, "tool", color=(50, 56, 50))


TOOLS = {k: v for k, v in dict(staff=staff, axe=axe, pickaxe=pickaxe, hammer=hammer, mallet=mallet, pitchfork=pitchfork, spade=spade, scythe=scythe, sword=sword,
                              spear=spear, shield=shield, bow=bow, rod=rod, mug=mug, loaf=loaf, peel=peel, basket=basket, wrench=wrench, scroll=scroll, book=book,
                              lantern=lantern, club=club, rifle=rifle, sling=sling, torch=torch, tongs=tongs, chisel=chisel, saw=saw, cleaver=cleaver, ladle=ladle,
                              wand=pipe_wand, medbag=syringe_bag, pistols=pistols, tesla=tesla, flamer=flame_thrower, launcher=launcher).items()}


# ---------------------------------------------------------------- back items
def _back_center(f):
    sk = f.sk
    return sk["sh_x"], sk["sh_y"], sk["hip"][0], sk["hip"][1]


def sack(f, spec):
    sx, sy, hx, hy = _back_center(f)
    if f.view == "side":
        f.ell(sx - 5.8, sy + 6.2, 4.6, 6.2, "detail", 8, "back", color=(190, 150, 96))
        f.rect(sx - 7.4, sy + 0.2, sx - 3.8, sy + 2.2, "detail", 8.1, "back", color=(150, 108, 66), shade=False)
        f.line((sx - 3, sy + 1), (sx + 1.8, sy + 5), 0.9, "c", 46, "strap", shade=False, lum=0.82)
    elif f.view == "up":
        f.ell(sx, sy + 7.0, 6.2, 7.2, "detail", 70, "back", color=(190, 150, 96))
        f.rect(sx - 3.0, sy - 0.6, sx + 3.0, sy + 1.6, "detail", 70.1, "back", color=(150, 108, 66), shade=False)
    else:
        f.ell(sx + 3.2, sy - 0.6, 3.6, 3.0, "detail", 7, "back", color=(190, 150, 96))
        f.line((sx - 4.2, sy + 0.4), (sx + 2.0, sy + 8.4), 0.9, "c", 34, "strap", shade=False, lum=0.82)
        f.line((sx + 4.2, sy + 0.4), (sx - 2.0, sy + 8.4), 0.9, "c", 34, "strap", shade=False, lum=0.82)


def quiver(f, spec):
    sx, sy, hx, hy = _back_center(f)
    if f.view == "side":
        f.poly([(sx - 6.6, sy + 0.4), (sx - 3.4, sy - 1.2), (sx - 2.4, sy + 8.0), (sx - 5.6, sy + 9.0)], "detail", 8, "back", color=LEATHER)
        for i in range(3):
            f.poly([(sx - 6.4 + i, sy + 0.4), (sx - 7.4 + i, sy - 2.2), (sx - 5.6 + i, sy - 1.6)], "detail", 7.9, "back", color=(230, 220, 190), shade=False)
    elif f.view == "up":
        f.poly([(sx + 1.0, sy - 0.8), (sx + 5.4, sy + 0.6), (sx + 3.8, sy + 9.4), (sx - 0.2, sy + 8.4)], "detail", 70, "back", color=LEATHER)
        for i in range(3):
            f.poly([(sx + 1.6 + i * 1.2, sy), (sx + 1.2 + i * 1.2, sy - 3.0), (sx + 2.6 + i * 1.2, sy - 2.2)], "detail", 70.1, "back", color=(230, 220, 190), shade=False)
    else:
        f.poly([(sx + 3.0, sy - 2.2), (sx + 5.0, sy - 3.4), (sx + 5.4, sy - 0.4), (sx + 3.4, sy + 0.2)], "detail", 7, "back", color=(230, 220, 190), shade=False)


def backpack(f, spec):
    sx, sy, hx, hy = _back_center(f)
    if f.view == "side":
        f.poly([(sx - 7.2, sy + 0.5), (sx - 3.4, sy + 0.2), (sx - 3.2, sy + 9.0), (sx - 7.0, sy + 9.4)], "detail", 8, "back", color=LEATHER)
        f.rect(sx - 8.0, sy + 3.0, sx - 6.4, sy + 11.0, "detail", 7.9, "back", color=(210, 200, 170), shade=True)
    elif f.view == "up":
        f.poly([(sx - 5.2, sy - 0.2), (sx + 5.2, sy - 0.2), (sx + 5.6, sy + 10.0), (sx - 5.6, sy + 10.0)], "detail", 70, "back", color=LEATHER)
        f.rect(sx - 6.4, sy + 1.4, sx - 5.0, sy + 11.0, "detail", 70.1, "back", color=(210, 200, 170))
        f.rect(sx - 2.6, sy + 3.0, sx + 2.6, sy + 6.0, "detail", 70.1, "back", color=(140, 96, 60))
    else:
        f.line((sx - 4.0, sy + 0.4), (sx + 2.0, sy + 8.0), 0.9, "detail", 34, "strap", color=(120, 80, 50), shade=False)
        f.line((sx + 4.0, sy + 0.4), (sx - 2.0, sy + 8.0), 0.9, "detail", 34, "strap", color=(120, 80, 50), shade=False)
        f.ell(sx - 5.8, sy + 4, 1.6, 4, "detail", 7, "back", color=LEATHER)


def satchel(f, spec):
    sx, sy, hx, hy = _back_center(f)
    if f.view == "side":
        f.poly([(sx - 1.0, hy - 3), (sx + 4.2, hy - 3), (sx + 4.2, hy + 3.0), (sx - 1.0, hy + 3.0)], "detail", 46.5, "back", color=LEATHER)
        f.line((sx - 3, sy + 1), (sx + 3, hy - 3), 0.8, "detail", 46.4, "strap", color=(120, 80, 50), shade=False)
    elif f.view == "down":
        f.line((sx - 4.4, sy + 0.4), (hx + 3.0, hy - 1.0), 0.9, "detail", 34, "strap", color=(120, 80, 50), shade=False)
        f.poly([(hx + 1.6, hy - 3.6), (hx + 6.4, hy - 3.6), (hx + 6.4, hy + 1.8), (hx + 1.6, hy + 1.8)], "detail", 34.5, "back", color=LEATHER)
        f.rect(hx + 3.0, hy - 2.6, hx + 5.0, hy - 1.2, "detail", 34.6, "back", color=GOLD, shade=False)


def bedroll(f, spec):
    sx, sy, hx, hy = _back_center(f)
    if f.view == "side":
        f.cap((sx - 6.0, sy - 0.5), (sx - 6.0, sy + 9.0), 2.3, 2.3, "a", 8, "back")
    elif f.view == "up":
        f.cap((sx - 5.2, sy - 1.5), (sx + 5.2, sy - 1.5), 2.3, 2.3, "a", 70, "back")
    else:
        f.cap((sx - 5.2, sy - 1.0), (sx + 5.2, sy - 1.0), 2.0, 2.0, "a", 7, "back")


def scythe_back(f, spec):
    sx, sy, hx, hy = _back_center(f)
    f.cap((sx - 6, sy + 12), (sx - 1.5, sy - 8), 0.8, 0.8, "detail", 8 if f.view != "up" else 70, "back", color=(70, 60, 70))
    f.poly([(sx - 1.5, sy - 8), (sx + 3.0, sy - 8.8), (sx + 7.0, sy - 5.0), (sx + 2.6, sy - 6.2)], "detail", 8.1 if f.view != "up" else 70.1, "back", color=STEEL)


def wings_spirit(f, spec):
    sx, sy, hx, hy = _back_center(f)
    col = spec.get("magic", CYAN)
    for s in (-1, 1):
        f.poly([(sx + s * 3, sy + 2), (sx + s * 11, sy - 4), (sx + s * 9, sy + 6), (sx + s * 4, sy + 8)], "detail", 7 if f.view != "up" else 70, "back", color=col, shade=False)


BACK = dict(sack=sack, quiver=quiver, backpack=backpack, satchel=satchel, bedroll=bedroll, scythe=scythe_back, wings=wings_spirit)

"""Articulated humanoid rig.

`Figure` turns a pose (angles in degrees, offsets in pixels) into joint positions for one of three views (down = front,
side = facing right, up = back) and emits the body primitives (skin only).  Outfits add garments on top using the joints
(`Figure.sk`), so clothing, tools and hair follow every animation frame automatically.
"""
from __future__ import annotations

import math

from .raster import Prim

CELL_W, CELL_H = 56, 48
CX = 28.0
GROUND = 45.0

BODIES = {
    "adult": dict(leg1=6.0, leg2=6.4, torso=11.0, arm1=5.0, arm2=4.8, hrx=8.0, hry=7.8, tw=11.0, lw=2.2, aw=1.9),
    "child": dict(leg1=3.4, leg2=3.8, torso=8.4, arm1=3.4, arm2=3.3, hrx=7.8, hry=7.6, tw=8.6, lw=2.0, aw=1.7),
}

DEFAULT_POSE = dict(
    breath=0.0, head_dx=0.0, head_dy=0.0, lean=0.0, sway=0.0, squash=0.0, hop=0.0,
    mouth="closed", eyes="open", brows="neutral", blush=False,
    # side view: (thigh angle, knee bend) near / far
    legn=(0.0, 0.0), legf=(0.0, 0.0),
    # front/back: (lift px, outward spread px)
    legl=(0.0, 0.0), legr=(0.0, 0.0),
    # arms: (shoulder angle, elbow bend, foreshorten) near/far (side) or left/right (front/back)
    arm1=(8.0, 14.0, 0.0), arm2=(-8.0, 14.0, 0.0),
    rot=0.0, pivot=(CX, GROUND), fall_dx=0.0, fall_dy=0.0,
    glow=0.0, fx=None,
)


def pose(**kw) -> dict:
    p = dict(DEFAULT_POSE)
    p.update(kw)
    return p


def rad(d: float) -> float:
    return math.radians(d)


class Figure:
    def __init__(self, view: str, p: dict, body: str = "adult", scale_head: float = 1.0):
        self.view = view
        self.p = p
        self.body_type = body
        self.D = BODIES[body]
        self.prims: list[Prim] = []
        self.sk: dict = {}
        self._rot = rad(p["rot"])
        self._pv = p["pivot"]
        self.hs = scale_head
        self.ears = "round"
        self._skeleton()

    # ------------------------------------------------------------------ transform helpers
    def T(self, x: float, y: float) -> tuple[float, float]:
        if self._rot == 0.0:
            return (x, y)
        px, py = self._pv
        dx, dy = x - px, y - py
        c, s = math.cos(self._rot), math.sin(self._rot)
        return (px + dx * c - dy * s + self.p["fall_dx"], py + dx * s + dy * c + self.p["fall_dy"])

    def poly(self, pts, layer, z, grp="", **kw):
        self.prims.append(Prim("poly", tuple(self.T(*q) for q in pts), layer, z, grp, **kw))

    def ell(self, cx, cy, rx, ry, layer, z, grp="", **kw):
        if self._rot != 0.0:
            n = 18
            pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
            self.poly(pts, layer, z, grp, **kw)
            return
        self.prims.append(Prim("ell", (cx, cy, rx, ry), layer, z, grp, **kw))

    def cap(self, a, b, r0, r1, layer, z, grp="", **kw):
        (x0, y0), (x1, y1) = self.T(*a), self.T(*b)
        self.prims.append(Prim("cap", (x0, y0, x1, y1, r0, r1), layer, z, grp, **kw))

    def rect(self, x0, y0, x1, y1, layer, z, grp="", **kw):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer, z, grp, **kw)

    def line(self, a, b, wd, layer, z, grp="", **kw):
        (x0, y0), (x1, y1) = self.T(*a), self.T(*b)
        self.prims.append(Prim("line", (x0, y0, x1, y1, wd), layer, z, grp, thr=kw.pop("thr", 0.4), **kw))

    # ------------------------------------------------------------------ skeleton
    def _skeleton(self) -> None:
        D, p, v = self.D, self.p, self.view
        sk = self.sk
        leg = D["leg1"] + D["leg2"]
        if v == "side":
            feet = []
            for key in ("legn", "legf"):
                a, k = p[key]
                dy = D["leg1"] * math.cos(rad(a)) + D["leg2"] * math.cos(rad(a - k))
                dx = D["leg1"] * math.sin(rad(a)) + D["leg2"] * math.sin(rad(a - k))
                feet.append((dx, dy))
            hip_y = GROUND - max(f[1] for f in feet) - p["hop"] + p["squash"] * 0.0
            hip_y += p["squash"]
            hx = CX + p["sway"]
            sk["hip"] = (hx, hip_y)
            for key, f, name in (("legn", feet[0], "n"), ("legf", feet[1], "f")):
                a, k = p[key]
                knee = (hx + D["leg1"] * math.sin(rad(a)), hip_y + D["leg1"] * math.cos(rad(a)))
                ank = (hx + f[0], hip_y + f[1])
                sk["knee_" + name], sk["ankle_" + name] = knee, ank
        else:
            lifts = (p["legl"][0], p["legr"][0])
            hip_y = GROUND - leg - 0.35 * max(lifts) - p["hop"] + p["squash"]
            hx = CX + p["sway"]
            sk["hip"] = (hx, hip_y)
            for name, key, sgn in (("l", "legl", -1), ("r", "legr", 1)):
                lift, spread = p[key]
                top = (hx + sgn * 2.7, hip_y)
                ank = (hx + sgn * (3.0 + spread), min(GROUND - 1.0, hip_y + leg - lift - 1.4 + (p["squash"] * 0.0)))
                ank = (ank[0], min(ank[1], GROUND - 1.4 - lift))
                sk["top_" + name] = top
                sk["ankle_" + name] = ank
        hx, hip_y = sk["hip"]
        sh_y = hip_y - D["torso"] + p["breath"] * 0.5 + (p["squash"] * 0.2)
        lean = p["lean"]
        sk["sh_y"] = sh_y
        sk["sh_x"] = hx + lean
        hcy = sh_y - D["hry"] + 1.4 + p["head_dy"] - p["breath"] * 0.4
        sk["head"] = (sk["sh_x"] + p["head_dx"] + (0.8 if v == "side" else 0.0) + lean * 0.3, hcy)
        # arms
        a1, a2 = p["arm1"], p["arm2"]
        sk["arm_ang"] = {}
        if v == "side":
            S = (sk["sh_x"] - 0.2, sh_y + 2.4)
            for name, a in (("n", a1), ("f", a2)):
                sk["sh_" + name] = S
                el, wr = self._limb(S, a, +1, D, 1.0)
                sk["elbow_" + name], sk["wrist_" + name] = el, wr
                sk["arm_ang"][name] = a[0] + a[1]
        else:
            for name, a, sgn in (("l", a1, -1), ("r", a2, 1)):
                S = (sk["sh_x"] + sgn * (D["tw"] / 2 - 0.6), sh_y + 2.4)
                sk["sh_" + name] = S
                el, wr = self._limb(S, a, sgn, D, 1.0)
                sk["elbow_" + name], sk["wrist_" + name] = el, wr
                sk["arm_ang"][name] = a[0] - a[1]

    def _limb(self, S, a, sgn, D, k):
        ang, bend, fs = a
        fl = 1.0 - 0.22 * abs(fs)
        u, f = D["arm1"] * fl, D["arm2"] * fl
        if self.view == "side":
            e = (S[0] + u * math.sin(rad(ang)), S[1] + u * math.cos(rad(ang)))
            w = (e[0] + f * math.sin(rad(ang + bend)), e[1] + f * math.cos(rad(ang + bend)))
        else:
            e = (S[0] + sgn * u * math.sin(rad(ang)), S[1] + u * math.cos(rad(ang)) + 0.5 * fs)
            w = (e[0] + sgn * f * math.sin(rad(ang - bend)), e[1] + f * math.cos(rad(ang - bend)) + 0.5 * fs)
        return e, w

    # ------------------------------------------------------------------ body (skin) primitives
    def body(self, skin_z0: float = 0.0) -> None:
        D, v, p, sk = self.D, self.view, self.p, self.sk
        lw, aw = D["lw"], D["aw"]
        hx, hip_y = sk["hip"]
        if v == "side":
            for name, z in (("f", 14), ("n", 20)):
                self.cap((hx, hip_y), sk["knee_" + name], lw, lw - 0.1, "skin", z, "leg" + name)
                self.cap(sk["knee_" + name], sk["ankle_" + name], lw - 0.1, lw - 0.35, "skin", z + 0.1, "leg" + name)
            self.poly([(hx - 4.4, hip_y + 0.5), (hx - 4.0, sk["sh_y"] + 1.0), (hx - 2.4, sk["sh_y"] - 0.4), (hx + 2.6, sk["sh_y"] - 0.4),
                       (hx + 4.4, sk["sh_y"] + 1.2), (hx + 4.2, hip_y + 0.5)], "skin", 30, "torso")
            for name, z in (("f", 12), ("n", 45)):
                self.cap(sk["sh_" + name], sk["elbow_" + name], aw, aw - 0.1, "skin", z, "arm" + name)
                self.cap(sk["elbow_" + name], sk["wrist_" + name], aw - 0.1, aw - 0.25, "skin", z + 0.1, "arm" + name)
                self.ell(*sk["wrist_" + name], 1.7, 1.7, "skin", z + 0.2, "arm" + name)
        else:
            for name in ("l", "r"):
                self.cap(sk["top_" + name], sk["ankle_" + name], lw, lw - 0.2, "skin", 20, "leg" + name)
            tw = D["tw"] / 2
            self.poly([(sk["sh_x"] - tw, sk["sh_y"] + 0.5), (sk["sh_x"] - tw + 1.2, sk["sh_y"] - 0.4), (sk["sh_x"] + tw - 1.2, sk["sh_y"] - 0.4),
                       (sk["sh_x"] + tw, sk["sh_y"] + 0.5), (hx + tw - 0.8, hip_y + 0.6), (hx - tw + 0.8, hip_y + 0.6)], "skin", 30, "torso")
            for name in ("l", "r"):
                self.cap(sk["sh_" + name], sk["elbow_" + name], aw, aw - 0.1, "skin", 40, "arm" + name)
                self.cap(sk["elbow_" + name], sk["wrist_" + name], aw - 0.1, aw - 0.25, "skin", 40.1, "arm" + name)
                self.ell(*sk["wrist_" + name], 1.7, 1.7, "skin", 40.2, "arm" + name)
        # head
        hcx, hcy = sk["head"]
        rx, ry = D["hrx"], D["hry"]
        self.cap((sk["sh_x"], sk["sh_y"] + 1.0), (sk["sh_x"], hcy + 3), 2.2, 2.2, "skin", 31, "neck")
        if v == "side":
            self.ell(hcx - 0.4, hcy, rx - 0.6, ry, "skin", 50, "head")
            self.poly([(hcx + rx - 1.6, hcy + 0.6), (hcx + rx + 0.7, hcy + 2.2), (hcx + rx - 1.4, hcy + 3.0)], "skin", 50.2, "head", shade=False, lum=0.9)  # nose
            if self.ears == "pointed":
                self.poly([(hcx - 0.4, hcy - 0.2), (hcx - 4.6, hcy - 3.4), (hcx - 2.8, hcy + 2.6)], "skin", 50.3, "ear")
            else:
                self.ell(hcx - 1.2, hcy + 1.4, 1.2, 1.7, "skin", 50.3, "ear", shade=True)
        else:
            self.ell(hcx, hcy, rx, ry, "skin", 50, "head")
            if v == "down":
                if self.ears == "pointed":
                    for sg in (-1, 1):
                        self.poly([(hcx + sg * (rx - 0.6), hcy - 0.6), (hcx + sg * (rx + 3.4), hcy - 3.4), (hcx + sg * (rx + 1.0), hcy + 3.2)], "skin", 49.9, "ear")
                else:
                    self.ell(hcx - rx + 0.2, hcy + 1.2, 1.2, 1.7, "skin", 49.9, "ear")
                    self.ell(hcx + rx - 0.2, hcy + 1.2, 1.2, 1.7, "skin", 49.9, "ear")

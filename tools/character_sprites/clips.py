"""Animation clips.  Each clip maps (frame index, view) to a rig pose; `FRAMES` gives the length of every clip."""
from __future__ import annotations

import math

from .rig import pose, rad

FRAMES = {"idle": 4, "walk": 6, "talk": 6, "hurt": 2, "die": 5, "surprise": 2, "work": 4, "cast": 5, "celebrate": 4}
# the civil set is a prefix of the full set, so one hair sheet fits every outfit
CLIPS_CIVIL = ["idle", "walk", "talk", "hurt", "die", "surprise", "work"]
CLIPS_FULL = ["idle", "walk", "talk", "hurt", "die", "surprise", "work", "cast", "celebrate"]
VIEWS = ["down", "side", "up"]


def _walk(i: int, view: str):
    p = 2 * math.pi * i / 6.0
    s, c = math.sin(p), math.cos(p)
    if view == "side":
        def leg(ph):
            a = 30.0 * math.sin(ph)
            k = 62.0 * max(0.0, math.cos(ph)) ** 1.3 + (6.0 if math.cos(ph) <= 0 else 0.0)
            return (a, k)
        legn, legf = leg(p), leg(p + math.pi)
        arm_n = (-32.0 * math.sin(p) + 4.0, 16.0 + 26.0 * max(0.0, math.sin(p)), 0.0)
        arm_f = (32.0 * math.sin(p) + 4.0, 16.0 + 26.0 * max(0.0, -math.sin(p)), 0.0)
        return pose(legn=legn, legf=legf, arm1=arm_n, arm2=arm_f, lean=0.7, sway=0.0, head_dy=0.0)
    lift_l = 2.6 * max(0.0, math.sin(p)) ** 1.1
    lift_r = 2.6 * max(0.0, -math.sin(p)) ** 1.1
    return pose(legl=(lift_l, 0.0), legr=(lift_r, 0.0), sway=0.5 * s if view == "down" else -0.5 * s,
                arm1=(9.0 + 4 * s, 14.0, -0.9 * s), arm2=(9.0 - 4 * s, 14.0, 0.9 * s))


def _idle(i: int, view: str):
    if view == "side":
        base = pose(arm1=(8.0, 16.0, 0.0), arm2=(-6.0, 12.0, 0.0), legn=(3.0, 0.0), legf=(-3.0, 0.0))
    else:
        base = pose(arm1=(8.0, 14.0, 0.0), arm2=(8.0, 14.0, 0.0))
    if i == 1:
        base["breath"] = 1.0
        base["head_dy"] = 0.0
        base["glow"] = 0.45   # a staff's orb swells and throws a few sparks (nothing else is affected)
    elif i == 2:
        base["glow"] = 0.25
        base["breath"] = 0.5
        base["arm1"] = (base["arm1"][0] + 3, base["arm1"][1], 0.0)
        base["arm2"] = (base["arm2"][0] + (3 if view != "side" else -2), base["arm2"][1], 0.0)
    elif i == 3:
        base["eyes"] = "blink"
    return base


_TALK = [  # mouth, head dy, gesture strength 0..1, gesturing hand ('1' near/left or '2' far/right or 'b' both), eyes
    ("open_s", 0.0, 0.0, "1", "open"), ("open_l", -1.0, 0.7, "1", "open"), ("open_m", 0.0, 1.0, "1", "open"),
    ("closed", 0.0, 0.5, "b", "open"), ("open_l", -1.0, 0.9, "2", "open"), ("open_s", 0.0, 0.2, "b", "blink"),
]


def _talk(i: int, view: str):
    mouth, hdy, g, who, eyes = _TALK[i]
    p = _idle(0, view)
    p.update(mouth=mouth, head_dy=hdy, eyes=eyes, brows="up" if g > 0.8 else "neutral", breath=0.4 if i % 2 else 0.0)
    if view == "side":
        up = (8 + 52 * g, 14 + 60 * g, 0.0)
        if who in ("1", "b"):
            p["arm1"] = up
        if who in ("2", "b"):
            p["arm2"] = (-4 + 60 * g, 14 + 60 * g, 0.0)
    else:
        up = (14 + 50 * g, 14 + 74 * g, 0.4 * g)
        if who in ("1", "b"):
            p["arm1"] = up
        if who in ("2", "b"):
            p["arm2"] = (14 + 50 * g, 14 + 74 * g, 0.4 * g)
    return p


def _hurt(i: int, view: str):
    p = _idle(0, view)
    if view == "side":
        p.update(lean=-2.0 if i == 0 else -0.8, arm1=(-30.0, 40.0, 0.0), arm2=(40.0, 30.0, 0.0), legn=(-8.0, 12.0), legf=(10.0, 0.0))
    else:
        p.update(lean=-0.5, arm1=(40.0 if i == 0 else 22, 30.0, 0.0), arm2=(40.0 if i == 0 else 22, 30.0, 0.0), squash=1.2 if i == 0 else 0.4)
    p.update(eyes="closed" if i == 0 else "half", mouth="open_m" if i == 0 else "frown", brows="worried", head_dy=1.0 if i == 0 else 0.0)
    return p


def _die(i: int, view: str):
    rot = [10.0, 32.0, 58.0, 84.0, 90.0][i]
    fdx = [0.0, -6.0, -15.0, -19.0, -21.0][i]
    fdy = [0.0, 0.0, -1.5, -4.0, -6.5][i]
    p = pose(arm1=(14.0 + 14 * i, 30.0, 0.0), arm2=(6.0 + 12 * i, 40.0, 0.0), legn=(-6.0 + 4 * i, 10.0 + 10 * i), legf=(8.0, 20.0 + 6 * i),
             eyes="closed" if i < 4 else "dead", mouth="o" if i < 2 else "open_s", brows="worried", rot=rot, fall_dx=fdx, fall_dy=fdy, squash=0.0)
    p["_side"] = True
    return p


def _surprise(i: int, view: str):
    p = _idle(0, view)
    p.update(eyes="wide", mouth="o", brows="up", hop=2.5 if i == 0 else 0.0)
    if view == "side":
        p.update(arm1=(70.0, 70.0, 0.0), arm2=(30.0, 40.0, 0.0), lean=-1.0)
    else:
        p.update(arm1=(104.0, 34.0, 0.0), arm2=(104.0, 34.0, 0.0))
    return p


def _cast(i: int, view: str):
    p = _idle(0, view)
    g = [0.35, 0.8, 1.0, 1.0, 0.4][i]
    p.update(mouth="open_s" if i in (1, 2, 3) else "closed", brows="down" if i in (1, 2) else "neutral", glow=[0.0, 0.4, 1.0, 0.8, 0.2][i], eyes="open")
    if view == "side":
        p.update(arm1=(10 + 62 * g, 10 + 8 * g, 0.0), arm2=(-30 * g, 50 * g, 0.0), lean=[0, -0.5, 1.5, 1.2, 0.3][i], legn=(10.0, 0.0), legf=(-12.0, 4.0))
    else:
        p.update(arm1=(20 + 66 * g, 20 + 40 * g, 0.0), arm2=(20 + 66 * g, 20 + 40 * g, 0.0))
    return p


def _work(i: int, view: str):
    """A tool stroke: raise, swing, strike, recover (the tool follows the main hand)."""
    a = [150.0, 105.0, 42.0, 95.0][i]
    p = _idle(0, view)
    p.update(mouth="closed", eyes="open", brows="down" if i == 2 else "neutral")
    if view == "side":
        p.update(arm1=(a, 12.0 if i != 2 else 4.0, 0.0), arm2=(a * 0.55, 30.0, 0.0), lean=[-0.4, 0.6, 1.8, 0.6][i], squash=[0.0, 0.0, 0.9, 0.2][i],
                 legn=(12.0, 8.0), legf=(-12.0, 8.0))
    else:
        p.update(arm1=(a * 0.55 + 10, 24.0, 0.3), arm2=(a * 0.45 + 12, 30.0, 0.3), squash=[0.0, 0.2, 1.0, 0.3][i], head_dy=[0.0, 0.0, 0.6, 0.0][i])
    return p


def _celebrate(i: int, view: str):
    hop = [-1.5, 3.5, 5.0, 1.0][i]
    p = _idle(0, view)
    p.update(hop=max(hop, 0.0), squash=1.5 if i == 0 else 0.0, mouth="grin" if i else "smile", brows="up", eyes="blink" if i == 2 else "open")
    up = 150.0 if i in (1, 2) else 40.0
    if view == "side":
        p.update(arm1=(up, 25.0, 0.0), arm2=(up - 20, 30.0, 0.0), legn=(15.0 if i in (1, 2) else 4, 40.0 if i in (1, 2) else 0), legf=(-15.0, 50.0 if i in (1, 2) else 0))
    else:
        p.update(arm1=(up, 20.0, 0.0), arm2=(up, 20.0, 0.0), legl=(2.5 if i in (1, 2) else 0, 0), legr=(2.5 if i in (1, 2) else 0, 0))
    return p


def pose_for(clip: str, i: int, view: str, mod=None):
    if clip == "idle":
        p = _idle(i, view)
    elif clip == "walk":
        p = _walk(i, view)
    elif clip == "talk":
        p = _talk(i, view)
    elif clip == "hurt":
        p = _hurt(i, view)
    elif clip == "die":
        p = _die(i, view)
    elif clip == "work":
        p = _work(i, view)
    elif clip == "surprise":
        p = _surprise(i, view)
    elif clip == "cast":
        p = _cast(i, view)
    elif clip == "celebrate":
        p = _celebrate(i, view)
    else:
        raise ValueError(clip)
    if mod == "zombie":
        _zombie(p, clip, view)
    return p


def _zombie(p, clip, view):
    """Arms stretched out in front, head lolling, shuffling gait."""
    if clip in ("idle", "walk", "talk", "surprise", "hurt"):
        if view == "side":
            p["arm1"] = (84.0, 6.0, 0.0)
            p["arm2"] = (78.0, 10.0, 0.0)
        else:
            p["arm1"] = (40.0, 20.0, 0.9)
            p["arm2"] = (40.0, 20.0, 0.9)
    if clip in ("idle", "talk"):
        p["mouth"] = "open_s"
        p["eyes"] = "half" if p["eyes"] != "blink" else "blink"

"""The campaign as the viewer sees it (D55, stage 5): threat formations in the age's hostile art with enemy livery at their locations, responders
in the age's art with a role crest walking their last turn's path along the corridors, the field posts at the bases, the panel's numbers, and the
short-lived effects (arrivals, outbreaks, treatments, cures) the client animates. Positions are tiles. Nothing here feeds back."""

from __future__ import annotations

import math
from typing import Any

from .. import rules as world_rules
from . import rules as R

FAMILY_COLOUR = {"F1": "#d8403a", "F2": "#e0a52a", "F3": "#2fb5a8", "F4": "#8b5cd6"}
FAMILY_GLYPH = {"F1": "I", "F2": "II", "F3": "III", "F4": "IV"}
FAMILY_NAMES = {
    1: {"F1": "Raiders", "F2": "Wolf packs", "F3": "Marauders", "F4": "Reavers"},
    2: {"F1": "Mercenaries", "F2": "Brigands", "F3": "Corsairs", "F4": "Rebels"},
    3: {"F1": "Insurgents", "F2": "Militia", "F3": "Mercenary column", "F4": "Rogue armour"},
    4: {"F1": "Rogue swarm", "F2": "Crawler nest", "F3": "Rogue novas", "F4": "Rogue maces"},
}
FORMATION_ART = {
    1: {"F1": "widelands.soldier", "F2": "widelands.soldier", "F3": "widelands.soldier", "F4": "widelands.soldier"},
    2: {"F1": "openra.e1", "F2": "openra.e2", "F3": "openra.e3", "F4": "openra.dog"},
    3: {"F1": "openra.e1", "F2": "openra.e3", "F3": "openra.jeep", "F4": "openra.1tnk"},
    4: {"F1": "mindustry.unit.dagger", "F2": "mindustry.unit.crawler", "F3": "mindustry.unit.nova", "F4": "mindustry.unit.mace"},
}
RESPONDER_ART = {1: "widelands.soldier", 2: "openra.medi", 3: "openra.medi", 4: "mindustry.unit.nova"}
ROLE_GLYPH = {"medic": "M", "scientist": "S", "researcher": "R", "dispatcher": "D", "operations_expert": "O", "quarantine_specialist": "Q"}
CAMPAIGN_NAMES = {1: "The raiding season", 2: "The war of the bands", 3: "The insurgency", 4: "The rogue swarm"}


def family_name(age: int, fam: str) -> str:
    return FAMILY_NAMES.get(int(age), FAMILY_NAMES[1]).get(fam, fam)


def _along(world, path: list[str], t: float) -> tuple[float, float]:
    """A point t in [0,1] along a node path, following the corridors (so a walking responder keeps to the road)."""
    board = world.board
    if len(path) <= 1:
        return board.node_xy(path[0])
    legs = []
    total = 0.0
    for a, b in zip(path, path[1:]):
        eid = board.edge_between(a, b) if hasattr(board, "edge_between") else None
        pts = None
        if eid is not None:
            poly = board.corridor(eid)
            if poly:
                pts = [tuple(p) for p in poly]
                if pts and math.hypot(pts[0][0] - board.node_xy(a)[0], pts[0][1] - board.node_xy(a)[1]) > 1e-6:
                    pts = list(reversed(pts))
        if not pts:
            pts = [board.node_xy(a), board.node_xy(b)]
        seg_len = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
        legs.append((pts, seg_len))
        total += seg_len
    want = max(0.0, min(1.0, t)) * total
    run = 0.0
    for pts, seg_len in legs:
        if want <= run + seg_len or (pts, seg_len) is legs[-1]:
            local = want - run
            for i in range(len(pts) - 1):
                d = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                if local <= d or i == len(pts) - 2:
                    f = 0.0 if d <= 1e-9 else max(0.0, min(1.0, local / d))
                    return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f)
                local -= d
        run += seg_len
    return board.node_xy(path[-1])


def view(world, camp: dict[str, Any], window: list[float] | None = None) -> dict[str, Any]:
    st = camp["state"]
    age = int(camp["age"])
    now = int(world.game_ms)
    board = world.board
    in_win = (lambda x, y: True) if window is None else (lambda x, y: window[0] <= x <= window[2] and window[1] <= y <= window[3])
    formations = []
    for nid, loc in st["locations"].items():
        x, y = board.node_xy(nid)
        k = 0
        for fam in R.FAMILIES:
            n = int(loc["units"][fam])
            if n <= 0:
                continue
            ang = (R.FAMILIES.index(fam) / 4.0) * math.tau + 0.6
            fx, fy = x + math.cos(ang) * 3.2, y + math.sin(ang) * 3.2
            formations.append({"id": f"formation:{nid}:{fam}", "node": nid, "family": fam, "n": n, "x": round(fx, 2), "y": round(fy, 2), "art": FORMATION_ART.get(age, FORMATION_ART[1])[fam],
                               "colour": FAMILY_COLOUR[fam], "glyph": FAMILY_GLYPH[fam], "name": family_name(age, fam), "home": loc["family"] == fam, "near": in_win(fx, fy)})
            k += 1
    responders = []
    for r in st["responders"]:
        x, y = board.node_xy(r["location"])
        anim = r.get("anim")
        moving = False
        heading = 0.0
        if anim and now < int(anim["end_ms"]) and len(anim["path"]) > 1:
            t = (now - int(anim["start_ms"])) / float(max(1, int(anim["end_ms"]) - int(anim["start_ms"])))
            x, y = _along(world, anim["path"], t)
            x2, y2 = _along(world, anim["path"], min(1.0, t + 0.02))
            heading = math.atan2(y2 - y, x2 - x)
            moving = t < 1.0
        ready_ms = int(r.get("ready_ms", 0))
        emerging = now < ready_ms
        if emerging:
            site = next((c for c in camp["contracts"] if c["responder"] == r["id"]), None)
            base_v = world.villages.get(site["village"]) if site and site.get("village") else None
            if base_v is not None and base_v.get("ops") and site.get("site") in base_v["ops"]["sites"]:
                s = base_v["ops"]["sites"][site["site"]]
                x, y = s["ex"], s["ey"]
        responders.append({"id": f"responder:{r['id']}", "rid": r["id"], "role": r["role"], "role_name": R.ROLE_NAMES[r["role"]], "glyph": ROLE_GLYPH[r["role"]], "faction": r["faction"],
                           "node": r["location"], "x": round(x, 2), "y": round(y, 2), "heading": round(heading, 3), "moving": moving, "art": RESPONDER_ART.get(age, RESPONDER_ART[1]),
                           "hand": len(r["hand"]), "cards": {f: len(c) for f, c in R.hand_by_family(st, r).items()}, "events": [c for c in r["hand"] if c in R.EVENTS],
                           "acting": r is R.current(st) and st["result"] is None, "emerging": emerging, "emerge_t": 0.0 if not emerging else max(0.0, 1.0 - (ready_ms - now) / float(MANUFACTURE_WINDOW_MS)),
                           "near": in_win(x, y)})
    posts = []
    for nid in st["posts"]:
        x, y = board.node_xy(nid)
        owner = next((fid for fid, b in camp.get("bases", {}).items() if b == nid), "")
        posts.append({"id": f"post:{nid}", "node": nid, "x": round(x, 2), "y": round(y, 2), "faction": owner, "near": in_win(x, y)})
    s = R.summary(st)
    fx = [f for f in camp["fx"] if now - int(f["game_ms"]) <= 12_000]
    for f in fx:
        if f.get("location") in st["locations"]:
            f["x"], f["y"] = board.node_xy(f["location"])
    current = R.current(st)
    panel = {"name": CAMPAIGN_NAMES.get(age, "The campaign"), "result": s["result"], "lost_reason": s["lost_reason"], "outbreaks": s["outbreaks"], "outbreaks_max": R.LOSE_AT_OUTBREAKS,
             "rate": s["rate"], "rate_index": s["rate_index"], "rate_track": list(R.RATE_TRACK), "turn_count": s["turn_count"], "player_deck": s["player_deck"], "infection_deck": s["infection_deck"],
             "families": [{"id": f, "name": family_name(age, f), "colour": FAMILY_COLOUR[f], "glyph": FAMILY_GLYPH[f], "cured": st["families"][f]["cured"], "eradicated": st["families"][f]["eradicated"],
                           "reserve": int(st["families"][f]["reserve"]), "out": int(s["units_out"][f])} for f in R.FAMILIES],
             "current": {"rid": current["id"], "role": current["role"], "role_name": R.ROLE_NAMES[current["role"]], "faction": current["faction"]},
             "next_turn_in_ms": max(0, int(camp["next_turn_ms"]) - now) if s["result"] is None else 0, "cadence_ms": world_rules.timing("pandemic_turn"),
             "retries": int(camp["retries"]), "posts": len(st["posts"]), "recent": list(st["log"][-6:])}
    return {"age": age, "formations": formations, "responders": responders, "posts": posts, "panel": panel, "fx": fx}


MANUFACTURE_WINDOW_MS = 2500

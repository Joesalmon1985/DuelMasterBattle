"""The cooperative coordinator (D55): one mind playing all six responders from the public state only. It never reads the order of a deck
(`rules.public_view` hides them; Forecast's six are the rules' own look). Its play is the published cooperative heuristics: find a countermeasure the
moment a hand allows it, concentrate one family's cards in one hand (the collector) by sharing, treat the heaviest formations first and stand in the
way of outbreaks, keep the medic moving, use events when they are worth more than keeping. Combat is action economy: a formation is beaten by
treating, never by fighting units."""

from __future__ import annotations

from collections import deque
from typing import Any

from . import rules as R

MAX_PLAN_STEPS = 40
# the play's tunable habits (benchmarked in the ledger; every one of them is a choice within the published rules, never a rule)
TUNING = {"treat_skip_ones": True, "collector_to_post": True, "dispatch_broker": True, "medic_never_collects": True, "quarantine_station": True, "flight_dist": 2, "hot_cards": True, "reserve_weight": True}


def bfs(links: dict[str, list[str]], start: str) -> dict[str, int]:
    dist = {start: 0}
    q = deque([start])
    while q:
        n = q.popleft()
        for o in links.get(n, []):
            if o not in dist:
                dist[o] = dist[n] + 1
                q.append(o)
    return dist


def first_step(links: dict[str, list[str]], start: str, goal: str) -> str | None:
    """The neighbour of `start` on a shortest path to `goal` (lowest id among ties), None when unreachable or already there."""
    if start == goal:
        return None
    back = bfs(links, goal)
    if start not in back:
        return None
    best = None
    for o in sorted(links.get(start, [])):
        if back.get(o, 1 << 30) == back[start] - 1:
            best = o
            break
    return best


def danger(view: dict[str, Any], nid: str) -> float:
    loc = view["locations"][nid]
    total = sum(loc["units"].values())
    if total == 0:
        return 0.0
    worst = max(loc["units"].values())
    score = total * total * 2.0 + (18.0 if worst >= 3 else (5.0 if worst == 2 else 0.0))
    if TUNING["reserve_weight"]:
        for f, u in loc["units"].items():
            if u and int(view["families"][f]["reserve"]) <= 6:
                score += 6.0 * u  # a family near the end of its reserve loses the campaign by itself
    for o in view["links"].get(nid, []):
        if max(view["locations"][o]["units"].values()) >= 3:
            score += 3.0  # an outbreak next door would spill here and chain
    if TUNING["hot_cards"] and nid in view.get("hot", []):
        score += 4.0 + 4.0 * total  # its card went back on top at the last escalation: it is coming again soon
    return score


def collectors(view: dict[str, Any]) -> dict[str, str]:
    """For each uncured family, the responder holding most of its cards (ties: the scientist, then the lower id)."""
    out = {}
    for f in R.FAMILIES:
        if view["families"][f]["cured"]:
            continue
        best = None
        others_hold = any(len(R.hand_by_family(view, o)[f]) > 0 and o["role"] != "medic" for o in view["responders"])
        for r in view["responders"]:
            if TUNING["medic_never_collects"] and r["role"] == "medic" and others_hold:
                continue  # the medic roams and treats; her cards go to whoever collects
            n = len(R.hand_by_family(view, r)[f])
            key = (n, 1 if r["role"] == "scientist" else 0, r["id"])
            if best is None or key > best[0]:
                best = (key, r["id"])
        out[f] = best[1]
    return out


def discard_policy(st: dict[str, Any], r: dict[str, Any]) -> str:
    """Hand-limit discards: never an event, never a card of the family this responder collects, else the family held least (cured first)."""
    view = R.public_view(st)
    col = collectors(view)
    by = R.hand_by_family(view, r)
    cands = []
    for f in R.FAMILIES:
        if not by[f]:
            continue
        cands.append((0 if st["families"][f]["cured"] else 1, 1 if col.get(f) == r["id"] else 0, len(by[f]), f))
    if not cands:
        return r["hand"][0]
    cands.sort()
    return by[cands[0][3]][0]


def take_turn(st: dict[str, Any]) -> list[dict[str, Any]]:
    """Play the current responder's four actions and end the turn. Returns the actions taken (for the log and the picture)."""
    taken: list[dict[str, Any]] = []
    guard = 0
    while st["result"] is None and int(st["actions_left"]) > 0 and guard < MAX_PLAN_STEPS:
        guard += 1
        view = R.public_view(st)
        r = R.current(st)
        act = _choose(view, r)
        if act is None:
            R.pass_turn(st, r)
            taken.append({"kind": "pass", "responder": r["id"]})
            break
        _apply(st, r, act)
        taken.append(act)
    if st["result"] is None:
        _events_before_infection(st)
        R.end_turn(st, discard_policy)
    return taken


# ------------------------------------------------------------------ choosing

def _choose(view: dict[str, Any], r: dict[str, Any]) -> dict[str, Any] | None:
    links = view["links"]
    here = r["location"]
    loc = view["locations"][here]
    # 1. a countermeasure now
    fam = R.can_cure(view, r)
    if fam:
        return {"kind": "cure", "family": fam}
    # 2. holding enough for a countermeasure: to the nearest field post
    by = R.hand_by_family(view, r)
    ready = [f for f in R.FAMILIES if not view["families"][f]["cured"] and len(by[f]) >= R.cure_cards_needed(r)]
    if ready:
        step = _toward_post(view, r)
        if step:
            return step
    # 3. share: a card the collector of its family wants, at this location
    col = collectors(view)
    for other in view["responders"]:
        if other["id"] == r["id"] or other["location"] != here:
            continue
        # give: the location's card (anyone) or any card (the researcher) to the collector of that family
        for c in list(r["hand"]):
            f = R.family_of(view, c)
            if f and col.get(f) == other["id"] and (r["role"] == "researcher" or c == here) and not view["families"][f]["cured"]:
                return {"kind": "share", "other": other["id"], "card": c}
        # take: the other's card of this location when I collect its family, or any from the researcher
        for c in list(other["hand"]):
            f = R.family_of(view, c)
            if f and col.get(f) == r["id"] and (other["role"] == "researcher" or c == here) and not view["families"][f]["cured"]:
                return {"kind": "share", "other": other["id"], "card": c}
    # 3b. a collector near a countermeasure keeps to a field post, so the fifth card is played the turn it arrives
    if TUNING["collector_to_post"] and not loc["post"]:
        near_cure = [f for f, rid in col.items() if rid == r["id"] and len(by[f]) >= R.cure_cards_needed(r) - 2]
        if near_cure:
            d_here = bfs(links, here)
            heavy_near = any(max(view["locations"][n]["units"].values()) >= 3 and d_here.get(n, 99) <= 2 for n in view["locations"])
            if not heavy_near:
                step = _toward_post(view, r)
                if step:
                    return step
    # 4. treat the heaviest formation here (a cured family's first: it vanishes whole); a lone unit can wait when a heavy stack is near
    present = [(view["families"][f]["cured"], loc["units"][f], f) for f in R.FAMILIES if loc["units"][f] > 0]
    if present:
        present.sort(key=lambda t: (not t[0], -t[1], int(view["families"][t[2]]["reserve"])))
        top = present[0]
        skip = False
        if TUNING["treat_skip_ones"] and top[1] == 1 and not top[0]:
            g = _threat_goal(view, r)
            if g and g != here and max(view["locations"][g]["units"].values()) >= 2 and bfs(links, here).get(g, 99) <= 3:
                skip = True
        if not skip:
            return {"kind": "treat", "family": top[2]}
    # 5. the dispatcher brings a far responder next to trouble when nobody is close
    if r["role"] == "dispatcher":
        move = _dispatch_plan(view, r)
        if move:
            return move
    # 6. the researcher goes to the collector who is closest to a countermeasure
    if r["role"] == "researcher":
        goal = _researcher_goal(view, r, col)
        if goal and goal != here:
            step = _step_to(view, r, goal)
            if step:
                return step
    # 6b. rendezvous (while no formation stands at full strength): a collector walks to a giver standing on a card of its family; a giver walks
    # to the location of a card the collector wants
    calm = not any(max(l["units"].values()) >= 3 for l in view["locations"].values())
    goal = _rendezvous_goal(view, r, col) if calm else None
    if goal and goal != here:
        step = _step_to(view, r, goal)
        if step:
            return step
    # 7. move toward the most dangerous location worth the trip (nearest among the top dangers), the medic furthest
    goal = _threat_goal(view, r)
    if goal and goal != here:
        step = _step_to(view, r, goal)
        if step:
            return step
    # 8. nothing worth doing: a collector waits at a post, others drift toward the centre of trouble
    if goal is None:
        if not loc["post"]:
            step = _toward_post(view, r)
            if step:
                return step
    return None


def _toward_post(view: dict[str, Any], r: dict[str, Any]) -> dict[str, Any] | None:
    here = r["location"]
    if view["locations"][here]["post"]:
        return None
    posts = [p for p in view["posts"]]
    if not posts:
        return {"kind": "build_post"} if r["role"] == "operations_expert" or here in r["hand"] else None
    dist = bfs(view["links"], here)
    target = min(posts, key=lambda p: (dist.get(p, 1 << 30), p))
    d = dist.get(target, 1 << 30)
    if d > 3 and (target in r["hand"]):
        return {"kind": "direct_flight", "to": target}
    if d > 3 and here in r["hand"] and not _needed(view, r, here):
        return {"kind": "charter_flight", "to": target}
    if d > 2 and r["role"] == "operations_expert" and here in r["hand"]:
        return {"kind": "build_post"}
    step = first_step(view["links"], here, target)
    return {"kind": "drive", "to": step} if step else None


def _needed(view: dict[str, Any], r: dict[str, Any], card: str) -> bool:
    f = R.family_of(view, card)
    if f is None or view["families"][f]["cured"]:
        return False
    return collectors(view).get(f) == r["id"]


def _step_to(view: dict[str, Any], r: dict[str, Any], goal: str) -> dict[str, Any] | None:
    here = r["location"]
    links = view["links"]
    dist = bfs(links, here).get(goal, 1 << 30)
    # shuttles between posts shorten long trips
    if view["locations"][here]["post"]:
        for p in view["posts"]:
            if p != here and bfs(links, p).get(goal, 1 << 30) + 1 < dist:
                return {"kind": "shuttle", "to": p}
        if r["role"] == "operations_expert" and dist > 3 and not r.get("ops_shuttle_used"):
            spare = next((c for c in r["hand"] if R.family_of(view, c) and not _needed(view, r, c)), None)
            if spare:
                return {"kind": "ops_shuttle", "to": goal, "card": spare}
    if dist > TUNING["flight_dist"] and goal in r["hand"] and not _needed(view, r, goal):
        return {"kind": "direct_flight", "to": goal}
    if dist > 4 and here in r["hand"] and not _needed(view, r, here):
        return {"kind": "charter_flight", "to": goal}
    step = first_step(links, here, goal)
    return {"kind": "drive", "to": step} if step else None


def _threat_goal(view: dict[str, Any], r: dict[str, Any]) -> str | None:
    here = r["location"]
    dist = bfs(view["links"], here)
    others = [o for o in view["responders"] if o["id"] != r["id"]]
    best = None
    if TUNING["quarantine_station"] and r["role"] == "quarantine_specialist":
        # she shields her place and its neighbours: stand where the most threatened mass is covered
        for nid in view["locations"]:
            dd = dist.get(nid, 1 << 30)
            if dd > 6:
                continue
            mass = 0.0
            for m in [nid] + list(view["links"].get(nid, [])):
                u = max(view["locations"][m]["units"].values())
                mass += u * u if u >= 2 else 0.0
            if mass <= 0:
                continue
            score = mass - dd * 1.5
            if best is None or score > best[0]:
                best = (score, nid)
        if best is not None and best[0] > 0:
            return best[1]
        best = None
    for nid, loc in view["locations"].items():
        d = danger(view, nid)
        if d <= 0:
            continue
        dd = dist.get(nid, 1 << 30)
        if dd > 8:
            continue
        # someone closer is already on it (unless this is the medic and the pile is heavy)
        claimed = any(bfs(view["links"], o["location"]).get(nid, 1 << 30) < dd and (sum(loc["units"].values()) < 3 or o["role"] == "medic") for o in others)
        if claimed and r["role"] != "medic":
            d *= 0.35
        score = d - dd * (1.2 if r["role"] == "medic" else 2.2)
        if best is None or score > best[0]:
            best = (score, nid)
    if best is None or best[0] <= 0:
        return None
    return best[1]


def _researcher_goal(view: dict[str, Any], r: dict[str, Any], col: dict[str, str]) -> str | None:
    by = R.hand_by_family(view, r)
    best = None
    for f, rid in col.items():
        if rid == r["id"] or not by[f]:
            continue
        other = R.responder(view, rid)
        have = len(R.hand_by_family(view, other)[f])
        need = R.cure_cards_needed(other)
        if have + len(by[f]) < need - 1:
            continue
        d = bfs(view["links"], r["location"]).get(other["location"], 1 << 30)
        key = (need - have, d)
        if best is None or key < best[0]:
            best = (key, other["location"])
    return best[1] if best else None


def _rendezvous_goal(view: dict[str, Any], r: dict[str, Any], col: dict[str, str]) -> str | None:
    """Card concentration without the researcher: the collector of a family goes to a responder who stands on one of that family's cards (the
    share then costs one action), and a holder of a wanted card goes to stand on it when the collector is near enough to come."""
    here = r["location"]
    dist = bfs(view["links"], here)
    my_fams = [f for f, rid in col.items() if rid == r["id"]]
    best = None
    for other in view["responders"]:
        if other["id"] == r["id"]:
            continue
        oby = R.hand_by_family(view, other)
        # I collect: is the other standing on a card of mine?
        for f in my_fams:
            have = len(R.hand_by_family(view, r)[f])
            if have < 2:
                continue
            if other["location"] in oby[f] or (other["role"] == "researcher" and oby[f]):
                d = dist.get(other["location"], 1 << 30)
                if d <= 4 and (best is None or d < best[0]):
                    best = (d, other["location"])
    if best:
        return best[1]
    # I hold a card the collector wants: stand on it when the collector is within reach of it
    by = R.hand_by_family(view, r)
    for f, rid in col.items():
        if rid == r["id"] or not by[f]:
            continue
        collector = R.responder(view, rid)
        if len(R.hand_by_family(view, collector)[f]) < 2:
            continue
        cdist = bfs(view["links"], collector["location"])
        for card in by[f]:
            d_me = dist.get(card, 1 << 30)
            d_col = cdist.get(card, 1 << 30)
            if d_me <= 2 and d_col <= 4 and (best is None or d_me < best[0]):
                best = (d_me, card)
    return best[1] if best else None


def _dispatch_plan(view: dict[str, Any], r: dict[str, Any]) -> dict[str, Any] | None:
    """Move the medic (or the idlest responder) one link toward a heavy formation that no one else is near."""
    if TUNING["dispatch_broker"]:
        # the broker: bring the researcher to the collector she can help most, or a holder of the collector's own-location card to the collector
        col = collectors(view)
        researcher = next((o for o in view["responders"] if o["role"] == "researcher"), None)
        if researcher is not None and researcher["id"] != r["id"]:
            rby = R.hand_by_family(view, researcher)
            best = None
            for f, rid in col.items():
                if rid == researcher["id"] or not rby[f]:
                    continue
                collector = R.responder(view, rid)
                if collector["location"] == researcher["location"]:
                    continue
                have = len(R.hand_by_family(view, collector)[f])
                need = R.cure_cards_needed(collector)
                if have + len(rby[f]) >= need - 1:
                    key = (need - have - len(rby[f]), -have)
                    if best is None or key < best[0]:
                        best = (key, collector["location"])
            if best is not None:
                return {"kind": "dispatch", "pawn": researcher["id"], "to": best[1]}
    heavy = [nid for nid, loc in view["locations"].items() if max(loc["units"].values()) >= 3]
    if not heavy:
        return None
    for nid in sorted(heavy, key=lambda n: -danger(view, n)):
        near = min((bfs(view["links"], o["location"]).get(nid, 1 << 30), o["id"]) for o in view["responders"])
        if near[0] <= 1:
            continue
        pawn = next((o for o in view["responders"] if o["role"] == "medic"), None) or R.responder(view, near[1])
        if pawn["id"] == r["id"]:
            continue
        step = first_step(view["links"], pawn["location"], nid)
        if step:
            return {"kind": "dispatch", "pawn": pawn["id"], "to": step}
    return None


# ------------------------------------------------------------------ applying

def _apply(st: dict[str, Any], r: dict[str, Any], act: dict[str, Any]) -> None:
    k = act["kind"]
    if k == "cure":
        R.cure(st, r, act["family"])
    elif k == "treat":
        R.treat(st, r, act["family"])
    elif k == "drive":
        R.drive(st, r, act["to"])
    elif k == "direct_flight":
        R.direct_flight(st, r, act["to"])
    elif k == "charter_flight":
        R.charter_flight(st, r, act["to"])
    elif k == "shuttle":
        R.shuttle(st, r, act["to"])
    elif k == "ops_shuttle":
        R.ops_shuttle(st, r, act["to"], act["card"])
    elif k == "share":
        R.share(st, r, R.responder(st, act["other"]), act["card"])
    elif k == "build_post":
        R.build_post(st, r)
    elif k == "dispatch":
        R.dispatch(st, r, R.responder(st, act["pawn"]), act["to"])
    else:
        raise ValueError(k)
    act["responder"] = r["id"]


def _events_before_infection(st: dict[str, Any]) -> None:
    """Events worth playing now: a quiet night when the board is about to boil, an airlift onto a heavy formation nobody can reach, a resilient
    population against the heaviest card in the discard, a forecast arranged so the heavy locations are drawn last."""
    view = R.public_view(st)
    heavy = [nid for nid, loc in view["locations"].items() if max(loc["units"].values()) >= 3]
    for holder in st["responders"]:
        for card in list(holder["hand"]):
            if card not in R.EVENTS:
                continue
            if card == "event:one_quiet_night" and (len(heavy) >= 3 or (R.rate(st) >= 3 and len(heavy) >= 2)):
                R.play_event(st, holder, card)
            elif card == "event:airlift" and heavy:
                target = max(heavy, key=lambda n: danger(view, n))
                near = min(bfs(view["links"], o["location"]).get(target, 1 << 30) for o in st["responders"])
                if near >= 3:
                    pawn = next((o for o in st["responders"] if o["role"] == "medic"), st["responders"][0])
                    R.play_event(st, holder, card, pawn=pawn["id"], to=target)
            elif card == "event:resilient_population" and st["infection_discard"] and int(st["outbreaks"]) >= 2:
                worst = max(st["infection_discard"], key=lambda n: danger(view, n))
                if danger(view, worst) >= 18.0:
                    R.play_event(st, holder, card, remove=worst)
            elif card == "event:forecast" and len(st["infection_deck"]) >= 6 and len(heavy) >= 2:
                six = R.forecast_peek(st, holder)
                safe_first = sorted(six, key=lambda n: danger(view, n))  # drawn first: the harmless ones
                R.play_event(st, holder, card, order=list(reversed(safe_first)))

"""Knucklebones: Yahtzee against the stonemason. Five carved stones, three throws a turn (hold what you like), thirteen orders on the slate: ones to
sixes (with the bonus of thirty-five at sixty-three or more), three and four of a face, a full course, the short and the long run of ashlar, five of a
face (fifty), and rubble (chance). The better slate wins. The mason holds the commonest face after each throw and fills the best-paying open order."""

from __future__ import annotations

from collections import Counter
from typing import Any

from wizard_rts.minigames import base

UPPER = ["ones", "twos", "threes", "fours", "fives", "sixes"]
LOWER = ["three_kind", "four_kind", "full_house", "small_straight", "large_straight", "yahtzee", "chance"]
CATEGORIES = UPPER + LOWER
NAMES = {"ones": "Ones", "twos": "Twos", "threes": "Threes", "fours": "Fours", "fives": "Fives", "sixes": "Sixes", "three_kind": "Three of a face", "four_kind": "Four of a face",
         "full_house": "A full course", "small_straight": "A short run", "large_straight": "A long run", "yahtzee": "Five of a face", "chance": "Rubble"}


def score_of(cat: str, dice: list[int]) -> int:
    c = Counter(dice)
    s = sum(dice)
    if cat in UPPER:
        face = UPPER.index(cat) + 1
        return face * c.get(face, 0)
    if cat == "three_kind":
        return s if max(c.values()) >= 3 else 0
    if cat == "four_kind":
        return s if max(c.values()) >= 4 else 0
    if cat == "full_house":
        return 25 if sorted(c.values()) == [2, 3] else 0
    if cat == "small_straight":
        u = set(dice)
        return 30 if any(run <= u for run in ({1, 2, 3, 4}, {2, 3, 4, 5}, {3, 4, 5, 6})) else 0
    if cat == "large_straight":
        return 40 if set(dice) in ({1, 2, 3, 4, 5}, {2, 3, 4, 5, 6}) else 0
    if cat == "yahtzee":
        return 50 if max(c.values()) == 5 else 0
    return s


def totals(sheet: dict[str, int]) -> dict[str, int]:
    upper = sum(sheet.get(k, 0) for k in UPPER)
    bonus = 35 if upper >= 63 else 0
    return {"upper": upper, "bonus": bonus, "total": sum(sheet.values()) + bonus}


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    names = {**NAMES, **{k: str(v).capitalize() for k, v in dict(opts.get("categories", {})).items() if k in NAMES}}
    st = base.fresh("yahtzee", seed, ["you", str(opts.get("host", "them"))], dice=[0, 0, 0, 0, 0], held=[False] * 5, rolls=0, sheets=[{}, {}], turn=0, names=names,
                    die=str(opts.get("die", "stone")))
    base.say(st, "Thirteen orders on the slate. Throw.")
    return st


def _open(state: dict[str, Any], seat: int) -> list[str]:
    return [c for c in CATEGORIES if c not in state["sheets"][seat]]


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != state["turn"]:
        return []
    out = []
    if state["rolls"] == 0:
        return [{"id": "roll", "text": f"Throw the {state['die']}s"}]
    if state["rolls"] < 3:
        out.append({"id": "roll", "text": "Throw again (%d left)" % (3 - state["rolls"])})
        for i in range(5):
            out.append({"id": f"hold:{i}", "die": i, "text": ("Free" if state["held"][i] else "Hold") + f" {state['die']} {i + 1}", "hidden": True})
    for c in _open(state, seat):
        out.append({"id": f"score:{c}", "cat": c, "text": f"{state['names'][c]}: {score_of(c, state['dice'])}"})
    return out


def _roll(state: dict[str, Any]) -> None:
    rng = base.rng(state, f"roll:{state['turn']}")
    for i in range(5):
        if state["rolls"] == 0 or not state["held"][i]:
            state["dice"][i] = rng.randint(1, 6)
    state["rolls"] += 1


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    if state["rolls"] == 0:
        return {"id": "roll"}
    dice = state["dice"]
    open_ = _open(state, seat)
    best = max(open_, key=lambda c: (score_of(c, dice), c == "chance"))
    best_score = score_of(best, dice)
    if state["rolls"] < 3 and best_score < 25:
        # hold the commonest face (or a straight's run) and throw the rest: done one die at a time, then the throw
        c = Counter(dice)
        face = max(c, key=lambda f: (c[f], f))
        keep = [i for i in range(5) if dice[i] == face]
        if score_of("small_straight", dice) and not score_of("large_straight", dice) and "large_straight" in open_:
            seen: set[int] = set()
            keep = [i for i in range(5) if not (dice[i] in seen or seen.add(dice[i]))]
        for i in range(5):
            want = i in keep
            if state["held"][i] != want:
                return {"id": f"hold:{i}", "die": i}
        return {"id": "roll"}
    return {"id": f"score:{best}", "cat": best}


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    state["moves"] += 1
    aid = a["id"]
    if aid == "roll":
        _roll(state)
        who = "You throw" if seat == 0 else f"{state['seats'][1]} throws"
        base.say(state, f"{who}: {' '.join(str(d) for d in state['dice'])}.")
        return state
    if aid.startswith("hold:"):
        i = int(a["die"])
        state["held"][i] = not state["held"][i]
        return state
    cat = str(a["cat"])
    pts = score_of(cat, state["dice"])
    state["sheets"][seat][cat] = pts
    who = "You fill" if seat == 0 else f"{state['seats'][1]} fills"
    base.say(state, f"{who} {state['names'][cat].lower()} for {pts}.")
    state["held"] = [False] * 5
    state["rolls"] = 0
    state["dice"] = [0, 0, 0, 0, 0]
    if all(len(s) == len(CATEGORIES) for s in state["sheets"]):
        you, them = totals(state["sheets"][0])["total"], totals(state["sheets"][1])["total"]
        base.finish(state, "win" if you > them else ("lose" if them > you else "draw"), f"{you} to {them}.")
        return state
    state["turn"] = 1 - seat
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    mine = state["turn"] == 0 and not state["over"]
    items = []
    for i, d in enumerate(state["dice"]):
        item = {"id": f"d{i}", "value": d, "held": state["held"][i]}
        if mine and 0 < state["rolls"] < 3:
            item["action"] = {"id": f"hold:{i}", "die": i}
        items.append(item)
    rows = []
    for c in CATEGORIES:
        rows.append({"name": state["names"][c], "value": "%s / %s" % (state["sheets"][0].get(c, "-"), state["sheets"][1].get(c, "-"))})
    t0, t1 = totals(state["sheets"][0]), totals(state["sheets"][1])
    rows.append({"name": "Bonus", "value": "%d / %d" % (t0["bonus"], t1["bonus"])})
    rows.append({"name": "Total", "value": "%d / %d" % (t0["total"], t1["total"])})
    areas = [base.area("dice", "The stones" + (" (tap to hold)" if mine and 0 < state["rolls"] < 3 else ""), size=64, items=items),
             base.area("score", "The slate (you / %s)" % state["seats"][1], rows=rows)]
    if state["over"]:
        msg = {"win": "The better slate.", "lose": "The mason's slate.", "draw": "Stone for stone."}[state["result"]]
    elif not mine:
        msg = f"{state['seats'][1]} is throwing."
    elif state["rolls"] == 0:
        msg = "Your turn. Throw."
    elif state["rolls"] < 3:
        msg = "Hold what you like and throw again, or fill an order."
    else:
        msg = "Fill an order."
    return base.head(state, "Knucklebones", msg, areas, actions(state, seat))

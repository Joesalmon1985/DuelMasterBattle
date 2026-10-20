"""Felling the big one: Can't Stop against the lumberjack. Four dice, paired as you like; each pair's sum is a trunk (2 to 12, the middle ones the
longest); a throw's strokes go on at most three trunks a turn (the runners). Bank your cuts when you like; throw once more and, if no pairing fits a
runner you have (or could still take), the trunk splits and the turn's cuts are lost. A trunk cut through is yours and closed to the other. Three
trunks win. The lumberjack stops after two good throws, or when a runner reaches the top."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base

LENGTHS = {2: 3, 3: 5, 4: 7, 5: 9, 6: 11, 7: 13, 8: 11, 9: 9, 10: 7, 11: 5, 12: 3}
PAIRINGS = ((0, 1, 2, 3), (0, 2, 1, 3), (0, 3, 1, 2))


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    st = base.fresh("cantstop", seed, ["you", str(opts.get("host", "them"))], positions=[{str(c): 0 for c in LENGTHS} for _ in range(2)], claimed={},
                    runners={}, dice=[0, 0, 0, 0], phase="roll", turn=0, good_throws=0, to_win=int(opts.get("columns_to_win", 3)),
                    column=str(opts.get("column", "trunk")), bust_text=str(opts.get("bust", "the trunk splits")))
    base.say(st, "Four dice, three trunks a turn. Throw.")
    return st


def _top(state: dict[str, Any], seat: int, col: int) -> int:
    """The position a runner on `col` would start from: the runner if placed, else the banked position."""
    return int(state["runners"].get(str(col), state["positions"][seat][str(col)]))


def _options(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    """The legal pairings of the four dice: for each pairing, the columns that can advance (both, or either one), given the three-runner limit."""
    d = state["dice"]
    out = []
    seen: set[tuple] = set()
    for i, (a, b, c, e) in enumerate(PAIRINGS):
        s1, s2 = d[a] + d[b], d[c] + d[e]
        for cols in ((s1, s2), (s1,), (s2,)):
            legal = []
            runners = dict(state["runners"])
            ok = True
            for col in cols:
                if str(col) in state["claimed"] or _top(state, seat, col) >= LENGTHS[col]:
                    ok = False
                    break
                if str(col) not in runners:
                    if len(runners) >= 3:
                        ok = False
                        break
                    runners[str(col)] = _top(state, seat, col)
                runners[str(col)] += 1
                legal.append(col)
            if not ok or not legal:
                continue
            key = tuple(sorted(legal))
            if key in seen:
                continue
            seen.add(key)
            out.append({"id": "pair:%d:%s" % (i, "+".join(str(c) for c in legal)), "cols": list(legal), "text": "Strokes on " + " and ".join(f"{state['column']} {c}" for c in legal)})
    full = [o for o in out if len(o["cols"]) == 2]
    return full if full else out  # a pairing that fits both of its columns must take both


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != state["turn"]:
        return []
    if state["phase"] == "roll":
        return [{"id": "roll", "text": "Throw the dice"}]
    if state["phase"] == "choose":
        return _options(state, seat)
    return [{"id": "roll", "text": "Throw again"}, {"id": "stop", "text": "Bank the cuts"}]


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    if state["phase"] == "roll":
        return {"id": "roll"}
    if state["phase"] == "choose":
        opts = _options(state, seat)
        best = max(opts, key=lambda o: (len(o["cols"]), sum(1 for c in o["cols"] if str(c) in state["runners"]), -sum(abs(7 - c) for c in o["cols"])))
        return {"id": best["id"], "cols": best["cols"]}
    topped = any(int(p) >= LENGTHS[int(c)] for c, p in state["runners"].items())
    if topped or state["good_throws"] >= 2 or (len(state["runners"]) == 3 and rng.random() < 0.5):
        return {"id": "stop"}
    return {"id": "roll"}


def _bank(state: dict[str, Any], seat: int) -> None:
    for c, p in state["runners"].items():
        state["positions"][seat][c] = int(p)
        if int(p) >= LENGTHS[int(c)]:
            state["claimed"][c] = seat
    state["runners"] = {}
    state["good_throws"] = 0
    won = sum(1 for s in state["claimed"].values() if s == seat)
    if won >= state["to_win"]:
        base.finish(state, "win" if seat == 0 else "lose", f"{'You have' if seat == 0 else state['seats'][1] + ' has'} {won} {state['column']}s down.")
        return
    state["turn"] = 1 - seat
    state["phase"] = "roll"


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    state["moves"] += 1
    who = "You" if seat == 0 else state["seats"][1]
    if a["id"] == "roll":
        rng = base.rng(state, "dice")
        state["dice"] = [rng.randint(1, 6) for _ in range(4)]
        state["phase"] = "choose"
        if not _options(state, seat):
            base.say(state, f"{who} throw{'' if seat == 0 else 's'} {' '.join(map(str, state['dice']))}: nothing fits. {state['bust_text'].capitalize()}.")
            state["runners"] = {}
            state["good_throws"] = 0
            state["turn"] = 1 - seat
            state["phase"] = "roll"
        else:
            base.say(state, f"{who} throw{'' if seat == 0 else 's'} {' '.join(map(str, state['dice']))}.")
        return state
    if a["id"].startswith("pair:"):
        for col in a["cols"]:
            if str(col) not in state["runners"]:
                state["runners"][str(col)] = _top(state, seat, col)
            state["runners"][str(col)] += 1
        state["good_throws"] += 1
        state["phase"] = "decide"
        base.say(state, f"Strokes on {', '.join(str(c) for c in a['cols'])}.")
        return state
    if a["id"] == "stop":
        base.say(state, f"{who} bank{'' if seat == 0 else 's'} the cuts.")
        _bank(state, seat)
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    rows = []
    for c in sorted(LENGTHS):
        cs = str(c)
        you, them = state["positions"][0][cs], state["positions"][1][cs]
        run = state["runners"].get(cs)
        owner = state["claimed"].get(cs)
        mark = f"{you}" + (f" (+{int(run) - you})" if run is not None and state["turn"] == 0 else "")
        val = f"{mark} / {them}" + (f" (+{int(run) - them})" if run is not None and state["turn"] == 1 else "") + f" of {LENGTHS[c]}"
        if owner is not None:
            val = ("yours" if owner == 0 else state["seats"][1] + "'s") + " - down"
        rows.append({"name": f"{state['column'].capitalize()} {c}", "value": val})
    dice = [{"id": f"d{i}", "value": d} for i, d in enumerate(state["dice"])]
    areas = [base.area("dice", "The throw", size=56, items=dice), base.area("score", f"The {state['column']}s (you / {state['seats'][1]})", rows=rows)]
    if state["over"]:
        msg = "Three trunks down. Yours." if state["result"] == "win" else "They felled three first."
    elif state["turn"] != 0:
        msg = f"{state['seats'][1]} is swinging."
    elif state["phase"] == "roll":
        msg = "Throw."
    elif state["phase"] == "choose":
        msg = "Pair the dice: which trunks take the strokes?"
    else:
        msg = "Bank the cuts, or throw again and risk the split."
    return base.head(state, "Felling the big one", msg, areas, actions(state, seat))

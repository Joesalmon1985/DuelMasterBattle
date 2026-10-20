"""The windlass: a European wheel (37 notches, one green) spun a few times. One pebble a spin on a colour, odd or even, high or low (even money), a
dozen (two to one) or a single notch (thirty-five to one). More pebbles than you came with wins; the drum keeps them otherwise."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base

RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
OUTSIDE = [("red", "Red rope", 1), ("black", "Black rope", 1), ("odd", "Odd", 1), ("even", "Even", 1), ("low", "Low (1 to 18)", 1), ("high", "High (19 to 36)", 1),
           ("dozen1", "First dozen", 2), ("dozen2", "Second dozen", 2), ("dozen3", "Third dozen", 2)]


def colour_of(n: int) -> str:
    return "green" if n == 0 else ("red" if n in RED else "black")


def wins(bet: str, n: int) -> bool:
    if bet.startswith("num:"):
        return int(bet[4:]) == n
    if n == 0:
        return False
    return {"red": n in RED, "black": n not in RED, "odd": n % 2 == 1, "even": n % 2 == 0, "low": n <= 18, "high": n >= 19,
            "dozen1": n <= 12, "dozen2": 13 <= n <= 24, "dozen3": n >= 25}[bet]


def payout(bet: str) -> int:
    if bet.startswith("num:"):
        return 35
    return next(p for b, _t, p in OUTSIDE if b == bet)


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    stake = int(opts.get("stake", 20))
    st = base.fresh("roulette", seed, ["you", str(opts.get("host", "them"))], stake=stake, pebbles=stake, spins=int(opts.get("spins", 8)), spun=0, last=None,
                    history=[], chips=str(opts.get("chips", "pebbles")))
    base.say(st, f"{stake} {st['chips']}. {st['spins']} spins. One {st['chips'][:-1]} a spin.")
    return st


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != 0:
        return []
    out = [{"id": f"bet:{b}", "bet": b, "text": t} for b, t, _p in OUTSIDE]
    out += [{"id": f"bet:num:{n}", "bet": f"num:{n}", "text": f"Notch {n}", "hidden": True} for n in range(37)]
    return out


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    return {"id": "bet:red", "bet": "red"}


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    bet = str(a["bet"])
    state["moves"] += 1
    n = base.rng(state, "spin").randrange(37)
    state["last"] = n
    state["spun"] += 1
    state["history"].append(n)
    state["pebbles"] -= 1
    if wins(bet, n):
        gain = payout(bet) + 1
        state["pebbles"] += gain
        base.say(state, f"The handle stops on {n} {colour_of(n)}. {bet.replace('num:', 'notch ')} wins {gain}.")
    else:
        base.say(state, f"The handle stops on {n} {colour_of(n)}. The drum keeps it.")
    if state["spun"] >= state["spins"] or state["pebbles"] <= 0:
        p, s = state["pebbles"], state["stake"]
        base.finish(state, "win" if p > s else ("draw" if p == s else "lose"), f"{p} {state['chips']} from {s}.")
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    last = state["last"]
    colours = {"green": 3, "red": 0, "black": "#262233"}
    drum = [{"id": "last", "text": str(last) if last is not None else "?", "colour": colours[colour_of(last)] if last is not None else -1, "sub": colour_of(last) if last is not None else ""}]
    notches = []
    for n in range(37):
        item = {"id": f"n{n}", "text": str(n), "colour": colours[colour_of(n)]}
        if not state["over"]:
            item["action"] = {"id": f"bet:num:{n}", "bet": f"num:{n}"}
        notches.append(item)
    areas = [base.area("score", "The drum", rows=[{"name": state["chips"], "value": state["pebbles"]}, {"name": "spins left", "value": state["spins"] - state["spun"]}]),
             base.area("tiles", "The handle stopped on", size=96, items=drum),
             base.area("tiles", "Or a single notch (35 to 1)", size=40, items=notches)]
    msg = "Put a pebble on the rim, or on a notch." if not state["over"] else {"win": "More than you came with.", "draw": "What you came with.", "lose": "The drum keeps them."}[state["result"]]
    return base.head(state, "The windlass", msg, areas, actions(state, seat))

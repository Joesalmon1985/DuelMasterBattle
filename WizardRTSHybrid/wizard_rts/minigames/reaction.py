"""The hunter's reaction game: a sign is shown (a print, a scat, a broken twig), then another; same beast as the last one, or different? Say it fast.
The client sends how long you took (`ms` on the action); a right answer scores two within the quick limit, one after it, nothing when wrong."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base

SIGNS = ["boar print", "deer print", "scat", "broken twig", "fur on bark", "a rub", "a bed in the grass"]
QUICK_MS = 1500


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    signs = list(opts.get("signs", SIGNS))
    rounds = int(opts.get("rounds", 12))
    st = base.fresh("reaction", seed, ["you", str(opts.get("host", "them"))], signs=signs, rounds=rounds, round=0, current=None, previous=None, score=0, times=[], right=0)
    rng = base.rng(st, "first")
    st["current"] = rng.randrange(len(signs))
    base.say(st, "Look at the sign. Then the next: same beast, or different?")
    return st


def _next(state: dict[str, Any]) -> None:
    rng = base.rng(state, f"sign:{state['round']}")
    state["previous"] = state["current"]
    if rng.random() < 0.45:
        state["current"] = state["previous"]  # the same beast again
    else:
        others = [i for i in range(len(state["signs"])) if i != state["previous"]]
        state["current"] = rng.choice(others)
    state["round"] += 1


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != 0:
        return []
    if state["previous"] is None:
        return [{"id": "next", "text": "I have it. Next sign."}]
    return [{"id": "same", "text": "Same beast"}, {"id": "different", "text": "Different beast"}]


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    return {"id": "next"}


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    state["moves"] += 1
    if a["id"] == "next":
        _next(state)
        return state
    ms = max(0, int(action.get("ms", 0) or 0))
    same = state["current"] == state["previous"]
    right = (a["id"] == "same") == same
    state["times"].append(ms)
    if right:
        state["right"] += 1
        gain = 2 if ms <= QUICK_MS else 1
        state["score"] += gain
        base.say(state, f"{'Same' if same else 'Different'}. Right{', quick' if gain == 2 else ', slow'} ({ms / 1000:.1f} s).")
    else:
        base.say(state, f"Wrong: it was {'the same beast' if same else 'a different beast'}.")
    if state["round"] >= state["rounds"]:
        best = 2 * state["rounds"]
        r = "win" if state["score"] >= 0.75 * best else ("draw" if state["score"] >= 0.5 * best else "lose")
        base.finish(state, r, f"{state['right']} of {state['rounds']} right, {state['score']} of {best} points.")
        return state
    _next(state)
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    sign = state["signs"][state["current"]]
    items = [{"id": "sign", "text": sign, "colour": state["current"] % 8}]
    areas = [base.area("score", "Trail", rows=[{"name": "sign", "value": f"{state['round']} of {state['rounds']}"}, {"name": "points", "value": state["score"]}]),
             base.area("tiles", "The sign", size=120, items=items)]
    msg = "Look. Then the next." if state["previous"] is None else "Same beast as the last one, or different? Quick."
    if state["over"]:
        msg = {"win": "A hunter's eye.", "draw": "Fair.", "lose": "Too slow, or wrong."}[state["result"]]
    return base.head(state, "Tracks", msg, areas, actions(state, seat), timed="reaction")

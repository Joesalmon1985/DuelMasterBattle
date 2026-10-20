"""Take the Last Carrot: rows of carrots on the table; take one, two or three from one row; whoever takes the last carrot peels the lot (misère:
the one who takes the last loses). The mother plays the winning strategy when there is one (a full search of the small game), else she takes one."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from wizard_rts.minigames import base


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    rows = [int(n) for n in opts.get("rows", [3, 5, 7])]
    st = base.fresh("nim", seed, ["you", str(opts.get("host", "them"))], rows=rows, take_max=int(opts.get("take_max", 3)), item=str(opts.get("item", "carrot")),
                    items=str(opts.get("items", "carrots")), turn=0)
    base.say(st, f"Take one, two or three {st['items']} from one row. The last {st['item']} peels.")
    return st


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != state["turn"]:
        return []
    out = []
    for r, n in enumerate(state["rows"]):
        for k in range(1, min(state["take_max"], n) + 1):
            out.append({"id": f"take:{r}:{k}", "row": r, "n": k, "text": f"Take {k} from row {r + 1}"})
    return out


@lru_cache(maxsize=None)
def _losing(rows: tuple[int, ...], take_max: int) -> bool:
    """True when the player to move loses with best play (misère: taking the last carrot loses)."""
    if sum(rows) == 0:
        return False  # the previous player took the last carrot: they lost, so the player to move has won
    for r, n in enumerate(rows):
        for k in range(1, min(take_max, n) + 1):
            nxt = list(rows)
            nxt[r] -= k
            if _losing(tuple(nxt), take_max):
                return False
    return True


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    acts = actions(state, seat)
    winning = []
    for a in acts:
        nxt = list(state["rows"])
        nxt[a["row"]] -= a["n"]
        if _losing(tuple(nxt), state["take_max"]):
            winning.append(a)
    pool = winning or [a for a in acts if a["n"] == 1] or acts
    return rng.choice(pool)


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    state["rows"][a["row"]] -= a["n"]
    state["moves"] += 1
    who = "You take" if seat == 0 else f"{state['seats'][1]} takes"
    base.say(state, f"{who} {a['n']} from row {a['row'] + 1}.")
    if sum(state["rows"]) == 0:
        if seat == 0:
            base.finish(state, "lose", f"You took the last {state['item']}. You peel.")
        else:
            base.finish(state, "win", f"{state['seats'][1]} took the last {state['item']}. They peel.")
        return state
    state["turn"] = 1 - seat
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    areas = []
    for r, n in enumerate(state["rows"]):
        areas.append(base.area("tiles", f"Row {r + 1}", size=44, items=[{"id": f"c{r}_{i}", "text": "", "colour": 5} for i in range(n)]))
    msg = "Your turn: take from one row." if state["turn"] == 0 else f"{state['seats'][1]} is thinking."
    if state["over"]:
        msg = "You peel." if state["result"] == "lose" else "They peel."
    return base.head(state, "The stew carrots", msg, areas, actions(state, seat))

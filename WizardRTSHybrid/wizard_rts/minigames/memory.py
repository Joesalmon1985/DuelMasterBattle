"""The forester's memory game: the saplings planted today, three, then four, then five; each time one is new and you point at it. Point at one that
was there before and it stops. A single player against the forester's patience: the result is how far you got."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base

OBJECTS = ["alder", "aspen", "birch", "larch", "oak", "rowan", "spruce", "beech", "maple", "elm", "pine", "willow", "ash", "hazel", "yew", "holly"]


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    objects = list(opts.get("objects", OBJECTS))
    start, cap = int(opts.get("start", 3)), min(int(opts.get("max", 14)), len(objects))
    st = base.fresh("memory", seed, ["you", str(opts.get("host", "them"))], start=start, max=cap, objects=objects, object=str(opts.get("object", "sapling")),
                    order=[], shown=[], round=0, passed=0)
    rng = base.rng(st, "order")
    order = list(range(len(objects)))
    rng.shuffle(order)
    st["order"] = order[:cap]  # the order the objects are added in: the first `start` are the opening set, each round adds the next
    _lay(st, start)
    base.say(st, f"These are today's. Look at them.")
    return st


def _lay(state: dict[str, Any], n: int) -> None:
    """Round with `n` objects on show: the first n of the order, shuffled for the eye."""
    state["round"] = n
    shown = list(state["order"][:n])
    base.rng(state, f"lay:{n}").shuffle(shown)
    state["shown"] = shown


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != 0:
        return []
    if state["round"] == state["start"] and state["passed"] == 0 and not state.get("looked"):
        return [{"id": "next", "text": "I have them."}]
    return [{"id": f"pick:{i}", "pick": i, "text": state["objects"][i]} for i in state["shown"]]


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    return {"id": "next"}


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    state["moves"] += 1
    if a["id"] == "next":
        state["looked"] = True
        _lay(state, state["round"] + 1)
        base.say(state, "One more has gone in. Which?")
        return state
    newest = state["order"][state["round"] - 1]
    if int(a["pick"]) == newest:
        state["passed"] += 1
        if state["round"] >= state["max"]:
            base.finish(state, "win", f"Every one of {state['max']} named. A forester's eye.")
            return state
        _lay(state, state["round"] + 1)
        base.say(state, f"Yes, the {state['objects'][newest]}. One more has gone in.")
        return state
    base.finish(state, "lose" if state["passed"] < 3 else "draw", f"No: the {state['objects'][int(a['pick'])]} was there before. The new one was the {state['objects'][newest]}. {state['passed']} named.")
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    items = []
    for i in state["shown"]:
        item = {"id": f"o{i}", "text": state["objects"][i], "colour": i % 8}
        if not state["over"] and state.get("looked"):
            item["action"] = {"id": f"pick:{i}", "pick": i}
        items.append(item)
    areas = [base.area("score", "Saplings", rows=[{"name": "on show", "value": state["round"]}, {"name": "named", "value": state["passed"]}, {"name": "to go", "value": state["max"]}]),
             base.area("tiles", "The plantings", size=72, items=items)]
    if not state.get("looked"):
        msg = "Look at them. Then say you have them."
    elif state["over"]:
        msg = "A forester's eye." if state["result"] == "win" else "That one was there before."
    else:
        msg = "Which one is new?"
    return base.head(state, "Which sapling is new?", msg, areas, actions(state, seat))

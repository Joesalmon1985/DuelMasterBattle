"""Rock Paper Scissors: three signs in a ring, each beating the next. With the mentor it is "three colours, no knots": Flame beats Vine, Vine beats
Frost, Frost beats Flame (the skin names the signs). First to `target` rounds (default 3, a best of five)."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base

SIGNS = ("rock", "scissors", "paper")  # sign i beats sign (i + 1) % 3: rock beats scissors, scissors beat paper, paper beats rock (Flame, Vine, Frost likewise)


def beats(a: int, b: int) -> bool:
    """Sign `a` beats sign `b`: each sign beats the next in the ring and loses to the one before it."""
    return (int(a) + 1) % 3 == int(b)


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    names = list(opts.get("signs") or ["Rock", "Paper", "Scissors"])
    st = base.fresh("rps", seed, ["you", str(opts.get("host", "them"))], names=names[:3], target=int(opts.get("target", 3)), score=[0, 0], rounds=[], last=None)
    base.say(st, f"First to {st['target']}.")
    return st


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != 0:
        return []
    return [{"id": f"sign:{i}", "text": state["names"][i], "sign": i} for i in range(3)]


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    """Not quite random: the villager leans a little on the sign that would have beaten the apprentice's last one."""
    last = state["last"]
    if last is not None and rng.random() < 0.4:
        i = (int(last[0]) + 2) % 3  # the sign that beats the apprentice's last throw
    else:
        i = rng.randrange(3)
    return {"id": f"sign:{i}", "sign": i}


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    if seat != 0:
        raise base.Illegal("seat")
    a = base.find(actions(state, seat), action)
    mine = int(a["sign"])
    theirs = int(bot(state, 1, base.rng(state, "bot"))["sign"])
    state["moves"] += 1
    state["last"] = [mine, theirs]
    names = state["names"]
    if mine == theirs:
        base.say(state, f"{names[mine]} against {names[theirs]}: nobody.")
    elif beats(mine, theirs):
        state["score"][0] += 1
        base.say(state, f"{names[mine]} beats {names[theirs]}. Yours.")
    else:
        state["score"][1] += 1
        base.say(state, f"{names[theirs]} beats {names[mine]}. Theirs.")
    state["rounds"].append([mine, theirs])
    if state["score"][0] >= state["target"]:
        base.finish(state, "win", f"{state['score'][0]} to {state['score'][1]}.")
    elif state["score"][1] >= state["target"]:
        base.finish(state, "lose", f"{state['score'][1]} to {state['score'][0]}.")
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    names = state["names"]
    last = state["last"]
    shown = [{"label": "You", "sign": names[last[0]] if last else "?", "colour": last[0] if last else -1},
             {"label": state["seats"][1], "sign": names[last[1]] if last else "?", "colour": last[1] if last else -1}]
    areas = [base.area("score", "Rounds", you=state["score"][0], them=state["score"][1], target=state["target"], names=[state["seats"][0], state["seats"][1]]),
             base.area("signs", "The last throw", items=shown, names=names)]
    msg = "Choose a sign." if not state["over"] else ("You win." if state["result"] == "win" else "They win.")
    return base.head(state, "Three colours, no knots", msg, areas, actions(state, seat))

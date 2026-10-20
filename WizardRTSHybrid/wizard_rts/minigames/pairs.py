"""Pairs: swatches face down in the basket, each with a twin cut from the same bolt. Turn two; a match is kept and the turn goes on; a miss turns
them back. Whoever has more pairs when the basket is empty. The mother remembers every swatch she has seen turned (she cut them)."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base

PATTERNS = ["check", "stripe", "dot", "herringbone", "plain", "twill", "chevron", "paisley", "diamond", "wave", "plaid", "cable"]


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    n = int(opts.get("pairs", 8))
    patterns = list(opts.get("patterns", PATTERNS))
    st = base.fresh("pairs", seed, ["you", str(opts.get("host", "them"))], n=n, item=str(opts.get("item", "swatch")))
    rng = base.rng(st, "deal")
    kinds = [(patterns[i % len(patterns)], i % 8) for i in range(n)]
    tiles = [k for k in kinds for _ in range(2)]
    rng.shuffle(tiles)
    st.update(tiles=[[p, c] for p, c in tiles], taken=[-1] * (2 * n), pending=None, shown=[], score=[0, 0], seen=[], turn=0)
    base.say(st, f"{2 * n} {st['item']}es in the basket. Turn two.")
    return st


def _open(state: dict[str, Any]) -> list[int]:
    return [i for i, t in enumerate(state["taken"]) if t < 0]


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != state["turn"]:
        return []
    return [{"id": f"flip:{i}", "tile": i, "text": f"Turn {state['item']} {i + 1}"} for i in _open(state) if i != state["pending"]]


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    """Perfect memory of what has been turned: a known pair is taken; a first pick is an unknown swatch; the second pick is the known twin if any."""
    open_ = [i for i in _open(state) if i != state["pending"]]
    seen = set(state["seen"])
    known = {i: tuple(state["tiles"][i]) for i in open_ if i in seen}
    if state["pending"] is not None:
        want = tuple(state["tiles"][state["pending"]])
        for i, k in known.items():
            if k == want:
                return {"id": f"flip:{i}", "tile": i}
        unknown = [i for i in open_ if i not in seen]
        return _pick(unknown or open_, rng)
    by_kind: dict[tuple, list[int]] = {}
    for i, k in known.items():
        by_kind.setdefault(k, []).append(i)
    for k, idxs in by_kind.items():
        if len(idxs) >= 2:
            return {"id": f"flip:{idxs[0]}", "tile": idxs[0]}
    unknown = [i for i in open_ if i not in seen]
    return _pick(unknown or open_, rng)


def _pick(pool: list[int], rng: Any) -> dict[str, Any]:
    i = rng.choice(pool)
    return {"id": f"flip:{i}", "tile": i}


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    i = int(a["tile"])
    state["moves"] += 1
    state["shown"] = [j for j in state["shown"] if state["taken"][j] >= 0]  # a miss from the turn before goes back face down now
    if i not in state["seen"]:
        state["seen"].append(i)
    who = "You turn" if seat == 0 else f"{state['seats'][1]} turns"
    if state["pending"] is None:
        state["pending"] = i
        state["shown"] = [i]
        base.say(state, f"{who} a {state['tiles'][i][0]}.")
        return state
    first = state["pending"]
    state["pending"] = None
    state["shown"] = [first, i]
    if state["tiles"][first] == state["tiles"][i]:
        state["taken"][first] = state["taken"][i] = seat
        state["score"][seat] += 1
        base.say(state, f"{who} another {state['tiles'][i][0]}: a pair.")
        if not _open(state):
            you, them = state["score"]
            base.finish(state, "win" if you > them else ("lose" if them > you else "draw"), f"{you} pairs to {them}.")
        return state  # a pair: the same player goes again
    base.say(state, f"{who} a {state['tiles'][i][0]}. No match.")
    state["turn"] = 1 - seat
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    items = []
    for i, (pattern, colour) in enumerate(state["tiles"]):
        taken = state["taken"][i] >= 0
        up = taken or i in state["shown"]
        item = {"id": f"t{i}", "text": "" if not up else "", "colour": colour if up else -1, "pattern": pattern if up else "", "down": not up,
                "sub": ("yours" if state["taken"][i] == 0 else state["seats"][1][:8]) if taken else ""}
        if not taken and state["turn"] == 0 and not state["over"] and i != state["pending"]:
            item["action"] = {"id": f"flip:{i}", "tile": i}
        if taken:
            item["disabled"] = True
        items.append(item)
    areas = [base.area("score", "Pairs", you=state["score"][0], them=state["score"][1], names=state["seats"]),
             base.area("tiles", "The basket", size=64, items=items)]
    msg = "Turn a swatch." if state["pending"] is None else "Turn another: find its twin."
    if state["turn"] == 1 and not state["over"]:
        msg = f"{state['seats'][1]} is turning."
    if state["over"]:
        msg = {"win": "More pairs than her.", "lose": "She has more pairs.", "draw": "Even."}[state["result"]]
    return base.head(state, "The same bolt", msg, areas, actions(state, seat))

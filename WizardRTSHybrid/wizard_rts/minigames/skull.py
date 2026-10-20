"""Under the cloth: Skull with the carriers, three players. Each has three flowers and a rat's skull on covered carts. Everyone lays a cart face
down; then anyone may lay another or open the bidding: how many carts they dare uncover without a skull. Others raise or pass. The highest bidder
uncovers their own carts first, then one of anybody's at a time; a skull costs the challenger a cart (and the round), the bid made is a point, two
points win. A player with no carts left is out."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    n = int(opts.get("players", 3))
    names = ["you", str(opts.get("host", "them"))] + [str(x) for x in opts.get("partners", [])]
    names = (names + [f"carrier {i}" for i in range(2, n)])[:n]
    st = base.fresh("skull", seed, names, players=n, discs=[{"flower": 3, "skull": 1} for _ in range(n)], stacks=[[] for _ in range(n)], revealed=[[] for _ in range(n)],
                    phase="place", current=0, bid=0, bidder=None, passed=[False] * n, points=[0] * n, alive=[True] * n, flipped=0, starter=0,
                    flower=str(opts.get("flower", "flower")), skull=str(opts.get("skull", "rat skull")), disc=str(opts.get("disc", "cart")))
    base.say(st, "Lay a cart face down.")
    return st


def _alive(state: dict[str, Any]) -> list[int]:
    return [i for i in range(state["players"]) if state["alive"][i]]


def _next(state: dict[str, Any], seat: int) -> int:
    s = seat
    for _ in range(state["players"]):
        s = (s + 1) % state["players"]
        if state["alive"][s]:
            return s
    return seat


def _hand(state: dict[str, Any], seat: int) -> dict[str, int]:
    placed = state["stacks"][seat]
    return {"flower": state["discs"][seat]["flower"] - placed.count("flower"), "skull": state["discs"][seat]["skull"] - placed.count("skull")}


def _total_placed(state: dict[str, Any]) -> int:
    return sum(len(s) for i, s in enumerate(state["stacks"]) if state["alive"][i])


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != state["current"] or not state["alive"][seat]:
        return []
    out = []
    if state["phase"] == "place":
        hand = _hand(state, seat)
        everyone = all(state["stacks"][i] for i in _alive(state))
        if hand["flower"] > 0:
            out.append({"id": "place:flower", "disc": "flower", "text": f"Lay a {state['flower']}"})
        if hand["skull"] > 0:
            out.append({"id": "place:skull", "disc": "skull", "text": f"Lay the {state['skull']}"})
        if everyone and state["stacks"][seat]:
            for k in range(1, _total_placed(state) + 1):
                out.append({"id": f"bid:{k}", "bid": k, "text": f"Bid {k}"})
        return out
    if state["phase"] == "bid":
        for k in range(state["bid"] + 1, _total_placed(state) + 1):
            out.append({"id": f"bid:{k}", "bid": k, "text": f"Raise to {k}"})
        out.append({"id": "pass", "text": "Pass"})
        return out
    if state["phase"] == "reveal":
        for i in _alive(state):
            if i != seat and len(state["revealed"][i]) < len(state["stacks"][i]):
                out.append({"id": f"flip:{i}", "who": i, "text": f"Uncover {state['seats'][i]}'s next {state['disc']}"})
        return out
    return out


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    acts = actions(state, seat)
    ids = [a["id"] for a in acts]
    if state["phase"] == "place":
        if not state["stacks"][seat]:
            return {"id": "place:skull", "disc": "skull"} if ("place:skull" in ids and rng.random() < 0.3) else {"id": "place:flower", "disc": "flower"} if "place:flower" in ids else {"id": "place:skull", "disc": "skull"}
        own_safe = "skull" not in state["stacks"][seat]
        if own_safe and rng.random() < 0.5:
            return {"id": f"bid:{len(state['stacks'][seat])}", "bid": len(state["stacks"][seat])}
        if "place:flower" in ids and rng.random() < 0.5:
            return {"id": "place:flower", "disc": "flower"}
        bids = [a for a in acts if a["id"].startswith("bid:")]
        if bids:
            return {"id": bids[0]["id"], "bid": bids[0]["bid"]}
        return {"id": ids[0], **({"disc": acts[0]["disc"]} if "disc" in acts[0] else {})}
    if state["phase"] == "bid":
        own_safe = "skull" not in state["stacks"][seat]
        raises = [a for a in acts if a["id"].startswith("bid:")]
        if own_safe and raises and raises[0]["bid"] <= len(state["stacks"][seat]) and rng.random() < 0.6:
            return {"id": raises[0]["id"], "bid": raises[0]["bid"]}
        return {"id": "pass"}
    flips = [a for a in acts if a["id"].startswith("flip:")]
    best = max(flips, key=lambda a: len(state["stacks"][a["who"]]) - len(state["revealed"][a["who"]]))
    return {"id": best["id"], "who": best["who"]}


def _new_round(state: dict[str, Any], starter: int) -> None:
    for i in range(state["players"]):
        state["stacks"][i] = []
        state["revealed"][i] = []
    state["phase"] = "place"
    state["bid"] = 0
    state["bidder"] = None
    state["passed"] = [False] * state["players"]
    state["flipped"] = 0
    state["starter"] = starter
    state["current"] = starter if state["alive"][starter] else _next(state, starter)


def _lose_disc(state: dict[str, Any], seat: int) -> None:
    d = state["discs"][seat]
    rng = base.rng(state, "lose")
    if d["flower"] > 0 and (d["skull"] == 0 or rng.random() < 0.75):
        d["flower"] -= 1
    else:
        d["skull"] -= 1
    if d["flower"] + d["skull"] == 0:
        state["alive"][seat] = False
        base.say(state, f"{state['seats'][seat]} {'have' if seat == 0 else 'has'} no carts left and {'are' if seat == 0 else 'is'} out.")


def _check_end(state: dict[str, Any]) -> bool:
    alive = _alive(state)
    if not state["alive"][0]:
        base.finish(state, "lose", "Out of carts.")
        return True
    if len(alive) == 1:
        base.finish(state, "win" if alive[0] == 0 else "lose", "Last with carts.")
        return True
    return False


def _start_reveal(state: dict[str, Any]) -> None:
    b = int(state["bidder"])
    state["phase"] = "reveal"
    state["current"] = b
    state["revealed"][b] = list(state["stacks"][b])
    state["flipped"] = len(state["stacks"][b])
    if "skull" in state["stacks"][b]:
        base.say(state, f"{state['seats'][b]} uncover{'' if b == 0 else 's'} {'their' if b else 'your'} own carts: a {state['skull']}.")
        _lose_disc(state, b)
        if _check_end(state):
            return
        _new_round(state, b)
        return
    base.say(state, f"{state['seats'][b]} uncover{'' if b == 0 else 's'} {'their' if b else 'your'} own carts: {len(state['stacks'][b])} {state['flower']}s.")
    _after_flip(state)


def _after_flip(state: dict[str, Any]) -> None:
    b = int(state["bidder"])
    if state["flipped"] >= state["bid"]:
        state["points"][b] += 1
        base.say(state, f"{state['bid']} {state['flower']}s: a point for {state['seats'][b]} ({state['points'][b]}).")
        if state["points"][b] >= 2:
            base.finish(state, "win" if b == 0 else "lose", "Two flowers.")
            return
        _new_round(state, b)


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    state["moves"] += 1
    aid = a["id"]
    who = "You" if seat == 0 else state["seats"][seat]
    if aid.startswith("place:"):
        state["stacks"][seat].append(a["disc"])
        base.say(state, f"{who} lay{'' if seat == 0 else 's'} a {state['disc']}.")
        state["current"] = _next(state, seat)
        return state
    if aid.startswith("bid:"):
        state["bid"] = int(a["bid"])
        state["bidder"] = seat
        state["passed"] = [False] * state["players"]
        state["phase"] = "bid"
        base.say(state, f"{who} bid{'' if seat == 0 else 's'} {state['bid']}.")
        if state["bid"] >= _total_placed(state):
            _start_reveal(state)
            return state
        state["current"] = _next(state, seat)
        return state
    if aid == "pass":
        state["passed"][seat] = True
        base.say(state, f"{who} pass{'' if seat == 0 else 'es'}.")
        others = [i for i in _alive(state) if i != state["bidder"]]
        if all(state["passed"][i] for i in others):
            _start_reveal(state)
            return state
        nxt = _next(state, seat)
        while state["passed"][nxt] or nxt == state["bidder"]:
            if nxt == state["bidder"]:
                _start_reveal(state)
                return state
            nxt = _next(state, nxt)
        state["current"] = nxt
        return state
    if aid.startswith("flip:"):
        i = int(a["who"])
        disc = state["stacks"][i][-1 - len(state["revealed"][i])]  # from the top
        state["revealed"][i].append(disc)
        state["flipped"] += 1
        if disc == "skull":
            base.say(state, f"{state['seats'][i]}'s {state['disc']}: the {state['skull']}.")
            _lose_disc(state, seat)
            if _check_end(state):
                return state
            _new_round(state, seat)
            return state
        base.say(state, f"{state['seats'][i]}'s {state['disc']}: a {state['flower']}.")
        _after_flip(state)
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    areas = [base.area("score", "Points", rows=[{"name": state["seats"][i] + ("" if state["alive"][i] else " (out)"), "value": f"{state['points'][i]} ({_hand(state, i)['flower'] + _hand(state, i)['skull'] + len(state['stacks'][i])} carts)"} for i in range(state["players"])])]
    for i in range(state["players"]):
        if not state["alive"][i]:
            continue
        items = []
        for k, disc in enumerate(state["stacks"][i]):
            shown = i == 0 or k >= len(state["stacks"][i]) - len(state["revealed"][i])
            items.append({"id": f"s{i}_{k}", "text": (state["flower"] if disc == "flower" else state["skull"]) if shown else "", "colour": (3 if disc == "flower" else 6) if shown else -1, "down": not shown})
        label = ("Your carts" if i == 0 else state["seats"][i] + "'s carts") + (" (bidding)" if state["bidder"] == i else "")
        if state["phase"] == "reveal" and state["current"] == 0 and i != 0 and len(state["revealed"][i]) < len(state["stacks"][i]):
            items.append({"id": f"flip{i}", "text": "?", "colour": -1, "action": {"id": f"flip:{i}", "who": i}})
        areas.append(base.area("tiles", label, size=56, items=items))
    hand = _hand(state, 0)
    areas.append(base.area("tiles", "In your hand", size=48, items=[{"id": f"hf{k}", "text": state["flower"], "colour": 3} for k in range(hand["flower"])] + [{"id": "hs", "text": state["skull"], "colour": 6} for _ in range(hand["skull"])]))
    if state["over"]:
        msg = "Two flowers." if state["result"] == "win" else "The skull, every time."
    elif state["current"] != 0:
        msg = f"{state['seats'][state['current']]} is thinking."
    elif state["phase"] == "place":
        msg = "Lay a cart, or bid how many you dare uncover."
    elif state["phase"] == "bid":
        msg = f"The bid is {state['bid']}. Raise or pass."
    else:
        msg = f"Uncover {state['bid'] - state['flipped']} more without a skull."
    return base.head(state, "Under the cloth", msg, areas, actions(state, seat))

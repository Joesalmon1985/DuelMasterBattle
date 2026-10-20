"""Bid your bouts: Oh Hell at the Rollkeeper's fire, three players. A run of hands with the deal shrinking and growing (five, four, three, two, one,
two, three); trumps turned; everyone bids the tricks they will take, the dealer last and never such that the bids come out even (the hook); exactly
the bid scores ten plus the bid, anything else nothing. The Rollkeeper keeps the score. The best score over the run wins."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base, cards, tricks


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    n = int(opts.get("players", 3))
    names = ["you", str(opts.get("host", "them"))] + [str(x) for x in opts.get("partners", [])]
    names = (names + [f"contestant {i}" for i in range(2, n)])[:n]
    st = base.fresh("ohhell", seed, names, players=n, sizes=[int(x) for x in opts.get("hands", [5, 4, 3, 2, 1, 2, 3])], hand_no=0, hands=[[] for _ in range(n)],
                    trump="", dealer=n - 1, bids=[None] * n, taken=[0] * n, score=[0] * n, phase="deal", trick=[], current=0, leader=0)
    _deal(st)
    return st


def _size(state: dict[str, Any]) -> int:
    return int(state["sizes"][state["hand_no"] - 1])


def _deal(state: dict[str, Any]) -> None:
    state["hand_no"] += 1
    n = state["players"]
    size = _size(state)
    rng = base.rng(state, f"deal:{state['hand_no']}")
    hands, rest = tricks.deal(rng, n, size)
    state["hands"] = hands
    state["trump"] = rest[0][1] if rest else "s"
    state["dealer"] = (state["dealer"] + 1) % n
    state["bids"] = [None] * n
    state["taken"] = [0] * n
    state["trick"] = []
    state["leader"] = (state["dealer"] + 1) % n
    state["current"] = state["leader"]
    state["phase"] = "bid"
    base.say(state, f"Hand {state['hand_no']}: {size} card{'s' if size != 1 else ''}, {tricks.SUIT_NAMES[state['trump']]} are trumps. {_name(state, state['dealer'])} deal{'' if state['dealer'] == 0 else 's'}.")


def _name(state: dict[str, Any], seat: int) -> str:
    return "You" if seat == 0 else state["seats"][seat]


def _hooked(state: dict[str, Any], seat: int, bid: int) -> bool:
    """The dealer may not make the bids add up to the tricks on offer."""
    if seat != state["dealer"]:
        return False
    others = sum(int(b) for i, b in enumerate(state["bids"]) if b is not None and i != seat)
    return others + bid == _size(state)


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != state["current"]:
        return []
    if state["phase"] == "bid":
        return [{"id": f"bid:{k}", "bid": k, "text": f"Bid {k}"} for k in range(_size(state) + 1) if not _hooked(state, seat, k)]
    hand = state["hands"][seat]
    return [{"id": f"play:{c}", "card": c, "text": "Play " + cards.card_text(c)} for c in tricks.legal(hand, state["trick"], state["trump"])]


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    acts = actions(state, seat)
    if state["phase"] == "bid":
        want = min(tricks.likely_tricks(state["hands"][seat], state["trump"]), _size(state))
        legal = [a["bid"] for a in acts]
        bid = want if want in legal else min(legal, key=lambda k: abs(k - want))
        return {"id": f"bid:{bid}", "bid": bid}
    want_win = state["taken"][seat] < int(state["bids"][seat] or 0)
    c = tricks.bot_play(state["hands"][seat], state["trick"], state["trump"], want_win)
    return {"id": f"play:{c}", "card": c}


def _next(state: dict[str, Any], seat: int) -> int:
    return (seat + 1) % state["players"]


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    state["moves"] += 1
    if a["id"].startswith("bid:"):
        state["bids"][seat] = int(a["bid"])
        base.say(state, f"{_name(state, seat)} bid{'' if seat == 0 else 's'} {a['bid']}.")
        if all(b is not None for b in state["bids"]):
            state["phase"] = "play"
            state["current"] = state["leader"]
        else:
            state["current"] = _next(state, seat)
        return state
    c = a["card"]
    state["hands"][seat].remove(c)
    state["trick"].append([seat, c])
    if len(state["trick"]) < state["players"]:
        state["current"] = _next(state, seat)
        return state
    w = tricks.winner(state["trick"], state["trump"])
    state["taken"][w] += 1
    base.say(state, f"{_name(state, w)} take{'' if w == 0 else 's'} the trick.")
    state["trick"] = []
    state["leader"] = w
    state["current"] = w
    if any(state["hands"]):
        return state
    # the hand is scored
    words = []
    for i in range(state["players"]):
        if state["taken"][i] == int(state["bids"][i]):
            state["score"][i] += 10 + int(state["bids"][i])
            words.append(f"{_name(state, i)} exact")
        else:
            words.append(f"{_name(state, i)} {state['taken'][i]} for {state['bids'][i]}")
    base.say(state, "; ".join(words) + ".")
    if state["hand_no"] >= len(state["sizes"]):
        you = state["score"][0]
        best_other = max(state["score"][1:])
        base.finish(state, "win" if you > best_other else ("draw" if you == best_other else "lose"), "The roll: " + ", ".join(f"{_name(state, i)} {state['score'][i]}" for i in range(state["players"])) + ".")
        return state
    _deal(state)
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    rows = [{"name": _name(state, i), "value": f"bid {state['bids'][i] if state['bids'][i] is not None else '-'}, took {state['taken'][i]}, score {state['score'][i]}"} for i in range(state["players"])]
    areas = [base.area("score", f"Hand {state['hand_no']} of {len(state['sizes'])}: {_size(state)} cards, trumps {tricks.SUIT_NAMES.get(state['trump'], '?')}", rows=rows)]
    areas.append(base.area("cards", "On the table", size=52, items=[cards.card_item(c, label=_name(state, int(s))) for s, c in state["trick"]]))
    mine = state["current"] == 0 and state["phase"] == "play" and not state["over"]
    legal = tricks.legal(state["hands"][0], state["trick"], state["trump"]) if mine else []
    items = []
    for c in state["hands"][0]:
        item = cards.card_item(c)
        if mine and c in legal:
            item["action"] = {"id": f"play:{c}", "card": c}
        else:
            item["disabled"] = True
        items.append(item)
    areas.append(base.area("cards", "Your hand (tap to play)" if mine else "Your hand", size=52, items=items))
    if state["over"]:
        msg = {"win": "The best roll.", "lose": "The roll shows it.", "draw": "Level on the roll."}[state["result"]]
    elif state["phase"] == "bid":
        msg = "How many tricks will you take?" if state["current"] == 0 else f"{_name(state, state['current'])} is bidding."
    elif mine:
        msg = "Your card." if state["trick"] else "Lead."
    else:
        msg = f"{_name(state, state['current'])} is playing."
    acts = [a for a in actions(state, seat) if not a["id"].startswith("play:")]
    return base.head(state, "Bid your bouts", msg, areas, acts + [dict(a, hidden=True) for a in actions(state, seat) if a["id"].startswith("play:")])

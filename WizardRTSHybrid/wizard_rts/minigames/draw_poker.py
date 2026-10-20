"""Skins: five-card draw against the hunter, heads up, pebbles for pelts. An ante each, five cards, a round of betting, throw away up to three and
take fresh, a second round, show. A fixed number of hands or an empty stack ends it; more pebbles than you came with wins."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base, betting, cards


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    stake = int(opts.get("stake", 20))
    st = base.fresh("draw_poker", seed, ["you", str(opts.get("host", "them"))], stake=stake, stacks=[stake, stake], pot=0, ante=int(opts.get("ante", 1)), hands=int(opts.get("hands", 5)),
                    hand_no=0, deck=[], cards=[[], []], phase="deal", dealer=1, selected=[], drawn=[0, 0], chips=str(opts.get("chips", "pebbles")), bet={}, outcome="")
    base.say(st, f"{stake} {st['chips']} each, {st['hands']} hands. One in for the ante.")
    return st


def _deal(state: dict[str, Any]) -> None:
    state["hand_no"] += 1
    state["dealer"] = 1 - state["dealer"]
    for s in (0, 1):
        n = min(state["ante"], state["stacks"][s])
        state["stacks"][s] -= n
        state["pot"] += n
    state["deck"] = cards.deck(base.rng(state, f"shuffle:{state['hand_no']}"))
    state["cards"] = [[state["deck"].pop() for _ in range(5)], [state["deck"].pop() for _ in range(5)]]
    state["selected"] = []
    state["drawn"] = [0, 0]
    state["outcome"] = ""
    state["phase"] = "bet1"
    betting.start(state, 1 - state["dealer"], 2)
    base.say(state, f"Hand {state['hand_no']}. {'You' if state['dealer'] == 0 else state['seats'][1]} deal{'' if state['dealer'] == 0 else 's'}.")


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"]:
        return []
    if state["phase"] in ("deal", "settled"):
        return [{"id": "deal", "text": "Deal" if not state["hand_no"] else "Deal the next hand"}] if seat == 0 else []
    if state["phase"] in ("bet1", "bet2"):
        return betting.options(state, seat)
    if state["phase"] == "draw":
        if seat != state["draw_seat"]:
            return []
        out = [{"id": f"toggle:{c}", "card": c, "text": "Throw away " + cards.card_text(c), "hidden": True} for c in state["cards"][seat]]
        n = len(state["selected"]) if seat == 0 else 0
        out.append({"id": "draw", "text": f"Take {n} fresh" if seat == 0 and n else "Stand pat"})
        return out
    return []


def _strength(hand: list[str]) -> int:
    return int(cards.rank5(hand)[0])


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    if state["phase"] == "draw":
        hand = state["cards"][seat]
        r = cards.rank5(hand)
        keep: set[str] = set()
        if r[0] >= 4:
            keep = set(hand)
        else:
            from collections import Counter

            counts = Counter(c[0] for c in hand)
            keep = {c for c in hand if counts[c[0]] >= 2}
            if not keep:
                keep = {max(hand, key=cards.rank_value)}
        throw = [c for c in hand if c not in keep][:3]
        state["_bot_throw"] = throw
        return {"id": "draw"}
    opts = betting.options(state, seat)
    ids = [o["id"] for o in opts]
    s = _strength(state["cards"][seat])
    high = max(cards.rank_value(c) for c in state["cards"][seat])
    strong = s >= 2 or (s == 1 and high >= 12)
    medium = s >= 1 or high >= 13
    if strong and "raise" in ids:
        return {"id": "raise"}
    if strong and "bet" in ids:
        return {"id": "bet"}
    if "check" in ids:
        return {"id": "check"}
    if "call" in ids and (medium or rng.random() < 0.3):
        return {"id": "call"}
    return {"id": "fold"} if "fold" in ids else {"id": ids[0]}


def _showdown(state: dict[str, Any]) -> None:
    r0, r1 = cards.rank5(state["cards"][0]), cards.rank5(state["cards"][1])
    if r0 > r1:
        winner: int | None = 0
    elif r1 > r0:
        winner = 1
    else:
        winner = None
    pot = state["pot"]
    betting.settle(state, winner)
    who = {0: "You take", 1: f"{state['seats'][1]} takes", None: "You split"}[winner]
    state["outcome"] = f"{cards.category_name(r0)} against {cards.category_name(r1)}: {who} the pot of {pot}."
    base.say(state, state["outcome"])
    _after_hand(state)


def _after_hand(state: dict[str, Any]) -> None:
    state["phase"] = "settled"
    if state["hand_no"] >= state["hands"] or min(state["stacks"]) <= 0:
        p, s = state["stacks"][0], state["stake"]
        base.finish(state, "win" if p > s else ("draw" if p == s else "lose"), f"{p} {state['chips']} from {s}.")


def _after_betting(state: dict[str, Any]) -> None:
    b = state["bet"]
    if b["folded"] is not None:
        w = 1 - int(b["folded"])
        pot = state["pot"]
        betting.settle(state, w)
        state["outcome"] = f"{'You fold' if b['folded'] == 0 else state['seats'][1] + ' folds'}: {'you take' if w == 0 else state['seats'][1] + ' takes'} {pot}."
        base.say(state, state["outcome"])
        _after_hand(state)
        return
    if state["phase"] == "bet1":
        state["phase"] = "draw"
        state["draw_seat"] = 1 - state["dealer"]
        return
    _showdown(state)


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    state["moves"] += 1
    aid = a["id"]
    if aid == "deal":
        _deal(state)
        return state
    if state["phase"] in ("bet1", "bet2"):
        betting.apply(state, seat, aid)
        base.say(state, f"{'You' if seat == 0 else state['seats'][1]} {aid}{'s' if seat else ''}.")
        if state["bet"]["done"]:
            _after_betting(state)
        return state
    if aid.startswith("toggle:"):
        c = a["card"]
        if c in state["selected"]:
            state["selected"].remove(c)
        elif len(state["selected"]) < 3:
            state["selected"].append(c)
        return state
    if aid == "draw":
        throw = list(state["selected"]) if seat == 0 else list(state.pop("_bot_throw", []))
        hand = state["cards"][seat]
        for c in throw:
            if c in hand:
                hand.remove(c)
                hand.append(state["deck"].pop())
        state["drawn"][seat] = len(throw)
        state["selected"] = []
        base.say(state, f"{'You take' if seat == 0 else state['seats'][1] + ' takes'} {len(throw)}.")
        if seat == 1 - state["dealer"]:
            state["draw_seat"] = state["dealer"]
            return state
        state["phase"] = "bet2"
        betting.start(state, 1 - state["dealer"], 4)
        return state
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    show = state["phase"] == "settled" and "against" in state["outcome"]
    areas = [base.area("score", "Pelts", rows=[{"name": f"your {state['chips']}", "value": state["stacks"][0]}, {"name": f"{state['seats'][1]}'s", "value": state["stacks"][1]},
                                                {"name": "pot", "value": state["pot"]}, {"name": "hand", "value": f"{state['hand_no']} of {state['hands']}"}])]
    if state["cards"][1]:
        areas.append(base.area("cards", state["seats"][1] + (f" (took {state['drawn'][1]})" if state["phase"] in ("bet2", "settled") else ""), size=52,
                               items=[cards.card_item(c, down=not show) for c in state["cards"][1]]))
    if state["cards"][0]:
        items = []
        drawing = state["phase"] == "draw" and state.get("draw_seat") == 0
        for c in state["cards"][0]:
            item = cards.card_item(c, selected=c in state["selected"])
            if drawing:
                item["action"] = {"id": f"toggle:{c}", "card": c}
            items.append(item)
        label = "Your hand" + (" (tap up to three to throw away)" if drawing else f" ({cards.category_name(cards.rank5(state['cards'][0]))})")
        areas.append(base.area("cards", label, size=52, items=items))
    if state["over"]:
        msg = {"win": "Their pebbles. In the game, pelts.", "draw": "Even.", "lose": "The hunter keeps them."}[state["result"]]
    elif state["phase"] == "deal":
        msg = "An ante each. Deal?"
    elif state["phase"] in ("bet1", "bet2"):
        msg = "Your bet." if state["bet"].get("current") == 0 else f"{state['seats'][1]} is thinking."
    elif state["phase"] == "draw":
        msg = "Throw away up to three, then take fresh." if state.get("draw_seat") == 0 else f"{state['seats'][1]} is drawing."
    else:
        msg = state["outcome"]
    return base.head(state, "Skins", msg, areas, actions(state, seat))

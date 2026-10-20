"""The carriers' pot: Texas Hold'em heads up against a carrier, fixed limit. Blinds of one and two, two cards each, the flop, the turn and the river
on the road between you, a round of betting on each; best five of seven. A fixed number of hands or an empty stack ends it; more pebbles than you
came with wins."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base, betting, cards

STREETS = ("preflop", "flop", "turn", "river")


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    stake = int(opts.get("stake", 30))
    st = base.fresh("holdem", seed, ["you", str(opts.get("host", "them"))], stake=stake, stacks=[stake, stake], pot=0, blind=int(opts.get("blind", 1)), hands=int(opts.get("hands", 6)),
                    hand_no=0, deck=[], hole=[[], []], board=[], phase="deal", street=0, dealer=1, chips=str(opts.get("chips", "pebbles")), bet={}, outcome="")
    base.say(st, f"{stake} {st['chips']} each, {st['hands']} hands, blinds {st['blind']} and {2 * st['blind']}.")
    return st


def _deal(state: dict[str, Any]) -> None:
    state["hand_no"] += 1
    state["dealer"] = 1 - state["dealer"]
    small, big = state["dealer"], 1 - state["dealer"]  # heads up: the dealer posts the small blind and acts first before the flop
    for s, n in ((small, state["blind"]), (big, 2 * state["blind"])):
        n = min(n, state["stacks"][s])
        state["stacks"][s] -= n
        state["pot"] += n
    state["deck"] = cards.deck(base.rng(state, f"shuffle:{state['hand_no']}"))
    state["hole"] = [[state["deck"].pop(), state["deck"].pop()], [state["deck"].pop(), state["deck"].pop()]]
    state["board"] = []
    state["street"] = 0
    state["outcome"] = ""
    state["phase"] = "bet"
    betting.start(state, small, 2 * state["blind"])
    state["bet"]["to_call"][small] = state["blind"]  # the small blind owes the difference
    state["bet"]["put"] = [0, 0]
    base.say(state, f"Hand {state['hand_no']}. {'You' if state['dealer'] == 0 else state['seats'][1]} deal{'' if state['dealer'] == 0 else 's'}.")


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"]:
        return []
    if state["phase"] in ("deal", "settled"):
        return [{"id": "deal", "text": "Deal" if not state["hand_no"] else "Deal the next hand"}] if seat == 0 else []
    return betting.options(state, seat)


def _strength(state: dict[str, Any], seat: int) -> tuple[int, int]:
    """(category of the best hand so far, the high card) for a bot's decision."""
    known = state["hole"][seat] + state["board"]
    if len(known) >= 5:
        r = cards.best_of(known)
        return int(r[0]), int(r[1]) if len(r) > 1 else 0
    a, b = state["hole"][seat]
    pair = a[0] == b[0]
    high = max(cards.rank_value(a), cards.rank_value(b))
    return (1 if pair else 0), high


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    opts = betting.options(state, seat)
    ids = [o["id"] for o in opts]
    cat, high = _strength(state, seat)
    strong = cat >= 2 or (cat == 1 and high >= 11)
    medium = cat >= 1 or high >= 12
    if strong and "raise" in ids and state["bet"]["raises"] < 2:
        return {"id": "raise"}
    if strong and "bet" in ids:
        return {"id": "bet"}
    if "check" in ids:
        return {"id": "check"}
    if "call" in ids and (medium or state["bet"]["to_call"][seat] <= 2 * state["blind"] or rng.random() < 0.25):
        return {"id": "call"}
    return {"id": "fold"} if "fold" in ids else {"id": ids[0]}


def _after_hand(state: dict[str, Any]) -> None:
    state["phase"] = "settled"
    if state["hand_no"] >= state["hands"] or min(state["stacks"]) <= 0:
        p, s = state["stacks"][0], state["stake"]
        base.finish(state, "win" if p > s else ("draw" if p == s else "lose"), f"{p} {state['chips']} from {s}.")


def _showdown(state: dict[str, Any]) -> None:
    r0 = cards.best_of(state["hole"][0] + state["board"])
    r1 = cards.best_of(state["hole"][1] + state["board"])
    winner: int | None = 0 if r0 > r1 else (1 if r1 > r0 else None)
    pot = state["pot"]
    betting.settle(state, winner)
    who = {0: "you take", 1: f"{state['seats'][1]} takes", None: "the pot is split"}[winner]
    state["outcome"] = f"{cards.category_name(r0)} against {cards.category_name(r1)}: {who} {pot}."
    base.say(state, state["outcome"])
    _after_hand(state)


def _next_street(state: dict[str, Any]) -> None:
    b = state["bet"]
    if b["folded"] is not None:
        w = 1 - int(b["folded"])
        pot = state["pot"]
        betting.settle(state, w)
        state["outcome"] = f"{'You fold' if b['folded'] == 0 else state['seats'][1] + ' folds'}: {'you take' if w == 0 else state['seats'][1] + ' takes'} {pot}."
        base.say(state, state["outcome"])
        _after_hand(state)
        return
    if state["street"] == 3:
        _showdown(state)
        return
    state["street"] += 1
    n = 3 if state["street"] == 1 else 1
    state["board"] += [state["deck"].pop() for _ in range(n)]
    base.say(state, f"The {STREETS[state['street']]}: {', '.join(cards.card_text(c) for c in state['board'][-n:])}.")
    if min(state["stacks"]) == 0:  # somebody is all in: the rest of the board runs out
        while state["street"] < 3:
            state["street"] += 1
            state["board"].append(state["deck"].pop())
        _showdown(state)
        return
    betting.start(state, 1 - state["dealer"], 2 * state["blind"] if state["street"] < 2 else 4 * state["blind"])


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    state["moves"] += 1
    if a["id"] == "deal":
        _deal(state)
        return state
    betting.apply(state, seat, a["id"])
    base.say(state, f"{'You' if seat == 0 else state['seats'][1]} {a['id']}{'s' if seat else ''}.")
    if state["bet"]["done"]:
        _next_street(state)
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    show = state["phase"] == "settled" and "against" in state["outcome"]
    areas = [base.area("score", "The pot", rows=[{"name": f"your {state['chips']}", "value": state["stacks"][0]}, {"name": f"{state['seats'][1]}'s", "value": state["stacks"][1]},
                                                  {"name": "pot", "value": state["pot"]}, {"name": "hand", "value": f"{state['hand_no']} of {state['hands']}"}])]
    if state["hole"][1]:
        areas.append(base.area("cards", state["seats"][1], size=52, items=[cards.card_item(c, down=not show) for c in state["hole"][1]]))
    if state["board"] or state["hand_no"]:
        areas.append(base.area("cards", "The road (" + STREETS[state["street"]] + ")", size=52, items=[cards.card_item(c) for c in state["board"]]))
    if state["hole"][0]:
        known = state["hole"][0] + state["board"]
        label = "Your cards" + (f" ({cards.category_name(cards.best_of(known))})" if len(known) >= 5 else "")
        areas.append(base.area("cards", label, size=52, items=[cards.card_item(c) for c in state["hole"][0]]))
    if state["over"]:
        msg = {"win": "Light loads for you.", "draw": "Nobody carries anything.", "lose": "Granite for a week."}[state["result"]]
    elif state["phase"] == "deal":
        msg = "Blinds in. Deal?"
    elif state["phase"] == "bet":
        msg = "Your bet." if state["bet"].get("current") == 0 else f"{state['seats'][1]} is thinking."
    else:
        msg = state["outcome"]
    return base.head(state, "The carriers' pot", msg, areas, actions(state, seat))

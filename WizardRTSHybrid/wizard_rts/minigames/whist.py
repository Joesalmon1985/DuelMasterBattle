"""Knocked out: Knock-out Whist with the contestants (three at the fire). Seven cards each, then six, then five, down to one; trumps are turned for
the first hand, after that the player who took most tricks chooses. Take no trick in a hand and you are out, except once: the first time, a dog's life,
one card in the next hand to play on any trick you choose. Last one standing. If the apprentice is knocked out the game is over for them."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base, cards, tricks


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    n = int(opts.get("players", 3))
    names = ["you", str(opts.get("host", "them"))] + [str(x) for x in opts.get("partners", [])]
    names = (names + [f"contestant {i}" for i in range(2, n)])[:n]
    st = base.fresh("whist", seed, names, players=n, alive=[True] * n, dog=[False] * n, dog_used=[False] * n, hands=[[] for _ in range(n)], size=int(opts.get("start", 7)),
                    trump="", chooser=None, phase="deal", trick=[], leader=0, current=0, taken=[0] * n, hand_no=0)
    _deal(st)
    return st


def _alive(state: dict[str, Any]) -> list[int]:
    return [i for i in range(state["players"]) if state["alive"][i]]


def _deal(state: dict[str, Any]) -> None:
    state["hand_no"] += 1
    rng = base.rng(state, f"deal:{state['hand_no']}")
    hands, rest = tricks.deal(rng, state["players"], state["size"])
    for i in range(state["players"]):
        if not state["alive"][i]:
            hands[i] = []
        elif state["dog"][i]:
            hands[i] = hands[i][:1]
    state["hands"] = hands
    state["taken"] = [0] * state["players"]
    state["trick"] = []
    alive = _alive(state)
    state["leader"] = alive[(state["hand_no"] - 1) % len(alive)]
    state["current"] = state["leader"]
    if state["chooser"] is None:
        state["trump"] = rest[0][1] if rest else "s"
        state["phase"] = "play"
        base.say(state, f"Hand of {state['size']}: {tricks.SUIT_NAMES[state['trump']]} are trumps.")
    else:
        state["phase"] = "choose"
        state["current"] = state["chooser"]


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != state["current"] or not state["alive"][seat]:
        return []
    if state["phase"] == "choose":
        return [{"id": f"trumps:{s}", "suit": s, "text": f"{tricks.SUIT_NAMES[s].capitalize()} are trumps"} for s in "shdc"]
    hand = state["hands"][seat]
    if state["dog"][seat]:
        out = [{"id": f"play:{c}", "card": c, "text": "Play " + cards.card_text(c)} for c in hand]
        if hand and state["size"] > 1 and len(state["trick"]) < len(_alive(state)) and _tricks_left(state) > 1:
            out.append({"id": "wait", "text": "Hold the card for a later trick"})
        return out
    return [{"id": f"play:{c}", "card": c, "text": "Play " + cards.card_text(c)} for c in tricks.legal(hand, state["trick"], state["trump"])]


def _tricks_left(state: dict[str, Any]) -> int:
    return max(len(h) for i, h in enumerate(state["hands"]) if state["alive"][i] and not state["dog"][i]) if any(state["alive"][i] and not state["dog"][i] for i in range(state["players"])) else 0


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    if state["phase"] == "choose":
        s = tricks.bot_trumps(state["hands"][seat])
        return {"id": f"trumps:{s}", "suit": s}
    acts = actions(state, seat)
    if state["dog"][seat]:
        card = state["hands"][seat][0]
        wins = state["trick"] and tricks.would_win(card, state["trick"], state["trump"])
        if (wins or _tricks_left(state) <= 1 or not any(a["id"] == "wait" for a in acts)) and any(a["id"] == f"play:{card}" for a in acts):
            return {"id": f"play:{card}", "card": card}
        return {"id": "wait"}
    c = tricks.bot_play(state["hands"][seat], state["trick"], state["trump"], True)
    return {"id": f"play:{c}", "card": c}


def _next_seat(state: dict[str, Any], seat: int) -> int:
    n = state["players"]
    s = (seat + 1) % n
    while not state["alive"][s]:
        s = (s + 1) % n
    return s


def _in_trick(state: dict[str, Any], seat: int) -> bool:
    return any(int(sc[0]) == seat for sc in state["trick"])


def _advance_after_play(state: dict[str, Any]) -> None:
    """Everyone alive who still holds a card to play on this trick has played, or waited (a dog): the trick is taken."""
    alive = _alive(state)
    players_in = [i for i in alive if (state["hands"][i] or _in_trick(state, i))]
    pending = [i for i in players_in if not _in_trick(state, i) and not (state["dog"][i] and state.get("waited", {}).get(str(i)))]
    if pending:
        state["current"] = _next_in(state, pending)
        return
    if not state["trick"]:
        _hand_over(state)
        return
    w = tricks.winner(state["trick"], state["trump"])
    state["taken"][w] += 1
    base.say(state, f"{_name(state, w)} take{'' if w == 0 else 's'} the trick.")
    state["trick"] = []
    state["waited"] = {}
    state["leader"] = w
    state["current"] = w
    if not any(state["hands"][i] for i in alive):
        _hand_over(state)
    elif not state["hands"][w]:
        state["current"] = _next_with_cards(state, w)


def _next_in(state: dict[str, Any], pending: list[int]) -> int:
    s = state["leader"]
    for _ in range(state["players"]):
        if s in pending:
            return s
        s = (s + 1) % state["players"]
    return pending[0]


def _next_with_cards(state: dict[str, Any], seat: int) -> int:
    s = seat
    for _ in range(state["players"]):
        s = _next_seat(state, s)
        if state["hands"][s]:
            return s
    return seat


def _name(state: dict[str, Any], seat: int) -> str:
    return "You" if seat == 0 else state["seats"][seat]


def _hand_over(state: dict[str, Any]) -> None:
    alive = _alive(state)
    out = [i for i in alive if state["taken"][i] == 0]
    for i in out:
        if not state["dog_used"][i]:
            state["dog_used"][i] = True
            state["dog"][i] = True
            base.say(state, f"{_name(state, i)} took nothing: a dog's life, one card next hand.")
        else:
            state["alive"][i] = False
            state["dog"][i] = False
            base.say(state, f"{_name(state, i)} {'are' if i == 0 else 'is'} knocked out.")
    for i in alive:
        if state["taken"][i] > 0 and state["dog"][i]:
            state["dog"][i] = False  # the dog took a trick: back in with a full hand
    alive = _alive(state)
    if not state["alive"][0]:
        base.finish(state, "lose", "Knocked out.")
        return
    if len(alive) == 1:
        base.finish(state, "win", "Last standing.")
        return
    state["chooser"] = max(alive, key=lambda i: (state["taken"][i], -i))
    state["size"] -= 1
    if state["size"] <= 0:
        best = max(alive, key=lambda i: (state["taken"][i], -i))
        base.finish(state, "win" if best == 0 else "lose", "The last hand decides it.")
        return
    _deal(state)


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    state["moves"] += 1
    if a["id"].startswith("trumps:"):
        state["trump"] = a["suit"]
        state["phase"] = "play"
        state["current"] = state["leader"]
        base.say(state, f"{_name(state, seat)} call{'' if seat == 0 else 's'} {tricks.SUIT_NAMES[state['trump']]}. Hand of {state['size']}.")
        return state
    if a["id"] == "wait":
        state.setdefault("waited", {})[str(seat)] = True
        _advance_after_play(state)
        return state
    c = a["card"]
    state["hands"][seat].remove(c)
    state["trick"].append([seat, c])
    _advance_after_play(state)
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    areas = [base.area("score", f"Hand {state['hand_no']}: {state['size']} cards, trumps {tricks.SUIT_NAMES.get(state['trump'], '?')}",
                       rows=[{"name": _name(state, i) + (" (dog)" if state["dog"][i] else "") + ("" if state["alive"][i] else " (out)"), "value": f"{state['taken'][i]} tricks"} for i in range(state["players"])])]
    areas.append(base.area("cards", "On the table", size=52, items=[cards.card_item(c, label=_name(state, int(s))) for s, c in state["trick"]]))
    mine = state["current"] == 0 and state["phase"] == "play" and not state["over"]
    legal = tricks.legal(state["hands"][0], state["trick"], state["trump"]) if mine else []
    items = []
    for c in state["hands"][0]:
        item = cards.card_item(c)
        if mine and (c in legal or state["dog"][0]):
            item["action"] = {"id": f"play:{c}", "card": c}
        else:
            item["disabled"] = True
        items.append(item)
    areas.append(base.area("cards", "Your hand (tap to play)" if mine else "Your hand", size=52, items=items))
    if state["over"]:
        msg = "Last standing." if state["result"] == "win" else "Knocked out."
    elif state["phase"] == "choose":
        msg = "Choose trumps." if state["current"] == 0 else f"{_name(state, state['current'])} chooses trumps."
    elif mine:
        msg = "Your card." if state["trick"] else "Lead."
    else:
        msg = f"{_name(state, state['current'])} is playing."
    acts = [a for a in actions(state, seat) if not a["id"].startswith("play:")]  # the cards are tapped; trumps and the dog's wait are buttons
    return base.head(state, "Knocked out", msg, areas, acts + [dict(a, hidden=True) for a in actions(state, seat) if a["id"].startswith("play:")])

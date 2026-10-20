"""Twenty-one feet: Blackjack with the sawyer dealing. Every card is a length of plank; cut to twenty-one and not an inch over. The dealer stands on
seventeen, soft or hard; a natural pays three to two (the base bet is two pebbles, so it pays three); double on the first two cards; one split of a
pair. A fixed number of hands, then the pebbles decide: more than you came with wins."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base, cards

BET = 2


def total(hand: list[str]) -> tuple[int, bool]:
    """(best total, soft) with aces as eleven while that does not bust."""
    t = 0
    aces = 0
    for c in hand:
        r = c[0]
        if r == "A":
            aces += 1
            t += 11
        elif r in "TJQK":
            t += 10
        else:
            t += int(r)
    soft = aces > 0
    while t > 21 and aces:
        t -= 10
        aces -= 1
    return t, soft and aces > 0


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    stake = int(opts.get("stake", 10))
    st = base.fresh("blackjack", seed, ["you", str(opts.get("host", "them"))], stake=stake, pebbles=stake, hands=int(opts.get("hands", 5)), hand_no=0, deck=[],
                    dealer=[], player=[], bets=[], active=0, phase="deal", chips=str(opts.get("chips", "pebbles")), card=str(opts.get("card", "plank")), outcome="")
    base.say(st, f"{stake} {st['chips']}, {BET} a hand, {st['hands']} hands.")
    return st


def _draw(state: dict[str, Any]) -> str:
    if len(state["deck"]) < 15:
        state["deck"] = cards.deck(base.rng(state, f"shuffle:{state['hand_no']}"))
    return state["deck"].pop()


def _deal(state: dict[str, Any]) -> None:
    state["hand_no"] += 1
    state["pebbles"] -= BET
    state["player"] = [[_draw(state), _draw(state)]]
    state["dealer"] = [_draw(state), _draw(state)]
    state["bets"] = [BET]
    state["active"] = 0
    state["phase"] = "play"
    state["outcome"] = ""
    base.say(state, f"Hand {state['hand_no']}: you show {total(state['player'][0])[0]}, the sawyer shows {cards.card_text(state['dealer'][0])}.")
    if total(state["player"][0])[0] == 21:
        _settle(state)


def _settle(state: dict[str, Any]) -> None:
    """Every player hand stands or is bust: the dealer draws to seventeen, each hand is paid."""
    dealer_total = total(state["dealer"])[0]
    any_live = any(total(h)[0] <= 21 for h in state["player"])
    while any_live and total(state["dealer"])[0] < 17:
        state["dealer"].append(_draw(state))
    dealer_total = total(state["dealer"])[0]
    words = []
    for hand, bet in zip(state["player"], state["bets"]):
        t = total(hand)[0]
        natural = len(hand) == 2 and t == 21 and len(state["player"]) == 1
        dealer_natural = len(state["dealer"]) == 2 and dealer_total == 21
        if t > 21:
            words.append("over the mark")
        elif natural and not dealer_natural:
            state["pebbles"] += bet + bet + bet // 2
            words.append("twenty-one on the deal, three to two")
        elif dealer_total > 21 or t > dealer_total:
            state["pebbles"] += 2 * bet
            words.append(f"{t} beats {dealer_total}")
        elif t == dealer_total:
            state["pebbles"] += bet
            words.append(f"{t} each, a push")
        else:
            words.append(f"{t} under {dealer_total}")
    state["outcome"] = "; ".join(words)
    state["phase"] = "settled"
    base.say(state, f"The sawyer has {dealer_total}: {state['outcome']}.")
    if state["hand_no"] >= state["hands"] or state["pebbles"] < BET:
        p, s = state["pebbles"], state["stake"]
        base.finish(state, "win" if p > s else ("draw" if p == s else "lose"), f"{p} {state['chips']} from {s}.")


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != 0:
        return []
    if state["phase"] in ("deal", "settled"):
        return [{"id": "deal", "text": "Deal the next hand" if state["hand_no"] else "Deal"}]
    hand = state["player"][state["active"]]
    out = [{"id": "hit", "text": "Another plank (hit)"}, {"id": "stand", "text": "Stand"}]
    if len(hand) == 2 and state["pebbles"] >= BET:
        out.append({"id": "double", "text": "Double the bet, one card"})
        if hand[0][0] == hand[1][0] and len(state["player"]) == 1:
            out.append({"id": "split", "text": "Split the pair"})
    return out


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    return {"id": "deal"}


def _advance(state: dict[str, Any]) -> None:
    """The active hand is done (stood, bust, or doubled): the next hand, or the settlement."""
    if state["active"] + 1 < len(state["player"]):
        state["active"] += 1
        return
    _settle(state)


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    state["moves"] += 1
    aid = a["id"]
    if aid == "deal":
        _deal(state)
        return state
    hand = state["player"][state["active"]]
    if aid == "hit":
        hand.append(_draw(state))
        t = total(hand)[0]
        base.say(state, f"{cards.card_text(hand[-1])}: {t}.")
        if t >= 21:
            _advance(state)
    elif aid == "stand":
        base.say(state, f"You stand on {total(hand)[0]}.")
        _advance(state)
    elif aid == "double":
        state["pebbles"] -= BET
        state["bets"][state["active"]] += BET
        hand.append(_draw(state))
        base.say(state, f"Doubled: {cards.card_text(hand[-1])}, {total(hand)[0]}.")
        _advance(state)
    elif aid == "split":
        state["pebbles"] -= BET
        state["player"] = [[hand[0], _draw(state)], [hand[1], _draw(state)]]
        state["bets"] = [BET, BET]
        state["active"] = 0
        base.say(state, "Split: two hands.")
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    settled = state["phase"] != "play"
    dealer_items = []
    for i, c in enumerate(state["dealer"]):
        dealer_items.append(cards.card_item(c, down=(i == 1 and not settled)))
    areas = [base.area("score", "The sawyer's yard", rows=[{"name": state["chips"], "value": state["pebbles"]}, {"name": "hand", "value": f"{state['hand_no']} of {state['hands']}"}])]
    if state["dealer"]:
        dt = total(state["dealer"])[0] if settled else total(state["dealer"][:1])[0]
        areas.append(base.area("cards", f"The sawyer ({dt}{'+' if not settled else ''})", size=56, items=dealer_items))
    for i, hand in enumerate(state["player"]):
        t, soft = total(hand)
        label = f"You ({t}{' soft' if soft else ''})" if len(state["player"]) == 1 else f"Hand {i + 1} ({t})" + (" - playing" if i == state["active"] and not settled else "")
        areas.append(base.area("cards", label, size=56, items=[cards.card_item(c) for c in hand]))
    if state["phase"] == "deal":
        msg = "Two pebbles a hand. Deal?"
    elif state["phase"] == "play":
        msg = "Another plank, or stand?"
    elif state["over"]:
        msg = {"win": "More than you came with.", "draw": "Length for length.", "lose": "The sawyer keeps them."}[state["result"]]
    else:
        msg = state["outcome"].capitalize() + "."
    return base.head(state, "Twenty-one feet", msg, areas, actions(state, seat))

"""The Ward you cannot see: Hanabi with the mentor and Mira, three players. Five colours (the ladder's: Flame, Frost, Vine, Light, Stone), ones to
fives (three ones, two of twos to fours, one five), five cards each held facing out. A turn: play a card, discard one for a clue token (eight at
most), or spend a token to tell another player every card of one colour or one number they hold. A wrong play is a fracture; three fractures and
the Ward breaks. The deck's last card gives everyone one more turn. Eighteen or more built wins; the Ward breaking loses; anything else is a draw.

The others play a plain Hanabi: a card they know is playable, else a clue that marks a playable card, else the oldest unclued card discarded."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base

NUMBERS = [1, 1, 1, 2, 2, 3, 3, 4, 4, 5]
WIN_AT = 18


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    colours = list(opts.get("colours", ["Flame", "Frost", "Vine", "Light", "Stone"]))[:5]
    names = ["you", str(opts.get("host", "them"))] + [str(x) for x in opts.get("partners", [])]
    n = int(opts.get("players", 3))
    names = (names + [f"player {i}" for i in range(2, n)])[:n]
    st = base.fresh("hanabi", seed, names, players=n, colours=colours, deck=[], hands=[[] for _ in range(n)], known=[[] for _ in range(n)], fireworks=[0] * len(colours),
                    clues=8, fuses=3, discards=[], turn=0, last_round=None, fuse=str(opts.get("fuse", "fracture")))
    rng = base.rng(st, "deck")
    deck = [[c, v] for c in range(len(colours)) for v in NUMBERS]
    rng.shuffle(deck)
    st["deck"] = deck
    per = 5 if n <= 3 else 4
    for i in range(n):
        for _ in range(per):
            _draw(st, i)
    base.say(st, "Your cards face away from you. Tell, play, or discard.")
    return st


def _draw(state: dict[str, Any], seat: int) -> None:
    if not state["deck"]:
        return
    card = state["deck"].pop()
    state["hands"][seat].append(card)
    state["known"][seat].append([None, None])
    if not state["deck"]:
        state["last_round"] = state["players"]  # everyone gets one more turn, the drawer included


def _playable(state: dict[str, Any], card: list[int]) -> bool:
    return state["fireworks"][card[0]] == card[1] - 1


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != state["turn"]:
        return []
    out = []
    for i, _c in enumerate(state["hands"][seat]):
        out.append({"id": f"play:{i}", "slot": i, "text": f"Play card {i + 1}"})
        if state["clues"] < 8:
            out.append({"id": f"discard:{i}", "slot": i, "text": f"Discard card {i + 1}", "hidden": True})
    if state["clues"] > 0:
        for other in range(state["players"]):
            if other == seat:
                continue
            hand = state["hands"][other]
            for c in sorted({card[0] for card in hand}):
                out.append({"id": f"clue:{other}:colour:{c}", "who": other, "colour": c, "text": f"Tell {state['seats'][other]} their {state['colours'][c]}s"})
            for v in sorted({card[1] for card in hand}):
                out.append({"id": f"clue:{other}:number:{v}", "who": other, "number": v, "text": f"Tell {state['seats'][other]} their {v}s"})
    return out


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    hand, known = state["hands"][seat], state["known"][seat]
    for i, card in enumerate(hand):  # a card known well enough to be playable
        kc, kv = known[i]
        if kv is not None and (kc is not None and _playable(state, [kc, kv]) or (kc is None and all(state["fireworks"][c] == kv - 1 for c in range(len(state["colours"]))))):
            return {"id": f"play:{i}", "slot": i}
        if kc is not None and kv is None and state["fireworks"][kc] == 0 and sum(1 for cc, _vv in state["discards"] if cc == kc) == 0 and rng.random() < 0.0:
            return {"id": f"play:{i}", "slot": i}
    if state["clues"] > 0:  # a clue that marks a playable card nobody has been told about
        for other in range(state["players"]):
            if other == seat:
                continue
            for i, card in enumerate(state["hands"][other]):
                if _playable(state, card):
                    if state["known"][other][i][1] is None:
                        return {"id": f"clue:{other}:number:{card[1]}", "who": other, "number": card[1]}
                    if state["known"][other][i][0] is None:
                        return {"id": f"clue:{other}:colour:{card[0]}", "who": other, "colour": card[0]}
    if state["clues"] < 8:  # discard the oldest card nobody has told us about
        for i, (kc, kv) in enumerate(known):
            if kc is None and kv is None:
                return {"id": f"discard:{i}", "slot": i}
        return {"id": "discard:0", "slot": 0}
    acts = actions(state, seat)
    clue = next((a for a in acts if a["id"].startswith("clue:")), None)
    if clue:
        return {k: v for k, v in clue.items() if k != "text"}
    return {"id": "play:0", "slot": 0}


def _end_check(state: dict[str, Any]) -> None:
    score = sum(state["fireworks"])
    if state["fuses"] <= 0:
        base.finish(state, "lose", f"Three {state['fuse']}s. The Ward breaks at {score}.")
        return
    if all(f == 5 for f in state["fireworks"]):
        base.finish(state, "win", "Every colour to five.")
        return
    if state["last_round"] is not None and state["last_round"] <= 0:
        base.finish(state, "win" if score >= WIN_AT else "draw", f"The deck is done: {score} of 25 built.")


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    state["moves"] += 1
    aid = a["id"]
    who = "You" if seat == 0 else state["seats"][seat]
    counting = state["last_round"] is not None  # the turn that draws the last card is not one of the last turns: everyone gets one more after it
    if aid.startswith("play:") or aid.startswith("discard:"):
        i = int(a["slot"])
        card = state["hands"][seat].pop(i)
        state["known"][seat].pop(i)
        name = f"{state['colours'][card[0]]} {card[1]}"
        if aid.startswith("play:"):
            if _playable(state, card):
                state["fireworks"][card[0]] = card[1]
                if card[1] == 5 and state["clues"] < 8:
                    state["clues"] += 1
                base.say(state, f"{who} play{'' if seat == 0 else 's'} {name}: it fits.")
            else:
                state["fuses"] -= 1
                state["discards"].append(card)
                base.say(state, f"{who} play{'' if seat == 0 else 's'} {name}: a {state['fuse']} ({3 - state['fuses']} of 3).")
        else:
            state["discards"].append(card)
            state["clues"] += 1
            base.say(state, f"{who} discard{'' if seat == 0 else 's'} {name}.")
        _draw(state, seat)
    else:
        other = int(a["who"])
        state["clues"] -= 1
        hits = []
        for i, card in enumerate(state["hands"][other]):
            if "colour" in a and card[0] == int(a["colour"]):
                state["known"][other][i][0] = card[0]
                hits.append(i + 1)
            if "number" in a and card[1] == int(a["number"]):
                state["known"][other][i][1] = card[1]
                hits.append(i + 1)
        what = state["colours"][int(a["colour"])] if "colour" in a else str(a["number"])
        base.say(state, f"{who} tell{'' if seat == 0 else 's'} {state['seats'][other]}: {what} at {', '.join(map(str, hits))}.")
    if counting:
        state["last_round"] -= 1
    _end_check(state)
    if not state["over"]:
        state["turn"] = (seat + 1) % state["players"]
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    mine = state["turn"] == 0 and not state["over"]
    rows = [{"name": c, "value": state["fireworks"][i]} for i, c in enumerate(state["colours"])]
    rows += [{"name": "clue tokens", "value": state["clues"]}, {"name": state["fuse"] + "s left", "value": state["fuses"]}, {"name": "deck", "value": len(state["deck"])}]
    areas = [base.area("score", "The Ward so far", rows=rows)]
    items = []
    for i, (kc, kv) in enumerate(state["known"][0]):
        item = {"id": f"h{i}", "colour": kc if kc is not None else -1, "number": kv if kv is not None else 0, "down": kc is None and kv is None,
                "label": (state["colours"][kc] if kc is not None else "?") + " " + (str(kv) if kv is not None else "?")}
        if mine:
            item["action"] = {"id": f"play:{i}", "slot": i}
        items.append(item)
    areas.append(base.area("cards", "Your cards, facing out (what you have been told; tap to play)" if mine else "Your cards, facing out", size=52, items=items))
    for other in range(1, state["players"]):
        o_items = [{"id": f"o{other}_{i}", "colour": card[0], "number": card[1], "label": ("" if state["known"][other][i][0] is None else "c") + ("" if state["known"][other][i][1] is None else "n")}
                   for i, card in enumerate(state["hands"][other])]
        areas.append(base.area("cards", state["seats"][other], size=52, items=o_items))
    if state["discards"]:
        areas.append(base.area("tiles", "Discarded", size=36, items=[{"id": f"d{i}", "text": str(v), "colour": c} for i, (c, v) in enumerate(state["discards"][-12:])]))
    if state["over"]:
        msg = {"win": "The whole Ward.", "lose": "The Ward breaks.", "draw": "Part of the Ward."}[state["result"]]
    elif mine:
        msg = "Play, discard, or tell someone."
    else:
        msg = f"{state['seats'][state['turn']]} is thinking."
    acts = actions(state, seat)
    for a in acts:
        if a["id"].startswith("play:"):
            a["hidden"] = True
    if mine and state["clues"] < 8:
        for a in acts:
            if a["id"].startswith("discard:"):
                a["hidden"] = False
    return base.head(state, "The Ward you cannot see", msg, areas, acts)

"""The tally board: Rummikub against the warehouse keeper, no jokers. Tallies 1 to 13 in four colours, two of each; fourteen on each rack. A turn
lays runs (three or more of one colour in sequence) or sets (three or four of one number in different colours) from the rack, or adds a tally to a
meld on the board; the first melds must come to thirty from the rack alone ("opening the ledger"). A turn that lays nothing draws a tally; a turn
that opens short of thirty takes its tallies back and draws. First empty rack wins; an empty pool with nobody able to lay ends it on the lower rack.

The human selects tallies on the rack (`select`), then lays the selection as a new meld (`lay`) or adds the one selected tally to a meld (`add`),
and ends the turn (`end`). The keeper lays every meld she can find in her rack (largest first) and adds what fits."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base

COLOURS = 4
NUMBERS = 13
OPENING = 30


def tile_id(colour: int, number: int, copy: int) -> str:
    return f"{colour}:{number}:{copy}"


def parse(tid: str) -> tuple[int, int]:
    c, n, _k = tid.split(":")
    return int(c), int(n)


def is_meld(tiles: list[str]) -> bool:
    if len(tiles) < 3:
        return False
    parsed = [parse(t) for t in tiles]
    colours = {c for c, _n in parsed}
    numbers = sorted(n for _c, n in parsed)
    if len(colours) == 1:  # a run
        return len(set(numbers)) == len(numbers) and numbers[-1] - numbers[0] == len(numbers) - 1
    return len(set(numbers)) == 1 and len(colours) == len(parsed) and len(parsed) <= COLOURS  # a set


def points(tiles: list[str]) -> int:
    return sum(parse(t)[1] for t in tiles)


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    st = base.fresh("rummikub", seed, ["you", str(opts.get("host", "them"))], pool=[], racks=[[], []], board=[], opened=[False, False], selected=[], turn=0,
                    laid_this_turn=[], laid_points=0, drew=False, colours=list(opts.get("colour_names", ["red", "blue", "yellow", "black"])), tile=str(opts.get("tile", "tally")),
                    passes=0)
    rng = base.rng(st, "deal")
    pool = [tile_id(c, n, k) for c in range(COLOURS) for n in range(1, NUMBERS + 1) for k in range(2)]
    rng.shuffle(pool)
    st["racks"] = [sorted(pool[:14], key=parse), sorted(pool[14:28], key=parse)]
    st["pool"] = pool[28:]
    base.say(st, f"Fourteen {st['tile']}s each. Open the ledger with thirty.")
    return st


def _melds_in(rack: list[str]) -> list[list[str]]:
    """Every maximal run and every set in a rack (one copy of a number per meld)."""
    out: list[list[str]] = []
    by_colour: dict[int, dict[int, str]] = {}
    by_number: dict[int, dict[int, str]] = {}
    for t in rack:
        c, n = parse(t)
        by_colour.setdefault(c, {}).setdefault(n, t)
        by_number.setdefault(n, {}).setdefault(c, t)
    for c, nums in by_colour.items():
        run: list[str] = []
        for n in range(1, NUMBERS + 2):
            if n in nums:
                run.append(nums[n])
            else:
                if len(run) >= 3:
                    out.append(list(run))
                run = []
    for n, cols in by_number.items():
        if len(cols) >= 3:
            out.append([cols[c] for c in sorted(cols)])
    return out


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != state["turn"]:
        return []
    out = []
    rack = state["racks"][seat]
    sel = state["selected"]
    for t in rack:
        c, n = parse(t)
        out.append({"id": f"select:{t}", "tile": t, "text": f"{'Unselect' if t in sel else 'Select'} {state['colours'][c]} {n}", "hidden": True})
    if is_meld(sel):
        out.append({"id": "lay", "text": f"Lay the {len(sel)} selected ({points(sel)} points)"})
    if len(sel) == 1 and (state["opened"][seat] or state["laid_points"] >= OPENING):
        for i, meld in enumerate(state["board"]):
            if is_meld(meld + sel):
                out.append({"id": f"add:{i}", "meld": i, "text": f"Add it to meld {i + 1}", "hidden": True})
    if state["laid_this_turn"]:
        out.append({"id": "end", "text": "End the turn"})
    else:
        out.append({"id": "end", "text": "Draw a tally and end the turn"})
    return out


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    """The keeper: lay every meld in the rack (largest first; the first turn only if they come to thirty together), then add single tallies that fit."""
    rack = state["racks"][seat]
    sel = state["selected"]
    opened = state["opened"][seat] or state["laid_points"] >= OPENING
    if sel:
        if is_meld(sel):
            return {"id": "lay"}
        if len(sel) == 1 and opened:
            for i, meld in enumerate(state["board"]):
                if is_meld(meld + sel):
                    return {"id": f"add:{i}", "meld": i}
        return {"id": f"select:{sel[0]}", "tile": sel[0]}  # a selection that leads nowhere is dropped
    melds = sorted(_melds_in(rack), key=lambda m: (-len(m), -points(m)))
    total = sum(points(m) for m in melds)
    for m in melds:
        if opened or state["laid_points"] + points(m) >= OPENING or total >= OPENING:
            return {"id": f"select:{m[0]}", "tile": m[0], "_meld": m}
    if opened:
        for t in rack:
            for i, meld in enumerate(state["board"]):
                if is_meld(meld + [t]):
                    return {"id": f"select:{t}", "tile": t}
    return {"id": "end"}


def _draw(state: dict[str, Any], seat: int) -> bool:
    if not state["pool"]:
        return False
    state["racks"][seat].append(state["pool"].pop())
    state["racks"][seat].sort(key=parse)
    return True


def _end_turn(state: dict[str, Any], seat: int) -> None:
    rack = state["racks"][seat]
    if state["laid_this_turn"] and not state["opened"][seat]:
        if state["laid_points"] >= OPENING:
            state["opened"][seat] = True
        else:  # short of thirty: the tallies come back
            for meld in state["laid_this_turn"]:
                if meld in state["board"]:
                    state["board"].remove(meld)
                rack.extend(meld)
            rack.sort(key=parse)
            base.say(state, f"Short of thirty: the {state['tile']}s come back.")
            state["laid_this_turn"] = []
    if not state["laid_this_turn"]:
        if not _draw(state, seat):
            state["passes"] += 1
        else:
            state["passes"] = 0
    else:
        state["passes"] = 0
    if not rack:
        state["ended"] = "empty"
        base.finish(state, "win" if seat == 0 else "lose", "The rack is empty.")
        return
    if state["passes"] >= 2:
        state["ended"] = "dry"
        you, them = points(state["racks"][0]), points(state["racks"][1])
        base.finish(state, "win" if you < them else ("lose" if them < you else "draw"), f"The pool ran dry: {you} on your rack, {them} on theirs.")
        return
    state["selected"] = []
    state["laid_this_turn"] = []
    state["laid_points"] = 0
    state["turn"] = 1 - seat


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    acts = actions(state, seat)
    if seat != 0 and action.get("_meld"):  # the keeper selects a whole meld in one move
        a = base.find(acts, {"id": action["id"]})
        state["moves"] += 1
        state["selected"] = [t for t in action["_meld"] if t in state["racks"][seat]]
        return state
    a = base.find(acts, action)
    state["moves"] += 1
    aid = a["id"]
    rack = state["racks"][seat]
    if aid.startswith("select:"):
        t = a["tile"]
        if t in state["selected"]:
            state["selected"].remove(t)
        else:
            state["selected"].append(t)
        return state
    if aid == "lay":
        meld = sorted(state["selected"], key=parse)
        for t in meld:
            rack.remove(t)
        state["board"].append(meld)
        state["laid_this_turn"].append(meld)
        state["laid_points"] += points(meld)
        state["selected"] = []
        who = "You lay" if seat == 0 else f"{state['seats'][1]} lays"
        base.say(state, f"{who} {len(meld)} {state['tile']}s for {points(meld)}.")
        if not rack:
            _end_turn(state, seat)
        return state
    if aid.startswith("add:"):
        i = int(a["meld"])
        t = state["selected"][0]
        rack.remove(t)
        state["board"][i] = sorted(state["board"][i] + [t], key=parse)
        state["laid_this_turn"].append([t])
        state["selected"] = []
        who = "You add" if seat == 0 else f"{state['seats'][1]} adds"
        base.say(state, f"{who} a {state['tile']} to meld {i + 1}.")
        if not rack:
            _end_turn(state, seat)
        return state
    if aid == "end":
        who = "You" if seat == 0 else state["seats"][1]
        if not state["laid_this_turn"]:
            base.say(state, f"{who} draw{'' if seat == 0 else 's'}.")
        _end_turn(state, seat)
    return state


def _tile_item(state: dict[str, Any], t: str, **extra: Any) -> dict[str, Any]:
    c, n = parse(t)
    return {"id": t, "text": str(n), "colour": c, **extra}


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    mine = state["turn"] == 0 and not state["over"]
    areas = [base.area("score", "The ledger", rows=[{"name": "your rack", "value": len(state["racks"][0])}, {"name": state["seats"][1] + "'s rack", "value": len(state["racks"][1])},
                                                     {"name": "pool", "value": len(state["pool"])}])]
    single = len(state["selected"]) == 1
    can_add = single and (state["opened"][0] or state["laid_points"] >= OPENING)
    for i, meld in enumerate(state["board"]):
        items = [_tile_item(state, t) for t in meld]
        label = f"Meld {i + 1}"
        if mine and can_add and is_meld(meld + state["selected"]):
            items.append({"id": f"add{i}", "text": "+", "colour": -1, "action": {"id": f"add:{i}", "meld": i}})
            label += " (tap + to add the selected tally)"
        areas.append(base.area("tiles", label, size=44, items=items))
    rack_items = []
    for t in state["racks"][0]:
        item = _tile_item(state, t, selected=t in state["selected"])
        if mine:
            item["action"] = {"id": f"select:{t}", "tile": t}
        rack_items.append(item)
    areas.append(base.area("tiles", "Your rack (tap to select)" if mine else "Your rack", size=44, items=rack_items))
    if state["over"]:
        if state.get("ended") == "dry":
            msg = {"win": "The pool ran dry: the lighter rack is yours.", "lose": "The pool ran dry: the lighter rack is theirs.", "draw": "The pool ran dry: even racks."}[state["result"]]
        else:
            msg = "Empty rack." if state["result"] == "win" else "Their rack is empty."
    elif not mine:
        msg = f"{state['seats'][1]} is sorting."
    elif not state["opened"][0] and state["laid_points"] < OPENING:
        msg = f"Select a run or a set and lay it: thirty points from the rack to open the ledger ({state['laid_points']} so far)."
    else:
        msg = "Select tallies to lay a meld, or one to add to the board."
    return base.head(state, "The tally board", msg, areas, actions(state, seat))

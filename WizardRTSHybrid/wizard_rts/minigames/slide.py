"""Clearing the face: oddly shaped blocks (or the farm's fussy sheep) slid one cell at a time out of a small board through the gate of their chalk
colour. Blocks move straight, never over each other; a block leaves when it is pushed against the rim where a gate of its colour covers its edge.
Every board is built backwards (each block enters through its gate and is slid inwards at random), so every board can be cleared; the construction's
length is the par. Clearing the board wins; a move cap well above the par ends a stuck attempt."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import base

SHAPES = {"domino": [(0, 0), (1, 0)], "tromino": [(0, 0), (1, 0), (2, 0)], "elbow": [(0, 0), (1, 0), (0, 1)], "single": [(0, 0)], "square": [(0, 0), (1, 0), (0, 1), (1, 1)]}
DIRS = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}
OPPOSITE = {"n": "s", "s": "n", "e": "w", "w": "e"}


def _cells(block: dict[str, Any]) -> list[tuple[int, int]]:
    return [(int(c[0]), int(c[1])) for c in block["cells"]]


def _occupied(state: dict[str, Any], skip: str = "") -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for b in state["blocks"]:
        if b["id"] != skip:
            out |= set(_cells(b))
    return out


def _gate_cells(state: dict[str, Any], gate: dict[str, Any]) -> list[tuple[int, int]]:
    """The rim cells just outside the board that the gate covers."""
    w, h = state["w"], state["h"]
    side, pos, span = gate["side"], int(gate["pos"]), int(gate.get("span", 2))
    if side == "n":
        return [(pos + i, -1) for i in range(span)]
    if side == "s":
        return [(pos + i, h) for i in range(span)]
    if side == "w":
        return [(-1, pos + i) for i in range(span)]
    return [(w, pos + i) for i in range(span)]


def _exit_cells(state: dict[str, Any], colour: int) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for g in state["gates"]:
        if int(g["colour"]) == colour:
            out |= set(_gate_cells(state, g))
    return out


def _inside(state: dict[str, Any], c: tuple[int, int]) -> bool:
    return 0 <= c[0] < state["w"] and 0 <= c[1] < state["h"]


def legal_move(state: dict[str, Any], block: dict[str, Any], d: str) -> str:
    """'slide' when the block can move one cell that way, 'exit' when the move takes it out through its gate, '' otherwise."""
    dx, dy = DIRS[d]
    taken = _occupied(state, block["id"])
    moved = [(x + dx, y + dy) for x, y in _cells(block)]
    if any(c in taken for c in moved):
        return ""
    if all(_inside(state, c) for c in moved):
        return "slide"
    outside = [c for c in moved if not _inside(state, c)]
    exits = _exit_cells(state, int(block["colour"]))
    if all(c in exits for c in outside):
        return "exit"
    return ""


def moves(state: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for b in state["blocks"]:
        for d in DIRS:
            kind = legal_move(state, b, d)
            if kind:
                out.append({"id": "move", "block": b["id"], "dir": d, "kind": kind})
    return out


def _build(state: dict[str, Any], rng: Any, n_blocks: int) -> None:
    """Backwards construction: a block appears just inside its gate (as if it had just come in) and is slid inwards at random."""
    w, h = state["w"], state["h"]
    sides = ["n", "e", "s", "w"]
    rng.shuffle(sides)
    state["gates"] = []
    for colour in range(3):
        side = sides[colour]
        span = 2
        limit = (w if side in ("n", "s") else h) - span
        state["gates"].append({"side": side, "pos": rng.randint(0, limit), "span": span, "colour": colour})
    shapes = list(SHAPES)
    par = 0
    solution: list[list[str]] = []  # the construction undone: the last block placed leaves first (every cell it needs was free when it came in)
    for i in range(n_blocks):
        colour = i % 3
        gate = state["gates"][colour]
        shape = rng.choice([s for s in shapes if s != "square"] if i % 4 else shapes)
        placed = False
        for _try in range(40):
            cells = SHAPES[shape]
            # the block's footprint pressed against the gate, inside the board
            bw = max(x for x, _y in cells) + 1
            bh = max(y for _x, y in cells) + 1
            if gate["side"] in ("n", "s"):
                ox = int(gate["pos"]) + rng.randint(-(bw - 1), 1)
                oy = 0 if gate["side"] == "n" else h - bh
            else:
                oy = int(gate["pos"]) + rng.randint(-(bh - 1), 1)
                ox = 0 if gate["side"] == "w" else w - bw
            block = {"id": chr(65 + i), "cells": [[ox + x, oy + y] for x, y in cells], "colour": colour, "shape": shape}
            if any(not _inside(state, c) for c in _cells(block)) or set(_cells(block)) & _occupied(state):
                continue
            # it must be able to leave again straight away: the way out is the reverse of coming in
            state["blocks"].append(block)
            if legal_move(state, block, gate["side"]) != "exit":
                state["blocks"].pop()
                continue
            placed = True
            break
        if not placed:
            continue
        par += 1
        # slide it inwards a few times (never back out)
        steps = rng.randint(1, 4)
        inward: list[str] = []
        for _s in range(steps):
            options = [d for d in DIRS if d != gate["side"] and legal_move(state, block, d) == "slide"]
            if not options:
                break
            d = rng.choice(options)
            dx, dy = DIRS[d]
            block["cells"] = [[x + dx, y + dy] for x, y in _cells(block)]
            inward.append(d)
            par += 1
        own = [[block["id"], OPPOSITE[d]] for d in reversed(inward)] + [[block["id"], gate["side"]]]
        solution = own + solution
    state["par"] = par
    state["total"] = len(state["blocks"])
    state["solution"] = solution


def new(seed: int, opts: dict[str, Any]) -> dict[str, Any]:
    size = int(opts.get("size", 6))
    st = base.fresh("slide", seed, ["you", str(opts.get("host", "them"))], w=size, h=size, blocks=[], gates=[], par=0, total=0, out=0, cap=0,
                    block=str(opts.get("block", "block")), gate=str(opts.get("gate", "cart")), board=str(opts.get("board", "the pit")),
                    colour_names=list(opts.get("colour_names", ["the red cart", "the blue cart", "the yellow cart"])))
    rng = base.rng(st, "build")
    _build(st, rng, int(opts.get("blocks", 6)))
    st["cap"] = max(40, st["par"] * 4 + 20)
    base.say(st, f"{st['total']} {st['block']}s in {st['board']}. Each out through the gate of its colour.")
    return st


def actions(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    if state["over"] or seat != 0:
        return []
    names = {"n": "up", "s": "down", "e": "right", "w": "left"}
    out = []
    for m in moves(state):
        out.append({"id": "move", "block": m["block"], "dir": m["dir"], "text": f"{state['block'].capitalize()} {m['block']} {names[m['dir']]}" + (" and out" if m["kind"] == "exit" else "")})
    return out


def bot(state: dict[str, Any], seat: int, rng: Any) -> dict[str, Any]:
    return {"id": "move"}


def act(state: dict[str, Any], seat: int, action: dict[str, Any]) -> dict[str, Any]:
    a = base.find(actions(state, seat), action)
    block = next(b for b in state["blocks"] if b["id"] == a["block"])
    d = a["dir"]
    kind = legal_move(state, block, d)
    state["moves"] += 1
    dx, dy = DIRS[d]
    if kind == "exit":
        state["blocks"].remove(block)
        state["out"] += 1
        base.say(state, f"{state['block'].capitalize()} {block['id']} is out through {state['colour_names'][int(block['colour'])]}.")
        if not state["blocks"]:
            base.finish(state, "win", f"{state['board'].capitalize()} is clear in {state['moves']} moves (par {state['par']}).")
            return state
    else:
        block["cells"] = [[x + dx, y + dy] for x, y in _cells(block)]
    if state["moves"] >= state["cap"] and not state["over"]:
        base.finish(state, "lose", f"Stuck after {state['moves']} moves; {state['out']} of {state['total']} out.")
    return state


def view(state: dict[str, Any], seat: int) -> dict[str, Any]:
    grid = base.area("grid", f"{state['board'].capitalize()} (tap a {state['block']}, then where it should go)", w=state["w"], h=state["h"], size=44,
                     blocks=[{"id": b["id"], "cells": b["cells"], "colour": b["colour"], "text": b["id"]} for b in state["blocks"]],
                     gates=list(state["gates"]), moves=[{"id": "move", "block": m["block"], "dir": m["dir"]} for m in moves(state)])
    score = base.area("score", "", rows=[{"name": "out", "value": f"{state['out']} of {state['total']}"}, {"name": "moves", "value": f"{state['moves']} (par {state['par']}, cap {state['cap']})"}])
    if state["over"]:
        msg = "Every one through its own gate." if state["result"] == "win" else "Stuck."
    else:
        msg = f"Slide the {state['block']}s out: the gate of their colour."
    acts = actions(state, seat)
    for a in acts:
        a["hidden"] = True  # the board is the input (a tap, a drag or the arrow keys); the actions stay for the tests and a scripted client
    return base.head(state, "Clearing the face" if state["block"] == "block" else "The fussy sheep", msg, [score, grid], acts)

"""A fixed-limit betting round between two seats (five-card draw and Hold'em): check, bet, call, raise (a cap on raises), fold. Pebbles are equal, so
there are no side pots; a seat that cannot cover a bet goes all in for what it has and the rest is returned."""

from __future__ import annotations

from typing import Any


def start(state: dict[str, Any], first: int, size: int, max_raises: int = 3) -> None:
    state["bet"] = {"to_call": [0, 0], "put": [0, 0], "acted": [False, False], "raises": 0, "current": first, "size": int(size), "max_raises": max_raises, "done": False, "folded": None}


def options(state: dict[str, Any], seat: int) -> list[dict[str, Any]]:
    b = state["bet"]
    if b["done"] or b["current"] != seat or b["folded"] is not None:
        return []
    owe = b["to_call"][seat]
    stack = state["stacks"][seat]
    out = []
    chips = state.get("chips", "pebbles")
    if owe == 0:
        out.append({"id": "check", "text": "Check"})
        if stack > 0:
            out.append({"id": "bet", "text": f"Bet {min(b['size'], stack)} {chips}"})
    else:
        out.append({"id": "call", "text": f"Call {min(owe, stack)} {chips}"})
        if stack > owe and b["raises"] < b["max_raises"]:
            out.append({"id": "raise", "text": f"Raise {b['size']} {chips}"})
        out.append({"id": "fold", "text": "Fold"})
    return out


def apply(state: dict[str, Any], seat: int, action_id: str) -> None:
    b = state["bet"]
    other = 1 - seat
    stacks = state["stacks"]

    def put(n: int) -> int:
        n = min(n, stacks[seat])
        stacks[seat] -= n
        b["put"][seat] += n
        state["pot"] += n
        return n

    if action_id == "fold":
        b["folded"] = seat
        b["done"] = True
        return
    if action_id == "check":
        b["acted"][seat] = True
    elif action_id == "call":
        owe = b["to_call"][seat]
        paid = put(owe)
        if paid < owe:  # all in for less: the part of the bet it does not cover goes back
            extra = owe - paid
            stacks[other] += extra
            b["put"][other] -= extra
            state["pot"] -= extra
        b["to_call"][seat] = 0
        b["acted"][seat] = True
    elif action_id in ("bet", "raise"):
        owe = b["to_call"][seat]
        put(owe)
        b["to_call"][seat] = 0
        n = put(b["size"])
        b["to_call"][other] += n
        b["acted"] = [False, False]
        b["acted"][seat] = True
        if action_id == "raise":
            b["raises"] += 1
    if all(b["acted"]) and all(x == 0 for x in b["to_call"]):
        b["done"] = True
        return
    if stacks[other] == 0 and b["to_call"][other] > 0:  # the other is all in already: the extra comes back
        extra = b["to_call"][other]
        stacks[seat] += extra
        state["pot"] -= extra
        b["put"][seat] -= extra
        b["to_call"][other] = 0
        b["done"] = True
        return
    b["current"] = other


def settle(state: dict[str, Any], winner: int | None) -> None:
    """The pot to the winner, or split."""
    if winner is None:
        half = state["pot"] // 2
        state["stacks"][0] += half
        state["stacks"][1] += state["pot"] - half
    else:
        state["stacks"][winner] += state["pot"]
    state["pot"] = 0

"""The engine contract every minigame follows (plan section 2.1), and the helpers they share.

An engine is a module with:

    new(seed, opts) -> state            deterministic from the seed; `state["seats"]` lists the players, seat 0 is the apprentice
    actions(state, seat) -> [action]    the legal moves of this seat now ({"id", "text", ...}); [] when it is not their turn
    act(state, seat, action) -> state   applies one move; raises Illegal for anything not in actions()
    bot(state, seat, rng) -> action     the villager's move for a non-human seat
    view(state, seat) -> dict           what this seat may see (hidden hands masked): title, message, log, over, result, areas, actions

States are plain JSON dicts (lists, dicts, ints, strings), so they can be saved with the world and sent to a client. Every random choice comes
from `rng(state)` seeded by the state's own seed and move count: the same seed plays the same game, whatever the PYTHONHASHSEED.
"""

from __future__ import annotations

import random
import zlib
from typing import Any

RESULTS = ("win", "lose", "draw")


class Illegal(ValueError):
    """An action that is not legal in this state (a stale client, a wrong seat, a move out of turn)."""


def fresh(game: str, seed: int, seats: list[str], **fields: Any) -> dict[str, Any]:
    """The common head of every state: game id, seed, seats, the move counter, the log, and `over`/`result` (the apprentice's result)."""
    return {"game": game, "seed": int(seed), "seats": list(seats), "moves": 0, "log": [], "over": False, "result": "", "turn": 0, **fields}


def rng(state: dict[str, Any], purpose: str = "") -> random.Random:
    """A generator for this moment of the game: seed, move count and purpose, never the hash of a string."""
    return random.Random(zlib.crc32(f"{state['seed']}|{state['moves']}|{purpose}".encode()))


def say(state: dict[str, Any], text: str, cap: int = 12) -> None:
    state["log"].append(str(text))
    del state["log"][:-cap]


def finish(state: dict[str, Any], result: str, text: str = "") -> None:
    assert result in RESULTS, result
    state["over"] = True
    state["result"] = result
    if text:
        say(state, text)


def find(actions: list[dict[str, Any]], action: dict[str, Any]) -> dict[str, Any]:
    """The legal action matching the one asked for (by id, and by every other key the request carries), or Illegal."""
    aid = str(action.get("id", ""))
    for a in actions:
        if a["id"] != aid:
            continue
        if all(action[k] == v for k, v in a.items() if k in action and k not in ("id", "text", "kind")):
            return a
    raise Illegal(aid or "no_action")


def area(kind: str, label: str = "", **fields: Any) -> dict[str, Any]:
    """One area of the table the client draws: `cards`, `dice`, `tiles`, `grid`, `faces`, `text`, `score`, `choices`."""
    return {"kind": kind, "label": label, **fields}


def head(state: dict[str, Any], title: str, message: str, areas: list[dict[str, Any]], actions: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    """The common head of every view."""
    return {"game": state["game"], "title": title, "message": message, "log": list(state["log"]), "over": bool(state["over"]), "result": state["result"],
            "moves": int(state["moves"]), "areas": areas, "actions": actions, **extra}

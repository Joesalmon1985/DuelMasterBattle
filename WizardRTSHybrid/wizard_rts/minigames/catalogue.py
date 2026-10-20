"""The catalogue of games (`data/narrative/minigames.json`): which host plays which game, what they say, and the engine that plays it.

A host is a resident role (the mentor, the mother, the keeper, the sawyer, the water-carrier, the Rollkeeper, a contestant), a worker role (the
lumberjack, the forester, the stonemason, the hunter, the farmer), a carrier, or a building kind for the inspect panel's "played here" line. Only a
game whose engine is registered in `ENGINES` is ever offered; the data may describe a game before its engine exists (the plan's later milestones).
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[1] / "data" / "narrative" / "minigames.json"
ENGINES: dict[str, str] = {  # game id -> engine module (the plan's milestones add to this list)
    "rps": "wizard_rts.minigames.rps",
    "nim": "wizard_rts.minigames.nim",
    "pairs": "wizard_rts.minigames.pairs",
    "memory": "wizard_rts.minigames.memory",
    "reaction": "wizard_rts.minigames.reaction",
    "roulette": "wizard_rts.minigames.roulette",
    "blackjack": "wizard_rts.minigames.blackjack",
    "yahtzee": "wizard_rts.minigames.yahtzee",
    "cantstop": "wizard_rts.minigames.cantstop",
    "rummikub": "wizard_rts.minigames.rummikub",
    "slide": "wizard_rts.minigames.slide",
    "whist": "wizard_rts.minigames.whist",
    "ohhell": "wizard_rts.minigames.ohhell",
    "draw_poker": "wizard_rts.minigames.draw_poker",
    "holdem": "wizard_rts.minigames.holdem",
    "skull": "wizard_rts.minigames.skull",
    "hanabi": "wizard_rts.minigames.hanabi",
    "guesswho": "wizard_rts.minigames.guesswho",
}


@lru_cache(maxsize=1)
def data() -> dict[str, Any]:
    return json.loads(DATA.read_text(encoding="utf-8"))


def entries() -> list[dict[str, Any]]:
    return list(data()["games"])


def entry(game_id: str) -> dict[str, Any] | None:
    return next((g for g in entries() if g["id"] == game_id), None)


def playable(game_id: str) -> bool:
    return game_id in ENGINES and entry(game_id) is not None


def engine(game_id: str) -> Any:
    return import_module(ENGINES[game_id])


def host_key(sp: dict[str, Any]) -> tuple[str, str]:
    """(kind, value) that a speaker offers games as: ("resident", role), ("role", worker role), ("carrier", ""), ("unit", kind)."""
    if sp["kind"] == "resident":
        return "resident", str(sp["res"].get("role", ""))
    if sp["kind"] == "carrier":
        return "carrier", ""
    if sp["kind"] == "unit":
        return "unit", str(sp["row"].get("kind", "soldier"))
    return "role", str(sp["row"].get("role", ""))


def _hosts(g: dict[str, Any]) -> list[tuple[str, str]]:
    """Every (kind, value) pair an entry's `host` names (one host, or a list of them)."""
    hosts = g["host"] if isinstance(g["host"], list) else [g["host"]]
    out: list[tuple[str, str]] = []
    for h in hosts:
        for kind in ("resident", "role", "carrier", "unit"):
            if kind in h:
                out.append((kind, "" if kind == "carrier" else str(h[kind])))
    return out


def games_for(sp: dict[str, Any]) -> list[dict[str, Any]]:
    """The playable games this speaker hosts, in catalogue order."""
    key = host_key(sp)
    return [g for g in entries() if playable(g["id"]) and key in _hosts(g)]


def games_at_building(kind: str, roles: list[str]) -> list[dict[str, Any]]:
    """The games played at a building of this kind: entries that name the building, or a worker role of the building."""
    out = []
    for g in entries():
        if not playable(g["id"]):
            continue
        keys = [("resident", r[len("resident:"):]) if r.startswith("resident:") else ("role", r) for r in roles]
        if str(g.get("building", "")) == kind or any(k in _hosts(g) for k in keys):
            out.append(g)
    return out


def skin_for(g: dict[str, Any], sp: dict[str, Any] | None = None) -> dict[str, Any]:
    """The entry's skin, or the variant skin whose host matches this speaker (the quarry's blocks become the farm's sheep)."""
    skin = dict(g.get("skin", {}))
    if sp is not None:
        key = host_key(sp)
        for v in g.get("variants", []):
            if key in _hosts({"host": v["host"]}):
                skin.update(v.get("skin", {}))
                break
    return skin

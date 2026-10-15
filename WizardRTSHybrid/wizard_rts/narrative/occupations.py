"""Everyday conversations for ordinary people, by occupation (data-driven: `data/narrative/dialogue/occupations.json`).

A woodcutter, forester, carrier or soldier answers as what they are. What they say is chosen by facts read from the simulation at the moment of
the conversation (trees near them, timber in the stores, whether a barracks exists, whether a hostile soldier is close, what they are carrying),
and a line whose facts do not hold is never offered, so nobody describes a castle that does not exist. Variation comes from the number of times the
wizard has already spoken to that person: the introduction once, then a rotating selection of what they might say.
"""

from __future__ import annotations

import json
import random
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from wizard_rts import diplomacy, settlements, territory
from wizard_rts.narrative import graph

DATA = Path(__file__).resolve().parents[1] / "data" / "narrative" / "dialogue" / "occupations.json"
RADIUS = 10  # tiles around the person that "near me" means
HOSTILE_RADIUS = 25
TOPICS_SHOWN = 3
HUT_NAMES = {"producer": "lumberjack's hut", "ranger": "forester's hut", "quarry": "quarry", "hunter": "hunter's hut", "well": "well", "processor": "sawmill"}
ROLE_KEYS = ("lumberjack", "ranger", "stonemason", "hunter")


@lru_cache(maxsize=1)
def data() -> dict[str, Any]:
    return json.loads(DATA.read_text())


def role_key(sp: dict[str, Any]) -> str:
    """Which entry of the data a speaker uses."""
    if sp["kind"] == "carrier":
        return "carrier"
    if sp["kind"] == "unit":
        return "soldier" if sp["row"].get("kind", "soldier") == "soldier" else "worker"
    return sp["row"]["role"] if sp["row"]["role"] in ROLE_KEYS else "worker"


def label(sp: dict[str, Any]) -> str:
    return data()["roles"][role_key(sp)]["label"]


def _near(world: Any, table: dict, tile: tuple[int, int], radius: int, pred=None) -> int:
    n = 0
    for r in table.values():
        if max(abs(int(r["tx"]) - tile[0]), abs(int(r["ty"]) - tile[1])) <= radius and (pred is None or pred(r)):
            n += 1
    return n


def facts_for(world: Any, sp: dict[str, Any]) -> dict[str, Any]:
    """What is true around this person right now (all read from the simulation, nothing invented)."""
    row = sp["row"]
    tile = (int(row["tx"]), int(row["ty"]))
    faction = str(row.get("faction_name", ""))
    f: dict[str, Any] = {"faction": faction}
    building = world.buildings.get(row.get("building", "")) if sp["kind"] == "worker" else None
    if building is not None:
        f["workplace"] = "the " + HUT_NAMES.get(building["kind"], str(building.get("label", "workshop")).replace(faction + " ", "").lower())
        cc = territory.settlement_of(world, building)
        rec = settlements.record(world, cc["settlement_id"]) if cc and cc.get("settlement_id") else None
        f["settlement"] = rec["name"] if rec else faction
    else:
        f["workplace"] = "the settlement"
        f["settlement"] = faction
    f["trees_big"] = _near(world, world.trees, tile, RADIUS, lambda t: t["stage"] in ("mature", "old"))
    f["saplings"] = _near(world, world.trees, tile, RADIUS, lambda t: t["stage"] in ("sapling", "pole"))
    f["rocks"] = _near(world, world.rocks, tile, RADIUS)
    f["animals"] = _near(world, world.animals, tile, RADIUS + 2, lambda a: a.get("alive", True))
    f["logs"] = sum(int(world.stocks.get(b["id"], {}).get("log", 0)) for b in world.buildings.values()
                    if b["faction_name"] == faction and b["kind"] == "warehouse" and b.get("operational", True))
    f["soldiers"] = sum(1 for u in world.units.values() if u["faction_name"] == faction and u.get("alive", True) and u.get("kind") == "soldier")
    barracks = sum(1 for b in world.buildings.values() if b["faction_name"] == faction and b["kind"] == "barracks" and b.get("operational", True))
    f["has_barracks"] = barracks > 0
    f["barracks"] = "a barracks" if barracks == 1 else f"{barracks} barracks"
    f["hostile_near"] = any(u.get("alive", True) and u["faction_name"] != faction and diplomacy.hostile(world, faction, u["faction_name"])
                            and max(abs(int(u["tx"]) - tile[0]), abs(int(u["ty"]) - tile[1])) <= HOSTILE_RADIUS for u in world.units.values())
    f["has_lumberjack"] = any(w["faction_name"] == faction and w["role"] == "lumberjack" for w in world.workers.values())
    carrying = row.get("carrying") if sp["kind"] == "worker" else ((row.get("cargo") or {}).get("good") if sp["kind"] == "carrier" else "")
    f["carrying"] = str(carrying or "")
    return f


def _rng(world: Any, pid: str, count: int, purpose: str) -> random.Random:
    return random.Random(zlib.crc32(f"{world.seed}|{pid}|{count}|{purpose}".encode()))


def talks(world: Any, pid: str) -> int:
    return int(world.narrative.setdefault("talks", {}).get(pid, 0))


def note_talk(world: Any, pid: str) -> None:
    world.narrative.setdefault("talks", {})[pid] = talks(world, pid) + 1


def view(world: Any, sp: dict[str, Any], ctx: dict[str, Any], intro: bool = True, asked: set[str] | None = None) -> dict[str, Any]:
    """Opening lines (the introduction the first time, a short greeting afterwards) and up to three topics the person can be asked about."""
    entry = data()["roles"][role_key(sp)]
    count = max(0, talks(world, sp["pid"]) - 1)  # `note_talk` has already counted this conversation
    pool = entry["intro"] if count == 0 else entry["hub"]
    lines = [pool[_rng(world, sp["pid"], count, "open").randrange(len(pool))]] if intro else []
    lines = graph._fmt(lines, ctx)
    open_topics = [t for t in entry["topics"] if t["id"] not in (asked or set()) and graph.holds(world, "occupation", t.get("when"), ctx)]
    seen_text: set[str] = set()
    unique = [t for t in open_topics if not (t["text"] in seen_text or seen_text.add(t["text"]))]  # alternates with one question show one of them
    shown: list[dict[str, Any]] = []
    if unique:
        start = (count * 2) % len(unique)
        shown = [unique[(start + i) % len(unique)] for i in range(min(TOPICS_SHOWN, len(unique)))]
    return {"lines": lines, "choices": [{"id": "topic:" + t["id"], "text": t["text"], "available": True} for t in shown], "extras": {}}


def topic(world: Any, sp: dict[str, Any], ctx: dict[str, Any], topic_id: str) -> list[str] | None:
    entry = data()["roles"][role_key(sp)]
    t = next((x for x in entry["topics"] if x["id"] == topic_id and graph.holds(world, "occupation", x.get("when"), ctx)), None)
    return graph._fmt(t["lines"], ctx) if t is not None else None

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
from wizard_rts.narrative import checks, graph

DATA = Path(__file__).resolve().parents[1] / "data" / "narrative" / "dialogue" / "occupations.json"
AFTERMATH = DATA.with_name("aftermath.json")
RADIUS = 10  # tiles around the person that "near me" means
HOSTILE_RADIUS = 25
TOPICS_SHOWN = 3
HUT_NAMES = {"producer": "lumberjack's hut", "ranger": "forester's hut", "quarry": "quarry", "hunter": "hunter's hut", "well": "well", "processor": "sawmill"}
ROLE_KEYS = ("lumberjack", "ranger", "stonemason", "hunter")


@lru_cache(maxsize=1)
def data() -> dict[str, Any]:
    return json.loads(DATA.read_text())


@lru_cache(maxsize=1)
def aftermath() -> dict[str, Any]:
    """What people say once the stranger has come and gone (`aftermath.json`): first reactions by persona, knowledge and trade, and topics every trade shares."""
    return json.loads(AFTERMATH.read_text())


def role_key(sp: dict[str, Any]) -> str:
    """Which entry of the data a speaker uses."""
    if sp["kind"] == "carrier":
        return "carrier"
    if sp["kind"] == "unit":
        return "soldier" if sp["row"].get("kind", "soldier") == "soldier" else "worker"
    return sp["row"]["role"] if sp["row"]["role"] in ROLE_KEYS else "worker"


def label(sp: dict[str, Any]) -> str:
    return data()["roles"][role_key(sp)]["label"]


def tribe_of(world: Any, sp: dict[str, Any]) -> str:
    faction = str(sp["row"].get("faction_name", ""))
    return str(world.faction_info.get(faction, {}).get("tribe", "")) if hasattr(world, "faction_info") else ""


def tribe_entry(world: Any, sp: dict[str, Any]) -> dict[str, Any]:
    """The tribe's own voice (`occupations.json` `tribes`): intro, hub and often pools and a few topics of its own. {} for a tribe without one."""
    return data().get("tribes", {}).get(tribe_of(world, sp), {})


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
    f: dict[str, Any] = {"faction": faction, "role": role_key(sp), "trade": label(sp).lower(), "tribe": tribe_of(world, sp)}
    # where this person belongs and where the apprentice comes from (the villages have names in the story, and the other villages know the wizard's)
    from wizard_rts.narrative import campaign, tutorial

    home_sid = tutorial.state(world).get("settlement", "")
    home_rec = world.dmb.settlements.get(home_sid) if home_sid else None
    their_sid = ""
    for sid, rec in world.dmb.settlements.items():
        if rec.get("faction") == faction and "home" in str(rec.get("name", "")):
            their_sid = sid
            break
    f["this_village"] = campaign.settlement_name(world, their_sid) if their_sid else "this place"
    f["home_village"] = campaign.village(world) if home_sid else "the wizard's village"
    f["is_home"] = 1 if (home_rec is not None and home_rec.get("faction") == faction) else 0
    f["home_distance"] = max(abs(tile[0] - int(home_rec["tile"][0])), abs(tile[1] - int(home_rec["tile"][1]))) if home_rec is not None else 0
    from wizard_rts.trial import run as trial

    gate = trial.gate_hint(world, tile)
    f["gate_distance"] = int(gate.get("distance", 0))
    f["gate_compass"] = str(gate.get("compass", "east"))
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


def _entry_topics(entry: dict[str, Any], tribe: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return list(entry["topics"]) + list((tribe or {}).get("topics", [])) + list(data().get("shared_topics", [])) + list(aftermath()["topics"])


def topic_def(world: Any, sp: dict[str, Any], topic_id: str) -> dict[str, Any] | None:
    return next((x for x in _entry_topics(data()["roles"][role_key(sp)], tribe_entry(world, sp)) if x["id"] == topic_id), None)


def _reaction(world: Any, pid: str, ctx: dict[str, Any]) -> list[Any] | None:
    """The person's first words about the attack, once: the first reaction (most specific first) whose persona, knowledge and trade conditions hold."""
    from wizard_rts.narrative import campaign

    if campaign.stage(world) not in ("victory", "aftermath", "complete"):
        return None
    seen = world.narrative.setdefault("reacted", [])
    if pid in seen:
        return None
    seen.append(pid)
    return next((r["lines"] for r in aftermath()["reactions"] if graph.holds(world, "occupation", r.get("when"), ctx)), None)


def reaction_lines(world: Any, sp: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    """The person's first words about the attack (once), already formatted; empty if it has not happened or they have already spoken of it."""
    react = _reaction(world, sp["pid"], ctx)
    return graph._fmt(react, ctx, world, "occupation") if react is not None else []


def view(world: Any, sp: dict[str, Any], ctx: dict[str, Any], intro: bool = True, asked: set[str] | None = None) -> dict[str, Any]:
    """Opening lines (the introduction the first time, a short greeting afterwards, their reaction to the attack once it has happened) and the topics the
    person can be asked about: the ones their trade offers plus what everyone has to say about the attack, as their circumstances allow."""
    entry = data()["roles"][role_key(sp)]
    tribe = tribe_entry(world, sp)
    count = max(0, talks(world, sp["pid"]) - 1)  # `note_talk` has already counted this conversation
    if count == 0:  # the first words: the tribe's way of greeting a stranger (an outsider's village greets the wizard's apprentice as one), else the trade's
        key = "intro_home" if ctx.get("facts", {}).get("is_home") else "intro_away"
        pool = tribe.get(key) or tribe.get("intro") or entry["intro"]
    else:
        pool = tribe.get("hub") or entry["hub"]
    if count >= int(data().get("often_after", 5)) and (tribe.get("often") or data().get("often")):
        pool = tribe.get("often") or data()["often"]  # the fifth visit and after: they have noticed you keep coming back
    lines = [pool[_rng(world, sp["pid"], count, "open").randrange(len(pool))]] if intro else []
    lines = graph._fmt(lines, ctx)
    if intro:
        react = _reaction(world, sp["pid"], ctx)
        if react is not None:
            lines = graph._fmt(react, ctx, world, "occupation")
    open_topics = [t for t in _entry_topics(entry, tribe) if t["id"] not in (asked or set()) and graph.holds(world, "occupation", t.get("when"), ctx)]
    seen_text: set[str] = set()
    unique = [t for t in open_topics if not (t["text"] in seen_text or seen_text.add(t["text"]))]  # alternates with one question show one of them
    first = [t for t in unique if t.get("priority")][:3]  # what everyone is talking about comes first
    rest = [t for t in unique if t not in first]
    shown: list[dict[str, Any]] = list(first)
    if rest:
        start = (count * 2) % len(rest)
        shown += [rest[(start + i) % len(rest)] for i in range(min(TOPICS_SHOWN, len(rest)))]
    choices = []
    for t in shown:
        text, avail = t["text"].format_map(graph.placeholders(ctx)), True
        if "check" in t:
            text = f"{checks.label(t['check'])} {text}"
            avail = not checks.retry_blocked(world, ctx, "t:" + t["id"], t["check"])
        choices.append({"id": "topic:" + t["id"], "text": text, "available": avail})
    return {"lines": lines, "choices": choices, "extras": {}}


def topic(world: Any, sp: dict[str, Any], ctx: dict[str, Any], topic_id: str) -> dict[str, Any] | None:
    """Ask a question. The answer is an authored block: lines, effects with receipts, and, if it has one, a real Aspect check with its pass/fail lines."""
    ctx = {"template": "occupation", "speaker": "occupation", "speaker_pid": sp["pid"], "cast": {}, **ctx}
    t = topic_def(world, sp, topic_id)
    if t is None or not graph.holds(world, "occupation", t.get("when"), ctx):
        return None
    if "check" in t and checks.retry_blocked(world, ctx, "t:" + t["id"], t["check"]):
        return None  # asked before and failed, and nothing has changed since
    out = graph.run_block(world, ctx, "t:" + t["id"], t)
    return out

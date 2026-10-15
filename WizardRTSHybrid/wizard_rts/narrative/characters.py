"""The simulation's own people as characters: one Person per worker, carrier or soldier (plan section 6), found or created on demand.

A Person is the identity (name, history, relationships); the simulation row (`world.workers[...]`, `world.carriers[...]`, `world.units[...]`) stays
the only body. The join is `world.dmb.people[pid]["link"]` plus the reverse index `world.narrative["links"]`; nothing is written onto the
simulation rows. `watch` turns the simulation's own deaths and displacements into the Person's lifecycle; `lifecycle` reads it back.

Determinism: names come from `random.Random(crc32(seed|entity key))`, so they do not depend on who was met first; iteration is sorted; no wall clock.
"""

from __future__ import annotations

import json
import random
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from sim.dmb.people.registry import PeopleService

from wizard_rts.narrative import events

DATA = Path(__file__).resolve().parents[1] / "data" / "narrative"
TABLES = {"worker": "workers", "carrier": "carriers", "unit": "units"}
TALK_RANGE = 3  # tiles (Manhattan), the same reach as the story's own people
LINK_RADIUS = 10  # a character is created for a simulation body when the wizard comes this close (Chebyshev tiles)
LINK_BUDGET = 24  # new characters per game second at most
PUBLISH_RADIUS = 40  # `story.snapshot()["persons"]` lists linked bodies this close to the wizard
DEFAULT_TRIBE = "barbarians"


@lru_cache(maxsize=None)
def _names(tribe: str) -> dict[str, Any]:
    path = DATA / "names" / f"{tribe}.json"
    if not path.exists():
        path = DATA / "names" / f"{DEFAULT_TRIBE}.json"
    return json.loads(path.read_text())


def _rng(world: Any, key: str, purpose: str) -> random.Random:
    return random.Random(zlib.crc32(f"{world.seed}|{key}|{purpose}".encode()))


def link_key(kind: str, entity_id: str) -> str:
    return f"{kind}:{entity_id}"


def locate(world: Any, entity_id: str) -> tuple[str, dict] | None:
    """(kind, row) of a simulation body that can be a character, by its stable id."""
    for kind, table in TABLES.items():
        row = getattr(world, table).get(entity_id)
        if row is not None:
            return kind, row
    return None


def _tribe(world: Any, faction_name: str) -> str:
    return str(world.faction_info.get(faction_name, {}).get("tribe", DEFAULT_TRIBE))


def identity_for(world: Any, tribe: str, key: str) -> dict[str, str]:
    """A stable generated name for the body with this link key (placeholder syllables; no canon names, D19)."""
    names = _names(tribe)
    rng = _rng(world, key, "name")
    given = rng.choice(names["given_a"]) + rng.choice(names["given_b"])
    family = rng.choice(names["family_a"]) + rng.choice(names["family_b"])
    return {"given": given, "family": family, "name": f"{given} {family}", "tribe": tribe}


def _occupation(kind: str, row: dict) -> str:
    if kind == "worker":
        return str(row["role"])
    return "carrier" if kind == "carrier" else str(row.get("kind", "soldier"))


def person_for(world: Any, kind: str, entity_id: str) -> str | None:
    """The Person id for this body, creating the Person (once) if it has none. None when the body does not exist or is dead."""
    n = world.narrative
    key = link_key(kind, entity_id)
    pid = n["links"].get(key)
    if pid is not None and pid in world.dmb.people:
        return pid
    row = getattr(world, TABLES[kind]).get(entity_id)
    if row is None or (kind == "unit" and not row.get("alive", True)):
        return None
    faction = str(row.get("faction_name", ""))
    ident = identity_for(world, _tribe(world, faction), key)
    occupation = _occupation(kind, row)
    building = str(row.get("building", "")) if kind == "worker" else ""
    person = PeopleService(world.dmb).create_person(
        name=ident["name"], role="soldier" if kind == "unit" else "worker", workplace_id=building or None, affiliation=faction,
        area_id="hybrid.world", position=[int(row["tx"]), int(row["ty"])])
    rec = world.dmb.people[person["id"]]
    rec["identity"] = ident
    rec["link"] = {"kind": kind, "id": entity_id, "building": building, "role": occupation,
                   "last": {"inside": kind == "worker" and _is_inside(world, row)}}
    n["links"][key] = person["id"]
    return person["id"]


# ------------------------------------------------------------------ lifecycle (plan section 5.2)

def _is_inside(world: Any, row: dict) -> bool:
    b = world.buildings.get(row["building"])
    return b is not None and row["anim"] == "idle" and not row["path"] and (row["tx"], row["ty"]) == (b["tx"], b["ty"])


def lifecycle(world: Any, pid: str) -> str:
    """One of present, inside, working_away, displaced, dead for a linked Person (the states the later milestones add are not reachable yet)."""
    person = world.dmb.people.get(pid)
    if person is None or not person.get("alive", True):
        return "dead"
    if person.get("status") == "displaced":
        return "displaced"
    link = person.get("link") or {}
    kind, eid = link.get("kind"), link.get("id")
    if kind == "worker":
        row = world.workers.get(eid)
        if row is None:
            return "displaced"
        if _is_inside(world, row):
            return "inside"
        return "working_away" if (row["path"] or row["program"] or row["returning"] or row["target_tree"]) else "present"
    if kind == "carrier":
        return "present" if eid in world.carriers else "displaced"
    if kind == "unit":
        row = world.units.get(eid)
        if row is None or not row.get("alive", True):
            return "dead"
        return "working_away" if (row.get("order") or row.get("path")) else "present"
    return "present"


def _die(world: Any, pid: str, cause: str) -> None:
    svc = PeopleService(world.dmb)
    svc.record_death(pid, cause_id=cause)
    events.log(world, "character_died", person=pid, name=world.dmb.people[pid]["name"], cause=cause)


def _displace(world: Any, pid: str, reason: str) -> None:
    PeopleService(world.dmb).displace(pid, reason=reason)
    events.log(world, "character_displaced", person=pid, name=world.dmb.people[pid]["name"], reason=reason)


def watch(world: Any) -> None:
    """Once a game second: turn the simulation's deaths and removals of linked bodies into Person deaths and displacements.

    Reasons come from the bounded event window (`worker_aborted`, `carrier_killed`, `building_removed`); where the body is simply gone with no
    event, the Person is displaced with reason `lost`. A worker that was inside its workplace when the workplace was destroyed dies with it
    (plan 5.3 and 6.4); one outside is displaced.
    """
    n = world.narrative
    w = n.setdefault("watch", {"events_seen": 0})
    total = int(world.events.total)
    fresh = total - int(w["events_seen"])
    w["events_seen"] = total
    window = list(world.events)
    recent = window[-fresh:] if 0 < fresh <= len(window) else (window if fresh > 0 else [])
    aborted = {e["id"]: e.get("reason", "") for e in recent if e["kind"] == "worker_aborted"}
    killed = {e["id"]: e.get("reason", "") for e in recent if e["kind"] == "carrier_killed"}
    for key, pid in sorted(n["links"].items()):
        person = world.dmb.people.get(pid)
        if person is None or not person.get("alive", True) or person.get("status") == "displaced":
            continue
        link = person["link"]
        kind, eid = link["kind"], link["id"]
        if kind == "worker":
            row = world.workers.get(eid)
            if row is not None:
                link["last"] = {"inside": _is_inside(world, row)}
                continue
            reason = aborted.get(eid, "")
            if reason == "killed_by_fire_magic":
                _die(world, pid, reason)
            elif reason == "workplace_destroyed" or link["building"] not in world.buildings:
                if link.get("last", {}).get("inside"):
                    _die(world, pid, "workplace_destroyed:" + link["building"])
                else:
                    _displace(world, pid, "building_destroyed")
            else:
                _displace(world, pid, reason or "lost")
        elif kind == "carrier":
            if eid in world.carriers:
                continue
            if eid in killed:
                _die(world, pid, killed[eid] or "carrier_killed")
            else:
                _displace(world, pid, "lost")
        elif kind == "unit":
            row = world.units.get(eid)
            if row is None or not row.get("alive", True):
                _die(world, pid, "unit_killed")


def link_nearby(world: Any) -> None:
    """Give a character to every worker, carrier and soldier the wizard walks up to (bounded per second), so each one can be talked to."""
    px, py = int(world.player["tx"]), int(world.player["ty"])
    budget = LINK_BUDGET
    for kind, table in TABLES.items():
        for eid, row in sorted(getattr(world, table).items()):
            if budget <= 0:
                return
            if link_key(kind, eid) in world.narrative["links"]:
                continue
            if max(abs(int(row["tx"]) - px), abs(int(row["ty"]) - py)) > LINK_RADIUS:
                continue
            if kind == "unit" and not row.get("alive", True):
                continue
            if kind == "worker" and _is_inside(world, row):
                continue
            if person_for(world, kind, eid) is not None:
                budget -= 1


# ------------------------------------------------------------------ what the client and the talk op read

def persons_view(world: Any) -> dict[str, dict[str, Any]]:
    """{body id: {person_id, name, has_quest, quest_status}} for linked bodies near the wizard (what Godot joins onto its rows)."""
    from wizard_rts import story

    px, py = int(world.player["tx"]), int(world.player["ty"])
    out: dict[str, dict[str, Any]] = {}
    for _key, pid in sorted(world.narrative["links"].items()):
        person = world.dmb.people.get(pid)
        if person is None or not person.get("alive", True):
            continue
        link = person["link"]
        row = getattr(world, TABLES[link["kind"]]).get(link["id"])
        if row is None or max(abs(int(row["tx"]) - px), abs(int(row["ty"]) - py)) > PUBLISH_RADIUS:
            continue
        found = story._quest_of_npc(world, pid)
        out[link["id"]] = {"person_id": pid, "name": person["name"], "has_quest": bool(found and world.dmb.quests[found[0]]["status"] in story.OPEN),
                           "quest_status": world.dmb.quests[found[0]]["status"] if found else ""}
    return out

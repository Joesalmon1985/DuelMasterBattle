"""Residents: people the narrative layer created (the teacher, the villagers of a story). Minimal form (execution plan B.4).

A resident is a Person record (`link.kind == "resident"`) plus a row in `world.narrative["residents"]`: a tile, a home settlement, a routine and a
dialogue graph. Residents are drawn from `story.entity_rows` as `npc` rows; they do not block tiles and are not part of the economy. The routine
here is `near_centre`: every beat the resident steps to another free tile within two of where it was placed (seeded by game time and id, no
`world.rng`). Mortality, households and the full routines arrive in D; until then residents cannot be burned.
"""

from __future__ import annotations

import random
import zlib
from typing import Any

from sim.dmb.people.registry import PeopleService

from wizard_rts.narrative import characters, events, party

BEAT_MS = 20_000
ROUTINE_RADIUS = 2
FIGURES = {  # the Widelands worker sprite that stands for a role, by tribe (art in godot_project/client/hybrid/art/widelands/gen)
    "mentor": {"barbarians": "barbarians_trainer", "empire": "empire_trainer", "atlanteans": "atlanteans_trainer", "frisians": "frisians_trainer", "amazons": "amazons_trainer"},
    "stranger": {"barbarians": "barbarians_blacksmith_master", "empire": "empire_miner_master", "atlanteans": "atlanteans_smoker", "frisians": "empire_miner_master", "amazons": "empire_miner_master"},
    "weaver": {"barbarians": "barbarians_weaver", "empire": "empire_weaver", "atlanteans": "atlanteans_weaver", "frisians": "frisians_seamstress", "amazons": "amazons_dressmaker"},
    "farmer": {"barbarians": "barbarians_farmer", "empire": "empire_farmer", "atlanteans": "atlanteans_farmer", "frisians": "frisians_farmer", "amazons": "amazons_cassava_farmer"},
    "baker": {"barbarians": "barbarians_baker", "empire": "empire_baker", "atlanteans": "atlanteans_baker", "frisians": "frisians_baker", "amazons": "amazons_cook"},
}


def table(world: Any) -> dict[str, Any]:
    return world.narrative["residents"]


def is_resident(world: Any, pid: str) -> bool:
    return "narrative" in world.__dict__ and pid in world.narrative["residents"]


def _occupied(world: Any) -> set[tuple[int, int]]:
    out = {(u["tx"], u["ty"]) for u in world.units.values() if u.get("alive", True)}
    out |= {tuple(r["tile"]) for r in table(world).values() if r["status"] in ("present", "dead")}  # a body still lies where it fell
    out.add((int(world.player["tx"]), int(world.player["ty"])))
    for p in (getattr(world, "players", None) or {}).values():  # every wizard in the world takes up a tile, not only the one acting
        out.add((int(p["tx"]), int(p["ty"])))
    return out


def free_tile(world: Any, cx: int, cy: int, radius: int, rng: random.Random | None = None, avoid: set[tuple[int, int]] | None = None) -> tuple[int, int] | None:
    """A walkable, unoccupied tile within `radius` (Chebyshev) of (cx, cy): the nearest, or a seeded pick among them when `rng` is given."""
    taken = _occupied(world) | (avoid or set())
    cands = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            t = (cx + dx, cy + dy)
            if t in taken or t in world.blocked or t in world.tree_tiles or t in world.road_tile_set or not world.tile_in_map(*t):
                continue
            if world.terrain is not None and not world.terrain.ground(*t):
                continue
            cands.append(((abs(dx) + abs(dy), t[1], t[0]), t))
    if not cands:
        return None
    cands.sort()
    return rng.choice([t for _k, t in cands]) if rng is not None else cands[0][1]


def create(world: Any, *, settlement: str, role: str, graph: str, speaker: str, tile: tuple[int, int], tribe: str, faction: str,
           key: str, temporary_until_ms: int | None = None, identity_tribe: str | None = None) -> str:
    """Create a resident Person (named from the tribe's generated syllables, `identity_tribe` if the person comes from elsewhere) standing on `tile`.
    `key` makes the name stable."""
    ident = characters.identity_for(world, identity_tribe or tribe, "resident:" + key)
    person = PeopleService(world.dmb).create_person(name=ident["name"], role="villager", affiliation=faction, area_id="hybrid.world",
                                                    position=[int(tile[0]), int(tile[1])])
    pid = person["id"]
    rec = world.dmb.people[pid]
    rec["identity"] = ident
    rec["link"] = {"kind": "resident", "id": pid, "building": "", "role": role, "settlement": settlement}
    table(world)[pid] = {"tile": [int(tile[0]), int(tile[1])], "anchor": [int(tile[0]), int(tile[1])], "settlement": settlement, "role": role,
                         "tribe": tribe, "faction": faction, "graph": graph, "speaker": speaker, "status": "present", "next_beat_ms": 0,
                         "expires_ms": temporary_until_ms, "key": key}
    events.log(world, "resident_arrived", person=pid, name=ident["name"], role=role, settlement=settlement)
    return pid


def figure(rec: dict[str, Any]) -> str:
    if rec.get("figure"):  # a body row names its own picture (the wizard's avatar lying down)
        return str(rec["figure"])
    role = {"teacher": "mentor", "mother": "weaver", "keeper": "baker", "official": "mentor"}.get(rec["role"], rec["role"])
    by_tribe = FIGURES.get(role, FIGURES["farmer"])
    return "widelands.%s_worker" % by_tribe.get(rec["tribe"], by_tribe["barbarians"])


def quantum(world: Any) -> None:
    """Once a game second: let each resident whose beat is due step to another tile near its post (unless someone is talking to it)."""
    now = int(world.dmb.clock.get("game_ms", 0))
    conv = party.talking_keys(world)  # a resident being talked to (by anyone) stands still (conversation.py ends abandoned conversations)
    for pid, r in sorted(table(world).items()):
        if r["status"] != "present":
            continue
        if r.get("walk"):  # a scripted walk (the stranger arriving or leaving): one tile a game second, along a path found when it was ordered
            nxt = r["walk"].pop(0)
            r["tile"] = [nxt[0], nxt[1]]
            world.dmb.people[pid]["position"] = [nxt[0], nxt[1]]
            continue
        if r.get("stay") or pid in conv or now < r["next_beat_ms"]:
            continue
        beat = now // BEAT_MS
        r["next_beat_ms"] = (beat + 1) * BEAT_MS
        rng = random.Random(zlib.crc32(f"{world.seed}|{pid}|{beat}".encode()))
        t = free_tile(world, r["anchor"][0], r["anchor"][1], ROUTINE_RADIUS, rng, avoid={tuple(r["tile"])})
        if t is not None:
            r["tile"] = [t[0], t[1]]
            world.dmb.people[pid]["position"] = [t[0], t[1]]


def walk_to(world: Any, pid: str, goal: tuple[int, int], limit: int = 60) -> int:
    """Order a resident to walk to `goal` (a path of at most `limit` steps over walkable ground); returns the number of steps, 0 when there is no path."""
    from wizard_rts import workers

    r = table(world)[pid]
    path = workers.find_path(world, (int(r["tile"][0]), int(r["tile"][1])), (int(goal[0]), int(goal[1])), limit=max(24, limit))
    if not path or len(path) > limit:
        return 0
    r["walk"] = [[int(t[0]), int(t[1])] for t in path]
    return len(path)


def remove(world: Any, pid: str, status: str = "gone") -> None:
    """A resident leaves the picture (status `gone`: alive but no longer here) without being resurrected or deleted: the Person keeps its history."""
    r = table(world)[pid]
    r["status"], r["walk"] = status, []


def entity_rows(world: Any, row_info: Any) -> list[dict[str, Any]]:
    """Residents as `npc` snapshot rows (what Godot draws, labels and lets the wizard talk to). `row_info(pid, rec)` supplies the quest marker."""
    rows = []
    for pid, r in sorted(table(world).items()):
        if r["status"] not in ("present", "dead"):
            continue
        person = world.dmb.people.get(pid, {})
        info = row_info(pid, r)
        rows.append({"id": pid, "class": "npc", "kind": "npc", "definition": "story.resident", "faction": "", "faction_name": r["faction"],
                     "label": person.get("name", "Villager"), "tx": r["tile"][0], "ty": r["tile"][1], "alive": bool(person.get("alive", True)) and r["status"] == "present",
                     "figure": figure(r), "role": r["role"], "dead": r["status"] == "dead", "hostile": bool(r.get("hostile")), "quest_status": info.get("quest_status", ""), "has_quest": bool(info.get("has_quest", False)),
                     "hint": info.get("hint", ""), **({"body": True, "seat": r.get("seat", ""), "avatar": r.get("avatar", "")} if r["role"] == "body" else {}),
                     **({"pest": dict(r["pest"])} if r["role"] == "pest" else {}), **({"contestant": r["contestant"]} if r.get("contestant") else {})})
    return rows

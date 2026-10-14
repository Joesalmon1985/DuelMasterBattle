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

from wizard_rts.narrative import characters, events

BEAT_MS = 20_000
ROUTINE_RADIUS = 2
CONVERSATION_MS = 15_000  # a conversation that was never closed freezes the routine for at most this long (game time)
FIGURES = {  # the Widelands worker sprite that stands for a role, by tribe (art in godot_project/client/hybrid/art/widelands/gen)
    "teacher": {"barbarians": "barbarians_trainer", "empire": "empire_trainer", "atlanteans": "atlanteans_trainer", "frisians": "frisians_trainer", "amazons": "amazons_trainer"},
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
    out |= {tuple(r["tile"]) for r in table(world).values() if r["status"] == "present"}
    out.add((int(world.player["tx"]), int(world.player["ty"])))
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
           key: str, temporary_until_ms: int | None = None) -> str:
    """Create a resident Person (named from the tribe's generated syllables) standing on `tile`. `key` makes the name stable."""
    ident = characters.identity_for(world, tribe, "resident:" + key)
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
    by_tribe = FIGURES.get(rec["role"], FIGURES["farmer"])
    return "widelands.%s_worker" % by_tribe.get(rec["tribe"], by_tribe["barbarians"])


def start_conversation(world: Any, pid: str) -> None:
    world.narrative["conversations"][pid] = int(world.dmb.clock.get("game_ms", 0))


def end_conversation(world: Any, pid: str | None = None) -> None:
    conv = world.narrative["conversations"]
    for k in ([pid] if pid else list(conv)):
        conv.pop(k, None)


def quantum(world: Any) -> None:
    """Once a game second: let each resident whose beat is due step to another tile near its post (unless someone is talking to it)."""
    now = int(world.dmb.clock.get("game_ms", 0))
    conv = world.narrative["conversations"]
    for pid in [p for p, t in conv.items() if now - int(t) > CONVERSATION_MS]:
        conv.pop(pid)
    for pid, r in sorted(table(world).items()):
        if r["status"] != "present" or pid in conv or now < r["next_beat_ms"]:
            continue
        beat = now // BEAT_MS
        r["next_beat_ms"] = (beat + 1) * BEAT_MS
        rng = random.Random(zlib.crc32(f"{world.seed}|{pid}|{beat}".encode()))
        t = free_tile(world, r["anchor"][0], r["anchor"][1], ROUTINE_RADIUS, rng, avoid={tuple(r["tile"])})
        if t is not None:
            r["tile"] = [t[0], t[1]]
            world.dmb.people[pid]["position"] = [t[0], t[1]]


def entity_rows(world: Any, row_info: Any) -> list[dict[str, Any]]:
    """Residents as `npc` snapshot rows (what Godot draws, labels and lets the wizard talk to). `row_info(pid, rec)` supplies the quest marker."""
    rows = []
    for pid, r in sorted(table(world).items()):
        if r["status"] != "present":
            continue
        person = world.dmb.people.get(pid, {})
        info = row_info(pid, r)
        rows.append({"id": pid, "class": "npc", "kind": "npc", "definition": "story.resident", "faction": "", "faction_name": r["faction"],
                     "label": person.get("name", "Villager"), "tx": r["tile"][0], "ty": r["tile"][1], "alive": bool(person.get("alive", True)),
                     "figure": figure(r), "role": r["role"], "quest_status": info.get("quest_status", ""), "has_quest": bool(info.get("has_quest", False)),
                     "hint": info.get("hint", "")})
    return rows

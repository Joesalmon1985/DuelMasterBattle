"""The Trial's zones: the legacy Deathtrap Dungeon areas (`data/trial/legacy_zones.json`, exported from the old adventure's GDScript tables) plus the
Wizard World overlay (`data/trial/zones_wizard.json`: adapted texts, two-player rules, provenance). Read-only data; the run's state is `trial/run.py`.

Tile legend (the legacy's): `.` floor, `:` path, `,` dark floor, `~` water, `=` bridge, `#` wall, `T` wall (trees in the overworld), `r` stalagmite (solid),
`L` log pile (solid), space void. Solid entity kinds block a step: a sign, a door, a log pile, a person, a body, a creature.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[1] / "data" / "trial"
WALKABLE = set(".:,=a")
SOLID_KINDS = {"sign", "door", "logs", "npc", "corpse", "creature", "wizard"}
ENTRY_ZONE = "dd_entrance"
ENTRY_POS = (10, 11)
ENTRY_FACING = "up"


@lru_cache(maxsize=1)
def _legacy() -> dict[str, Any]:
    return json.loads((DATA / "legacy_zones.json").read_text(encoding="utf-8"))["zones"]


@lru_cache(maxsize=1)
def overlay() -> dict[str, Any]:
    p = DATA / "zones_wizard.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"zones": {}, "entities": {}, "ported": []}


@lru_cache(maxsize=1)
def zones() -> dict[str, Any]:
    """Every zone with the overlay applied: entity fields overridden by id, zone-level fields (name) overridden by id."""
    out: dict[str, Any] = {}
    ov = overlay()
    for zid, z in _legacy().items():
        zz = {"id": zid, "name": z["name"], "rows": list(z["rows"]), "entities": []}
        zz.update({k: v for k, v in ov.get("zones", {}).get(zid, {}).items() if k != "entities"})
        for e in z["entities"]:
            ee = dict(e)
            key = f"{zid}/{e.get('id', '')}" if e.get("id") else ""
            if key and key in ov.get("entities", {}):
                ee.update(ov["entities"][key])
            if ee.get("removed"):
                continue
            zz["entities"].append(ee)
        out[zid] = zz
    return out


def ported() -> list[str]:
    """The zone ids Wizard World plays (the rest are drawn for the developer tools only until their milestone ports them)."""
    return list(overlay().get("ported", []))


def zone(zid: str) -> dict[str, Any]:
    return zones()[zid]


def size(zid: str) -> tuple[int, int]:
    rows = zone(zid)["rows"]
    return len(rows[0]), len(rows)


def char_at(zid: str, x: int, y: int) -> str:
    w, h = size(zid)
    if x < 0 or y < 0 or x >= w or y >= h:
        return " "
    return zone(zid)["rows"][y][x]


def tile_walkable(zid: str, x: int, y: int) -> bool:
    return char_at(zid, x, y) in WALKABLE


def entity(zid: str, eid: str) -> dict[str, Any] | None:
    for e in zone(zid)["entities"]:
        if e.get("id") == eid:
            return e
    return None


def exits_at(zid: str, x: int, y: int) -> list[dict[str, Any]]:
    return [e for e in zone(zid)["entities"] if e["kind"] == "exit" and int(e["pos"][0]) == x and int(e["pos"][1]) == y]


def entities_at(zid: str, x: int, y: int) -> list[dict[str, Any]]:
    return [e for e in zone(zid)["entities"] if e["kind"] != "exit" and int(e["pos"][0]) == x and int(e["pos"][1]) == y]

"""The developer's village of games (plan section 2.5, host flag `--games-village`): the start village with every game's host present and reachable.

Applied once to a fresh world (`ensure` is idempotent and is run again on a loaded one): the early buildings the start lacks (a fisher's hut, a farm,
a tavern, a bakery: existing kinds, placed operational the way the start's showcase buildings are, each joined to the warehouse by a road), the
narrative hosts cast now (the mother, the warehouse keeper, a sawyer at the sawmill, a water-carrier at the well, a Rollkeeper and two contestants
at the green), the opening read and the essential lessons done so the mentor talks games rather than knots, the stranger switched off
(`campaign.explore_due` reads the flag), and the apprentice stood beside the warehouse. Nothing here is a new roster entity: the buildings are
existing kinds and the people are narrative residents like the keeper.
"""

from __future__ import annotations

from typing import Any

from wizard_rts import construction as con
from wizard_rts.narrative import config, events, mother, mortality, pests, residents, tutorial, wizard

GRAPH = "games"
EXTRA_BUILDINGS = (  # kind, definition, label, size, offset from the warehouse (the showcase's own offsets)
    ("farm", "widelands.farm", "Farm", "big", (1, -11)),
    ("tavern", "widelands.tavern", "Tavern", "medium", (-10, -8)),
    ("bakery", "widelands.bakery", "Bakery", "medium", (-6, -10)),
    ("fisher", "widelands.fishers_hut", "Fisher's hut", "small", (8, 8)),
)
FAIR = (("official", "official", "rollkeeper"), ("contestant", "contestant", "contestant:knight"), ("contestant", "contestant", "contestant:elf"))
FAIR_NAMES = {"contestant:knight": ("Serra of the White Road", "contestant:knight"), "contestant:elf": ("An elven woman", "contestant:elf")}


def active(world: Any) -> bool:
    return "narrative" in world.__dict__ and bool(world.narrative.get("games_village"))


def _home(world: Any) -> tuple[str, dict[str, Any], str, str] | None:
    """(settlement id, the home warehouse, faction, tribe) of the apprentice's village."""
    found = pests.home(world)
    if found is None:
        return None
    sid, b = found
    faction = str(b["faction_name"])
    tribe = str(world.faction_info.get(faction, {}).get("tribe", "barbarians"))
    return sid, b, faction, tribe


def _place_buildings(world: Any, wh: dict[str, Any], faction: str) -> list[str]:
    """The early buildings the start lacks, operational at once and joined to the warehouse (the showcase's own placement, outside the economy's cost)."""
    placed: list[str] = []
    if world.terrain is None:
        return placed
    have = {b["kind"] for b in world.buildings.values() if b["faction_name"] == faction and b.get("operational", True)}
    centre = (int(wh["tx"]), int(wh["ty"]))
    for kind, definition, label, size, (dx, dy) in EXTRA_BUILDINGS:
        if kind in have:
            continue
        try:
            tile = world._site(centre, dx, dy, size, set(world.road_tile_set), extra=con.GROUND_FOOTPRINT.get(kind))
        except RuntimeError as exc:
            events.log(world, "games_village_no_site", kind=kind, why=str(exc))
            continue
        bid = world._building(wh["faction"], faction, kind, tile, label, definition)
        res = con.build_road(world, faction, bid, wh["id"])
        if res.get("status") != "ok":
            events.log(world, "games_village_no_road", kind=kind, why=res.get("reason", ""))
        placed.append(bid)
    return placed


def _post(world: Any, sid: str, b: dict[str, Any], role: str, speaker: str, tribe: str, faction: str, key: str) -> str | None:
    """A resident standing at a building's door, anchored there (the sawyer at the sawmill, the water-carrier at the well)."""
    for r in residents.table(world).values():
        if r.get("key") == key and r["status"] == "present":
            return None
    tile = residents.free_tile(world, int(b["tx"]) + 1, int(b["ty"]) + 1, 3)
    if tile is None:
        return None
    pid = residents.create(world, settlement=sid, role=role, graph=GRAPH, speaker=speaker, tile=tile, tribe=tribe, faction=faction, key=key)
    rec = residents.table(world)[pid]
    rec["anchor"] = [int(b["tx"]) + 1, int(b["ty"]) + 1]
    rec["building"] = b["id"]
    return pid


def _green(world: Any, sid: str, wh: dict[str, Any], tribe: str, faction: str) -> list[str]:
    """The games fair on the green beside the warehouse: a Rollkeeper and two contestants of the games village (not the Trial's)."""
    out: list[str] = []
    taken: set[tuple[int, int]] = set()
    for role, speaker, key in FAIR:
        if any(r.get("key") == "fair:" + key and r["status"] == "present" for r in residents.table(world).values()):
            continue
        tile = residents.free_tile(world, int(wh["tx"]) + 4, int(wh["ty"]) + 3, 4, avoid=taken)
        if tile is None:
            continue
        taken.add(tile)
        pid = residents.create(world, settlement=sid, role=role, graph=GRAPH, speaker=speaker, tile=tile, tribe=tribe, faction=faction if role == "official" else "", key="fair:" + key)
        if key in FAIR_NAMES:
            name, figure = FAIR_NAMES[key]
            world.dmb.people[pid]["name"] = name
            world.dmb.people[pid]["display_name"] = name
            residents.table(world)[pid]["figure"] = figure
        out.append(pid)
    return out


def ensure(world: Any) -> dict[str, Any]:
    """Make this world the games village (idempotent). Returns what was added."""
    if "narrative" not in world.__dict__:
        return {"status": "rejected", "reason": "no_narrative"}
    tutorial.start(world)
    home = _home(world)
    if home is None:
        return {"status": "rejected", "reason": "no_home"}
    sid, wh, faction, tribe = home
    first = not world.narrative.get("games_village")
    world.narrative["games_village"] = True
    out: dict[str, Any] = {"status": "ok", "buildings": _place_buildings(world, wh, faction), "residents": []}
    # the opening is read and the lessons are done: the mentor has nothing to teach but games (the colours came with grant_basics)
    w = wizard.wiz(world)
    w["opening_seen"] = True
    for lesson in config.get("tutorial", "essential", []):
        wizard.complete_lesson(world, lesson)
    if not all(wizard.knows(world, sp) for sp in wizard.palette()):
        wizard.learn(world, wizard.palette(), 3)
    # the hosts
    seat = mortality.me(world)
    pid = mother.ensure(world, seat)
    if pid:
        out["residents"].append(pid)
    pests.ensure(world)  # the keeper comes with the rats, as in any village
    sawmill = next((b for b in world.buildings.values() if b["faction_name"] == faction and b["kind"] == "processor"), None)
    well = next((b for b in world.buildings.values() if b["faction_name"] == faction and b["kind"] == "well"), None)
    if sawmill is not None:
        pid = _post(world, sid, sawmill, "sawyer", "sawyer", tribe, faction, "sawyer:" + sid)
        if pid:
            out["residents"].append(pid)
    if well is not None:
        pid = _post(world, sid, well, "water_carrier", "water_carrier", tribe, faction, "water_carrier:" + sid)
        if pid:
            out["residents"].append(pid)
    out["residents"] += _green(world, sid, wh, tribe, faction)
    if first:  # the apprentice begins beside the warehouse, in the middle of it all
        tile = residents.free_tile(world, int(wh["tx"]) + 2, int(wh["ty"]) + 2, 4)
        if tile is not None:
            world.player["tx"], world.player["ty"] = int(tile[0]), int(tile[1])
            for p in (getattr(world, "players", None) or {}).values():
                p["tx"], p["ty"] = int(tile[0]), int(tile[1])
    events.log(world, "games_village", first=first, buildings=len(out["buildings"]), residents=len(out["residents"]))
    return out


def hosts(world: Any) -> list[dict[str, Any]]:
    """Every host in this village with their games (for the tests and the HUD): residents by role, workers by role, one carrier."""
    from wizard_rts.minigames import catalogue
    from wizard_rts.narrative import conversation

    out = []
    seen: set[str] = set()
    keys = sorted(residents.table(world)) + sorted(world.workers) + sorted(world.carriers)
    for key in keys:
        sp = conversation.resolve(world, key)
        if sp is None or (sp["kind"] == "resident" and sp["res"]["status"] != "present"):
            continue
        games = catalogue.games_for(sp)
        if not games:
            continue
        label = catalogue.host_key(sp)
        if label in seen and sp["kind"] != "resident":
            continue
        seen.add(label)
        out.append({"key": key, "kind": sp["kind"], "name": world.dmb.people[sp["pid"]]["name"], "tile": list(sp["tile"]), "games": [g["id"] for g in games]})
    return out

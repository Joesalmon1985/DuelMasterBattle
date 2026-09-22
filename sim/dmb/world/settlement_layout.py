"""Local settlement spatial grammar for village presentation (C09).

strategic node + touching hex directions + buildings
        ↓
persisted LocalArea anchors
        ↓
perimeter resource sites + built core + exits

Presentation only — does not invent Buildings or People.
"""

from __future__ import annotations

from typing import Any

from sim.dmb.world.board import HexBoard, parse_hex_id

LAYOUT_SCHEMA_VERSION = 2
BASE_SIZE = 48
FOOTPRINT_CORE = (3, 3)
FOOTPRINT_PRIMARY = (4, 3)

# Axial delta (dq, dr) from node plane → local perimeter sector.
_SECTOR_BY_CARDINAL = {
    "N": "north",
    "NE": "northeast",
    "E": "east",
    "SE": "southeast",
    "S": "south",
    "SW": "southwest",
    "W": "west",
    "NW": "northwest",
}

OCCUPATION_BY_TERRAIN = {
    "woodland": "Woodcutter",
    "ore_mountains": "Miner",
    "clay_mountains": "Clay worker",
    "fields": "Field worker",
    "grazing_land": "Shepherd",
}

OCCUPATION_BY_SLOT = {
    "processor": "Works worker",
    "factory": "Factory worker",
    "warehouse": "Storekeeper",
    "centre": "Villager",
    "primary": "Worker",
}

PRIMARY_LABEL = {
    "woodland": "Woodland Cuttings",
    "ore_mountains": "Ore Ridge",
    "clay_mountains": "Clay Pits",
    "fields": "Grain Fields",
    "grazing_land": "Pasture",
}

# Map characters for primary footprints (not house walls).
PRIMARY_TILE_CHARS = {
    "woodland": "T",
    "ore_mountains": "r",
    "clay_mountains": "r",
    "fields": ".",
    "grazing_land": ".",
}

PRIMARY_PROP_MARKERS = {
    "woodland": "logs",
    "ore_mountains": "rock",
    "clay_mountains": "rock",
    "fields": "sign",
    "grazing_land": "sign",
}


def node_plane_qr(board: HexBoard, node_id: str) -> tuple[float, float]:
    hexes = board.touching_hexes(node_id)
    if not hexes:
        return (0.0, 0.0)
    qs: list[float] = []
    rs: list[float] = []
    for hid in hexes:
        q, r = parse_hex_id(str(hid))
        qs.append(float(q))
        rs.append(float(r))
    return (sum(qs) / len(qs), sum(rs) / len(rs))


def hex_sector(board: HexBoard, node_id: str, hex_id: str) -> str:
    """Map a touching hex to an 8-way perimeter sector relative to the node."""
    nq, nr = node_plane_qr(board, node_id)
    hq, hr = parse_hex_id(str(hex_id))
    dq = float(hq) - nq
    dr = float(hr) - nr
    # Pointy-top axial → approximate screen: +q eastish, +r southeastish.
    # Convert to a 2D plane similar to wire_topology_travel.
    dx = dq + 0.5 * dr
    dy = dr
    import math

    ang = math.atan2(dy, dx)  # -pi..pi, 0 = east
    # 8 sectors centred on cardinals/diagonals.
    deg = (math.degrees(ang) + 360.0) % 360.0
    # 0° east, 90° south, 180° west, 270° north
    buckets = [
        (22.5, "E"),
        (67.5, "SE"),
        (112.5, "S"),
        (157.5, "SW"),
        (202.5, "W"),
        (247.5, "NW"),
        (292.5, "N"),
        (337.5, "NE"),
        (360.0, "E"),
    ]
    key = "E"
    for limit, name in buckets:
        if deg <= limit:
            key = name
            break
    return _SECTOR_BY_CARDINAL[key]


def perimeter_anchor(
    width: int,
    height: int,
    sector: str,
    *,
    footprint: tuple[int, int] = FOOTPRINT_PRIMARY,
    margin: int = 3,
) -> dict[str, Any]:
    """Place a site near the map edge in the given sector; entrance faces inward."""
    fw, fh = footprint
    cx, cy = width // 2, height // 2
    # Anchor origin (top-left of footprint).
    if sector == "north":
        ox, oy = cx - fw // 2, margin
    elif sector == "northeast":
        ox, oy = width - fw - margin, margin
    elif sector == "east":
        ox, oy = width - fw - margin, cy - fh // 2
    elif sector == "southeast":
        ox, oy = width - fw - margin, height - fh - margin - 2
    elif sector == "south":
        ox, oy = cx - fw // 2, height - fh - margin - 2
    elif sector == "southwest":
        ox, oy = margin, height - fh - margin - 2
    elif sector == "west":
        ox, oy = margin, cy - fh // 2
    else:  # northwest
        ox, oy = margin, margin
    ox = max(margin, min(width - fw - margin, ox))
    oy = max(margin, min(height - fh - margin - 2, oy))
    # Entrance on the side facing the village centre.
    if abs(cx - (ox + fw // 2)) >= abs(cy - (oy + fh // 2)):
        if cx >= ox + fw // 2:
            ex, ey = ox + fw, oy + fh // 2
        else:
            ex, ey = ox - 1, oy + fh // 2
    else:
        if cy >= oy + fh // 2:
            ex, ey = ox + fw // 2, oy + fh
        else:
            ex, ey = ox + fw // 2, oy - 1
    ex = max(1, min(width - 2, ex))
    ey = max(1, min(height - 2, ey))
    # Approach one step further toward centre.
    ax = ex + (1 if cx > ex else -1 if cx < ex else 0)
    ay = ey + (1 if cy > ey else -1 if cy < ey else 0)
    ax = max(1, min(width - 2, ax))
    ay = max(1, min(height - 2, ay))
    return {
        "grid": [ox, oy],
        "footprint": [fw, fh],
        "entrance": [ex, ey],
        "approach": [ax, ay],
        "sector": sector,
        "presentation": "primary_site",
    }


def core_anchor(
    width: int,
    height: int,
    slot_kind: str,
    index: int,
    *,
    footprint: tuple[int, int] = FOOTPRINT_CORE,
) -> dict[str, Any]:
    """Pack civic/industrial buildings around the built core (centre of map)."""
    fw, fh = footprint
    cx, cy = width // 2, height // 2
    # Relative offsets from centre for core slots (deterministic).
    offsets = {
        "centre": [(0, 0)],
        "warehouse": [(-5, 2)],
        "processor": [(-4, -4), (3, -3), (-1, 5)],
        "factory": [(5, 1), (6, 5), (4, -5)],
    }
    choices = offsets.get(slot_kind) or [(index % 3 - 1) * 4, 3 + (index // 3) * 4]
    if isinstance(choices[0], tuple):
        dx, dy = choices[min(index, len(choices) - 1)]
    else:
        dx, dy = int(choices[0]), int(choices[1])
    ox = cx + dx - fw // 2
    oy = cy + dy - fh // 2
    ox = max(8, min(width - fw - 8, ox))
    oy = max(10, min(height - fh - 10, oy))
    entrance = [ox + fw // 2, oy + fh]
    approach = [entrance[0], entrance[1] + 1]
    return {
        "grid": [ox, oy],
        "footprint": [fw, fh],
        "entrance": entrance,
        "approach": approach,
        "sector": "core",
        "presentation": "structure",
    }


def public_occupation_for(
    person: dict[str, Any],
    *,
    workplace: dict[str, Any] | None = None,
    job: dict[str, Any] | None = None,
) -> str:
    """Stable player-facing occupation — never 'Carrier' unless that is the real job."""
    workplace = workplace or {}
    job = job or {}
    # Explicit occupation already stamped wins if specific.
    existing = str(person.get("occupation") or "").strip()
    if existing and existing.lower() not in {"", "carrier", "worker", "attendant", "villager"}:
        return existing.replace("_", " ").title() if existing.islower() else existing
    terrain = str(workplace.get("terrain") or person.get("terrain") or "")
    if terrain in OCCUPATION_BY_TERRAIN:
        return OCCUPATION_BY_TERRAIN[terrain]
    slot = str(workplace.get("slot_kind") or "")
    if slot in OCCUPATION_BY_SLOT and slot != "primary":
        return OCCUPATION_BY_SLOT[slot]
    job_id = str(job.get("job_id") or person.get("job_id") or "")
    if job_id in {"job.factory_worker", "job:attendant"}:
        return "Factory worker"
    if job_id == "job:site_worker" and terrain in OCCUPATION_BY_TERRAIN:
        return OCCUPATION_BY_TERRAIN[terrain]
    sprite = str(person.get("sprite") or person.get("visual_profile") or "")
    sprite_map = {
        "woodcutter": "Woodcutter",
        "miner": "Miner",
        "farmer": "Field worker",
        "shepherd": "Shepherd",
        "worker": "Factory worker",
        "villager_a": "Villager",
        "villager_b": "Villager",
    }
    if sprite in sprite_map:
        return sprite_map[sprite]
    role = str(person.get("role") or "")
    if role in {"leader", "soldier"}:
        return role.title()
    return "Villager"


def activity_label(activity: str, *, resource_label: str | None = None) -> str:
    act = str(activity or "idle")
    resource = str(resource_label or "goods")
    if act == "carrying":
        return f"Carrying {resource.lower()}"
    if act == "returning":
        return "Returning"
    if act == "waiting":
        return "Waiting"
    if act == "working":
        return "Working"
    if act == "idle":
        return "Idle"
    return act.replace("_", " ").title()


def baseline_dialogue(
    person: dict[str, Any],
    *,
    occupation: str,
    activity: str = "idle",
    resource_label: str | None = None,
    workplace_label: str | None = None,
) -> list[str]:
    """Truthful occupation/activity lines — never promises guide/follow behaviour."""
    occ = occupation or "Villager"
    act = str(activity or "idle")
    resource = str(resource_label or "goods")
    place = str(workplace_label or "the works")
    if act == "carrying":
        return [f"I'm taking {resource.lower()} down to the works."]
    if act == "returning":
        return ["Back for another load."]
    if act == "waiting":
        return ["Nothing needs moving just now."]
    if act == "working":
        if "factory" in occ.lower() or "Factory" in occ:
            return ["The works are running steadily."]
        return [f"Steady work at {place}."]
    if "Woodcutter" in occ:
        return ["Timber comes off the woodland edge."]
    if "Miner" in occ:
        return ["The ridge has been productive today."]
    if "Clay" in occ:
        return ["Clay comes up from the pits at the edge of town."]
    if "Shepherd" in occ or "Field" in occ:
        return ["The land around the settlement keeps us supplied."]
    if "Factory" in occ or "Works" in occ:
        return ["The works are running steadily."]
    name = str(person.get("display_name") or person.get("name") or "")
    if name and not name.startswith("person:"):
        return [f"Just another day in the settlement."]
    return ["The settlement keeps us busy."]


def build_village_layout_sites(
    *,
    board: HexBoard,
    node_id: str,
    buildings: dict[str, dict[str, Any]],
    width: int = BASE_SIZE,
    height: int = BASE_SIZE,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Compute durable anchors + fx_industry site rows for buildings on a node.

    Returns (building_anchors, industry_sites).
    """
    anchors: dict[str, dict[str, Any]] = {}
    sites: list[dict[str, Any]] = []
    used_sectors: set[str] = set()
    core_index: dict[str, int] = {"processor": 0, "factory": 0, "warehouse": 0, "centre": 0}

    # Primaries first — perimeter by touching hex orientation.
    primaries = [
        (bid, b)
        for bid, b in sorted(buildings.items())
        if b.get("node_id") == node_id
        and str(b.get("slot_kind") or "") == "primary"
        and b.get("active", True)
    ]
    for bid, b in primaries:
        hid = str(b.get("hex_id") or "")
        terrain = str(b.get("terrain") or "")
        if hid:
            sector = hex_sector(board, node_id, hid)
        else:
            sector = "northwest"
        # Avoid stacking two primaries on the exact same sector.
        if sector in used_sectors:
            for alt in ("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"):
                if alt not in used_sectors:
                    sector = alt
                    break
        used_sectors.add(sector)
        anchor = perimeter_anchor(width, height, sector, footprint=FOOTPRINT_PRIMARY)
        anchor["presentation"] = "primary_site"
        anchor["terrain"] = terrain
        anchors[str(bid)] = anchor
        label = str(b.get("label") or PRIMARY_LABEL.get(terrain) or "Resource site")
        sites.append(
            {
                "id": str(bid),
                "kind": "source",
                "label": label,
                "grid": list(anchor["grid"]),
                "entrance": list(anchor["entrance"]),
                "approach": list(anchor["approach"]),
                "footprint": list(anchor["footprint"]),
                "terrain": terrain,
                "sector": sector,
                "presentation": "primary_site",
            }
        )

    # Core buildings.
    for bid, b in sorted(buildings.items()):
        if b.get("node_id") != node_id or not b.get("active", True):
            continue
        slot = str(b.get("slot_kind") or "")
        if slot == "primary":
            continue
        if str(bid) in anchors:
            continue
        idx = core_index.get(slot, 0)
        core_index[slot] = idx + 1
        anchor = core_anchor(width, height, slot or "processor", idx)
        # Nudge if overlapping existing footprint cells.
        anchor = _avoid_overlap(anchor, anchors, width, height)
        anchors[str(bid)] = anchor
        kind = {"processor": "processor", "factory": "factory", "warehouse": "warehouse", "centre": "centre"}.get(
            slot, "building"
        )
        sites.append(
            {
                "id": str(bid),
                "kind": kind,
                "label": str(b.get("label") or slot.title()),
                "grid": list(anchor["grid"]),
                "entrance": list(anchor["entrance"]),
                "approach": list(anchor["approach"]),
                "footprint": list(anchor["footprint"]),
                "sector": "core",
                "presentation": "structure",
            }
        )

    return anchors, sites


def _avoid_overlap(
    candidate: dict[str, Any],
    existing: dict[str, dict[str, Any]],
    width: int,
    height: int,
) -> dict[str, Any]:
    fw, fh = int(candidate["footprint"][0]), int(candidate["footprint"][1])

    def cells(origin: list[int], footprint: list[int]) -> set[tuple[int, int]]:
        ox, oy = int(origin[0]), int(origin[1])
        w, h = int(footprint[0]), int(footprint[1])
        return {(ox + dx, oy + dy) for dx in range(w) for dy in range(h)}

    occupied: set[tuple[int, int]] = set()
    for anchor in existing.values():
        occupied |= cells(list(anchor.get("grid") or [0, 0]), list(anchor.get("footprint") or [3, 3]))

    ox, oy = int(candidate["grid"][0]), int(candidate["grid"][1])
    for dy in range(0, 12, 4):
        for dx in range(0, 12, 4):
            for sx, sy in ((ox + dx, oy + dy), (ox - dx, oy + dy), (ox + dx, oy - dy)):
                if sx < 6 or sy < 8 or sx + fw >= width - 6 or sy + fh >= height - 8:
                    continue
                trial_cells = cells([sx, sy], [fw, fh])
                if trial_cells.isdisjoint(occupied):
                    entrance = [sx + fw // 2, sy + fh]
                    approach = [entrance[0], entrance[1] + 1]
                    out = dict(candidate)
                    out["grid"] = [sx, sy]
                    out["entrance"] = entrance
                    out["approach"] = approach
                    return out
    return candidate


def apply_anchors_to_local_projection(
    state: Any,
    node_id: str,
    anchors: dict[str, dict[str, Any]],
    *,
    seed: str | int | None = None,
    width: int = BASE_SIZE,
    height: int = BASE_SIZE,
) -> dict[str, Any]:
    """Write/replace LocalProjection building anchors for the settlement spatial grammar."""
    board = state.board if isinstance(state.board, dict) else {}
    store = board.setdefault("local_projections", {})
    centre = [width // 2, height // 2]
    record = {
        "schema_version": LAYOUT_SCHEMA_VERSION,
        "node_id": node_id,
        "seed": str(seed or f"{getattr(state, 'world_id', 'world')}:{node_id}:v2"),
        "width": width,
        "height": height,
        "centre": centre,
        "buildings": {bid: dict(anchor) for bid, anchor in anchors.items()},
        "people_anchors": {},
        "cart_anchors": {},
        "unit_anchors": {},
        "objects": {},
        "exits": [
            {"id": "exit.north", "grid": [centre[0], 1], "direction": "north", "to": "overworld"},
            {"id": "exit.south", "grid": [centre[0], height - 2], "direction": "south", "to": "overworld"},
            {"id": "exit.east", "grid": [width - 2, centre[1]], "direction": "east", "to": "overworld"},
            {"id": "exit.west", "grid": [1, centre[1]], "direction": "west", "to": "overworld"},
        ],
        "destroyed_ids": [],
        "overrides": {},
        "edits": [{"kind": "settlement_spatial_grammar", "version": LAYOUT_SCHEMA_VERSION}],
        "spatial_grammar": "perimeter_primary_core_civic",
    }
    # People near workplaces.
    for person_id, person in (state.people or {}).items():
        if person.get("node_id") != node_id or not person.get("alive", True):
            continue
        workplace = str(person.get("workplace_id") or "")
        if workplace in anchors:
            approach = list(anchors[workplace].get("approach") or anchors[workplace]["grid"])
            record["people_anchors"][str(person_id)] = {"grid": approach, "workplace_id": workplace}
        else:
            record["people_anchors"][str(person_id)] = {"grid": [centre[0], centre[1] + 4]}
    store[node_id] = record
    state.board = board
    return record

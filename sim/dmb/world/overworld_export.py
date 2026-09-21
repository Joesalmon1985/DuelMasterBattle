"""Export LocalProjectionService layouts as Overworld area dicts.

Production path: project_node(node_id) → same-sized LocalArea for every
strategic board node. Presentation-only — never invents durable world truth.
"""

from __future__ import annotations

from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.world.projection import LocalProjectionService
from sim.dmb.world.settlement_layout import (
    PRIMARY_PROP_MARKERS,
    PRIMARY_TILE_CHARS,
    baseline_dialogue,
    public_occupation_for,
)


def export_overworld_area(
    state: WorldState,
    node_id: str | None = None,
    *,
    seed: int | str | None = None,
) -> dict[str, Any]:
    """Build rows + entities for the player's current (or requested) node."""
    player_area = str((state.player or {}).get("area_id") or "")
    if player_area == "area.sluice":
        return _export_archived_sluice_area(state)

    node_id = str(node_id or state.player.get("node_id") or "")
    if not node_id:
        raise ValueError("export_overworld_area requires a node_id")

    # Point industry presentation at this node's routes when available.
    by_node = (state.board or {}).get("fx_industry_by_node") or {}
    if node_id in by_node:
        state.board["fx_industry"] = dict(by_node[node_id])

    proj = LocalProjectionService(state)
    layout = proj.ensure_layout(node_id, seed=seed or f"{state.world_id}:{node_id}")
    view = proj.project(node_id)

    width = int(view.get("width") or layout.get("width") or 48)
    height = int(view.get("height") or layout.get("height") or 48)
    rows = [["."] * width for _ in range(height)]
    cx, cy = width // 2, height // 2

    # Geography patches from touching hexes (before paths so trails overlay).
    for patch in view.get("geography") or layout.get("geography") or []:
        gx, gy = int(patch["grid"][0]), int(patch["grid"][1])
        fw, fh = int(patch["footprint"][0]), int(patch["footprint"][1])
        tile = str(patch.get("tile") or ".")
        for dy in range(fh):
            for dx in range(fw):
                x, y = gx + dx, gy + dy
                if 0 <= x < width and 0 <= y < height and rows[y][x] not in {"#", "D"}:
                    rows[y][x] = tile

    # Paths only toward real topology exits — no artificial N/E/S/W cross.
    for exit_rec in view.get("exits") or []:
        eg = exit_rec.get("grid") or [cx, 1]
        ex, ey = int(eg[0]), int(eg[1])
        passage = str(exit_rec.get("passage") or "trail")
        # Constructed roads use '=' ; ordinary topology uses trail ':'.
        road_char = "=" if passage == "road" else ":"
        x, y = cx, cy
        for _ in range(max(width, height) * 2):
            if 0 <= x < width and 0 <= y < height and rows[y][x] not in {"#", "D"}:
                rows[y][x] = road_char
            if (x, y) == (ex, ey):
                break
            if abs(ex - x) >= abs(ey - y):
                x += 1 if ex > x else -1 if ex < x else 0
            else:
                y += 1 if ey > y else -1 if ey < y else 0
        if 0 <= ex < width and 0 <= ey < height:
            rows[ey][ex] = road_char

    entities: list[dict[str, Any]] = []
    for building in view.get("buildings") or []:
        bid = str(building["id"])
        building_rec = state.buildings.get(bid) or {}
        if building_rec.get("status") == "destroyed" or not building_rec.get("active", True):
            continue
        grid = building.get("grid") or [0, 0]
        footprint = building.get("footprint") or [3, 3]
        gx, gy = int(grid[0]), int(grid[1])
        fw, fh = int(footprint[0]), int(footprint[1])
        slot_kind = str(building_rec.get("slot_kind") or "")
        terrain = str(building_rec.get("terrain") or "")
        presentation = str(
            (layout.get("buildings") or {}).get(bid, {}).get("presentation")
            or ("primary_site" if slot_kind == "primary" else "structure")
        )
        label = _clean_building_label(building_rec, slot_kind)
        from sim.dmb.industry.projection import IndustryProjection

        obs = IndustryProjection(state).player_building_observation(bid)

        if presentation == "primary_site" or slot_kind == "primary":
            tile_ch = PRIMARY_TILE_CHARS.get(terrain, "r")
            for dy in range(fh):
                for dx in range(fw):
                    x, y = gx + dx, gy + dy
                    if 0 <= x < width and 0 <= y < height and rows[y][x] not in {":", "="}:
                        rows[y][x] = tile_ch if tile_ch != "." else ","
            entrance = building.get("entrance") or [gx + fw // 2, gy + fh]
            approach = building.get("approach") or [entrance[0], entrance[1] + 1]
            ax, ay = int(approach[0]), int(approach[1])
            entities.append(
                {
                    "kind": "sign",
                    "id": bid,
                    "pos": [ax, ay],
                    "marker": PRIMARY_PROP_MARKERS.get(terrain, "sign"),
                    "text": label,
                    "building": bid,
                    "bridge_entity": True,
                    "semantic": {
                        "knowledge_key": bid,
                        "interaction": "building",
                        "dismiss_on_move": True,
                        "labels": [{"level": 0, "text": label}],
                        "observe_far": str(obs.get("observe_far") or f"{label} lies at the landscape edge."),
                        "observe_near": str(obs.get("observe_near") or ""),
                    },
                }
            )
            continue

        for dy in range(fh):
            for dx in range(fw):
                x, y = gx + dx, gy + dy
                if 0 <= x < width and 0 <= y < height:
                    rows[y][x] = "#"
        entrance = building.get("entrance") or [gx + fw // 2, gy + fh]
        approach = building.get("approach") or [entrance[0], entrance[1] + 1]
        ex, ey = int(entrance[0]), int(entrance[1])
        ax, ay = int(approach[0]), int(approach[1])
        if 0 <= ex < width and 0 <= ey < height:
            rows[ey][ex] = "D"
        entities.append(
            {
                "kind": "door",
                "id": bid,
                "pos": [ax, ay],
                "marker": "door_closed",
                "text": label,
                "building": bid,
                "bridge_entity": True,
                "semantic": {
                    "knowledge_key": bid,
                    "interaction": "building",
                    "dismiss_on_move": True,
                    "labels": [{"level": 0, "text": label}],
                    "observe_far": str(obs.get("observe_far") or f"{label} stands here."),
                    "observe_near": str(obs.get("observe_near") or ""),
                },
            }
        )

    industry_people = _industry_person_ids(state, node_id)
    for person_view in view.get("people") or []:
        pid = str(person_view["id"])
        if pid in industry_people:
            continue
        person = state.people.get(pid) or {}
        if person.get("node_id") and person.get("node_id") != node_id:
            continue
        grid = person_view.get("grid") or person.get("grid") or [cx, cy + 2]
        px, py = int(grid[0]), int(grid[1])
        display = str(person.get("display_name") or person.get("name") or "Villager")
        from sim.dmb.world.fx_village_world import person_sprite_for

        sprite = person_sprite_for(person)
        workplace = state.buildings.get(str(person.get("workplace_id") or "")) or {}
        occupation = public_occupation_for(person, workplace=workplace)
        known = (state.knowledge or {}).get(pid) or {}
        label_text = str(known.get("name") or display)
        if label_text.startswith("person:") or label_text.startswith("Worker-"):
            label_text = occupation
        standing = occupation if not known.get("name") else label_text
        entities.append(
            {
                "kind": "npc",
                "id": pid,
                "pos": [px, py + 1],
                "name": display if not display.startswith("Worker-") else occupation,
                "sprite": sprite,
                "facing": "down",
                "lines": _opening_lines(state, pid),
                "bridge_entity": True,
                "bridge_talk": True,
                "semantic": {
                    "knowledge_key": pid,
                    "interaction": "npc",
                    "dismiss_on_move": True,
                    "labels": [
                        {"level": 0, "text": standing},
                        {"level": 1, "text": label_text},
                    ],
                    "observe_far": f"Someone stands here — a {occupation.lower()}.",
                    "observe_near": f"You can speak with this {occupation.lower()}.",
                },
            }
        )

    for cart in view.get("carts") or []:
        cid = str(cart.get("id") or "")
        if not cid:
            continue
        grid = cart.get("grid") or [cx + 2, cy]
        entities.append(
            {
                "kind": "deco",
                "id": cid,
                "pos": [int(grid[0]), int(grid[1])],
                "marker": "box",
                "bridge_entity": True,
                "dynamic": True,
                "semantic": {
                    "knowledge_key": cid,
                    "interaction": "cart",
                    "labels": [{"level": 0, "text": "Cart"}],
                },
            }
        )

    for unit in view.get("units") or []:
        uid = str(unit.get("id") or "")
        if not uid:
            continue
        unit_rec = (state.units or {}).get(uid) or {}
        person_id = str(unit_rec.get("person_id") or "")
        person = (state.people or {}).get(person_id) or {}
        label = str(person.get("name") or unit_rec.get("label") or "Soldier")
        if label.startswith("person:"):
            label = "Soldier"
        grid = unit.get("grid") or [cx - 2, cy]
        entities.append(
            {
                "kind": "npc",
                "id": person_id or uid,
                "pos": [int(grid[0]), int(grid[1])],
                "name": label,
                "sprite": str(person.get("sprite") or "worker"),
                "facing": "down",
                "bridge_entity": True,
                "dynamic": True,
                "semantic": {
                    "knowledge_key": person_id or uid,
                    "interaction": "npc",
                    "labels": [{"level": 0, "text": label}],
                },
            }
        )

    for exit_rec in view.get("exits") or []:
        eg = exit_rec.get("grid") or [0, 0]
        direction = str(exit_rec.get("direction") or "north")
        to_node = str(exit_rec.get("to_node") or exit_rec.get("to") or "")
        interactive = bool(exit_rec.get("interactive", to_node.startswith("node:")))
        passage = str(exit_rec.get("passage") or "trail")
        label = str(exit_rec.get("label") or f"Path {direction}")
        dest_label = str(exit_rec.get("dest_label") or "")
        far = f"The {'road' if passage == 'road' else 'path'} leads {direction}."
        if dest_label and dest_label != "Wilderness":
            far = f"The {'road' if passage == 'road' else 'path'} leads {direction} toward {dest_label}."
        entity = {
            "kind": "exit",
            "id": str(exit_rec.get("id") or f"exit.{direction}"),
            "pos": [int(eg[0]), int(eg[1])],
            "to_area": to_node if interactive else "",
            "to_node": to_node if interactive else "",
            "from_node": str(exit_rec.get("from_node") or node_id),
            "direction": direction,
            "travel_text": far,
            "bridge_entity": interactive,
            "bridge_travel": interactive,
            "text": label,
            "passage": passage,
        }
        if interactive:
            # Quiet labels: only show when focused/near (Godot still gets semantic).
            entity["semantic"] = {
                "knowledge_key": str(exit_rec.get("id") or f"exit.{direction}"),
                "interaction": "travel",
                "dismiss_on_move": True,
                "labels": [{"level": 0, "text": label}],
                "observe_far": far,
                "observe_near": "Travel along this way to leave for a neighbouring place.",
                "quiet_label": True,
            }
        entities.append(entity)

    player = state.player or {}
    ppos = player.get("position") or [cx, cy + 6]
    node_rec = ((state.board or {}).get("nodes") or {}).get(node_id) or {}
    area_name = str(node_rec.get("label") or "Wilderness")
    kind = str(view.get("kind") or layout.get("kind") or "wilderness")
    return {
        "id": str(node_rec.get("area_id") or f"area.{node_id.replace(':', '_')}"),
        "name": area_name,
        "theme": "grass",
        "rows": ["".join(row) for row in rows],
        "entities": entities,
        "player_start": [int(float(ppos[0])), int(float(ppos[1]))],
        "profile_id": "FX-VILLAGE",
        "quest_id": "",
        "bridge_mode": True,
        "node_id": node_id,
        "node_kind": kind,
        "fx_village": {
            "seed": (state.board.get("g05") or {}).get("seed"),
            "node_id": node_id,
            "mode": "full_prehistoric_world",
            "quest_enabled": False,
        },
        "width": width,
        "height": height,
    }


def _clean_building_label(building_rec: dict[str, Any], slot_kind: str) -> str:
    label = str(building_rec.get("label") or "")
    for suffix in (" (quiet)", " (working)"):
        label = label.replace(suffix, "")
    if not label or label.startswith("building:"):
        label = {
            "primary": "Resource site",
            "processor": "Works",
            "factory": "Factory",
            "centre": "Settlement Centre",
            "warehouse": "Warehouse",
        }.get(slot_kind, "Building")
    return label


def _industry_person_ids(state: WorldState, node_id: str) -> set[str]:
    from sim.dmb.industry.projection import IndustryProjection

    return {
        str(row.get("person_id"))
        for row in IndustryProjection(state).workers(node_id=node_id)
        if row.get("person_id")
    }


def _opening_lines(state: WorldState, person_id: str) -> list[str]:
    person = state.people.get(person_id) or {}
    workplace = state.buildings.get(str(person.get("workplace_id") or "")) or {}
    occupation = public_occupation_for(person, workplace=workplace)
    activity = "idle"
    resource_label = None
    try:
        from sim.dmb.industry.projection import IndustryProjection

        for row in IndustryProjection(state).workers():
            if str(row.get("person_id")) == person_id:
                activity = str(row.get("activity") or "idle")
                resource_label = row.get("resource_label")
                occupation = str(row.get("public_occupation") or row.get("occupation") or occupation)
                break
    except Exception:
        pass
    lines = baseline_dialogue(
        person,
        occupation=occupation,
        activity=activity,
        resource_label=str(resource_label) if resource_label else None,
        workplace_label=str(workplace.get("label") or "") or None,
    )
    cleaned = []
    for line in lines:
        low = line.lower()
        if "show you where" in low or "follow me" in low or "blockage" in low:
            continue
        cleaned.append(line)
    return cleaned or ["The land keeps us busy."]

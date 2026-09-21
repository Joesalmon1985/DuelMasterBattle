"""Export LocalProjectionService layouts as Overworld area dicts (G05).

Presentation-only: durable IDs come from Python state. Godot must not invent
people/buildings or write world truth from this payload.
"""

from __future__ import annotations

from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.narrative.dialogue import DialogueResolver
from sim.dmb.narrative.line_catalog import LineCatalog
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
    """Build rows + entities for production Overworld from FX-VILLAGE state."""
    player_area = str((state.player or {}).get("area_id") or "")
    if player_area == "area.sluice":
        return export_sluice_area(state)
    fx = (state.board or {}).get("fx_village") or {}
    quest_enabled = bool(fx.get("quest_enabled"))
    node_id = str(node_id or fx.get("node_id") or state.player.get("node_id") or "node:village")
    proj = LocalProjectionService(state)
    # Ensure durable layout exists (idempotent).
    layout = proj.ensure_layout(node_id, seed=seed or fx.get("seed") or f"{state.world_id}:{node_id}")
    if quest_enabled:
        _ensure_g05_landmarks(state, layout, fx)
    view = proj.project(node_id)

    width = int(view.get("width") or layout.get("width") or 48)
    height = int(view.get("height") or layout.get("height") or 48)
    rows = [["."] * width for _ in range(height)]

    # Soft path cross through centre — roads out of the settlement.
    cx, cy = width // 2, height // 2
    for x in range(width):
        rows[cy][x] = ":"
    for y in range(height):
        rows[y][cx] = ":"

    entities: list[dict[str, Any]] = []
    for building in view.get("buildings") or []:
        bid = str(building["id"])
        building_rec = state.buildings.get(bid) or {}
        if building_rec.get("status") == "destroyed":
            continue
        if not building_rec.get("active", True):
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

        if presentation == "primary_site" or slot_kind == "primary":
            tile_ch = PRIMARY_TILE_CHARS.get(terrain, "r")
            for dy in range(fh):
                for dx in range(fw):
                    x, y = gx + dx, gy + dy
                    if 0 <= x < width and 0 <= y < height:
                        # Keep road cells as road if they cross; otherwise site tiles.
                        if rows[y][x] != ":":
                            rows[y][x] = tile_ch if tile_ch != "." else ","
            # Stacked logs / rocks as work markers (not house doors).
            entrance = building.get("entrance") or [gx + fw // 2, gy + fh]
            approach = building.get("approach") or [entrance[0], entrance[1] + 1]
            ax, ay = int(approach[0]), int(approach[1])
            marker = PRIMARY_PROP_MARKERS.get(terrain, "sign")
            label = _clean_building_label(building_rec, slot_kind)
            from sim.dmb.industry.projection import IndustryProjection

            obs = IndustryProjection(state).player_building_observation(bid)
            entities.append(
                {
                    "kind": "sign",
                    "id": bid,
                    "pos": [ax, ay],
                    "marker": marker,
                    "text": label,
                    "building": bid,
                    "bridge_entity": True,
                    "semantic": {
                        "knowledge_key": bid,
                        "interaction": "building",
                        "dismiss_on_move": True,
                        "labels": [{"level": 0, "text": label}],
                        "observe_far": str(obs.get("observe_far") or f"{label} lies at the settlement edge."),
                        "observe_near": str(obs.get("observe_near") or obs.get("inspect") or ""),
                    },
                }
            )
            continue

        # Ordinary structures: walls + door.
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
        label = _clean_building_label(building_rec, slot_kind)
        from sim.dmb.industry.projection import IndustryProjection

        obs = IndustryProjection(state).player_building_observation(bid)
        observe_far = str(obs.get("observe_far") or f"{label} stands here.")
        observe_near = str(obs.get("observe_near") or observe_far)
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
                    "observe_far": observe_far,
                    "observe_near": observe_near,
                },
            }
        )

    # People — exclude anyone owned by IndustryProjection/WorkerController.
    industry_people = _industry_person_ids(state)
    for person_view in view.get("people") or []:
        pid = str(person_view["id"])
        if pid in industry_people:
            continue
        person = state.people.get(pid) or {}
        grid = person_view.get("grid") or person.get("grid") or person.get("position") or [cx, cy + 2]
        px, py = int(grid[0]), int(grid[1])
        display = str(person.get("display_name") or person.get("name") or "Villager")
        from sim.dmb.world.fx_village_world import person_sprite_for

        sprite = person_sprite_for(person)
        workplace = state.buildings.get(str(person.get("workplace_id") or "")) or {}
        occupation = public_occupation_for(person, workplace=workplace)
        known = (state.knowledge or {}).get(pid) or {}
        label_text = str(known.get("name") or display)
        if label_text.startswith("person:"):
            label_text = occupation
        standing = occupation if not known.get("name") else label_text
        stand = [px, py + 1]
        entities.append(
            {
                "kind": "npc",
                "id": pid,
                "pos": stand,
                "name": display,
                "sprite": sprite,
                "facing": "down",
                "lines": _opening_lines(state, pid),
                "bridge_entity": True,
                "bridge_talk": True,
                "village_test_story": False,
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

    # Demon cube — quest mode only.
    if quest_enabled:
        demon_id = str(fx.get("demon_cube_id") or "cube:demon")
        cubes = ((state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
        cube = cubes.get(demon_id) or {}
        if cube.get("active", True) and cube:
            hid = str(cube.get("hex_id") or fx.get("demon_hex") or "")
            anchors = (state.board or {}).get("hex_anchors") or {}
            grid = (anchors.get(hid) or {}).get("grid") or cube.get("position") or [cx + 6, cy - 4]
            entities.append(
                {
                    "kind": "creature",
                    "id": demon_id,
                    "pos": [int(grid[0]), int(grid[1])],
                    "enemy_id": "cave_troll",
                    "bridge_entity": True,
                    "bridge_challenge": True,
                    "cube_id": demon_id,
                    "intro": "A ridge manifestation blocks the ore path.",
                    "semantic": {
                        "knowledge_key": demon_id,
                        "interaction": "enemy",
                        "labels": [{"level": 0, "text": "Ridge manifestation"}],
                    },
                }
            )

        entrances = ((state.board or {}).get("entrances") or {})
        sluice = entrances.get("entrance:sluice")
        if sluice and sluice.get("active", True):
            sg = sluice.get("grid") or [cx - 8, cy + 4]
            entities.append(
                {
                    "kind": "door",
                    "id": str(sluice.get("id") or "entrance:sluice"),
                    "pos": [int(sg[0]), int(sg[1])],
                    "marker": "door_dungeon",
                    "text": str(sluice.get("label") or "Sluice Works"),
                    "dungeon_id": str(sluice.get("dungeon_id") or "dungeon.sluice"),
                    "bridge_entity": True,
                    "bridge_enter": True,
                    "semantic": {
                        "knowledge_key": "entrance:sluice",
                        "interaction": "entrance",
                        "labels": [{"level": 0, "text": "Sluice Works"}],
                    },
                }
            )

    # Ground items for the current village area only.
    for item_id, item in (state.items or {}).items():
        ground = item.get("ground")
        if not ground or not item.get("alive", True):
            continue
        area_id = str(ground.get("area_id") or "")
        if area_id not in {"", "area.village", str(fx.get("area_id") or "area.village")}:
            continue
        if item.get("quest_bound") and not quest_enabled:
            continue
        pos = ground.get("position") or [cx, cy]
        entities.append(
            {
                "kind": "pickup",
                "id": str(item_id),
                "pos": [int(pos[0]), int(pos[1])],
                "sprite": str(item.get("sprite") or "pendant"),
                "text": str(item.get("label") or item.get("definition_id") or "Item"),
                "bridge_entity": True,
                "bridge_pickup": True,
                "semantic": {
                    "knowledge_key": str(item_id),
                    "interaction": "pickup",
                    "labels": [{"level": 0, "text": str(item.get("label") or "Item")}],
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
        grid = unit.get("grid") or [cx - 2, cy]
        unit_rec = (state.units or {}).get(uid) or {}
        person_id = str(unit_rec.get("person_id") or "")
        person = (state.people or {}).get(person_id) or {}
        label = str(person.get("name") or unit_rec.get("label") or unit_rec.get("definition_id") or "Soldier")
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
                    "labels": [{"level": 0, "text": label if not label.startswith("person:") else "Soldier"}],
                },
            }
        )

    for exit_rec in view.get("exits") or []:
        eg = exit_rec.get("grid") or [0, 0]
        direction = str(exit_rec.get("direction") or "north")
        to_node = str(exit_rec.get("to_node") or exit_rec.get("to") or "")
        interactive = bool(exit_rec.get("interactive", to_node.startswith("node:")))
        label = str(exit_rec.get("label") or f"{direction.title()} path")
        dest_label = str(exit_rec.get("dest_label") or "")
        if dest_label and dest_label not in {"Wilderness", "Settlement", ""}:
            known_label = f"Path to {dest_label}"
        elif dest_label == "Settlement":
            known_label = "Path to the settlement"
        else:
            known_label = label
        far = f"The path leads {direction} out of this place."
        if dest_label:
            far = f"The path leads {direction} toward {dest_label.lower()}."
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
            "text": known_label,
        }
        if interactive:
            entity["semantic"] = {
                "knowledge_key": str(exit_rec.get("id") or f"exit.{direction}"),
                "interaction": "travel",
                "dismiss_on_move": True,
                "labels": [{"level": 0, "text": known_label}],
                "observe_far": far,
                "observe_near": "Travel along this path to leave for a neighbouring place.",
            }
        entities.append(entity)

    player = state.player or {}
    ppos = player.get("position") or [cx, cy + 6]
    node_rec = ((state.board or {}).get("nodes") or {}).get(node_id) or {}
    area_name = str(node_rec.get("label") or fx.get("name") or "Village")
    if node_id == str(fx.get("node_id") or ""):
        area_name = "Village" if not quest_enabled else "FX Village"
    row_strings = ["".join(row) for row in rows]
    return {
        "id": str(node_rec.get("area_id") or "area.fx_village"),
        "name": area_name,
        "theme": "grass" if area_name != "Wilderness" else "path",
        "rows": row_strings,
        "entities": entities,
        "player_start": [int(ppos[0]), int(ppos[1])],
        "profile_id": "FX-VILLAGE-QUEST" if quest_enabled else "FX-VILLAGE",
        "quest_id": str(fx.get("quest_id") or "") if quest_enabled else "",
        "bridge_mode": True,
        "node_id": node_id,
        "fx_village": {
            "mara_id": fx.get("mara_id"),
            "factory_id": fx.get("factory_id"),
            "cause_id": fx.get("cause_id") if quest_enabled else None,
            "quest_id": fx.get("quest_id") if quest_enabled else None,
            "seed": fx.get("seed"),
            "node_id": fx.get("node_id"),
            "mode": fx.get("mode") or ("quest" if quest_enabled else "baseline"),
        },
        "width": width,
        "height": height,
    }


def export_sluice_area(state: WorldState) -> dict[str, Any]:
    """Compact Overworld area for the sluice dungeon / puzzle lease."""
    from sim.dmb.adventure.puzzles import PuzzleService

    width, height = 16, 12
    rows = [["."] * width for _ in range(height)]
    for x in range(width):
        rows[0][x] = "#"
        rows[height - 1][x] = "#"
    for y in range(height):
        rows[y][0] = "#"
        rows[y][width - 1] = "#"
    for x in range(1, width - 1):
        rows[height // 2][x] = ":"
    for y in range(1, height - 1):
        rows[y][width // 2] = ":"

    entities: list[dict[str, Any]] = []
    origin = [2, 2]
    puzzles = PuzzleService(state)
    lease_payload = puzzles.prepare_lease("puzzle.sluice", area_id="area.sluice")
    lease = lease_payload.get("lease") or {}
    checkpoint = lease.get("checkpoint") or {}
    mechanisms = checkpoint.get("mechanisms") or {}
    definition = puzzles.get_definition("puzzle.sluice")
    mech_defs = {str(m["id"]): m for m in definition.get("mechanisms") or []}
    for mid, mech in mechanisms.items():
        mdef = mech_defs.get(mid) or {}
        pos = mech.get("position") or mdef.get("position") or [0, 0]
        gx = origin[0] + int(float(pos[0]))
        gy = origin[1] + int(float(pos[1]))
        kind = str(mech.get("kind") or mdef.get("kind") or "switch")
        marker = {
            "movable_box": "logs",
            "pressure_plate": "pedestal_1",
            "item_receptor": "pedestal_2",
            "gate": "door_closed",
            "switch": "pedestal_3",
        }.get(kind, "pedestal_1")
        entity_kind = "logs" if kind == "movable_box" else ("door" if kind == "gate" else "sign")
        entities.append(
            {
                "kind": entity_kind,
                "id": mid,
                "pos": [gx, gy],
                "marker": marker,
                "text": str(mdef.get("label") or mid.split(".")[-1].replace("_", " ").title()),
                "bridge_entity": True,
                "bridge_puzzle": True,
                "mechanism_id": mid,
                "mechanism_kind": kind,
                "lease_id": lease.get("id"),
                "lease_version": lease.get("version"),
                "semantic": {
                    "knowledge_key": mid,
                    "interaction": "puzzle",
                    "labels": [{"level": 0, "text": str(mdef.get("label") or mid)}],
                },
            }
        )
    for item_id, item in (state.items or {}).items():
        ground = item.get("ground")
        if not ground or ground.get("area_id") != "area.sluice":
            continue
        if not item.get("alive", True):
            continue
        pos = ground.get("position") or [2, 1]
        entities.append(
            {
                "kind": "pickup",
                "id": str(item_id),
                "pos": [origin[0] + int(float(pos[0])), origin[1] + int(float(pos[1]))],
                "sprite": "pendant",
                "text": str(item.get("label") or "Sluice handle"),
                "bridge_entity": True,
                "bridge_pickup": True,
                "semantic": {
                    "knowledge_key": str(item_id),
                    "interaction": "pickup",
                    "labels": [{"level": 0, "text": str(item.get("label") or "Item")}],
                },
            }
        )
    entities.append(
        {
            "kind": "exit",
            "id": "exit.village",
            "pos": [width // 2, height - 2],
            "to_area": "area.village",
            "bridge_entity": True,
            "bridge_return_village": True,
            "text": "Return to village",
        }
    )
    player = state.player or {}
    ppos = player.get("position") or [width // 2, height - 3]
    return {
        "id": "area.sluice",
        "name": "Sluice Works",
        "theme": "dungeon",
        "rows": ["".join(r) for r in rows],
        "entities": entities,
        "player_start": [
            int(ppos[0]) if float(ppos[0]) < width else width // 2,
            int(ppos[1]) if float(ppos[1]) < height else height - 3,
        ],
        "profile_id": "FX-VILLAGE-QUEST",
        "bridge_mode": True,
        "puzzle_lease_id": lease.get("id"),
        "puzzle_lease_version": lease.get("version"),
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


def _ensure_g05_landmarks(state: WorldState, layout: dict[str, Any], fx: dict[str, Any]) -> None:
    board = state.board if isinstance(state.board, dict) else {}
    entrances = board.setdefault("entrances", {})
    if "entrance:sluice" not in entrances:
        centre = layout.get("centre") or [24, 24]
        entrances["entrance:sluice"] = {
            "id": "entrance:sluice",
            "node_id": layout.get("node_id"),
            "grid": [int(centre[0]) - 8, int(centre[1]) + 4],
            "label": "Sluice Works",
            "dungeon_id": "dungeon.sluice",
            "active": True,
        }
    store = board.setdefault("local_projections", {})
    store[str(layout.get("node_id"))] = layout


def _industry_person_ids(state: WorldState) -> set[str]:
    from sim.dmb.industry.projection import IndustryProjection

    return {
        str(row.get("person_id"))
        for row in IndustryProjection(state).workers()
        if row.get("person_id")
    }


def _opening_lines(state: WorldState, person_id: str) -> list[str]:
    """Dialogue from actual Person + world state — quest only when bound/active."""
    person = state.people.get(person_id) or {}
    workplace = state.buildings.get(str(person.get("workplace_id") or "")) or {}
    occupation = public_occupation_for(person, workplace=workplace)
    fx = (state.board or {}).get("fx_village") or {}
    quest_enabled = bool(fx.get("quest_enabled"))
    quest_id = str(fx.get("quest_id") or "")
    cause_id = str(fx.get("cause_id") or "")
    mara_id = str(fx.get("mara_id") or "")

    # Quest-authored dialogue only for genuinely bound active quest stakeholders.
    if quest_enabled and quest_id and person_id == mara_id:
        try:
            catalog = LineCatalog.load()
            resolver = DialogueResolver(state, catalog)
            session = resolver.start(
                speaker_id=person_id,
                quest_id=str(fx.get("quest_template_id") or "quest.factory_shortage"),
                stage=0,
                cause_id=cause_id or "cause.factory_shortage",
                era_id=str((state.board or {}).get("era_id") or "ancient"),
            )
            text = str(session.get("text") or "").strip()
            if text and "show you where" not in text.lower() and "follow me" not in text.lower():
                return [text]
        except Exception:
            pass

    # Industry worker activity when projected.
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
    # Hard ban on unimplemented guide promises.
    cleaned = []
    for line in lines:
        low = line.lower()
        if "show you where" in low or "follow me" in low or "i can guide" in low:
            continue
        cleaned.append(line)
    return cleaned or ["The settlement keeps us busy."]

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
    node_id = str(node_id or fx.get("node_id") or state.player.get("node_id") or "node:village")
    proj = LocalProjectionService(state)
    # Ensure durable layout exists (idempotent).
    layout = proj.ensure_layout(node_id, seed=seed or fx.get("seed") or f"{state.world_id}:{node_id}")
    # Bind demon + sluice entrance into layout objects if missing.
    _ensure_g05_landmarks(state, layout, fx)
    view = proj.project(node_id)

    width = int(view.get("width") or layout.get("width") or 48)
    height = int(view.get("height") or layout.get("height") or 48)
    rows = [["."] * width for _ in range(height)]

    # Soft path cross through centre.
    cx, cy = width // 2, height // 2
    for x in range(width):
        rows[cy][x] = ":"
    for y in range(height):
        rows[y][cx] = ":"

    entities: list[dict[str, Any]] = []
    # Buildings → footprint walls + entrance markers.
    for building in view.get("buildings") or []:
        bid = str(building["id"])
        grid = building.get("grid") or [0, 0]
        footprint = building.get("footprint") or [3, 3]
        gx, gy = int(grid[0]), int(grid[1])
        fw, fh = int(footprint[0]), int(footprint[1])
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
        building = state.buildings.get(bid) or {}
        label = str(building.get("label") or bid)
        is_factory = str(building.get("slot_kind") or "") == "factory" or "factory" in bid
        if is_factory:
            from sim.dmb.industry import fraction

            rates: dict = {}
            for event in reversed((state.industry or {}).get("events") or []):
                if event.get("kind") == "industry_rates":
                    rates = event.get("rates") or {}
                    break
            rate = float(fraction(rates.get(bid) or 0))
            shortage = bool(building.get("shortage")) or rate <= 0
            if shortage:
                label = f"{label} (quiet)"
            else:
                label = f"{label} (working)"
        # Skip primary slots as interactive doors — keep factory + landmarks only.
        if str(building.get("slot_kind") or "") == "primary":
            continue
        if str(building.get("slot_kind") or "") == "processor":
            # Processors are shown via industry layout / WorkerController, not duplicate doors.
            continue
        if str(bid).startswith("source:"):
            continue
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
                    "labels": [{"level": 0, "text": label}],
                },
            }
        )

    # People / Mara.
    for person_view in view.get("people") or []:
        pid = str(person_view["id"])
        person = state.people.get(pid) or {}
        grid = person_view.get("grid") or person.get("grid") or person.get("position") or [cx, cy + 2]
        px, py = int(grid[0]), int(grid[1])
        display = str(person.get("display_name") or person.get("name") or "Person")
        # Stand beside the factory approach so Mara and the door are both selectable.
        stand = [px, py + 1]
        entities.append(
            {
                "kind": "npc",
                "id": pid,
                "pos": stand,
                "name": display,
                "sprite": "worker" if "mara" in display.lower() else "villager_a",
                "facing": "down",
                "lines": _opening_lines(state, pid),
                "bridge_entity": True,
                "bridge_talk": True,
                "village_test_story": False,
                "semantic": {
                    "knowledge_key": pid,
                    "interaction": "npc",
                    "labels": [{"level": 0, "text": "Worker" if not (state.knowledge or {}).get(pid, {}).get("name") else display}],
                },
            }
        )

    # Demon cube.
    cubes = ((state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
    for cube_id, cube in cubes.items():
        if not cube.get("active", True):
            continue
        hid = str(cube.get("hex_id") or "")
        anchors = (state.board or {}).get("hex_anchors") or {}
        grid = (anchors.get(hid) or {}).get("grid") or cube.get("position") or [cx + 6, cy - 4]
        entities.append(
            {
                "kind": "creature",
                "id": str(cube_id),
                "pos": [int(grid[0]), int(grid[1])],
                "enemy_id": "cave_troll",
                "bridge_entity": True,
                "bridge_challenge": True,
                "cube_id": str(cube_id),
                "intro": "A ridge manifestation blocks the ore path.",
                "semantic": {
                    "knowledge_key": str(cube_id),
                    "interaction": "enemy",
                    "labels": [{"level": 0, "text": "Ridge manifestation"}],
                },
            }
        )

    # Sluice dungeon entrance.
    entrances = ((state.board or {}).get("entrances") or {})
    sluice = entrances.get("entrance:sluice") or {
        "id": "entrance:sluice",
        "grid": [cx - 8, cy + 4],
        "label": "Sluice works",
        "dungeon_id": "dungeon.sluice",
    }
    sg = sluice.get("grid") or [cx - 8, cy + 4]
    entities.append(
        {
            "kind": "door",
            "id": str(sluice.get("id") or "entrance:sluice"),
            "pos": [int(sg[0]), int(sg[1])],
            "marker": "door_dungeon",
            "text": str(sluice.get("label") or "Sluice works"),
            "dungeon_id": str(sluice.get("dungeon_id") or "dungeon.sluice"),
            "bridge_entity": True,
            "bridge_enter": True,
            "semantic": {
                "knowledge_key": "entrance:sluice",
                "interaction": "entrance",
                "labels": [{"level": 0, "text": "Sluice works"}],
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

    # Live carts / units from LocalProjectionService (durable IDs; WorkerController owns carriers).
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
        label = str(unit_rec.get("label") or unit_rec.get("definition_id") or "Unit")
        entities.append(
            {
                "kind": "npc",
                "id": uid,
                "pos": [int(grid[0]), int(grid[1])],
                "name": label,
                "sprite": "soldier",
                "facing": "down",
                "bridge_entity": True,
                "dynamic": True,
                "semantic": {
                    "knowledge_key": uid,
                    "interaction": "unit",
                    "labels": [{"level": 0, "text": label}],
                },
            }
        )

    # Exits.
    for exit_rec in view.get("exits") or []:
        eg = exit_rec.get("grid") or [0, 0]
        entities.append(
            {
                "kind": "exit",
                "id": str(exit_rec.get("id") or "exit"),
                "pos": [int(eg[0]), int(eg[1])],
                "to_area": str(exit_rec.get("to") or "overworld"),
                "bridge_entity": True,
            }
        )

    player = state.player or {}
    ppos = player.get("position") or [cx, cy + 6]
    row_strings = ["".join(row) for row in rows]
    return {
        "id": "area.fx_village",
        "name": "FX Village",
        "theme": "grass",
        "rows": row_strings,
        "entities": entities,
        "player_start": [int(ppos[0]), int(ppos[1])],
        "profile_id": "FX-VILLAGE",
        "quest_id": str(fx.get("quest_id") or ""),
        "bridge_mode": True,
        "fx_village": {
            "mara_id": fx.get("mara_id"),
            "factory_id": fx.get("factory_id"),
            "cause_id": fx.get("cause_id"),
            "quest_id": fx.get("quest_id"),
            "seed": fx.get("seed"),
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
    # Open corridor
    for x in range(1, width - 1):
        rows[height // 2][x] = ":"
    for y in range(1, height - 1):
        rows[y][width // 2] = ":"

    entities: list[dict[str, Any]] = []
    origin = [2, 2]
    # Ensure lease exists so mechanism poses are authoritative.
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
    # Ground handle in workshop corner.
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
    # Exit back to village.
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
        "player_start": [int(ppos[0]) if float(ppos[0]) < width else width // 2, int(ppos[1]) if float(ppos[1]) < height else height - 3],
        "profile_id": "FX-VILLAGE",
        "bridge_mode": True,
        "puzzle_lease_id": lease.get("id"),
        "puzzle_lease_version": lease.get("version"),
        "width": width,
        "height": height,
    }


def _ensure_g05_landmarks(state: WorldState, layout: dict[str, Any], fx: dict[str, Any]) -> None:
    board = state.board if isinstance(state.board, dict) else {}
    entrances = board.setdefault("entrances", {})
    if "entrance:sluice" not in entrances:
        centre = layout.get("centre") or [24, 24]
        entrances["entrance:sluice"] = {
            "id": "entrance:sluice",
            "node_id": layout.get("node_id"),
            "grid": [int(centre[0]) - 8, int(centre[1]) + 4],
            "label": "Sluice works",
            "dungeon_id": "dungeon.sluice",
            "active": True,
        }
    # Persist layout edits.
    store = board.setdefault("local_projections", {})
    store[str(layout.get("node_id"))] = layout


def _opening_lines(state: WorldState, person_id: str) -> list[str]:
    """Authored dialogue lines from DialogueResolver; never debug facts."""
    try:
        catalog = LineCatalog.load()
        resolver = DialogueResolver(state, catalog)
        fx = (state.board or {}).get("fx_village") or {}
        session = resolver.start(
            speaker_id=person_id,
            quest_id=str(fx.get("quest_template_id") or "quest.factory_shortage"),
            stage=0,
            cause_id="cause.factory_shortage",
            era_id=str((state.board or {}).get("era_id") or "ancient"),
        )
        text = str(session.get("text") or "").strip()
        if text:
            return [text]
    except Exception:
        pass
    return ["The yard has gone quiet."]

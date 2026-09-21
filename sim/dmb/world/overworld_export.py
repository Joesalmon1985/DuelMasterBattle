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
    # Dense fill uses walkable ground chars plus sparse solids so exits stay open.
    for patch in view.get("geography") or layout.get("geography") or []:
        _paint_geography_patch(rows, patch, width, height)

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
        cart_rec = (state.carts or {}).get(cid) or {}
        grid = cart.get("grid") or [cx + 2, cy]
        cargo_goods = []
        for lot in cart_rec.get("cargo_lots") or []:
            if str(lot.get("status") or "") not in {"aboard", "loaded", ""}:
                # still show aboard / default
                if str(lot.get("physical_container") or "") != cid:
                    continue
            good = str(lot.get("good_id") or "")
            if good:
                cargo_goods.append(good)
        faction_id = str(cart_rec.get("owner_faction") or cart_rec.get("faction_id") or "")
        route = list(cart_rec.get("route") or [])
        status = str(cart_rec.get("status") or "idle")
        cargo_label = "+".join(g.title() for g in cargo_goods) if cargo_goods else "empty"
        entities.append(
            {
                "kind": "cart",
                "id": cid,
                "pos": [int(grid[0]), int(grid[1])],
                "faction_id": faction_id,
                "status": status,
                "cargo": cargo_goods,
                "route": route,
                "bridge_entity": True,
                "dynamic": True,
                "presentation": "cart",
                "semantic": {
                    "knowledge_key": cid,
                    "interaction": "cart",
                    "labels": [
                        {"level": 0, "text": "Cart"},
                        {"level": 1, "text": f"Cart — {cargo_label}"},
                    ],
                    "observe_far": "A cart stands on the way.",
                    "observe_near": (
                        f"Cart carrying {cargo_label}."
                        if cargo_goods
                        else "An empty cart waits here."
                    ),
                },
            }
        )

    soldier_index = 0
    for unit in view.get("units") or []:
        uid = str(unit.get("id") or "")
        if not uid:
            continue
        unit_rec = (state.units or {}).get(uid) or {}
        if unit_rec.get("status") == "dead" or not unit_rec.get("alive", True):
            continue
        person_id = str(unit_rec.get("person_id") or "")
        person = (state.people or {}).get(person_id) or {}
        archetype = str(unit_rec.get("archetype") or "")
        def_id = str(unit_rec.get("definition_id") or "")
        if not archetype:
            low = def_id.lower()
            if "skirmish" in low:
                archetype = "skirmisher"
            elif "heavy" in low:
                archetype = "heavy"
            else:
                archetype = "line"
        faction_id = str(unit_rec.get("faction_id") or "")
        person_name = str(person.get("name") or unit_rec.get("person_name") or "")
        if person_name.startswith("person:"):
            person_name = ""
        label = {
            "skirmisher": "Skirmisher",
            "line": "Line",
            "heavy": "Heavy",
        }.get(archetype, "Soldier")
        grid = unit.get("grid") or unit_rec.get("position") or [cx - 2, cy]
        try:
            gx = int(float(grid[0]))
            gy = int(float(grid[1]))
        except (TypeError, ValueError, IndexError):
            gx, gy = cx - 2, cy
        if gx < 0 or gx >= width or gy < 0 or gy >= height or (gx, gy) == (cx, cy):
            gx = cx - 4 + (soldier_index % 5) * 2
            gy = cy + 2 + (soldier_index // 5) * 2
        soldier_index += 1
        entities.append(
            {
                "kind": "soldier",
                "id": uid,
                "unit_id": uid,
                "person_id": person_id,
                "pos": [gx, gy],
                "faction_id": faction_id,
                "archetype": archetype,
                "definition_id": def_id,
                "name": person_name or label,
                "bridge_entity": True,
                "dynamic": True,
                "presentation": "soldier",
                "semantic": {
                    "knowledge_key": person_id or uid,
                    "interaction": "soldier",
                    "unit_id": uid,
                    "person_id": person_id,
                    "labels": [
                        {"level": 0, "text": label},
                        {"level": 1, "text": f"{label} — {person_name}" if person_name else label},
                    ],
                    "observe_far": f"A {label.lower()} stands ready.",
                    "observe_near": (
                        f"You can speak with this {label.lower()}"
                        + (f", {person_name}." if person_name else ".")
                    ),
                },
            }
        )

    # Catastrophe cubes whose hex touches this node — one cube_id, not cloned authority.
    touching = set((state.board.get("node_hexes") or {}).get(node_id) or [])
    cubes = ((state.hazards or {}).get("catastrophe") or {}).get("cubes") or {}
    for cube_id, cube in sorted(cubes.items()):
        if not cube.get("active", True):
            continue
        hex_id = str(cube.get("hex_id") or "")
        if hex_id not in touching:
            continue
        # Place near the geography sector matching the hex, else rim.
        hx, hy = cx, 2
        for patch in view.get("geography") or []:
            if str(patch.get("hex_id") or "") == hex_id:
                g = patch.get("grid") or [cx, 2]
                hx, hy = int(g[0]) + 1, int(g[1]) + 1
                break
        htype = str(cube.get("type") or "demon")
        entities.append(
            {
                "kind": "hazard",
                "id": cube_id,
                "cube_id": cube_id,
                "hex_id": hex_id,
                "hazard_type": htype,
                "pos": [max(1, min(width - 2, hx)), max(1, min(height - 2, hy))],
                "bridge_entity": True,
                "bridge_challenge": htype != "pollution",
                "dynamic": True,
                "presentation": "hazard",
                "semantic": {
                    "knowledge_key": cube_id,
                    "interaction": "hazard",
                    "labels": [{"level": 0, "text": htype.replace("_", " ").title()}],
                    "observe_far": "A dangerous manifestation fouls this ground.",
                    "observe_near": "You may Challenge this manifestation.",
                },
            }
        )

    # Construction orders on this node / incident edges.
    for order_id, order in sorted((state.orders or {}).items()):
        if str(order.get("status") or "") not in {"ready", "reserved", "in_progress", "delivering"}:
            continue
        edge = order.get("target_edge")
        target_node = str(order.get("target_node") or "")
        target_building = str(order.get("target_building") or "")
        action = str(order.get("action") or "build")
        show = False
        pos = [cx, cy]
        if isinstance(edge, (list, tuple)) and len(edge) == 2:
            a, b = str(edge[0]), str(edge[1])
            if node_id in {a, b}:
                show = True
                # Midway toward the other endpoint exit.
                other = b if a == node_id else a
                for exit_rec in view.get("exits") or []:
                    if str(exit_rec.get("to_node")) == other:
                        eg = exit_rec.get("grid") or [cx, cy]
                        pos = [int((cx + int(eg[0])) / 2), int((cy + int(eg[1])) / 2)]
                        break
        elif target_node == node_id or (
            target_building and str((state.buildings.get(target_building) or {}).get("node_id") or "") == node_id
        ):
            show = True
            if target_building and target_building in (layout.get("buildings") or {}):
                g = (layout["buildings"][target_building] or {}).get("grid") or [cx, cy]
                pos = [int(g[0]), int(g[1])]
        if not show:
            continue
        entities.append(
            {
                "kind": "construction",
                "id": order_id,
                "order_id": order_id,
                "action": action,
                "pos": pos,
                "faction_id": str(order.get("faction_id") or ""),
                "bridge_entity": True,
                "dynamic": True,
                "presentation": "construction",
                "semantic": {
                    "knowledge_key": order_id,
                    "interaction": "construction",
                    "labels": [{"level": 0, "text": f"Building {action}"}],
                    "observe_far": "Construction is underway.",
                    "observe_near": f"A {action} order is ready here.",
                },
            }
        )

    # Industry factory meters / processor recipe for presentation overlays.
    industry_overlay: list[dict[str, Any]] = []
    try:
        from sim.dmb.industry.projection import IndustryProjection

        ip = IndustryProjection(state)
        for row in ip.factory_readout():
            fid = str(row.get("factory_id") or "")
            b = state.buildings.get(fid) or {}
            if str(b.get("node_id") or "") != node_id:
                continue
            anchor = (layout.get("buildings") or {}).get(fid) or {}
            grid = anchor.get("grid") or [cx, cy]
            industry_overlay.append(
                {
                    "kind": "factory_meter",
                    "building_id": fid,
                    "grid": list(grid),
                    "unit_label": row.get("unit_label"),
                    "meter_progress": row.get("meter_progress"),
                    "meter_pct": row.get("meter_pct"),
                    "bottleneck_reason": row.get("bottleneck_reason"),
                    "unit_def_id": row.get("unit_def_id"),
                }
            )
        fx = state.board.get("fx_industry") or {}
        proc_id = str(fx.get("processor_id") or "")
        if proc_id and str((state.buildings.get(proc_id) or {}).get("node_id") or "") == node_id:
            proc = (state.industry.get("processors") or {}).get(proc_id) or {}
            recipe_id = str(proc.get("recipe_id") or fx.get("recipe_id") or "")
            industry_overlay.append(
                {
                    "kind": "processor_recipe",
                    "building_id": proc_id,
                    "recipe_id": recipe_id,
                    "output_name": fx.get("output_name"),
                    "input_a_channel_id": proc.get("input_a_channel_id"),
                    "input_b_channel_id": proc.get("input_b_channel_id"),
                }
            )
    except Exception:
        pass

    # Natural props + sector labels (presentation only; animals are non-interactive).
    _emit_natural_entities(entities, view.get("geography") or layout.get("geography") or [], width, height)

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
        "industry_overlay": industry_overlay,
        "fx_village": {
            "seed": (state.board.get("g05") or {}).get("seed"),
            "node_id": node_id,
            "mode": str((state.board.get("g05") or {}).get("mode") or "full_prehistoric_world"),
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


_TERRAIN_GROUND = {
    "woodland": ",",
    "clay_mountains": "c",
    "ore_mountains": ".",
    "fields": ",",
    "grazing_land": "g",
    "desert": "d",
}

_TERRAIN_ACCENT = {
    "woodland": "T",
    "clay_mountains": "r",
    "ore_mountains": "r",
    "fields": "f",
    "grazing_land": ",",
    "desert": ".",
}


def _paint_geography_patch(
    rows: list[list[str]],
    patch: dict[str, Any],
    width: int,
    height: int,
) -> None:
    """Fill a sector densely from touching-hex terrain without sealing exits."""
    import hashlib

    gx, gy = int(patch["grid"][0]), int(patch["grid"][1])
    fw, fh = int(patch["footprint"][0]), int(patch["footprint"][1])
    terrain = str(patch.get("terrain") or "fields")
    ground = _TERRAIN_GROUND.get(terrain, str(patch.get("tile") or "."))
    accent = _TERRAIN_ACCENT.get(terrain, ground)
    digest = hashlib.sha256(f"{patch.get('hex_id')}:{terrain}:paint".encode()).digest()
    for dy in range(fh):
        for dx in range(fw):
            x, y = gx + dx, gy + dy
            if not (0 <= x < width and 0 <= y < height):
                continue
            if rows[y][x] in {"#", "D"}:
                continue
            # Stable sparse accent so solid tiles never fill the sector solidly.
            pick = digest[(dy * fw + dx) % len(digest)]
            if terrain == "fields":
                # Striped patches: accent on even columns, ground elsewhere.
                ch = accent if dx % 2 == 0 and pick % 3 != 0 else ground
            elif terrain == "woodland":
                ch = accent if pick % 5 == 0 else ground
            elif terrain in {"clay_mountains", "ore_mountains"}:
                ch = accent if pick % 4 == 0 else ground
            elif terrain == "desert":
                ch = "r" if pick % 7 == 0 else ground
            else:
                ch = ground if pick % 11 != 0 else accent
            rows[y][x] = ch


def _emit_natural_entities(
    entities: list[dict[str, Any]],
    geography: list[dict[str, Any]],
    width: int,
    height: int,
) -> None:
    """Emit nature/deco props and quiet sector signs from persisted natural_props."""
    for patch in geography:
        hid = str(patch.get("hex_id") or "hex")
        terrain = str(patch.get("terrain") or "")
        props = list(patch.get("natural_props") or [])
        label_emitted = False
        for idx, prop in enumerate(props):
            grid = prop.get("grid") or [0, 0]
            px, py = int(grid[0]), int(grid[1])
            if not (0 <= px < width and 0 <= py < height):
                continue
            kind = str(prop.get("kind") or "nature")
            marker = str(prop.get("marker") or "rock")
            label = prop.get("label")
            # Ambient animals: presentation-only, never bridge-interactable.
            is_animal = kind == "animal"
            ent: dict[str, Any] = {
                "kind": "deco" if is_animal else "nature",
                "id": f"ambient.{hid}.{idx}" if is_animal else f"nature.{hid}.{idx}",
                "pos": [px, py],
                "marker": marker,
                "prop_kind": kind,
                "nature_kind": kind,
                "presentation": "nature",
                "terrain": terrain,
                "bridge_entity": False,
                "ambient": is_animal,
            }
            entities.append(ent)
            if label and not label_emitted and kind != "animal":
                label_emitted = True
                entities.append(
                    {
                        "kind": "sign",
                        "id": f"sign.nature.{hid}",
                        "pos": [px, max(0, py - 1) if py > 0 else py],
                        "marker": "sign",
                        "text": str(label),
                        "bridge_entity": False,
                        "semantic": {
                            "knowledge_key": f"nature.{hid}.label",
                            "interaction": "observe",
                            "dismiss_on_move": True,
                            "labels": [{"level": 0, "text": str(label)}],
                            "observe_far": str(label),
                            "observe_near": str(label),
                            "quiet_label": True,
                        },
                    }
                )
            elif label and is_animal and not any(
                e.get("kind") == "sign" and e.get("id") == f"sign.animal.{hid}" for e in entities
            ):
                entities.append(
                    {
                        "kind": "sign",
                        "id": f"sign.animal.{hid}",
                        "pos": [px, py],
                        "marker": "sign",
                        "text": str(label),
                        "bridge_entity": False,
                        "semantic": {
                            "knowledge_key": f"nature.{hid}.animals",
                            "interaction": "observe",
                            "dismiss_on_move": True,
                            "labels": [{"level": 0, "text": str(label)}],
                            "observe_far": str(label),
                            "observe_near": str(label),
                            "quiet_label": True,
                        },
                    }
                )

extends RefCounted
class_name VillageCompositeProjection

## Generic projector from content/village_tests/<profile_id>/ fixture data into
## the production Overworld area shape. No village/cast-specific ids live here.

const Catalog = preload("res://sim/world/village_test_catalog.gd")
const QuestRunner = preload("res://sim/world/village_quest_runner.gd")

const GRASS := "."
const DIRT := ","
const STONE := "#"
const TREE := "T"
const CROP := "c"
const ROCK := "r"
const WALL := "#"      # production Overworld treats # as solid
const FLOOR := "."
const ROAD := ","      # IMPORTANT: production treats R as solid; dirt is walkable
const FENCE := "f"
const WATER := "~"
const BRIDGE := "B"


static func project(profile_id: String) -> Dictionary:
    var fixture: Dictionary = Catalog.load_fixture(profile_id)
    if fixture.is_empty():
        push_error("VillageCompositeProjection: failed to load fixture " + profile_id)
        return {}
    var village_data: Dictionary = fixture.get("village", {})
    var cast_data: Dictionary = fixture.get("cast", {})
    var quest_data: Dictionary = fixture.get("quest", {})
    QuestRunner.begin(profile_id)

    var map_size: Dictionary = village_data.get("map", {})
    var w := int(map_size.get("width", 72))
    var h := int(map_size.get("height", 58))
    var grid: Array = []
    for _y in range(h):
        grid.append(GRASS.repeat(w))

    _build_regions(grid, village_data.get("regions", {}))
    _build_buildings(grid, village_data.get("buildings", []), village_data.get("semantic_anchors", {}))
    _build_roads(grid, village_data.get("roads", []), village_data.get("semantic_anchors", {}))
    var entities := _build_entities(
        grid,
        cast_data,
        quest_data,
        village_data.get("semantic_anchors", {}),
        village_data.get("signs", {})
    )
    var player_start: Array = village_data.get("player_start", [w / 2, h / 2])
    _make_walkable(grid, int(player_start[0]), int(player_start[1]))

    return {
        "id": "village_test_" + profile_id.to_lower(),
        "name": str(village_data.get("name", profile_id)),
        "rows": grid,
        "theme": "village",
        "entities": entities,
        "player_start": player_start,
        "profile_id": profile_id,
        "regions": village_data.get("regions", {}),
        "semantic_anchors": village_data.get("semantic_anchors", {}),
        "quest_id": quest_data.get("id", ""),
        "quest_title": quest_data.get("title", ""),
    }


static func _set_tile(grid: Array, x: int, y: int, tile: String) -> void:
    if y < 0 or y >= grid.size() or x < 0 or x >= str(grid[y]).length():
        return
    var row := str(grid[y])
    grid[y] = row.substr(0, x) + tile + row.substr(x + 1)


static func _make_walkable(grid: Array, x: int, y: int) -> void:
    _set_tile(grid, x, y, ROAD)


static func _rect(grid: Array, x: int, y: int, w: int, h: int, tile: String) -> void:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            _set_tile(grid, xx, yy, tile)


static func _building(grid: Array, x: int, y: int, w: int, h: int, door_x: int) -> void:
    for xx in range(x, x + w):
        _set_tile(grid, xx, y, WALL)
        _set_tile(grid, xx, y + h - 1, WALL)
    for yy in range(y, y + h):
        _set_tile(grid, x, yy, WALL)
        _set_tile(grid, x + w - 1, yy, WALL)
    for yy in range(y + 1, y + h - 1):
        for xx in range(x + 1, x + w - 1):
            _set_tile(grid, xx, yy, FLOOR)
    _set_tile(grid, door_x, y + h - 1, ROAD)
    _make_walkable(grid, door_x, y + h) # interaction approach tile outside door


static func _build_regions(grid: Array, regions: Dictionary) -> void:
    for region_id in regions:
        var region: Dictionary = regions[region_id]
        var bounds: Array = region.get("bounds", [])
        if bounds.size() != 4:
            continue
        var x := int(bounds[0])
        var y := int(bounds[1])
        var w := int(bounds[2])
        var h := int(bounds[3])
        match str(region.get("terrain", "grass")):
            "forest": _fill_forest(grid, x, y, w, h)
            "farmland": _fill_farmland(grid, x, y, w, h)
            "industrial", "mine": _fill_industrial(grid, x, y, w, h)
            "water": _fill_water(grid, x, y, w, h)
            "settlement": _fill_settlement_base(grid, x, y, w, h)
            _: _rect(grid, x, y, w, h, GRASS)


static func _fill_forest(grid: Array, x: int, y: int, w: int, h: int) -> void:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if xx in [x + w / 3, x + 2 * w / 3] or yy in [y + h / 3, y + 2 * h / 3]:
                _set_tile(grid, xx, yy, DIRT)
            elif ((xx * 17 + yy * 31) % 7) < 4:
                _set_tile(grid, xx, yy, TREE)
            else:
                _set_tile(grid, xx, yy, GRASS)


static func _fill_farmland(grid: Array, x: int, y: int, w: int, h: int) -> void:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if yy % 4 == 0 or xx == x + w / 2:
                _set_tile(grid, xx, yy, DIRT)
            else:
                _set_tile(grid, xx, yy, CROP)
    for xx in range(x, x + w):
        _set_tile(grid, xx, y, FENCE)
        _set_tile(grid, xx, y + h - 1, FENCE)
    for yy in range(y, y + h):
        _set_tile(grid, x, yy, FENCE)
        _set_tile(grid, x + w - 1, yy, FENCE)


static func _fill_industrial(grid: Array, x: int, y: int, w: int, h: int) -> void:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if xx == x + w / 2 or yy == y + h / 2:
                _set_tile(grid, xx, yy, DIRT)
            elif ((xx * 13 + yy * 11) % 6) < 2:
                _set_tile(grid, xx, yy, ROCK)
            else:
                _set_tile(grid, xx, yy, DIRT)


static func _fill_water(grid: Array, x: int, y: int, w: int, h: int) -> void:
    _rect(grid, x, y, w, h, WATER)


static func _fill_settlement_base(grid: Array, x: int, y: int, w: int, h: int) -> void:
    _rect(grid, x, y, w, h, DIRT)


static func _build_buildings(grid: Array, buildings: Array, anchors: Dictionary) -> void:
    for raw in buildings:
        if not (raw is Dictionary):
            continue
        var b: Dictionary = raw
        var anchor_name := str(b.get("anchor", ""))
        var anchor_pos: Array = anchors.get(anchor_name, [-1, -1])
        if int(anchor_pos[0]) < 0:
            continue
        var size: Array = b.get("size", [6, 5])
        var door_offset: Array = b.get("door_offset", [3, 4])
        var bx := int(anchor_pos[0]) - int(door_offset[0])
        var by := int(anchor_pos[1]) - int(door_offset[1])
        _building(grid, bx, by, int(size[0]), int(size[1]), int(anchor_pos[0]))


static func _build_roads(grid: Array, roads: Array, anchors: Dictionary) -> void:
    for raw in roads:
        if not (raw is Dictionary):
            continue
        var road: Dictionary = raw
        var a: Array = anchors.get(str(road.get("from", "")), [-1, -1])
        var b: Array = anchors.get(str(road.get("to", "")), [-1, -1])
        if int(a[0]) < 0 or int(b[0]) < 0:
            continue
        _draw_road(grid, a, b)


static func _draw_road(grid: Array, from_pos: Array, to_pos: Array) -> void:
    var x1 := int(from_pos[0])
    var y1 := int(from_pos[1])
    var x2 := int(to_pos[0])
    var y2 := int(to_pos[1])
    _draw_line(grid, x1, y1, x1, y2, ROAD)
    _draw_line(grid, x1, y2, x2, y2, ROAD)


static func _draw_line(grid: Array, x1: int, y1: int, x2: int, y2: int, tile: String) -> void:
    if x1 == x2:
        var step := 1 if y2 >= y1 else -1
        for y in range(y1, y2 + step, step):
            _set_tile(grid, x1, y, tile)
    elif y1 == y2:
        var step := 1 if x2 >= x1 else -1
        for x in range(x1, x2 + step, step):
            _set_tile(grid, x, y1, tile)


static func _build_entities(grid: Array, cast_data: Dictionary, quest_data: Dictionary, anchors: Dictionary, signs: Dictionary) -> Array:
    var entities: Array = []
    var quest_id := str(quest_data.get("id", ""))
    var cast: Array = cast_data.get("cast", [])
    for raw in cast:
        if not (raw is Dictionary):
            continue
        var c: Dictionary = raw
        var anchor_name := str(c.get("work_anchor", c.get("home_anchor", "")))
        var anchor_pos: Array = anchors.get(anchor_name, [-1, -1])
        if int(anchor_pos[0]) < 0:
            anchor_name = str(c.get("home_anchor", ""))
            anchor_pos = anchors.get(anchor_name, [-1, -1])
        if int(anchor_pos[0]) < 0:
            continue
        var off: Array = c.get("pos_offset", [0, 1])
        var npc_pos := [int(anchor_pos[0]) + int(off[0]), int(anchor_pos[1]) + int(off[1])]
        _make_walkable(grid, npc_pos[0], npc_pos[1])
        # Also guarantee at least one cardinal interaction tile is walkable.
        _make_walkable(grid, npc_pos[0], npc_pos[1] + 1)
        var npc_id := str(c.get("id", ""))
        entities.append({
            "kind": "npc",
            "id": npc_id,
            "pos": npc_pos,
            "name": str(c.get("name", npc_id)),
            "sprite": str(c.get("sprite", "villager_b")),
            "lines": ["..."],
            "village_test_story": {
                "story_id": quest_id,
                "npc_id": npc_id,
                "relationships": c.get("relationships", {}),
                "dialogue_context": c.get("dialogue_context", ""),
            }
        })

    # Existing and generated fixtures can define friendly labels. Older fixtures
    # without a signs dictionary retain useful generic anchor signs.
    var sign_map: Dictionary = signs.duplicate(true)
    if sign_map.is_empty():
        for anchor_name in anchors:
            sign_map[str(anchor_name)] = str(anchor_name).replace("_", " ").to_upper()
    for anchor_name in sign_map:
        var pos: Array = anchors.get(str(anchor_name), [-1, -1])
        if int(pos[0]) < 0:
            continue
        entities.append({
            "kind": "sign",
            "id": str(anchor_name) + "_sign",
            "pos": [int(pos[0]), int(pos[1]) - 1],
            "text": str(sign_map[anchor_name]),
        })

    # Investigation/travel nodes are projected as ordinary production signs at
    # their semantic anchor. Overworld detects only the generic metadata below.
    for node_id in quest_data.get("nodes", {}):
        var node: Dictionary = quest_data["nodes"][node_id]
        var node_type := str(node.get("type", ""))
        if node_type not in ["investigate", "travel"]:
            continue
        var anchor := str(node.get("anchor", ""))
        var pos: Array = anchors.get(anchor, [-1, -1])
        if int(pos[0]) < 0:
            continue
        var eid := "quest_anchor_" + str(node_id)
        entities.append({
            "kind": "sign",
            "id": eid,
            "pos": [int(pos[0]), int(pos[1])],
            "text": str(node.get("prompt", "Investigate " + anchor.replace("_", " "))),
            "village_quest_node": str(node_id),
            "village_quest_anchor": anchor,
        })
        _make_walkable(grid, int(pos[0]), int(pos[1]) + 1)
    return entities


static func validate_projection(area: Dictionary) -> Dictionary:
    var errors: Array = []
    var rows: Array = area.get("rows", [])
    if rows.is_empty():
        return {"valid": false, "errors": ["No rows"]}
    var w := str(rows[0]).length()
    for y in range(rows.size()):
        if str(rows[y]).length() != w:
            errors.append("Inconsistent row width at y=%d" % y)
    var ids: Dictionary = {}
    for raw in area.get("entities", []):
        var e: Dictionary = raw
        var p: Array = e.get("pos", [-1, -1])
        if int(p[0]) < 0 or int(p[0]) >= w or int(p[1]) < 0 or int(p[1]) >= rows.size():
            errors.append("Entity out of bounds: " + str(e.get("id", "?")))
        var eid := str(e.get("id", ""))
        if ids.has(eid):
            errors.append("Duplicate entity id: " + eid)
        ids[eid] = true
    return {"valid": errors.is_empty(), "errors": errors, "width": w, "height": rows.size()}

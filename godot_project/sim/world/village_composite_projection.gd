extends RefCounted
class_name VillageCompositeProjection

## Builds a single large continuous area dictionary from a village test fixture.
## Loads data from content/village_tests/<profile_id>/ and projects to production area format.
## Output shape matches DmbWorldData area dicts consumed by Overworld.

const Catalog = preload("res://sim/world/village_test_catalog.gd")
const QuestRunner = preload("res://sim/world/village_quest_runner.gd")

# Tile constants
const GRASS := "."
const DIRT := ","
const STONE := "#"
const TREE := "T"
const CROP := "c"
const ROCK := "r"
const WALL := "W"
const FLOOR := "F"
const ROAD := "R"
const FENCE := "f"
const WATER := "~"
const BRIDGE := "B"

static func project(profile_id: String) -> Dictionary:
    var fixture = Catalog.load_fixture(profile_id)
    if fixture.is_empty():
        push_error("VillageCompositeProjection: failed to load fixture " + profile_id)
        return {}
    
    var village_data = fixture.get("village", {})
    var cast_data = fixture.get("cast", {})
    var quest_data = fixture.get("quest", {})
    var dialogue_data = fixture.get("dialogue", {})
    
    # Initialize quest runner for this profile
    QuestRunner.begin(profile_id)
    
    var map_size = village_data.get("map", {})
    var w := int(map_size.get("width", 72))
    var h := int(map_size.get("height", 58))
    var grid: Array = []
    for _y in range(h):
        grid.append(GRASS.repeat(w))
    
    # Build terrain by region
    _build_regions(grid, village_data.get("regions", {}))
    
    # Build buildings
    _build_buildings(grid, village_data.get("buildings", []), village_data.get("semantic_anchors", {}))
    
    # Build roads
    _build_roads(grid, village_data.get("roads", []), village_data.get("semantic_anchors", {}))
    
    # Build entities (NPCs, signs, etc.)
    var entities = _build_entities(grid, cast_data, village_data.get("semantic_anchors", {}), dialogue_data)
    
    var player_start = village_data.get("player_start", [w/2, h/2])
    
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
    if y < 0 or y >= grid.size() or x < 0 or x >= grid[y].length():
        return
    var row: String = grid[y]
    grid[y] = row.substr(0, x) + tile + row.substr(x + 1)

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

static func _build_regions(grid: Array, regions: Dictionary) -> void:
    for region_id in regions:
        var region = regions[region_id]
        var bounds = region.get("bounds", [])
        if bounds.size() != 4:
            continue
        var x: int = bounds[0]
        var y: int = bounds[1]
        var w: int = bounds[2]
        var h: int = bounds[3]
        var terrain = region.get("terrain", "grass")
        
        match terrain:
            "forest":
                _fill_forest(grid, x, y, w, h)
            "farmland":
                _fill_farmland(grid, x, y, w, h)
            "industrial":
                _fill_industrial(grid, x, y, w, h)
            "water":
                _fill_water(grid, x, y, w, h)
            "settlement":
                _fill_settlement_base(grid, x, y, w, h)
            _:
                _rect(grid, x, y, w, h, GRASS)

static func _fill_forest(grid: Array, x: int, y: int, w: int, h: int) -> void:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            # Paths through forest
            if xx in [x + w/3, x + 2*w/3] or yy in [y + h/3, y + 2*h/3]:
                _set_tile(grid, xx, yy, DIRT)
            elif ((xx * 17 + yy * 31) % 7) < 4:
                _set_tile(grid, xx, yy, TREE)
            else:
                _set_tile(grid, xx, yy, GRASS)
    # Clearing for camp
    var cx = x + w - 8
    var cy = y + 4
    _rect(grid, cx, cy, 8, 6, DIRT)

static func _fill_farmland(grid: Array, x: int, y: int, w: int, h: int) -> void:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            # Crop rows
            if yy % 4 == 0:
                _set_tile(grid, xx, yy, DIRT)
            elif xx in [x + w/2] and yy in [y + h/2]:
                _set_tile(grid, xx, yy, DIRT)
            else:
                _set_tile(grid, xx, yy, CROP)
    # Fence perimeter
    for xx in range(x, x + w):
        _set_tile(grid, xx, y, FENCE)
        _set_tile(grid, xx, y + h - 1, FENCE)
    for yy in range(y, y + h):
        _set_tile(grid, x, yy, FENCE)
        _set_tile(grid, x + w - 1, yy, FENCE)

static func _fill_industrial(grid: Array, x: int, y: int, w: int, h: int) -> void:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if ((xx * 13 + yy * 11) % 6) < 3:
                _set_tile(grid, xx, yy, ROCK)
            elif xx in [x + 2, x + w - 3] or yy in [y + 2, y + h - 3]:
                _set_tile(grid, xx, yy, STONE)
            else:
                _set_tile(grid, xx, yy, DIRT)
    # Kiln structure
    _rect(grid, x + 3, y + 3, 8, 5, STONE)

static func _fill_water(grid: Array, x: int, y: int, w: int, h: int) -> void:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            _set_tile(grid, xx, yy, WATER)

static func _fill_settlement_base(grid: Array, x: int, y: int, w: int, h: int) -> void:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            _set_tile(grid, xx, yy, DIRT)

static func _build_buildings(grid: Array, buildings: Array, anchors: Dictionary) -> void:
    for b in buildings:
        var anchor_name = b.get("anchor", "")
        var anchor_pos = anchors.get(anchor_name, [-1, -1])
        if anchor_pos[0] < 0:
            continue
        var size = b.get("size", [6, 5])
        var door_offset = b.get("door_offset", [3, 4])
        var bx = anchor_pos[0] - door_offset[0]
        var by = anchor_pos[1] - door_offset[1]
        var door_x = anchor_pos[0]
        var door_y = by + size[1] - 1
        _building(grid, bx, by, size[0], size[1], door_x)

static func _build_roads(grid: Array, roads: Array, anchors: Dictionary) -> void:
    for road in roads:
        var from_anchor = road.get("from", "")
        var to_anchor = road.get("to", "")
        var from_pos = anchors.get(from_anchor, [-1, -1])
        var to_pos = anchors.get(to_anchor, [-1, -1])
        if from_pos[0] < 0 or to_pos[0] < 0:
            continue
        _draw_road(grid, from_pos, to_pos)

static func _draw_road(grid: Array, from: Array, to: Array) -> void:
    var x1: int = from[0]
    var y1: int = from[1]
    var x2: int = to[0]
    var y2: int = to[1]
    # Simple L-shaped path
    var mid_x = x1
    var mid_y = y2
    # Horizontal then vertical
    _draw_line(grid, x1, y1, mid_x, y1, ROAD)
    _draw_line(grid, mid_x, y1, mid_x, mid_y, ROAD)
    _draw_line(grid, mid_x, mid_y, x2, y2, ROAD)

static func _draw_line(grid: Array, x1: int, y1: int, x2: int, y2: int, tile: String) -> void:
    if x1 == x2:
        var step = 1 if y2 > y1 else -1
        for y in range(y1, y2 + step, step):
            _set_tile(grid, x1, y, tile)
    elif y1 == y2:
        var step = 1 if x2 > x1 else -1
        for x in range(x1, x2 + step, step):
            _set_tile(grid, x, y1, tile)

static func _build_entities(grid: Array, cast_data: Dictionary, anchors: Dictionary, dialogue_data: Dictionary) -> Array:
    var entities: Array = []
    var cast = cast_data.get("cast", [])
    
    # Add NPCs from cast
    for c in cast:
        var anchor_name = c.get("work_anchor", c.get("home_anchor", ""))
        var anchor_pos = anchors.get(anchor_name, [-1, -1])
        if anchor_pos[0] < 0:
            # Fallback to home anchor
            anchor_name = c.get("home_anchor", "")
            anchor_pos = anchors.get(anchor_name, [-1, -1])
        if anchor_pos[0] < 0:
            continue
        
        # Offset NPC slightly from anchor center
        var npc_pos = [anchor_pos[0] + (c.get("pos_offset", [0, 0])[0] if c.has("pos_offset") else 0),
                       anchor_pos[1] + (c.get("pos_offset", [0, 0])[1] if c.has("pos_offset") else 1)]
        
        var npc_id = c.get("id", "")
        var fallback_name = c.get("name", npc_id)
        var fallback_lines = ["..."]
        
        # Get dialogue for this NPC at quest start
        var quest_id = "broken_promise"
        var start_node = "talk_reve"
        var dialogue_lines = QuestRunner.get_dialogue(npc_id, quest_id, start_node)
        if dialogue_lines.is_empty():
            dialogue_lines = fallback_lines
        
        var entity = {
            "kind": "npc",
            "id": npc_id,
            "pos": npc_pos,
            "name": fallback_name,
            "sprite": c.get("sprite", "villager"),
            "lines": dialogue_lines,
            "locked_lines": [],
            "village_test_story": {
                "story_id": quest_id,
                "beat": "active" if c.get("quest_participation", []).size() > 0 else "ambient",
                "npc_id": npc_id,
                "relationships": c.get("relationships", {}),
                "dialogue_context": c.get("dialogue_context", "")
            }
        }
        entities.append(entity)
    
    # Add signs for semantic anchors
    var sign_anchors = {
        "village_square": "VILLAGE SQUARE",
        "village_hall": "VILLAGE HALL",
        "healer_house": "HEALER'S HOUSE",
        "pottery": "MARA'S POTTERY",
        "lime_kiln": "LIME KILN",
        "scavenger_yard": "JORY'S SCAVENGER YARD",
        "tavern": "THE RUSTED ANCHOR",
        "blacksmith": "TOMAS'S FORGE",
        "general_store": "MIRA'S GENERAL STORE",
        "farmstead": "ANNA'S FARMSTEAD",
        "woods_edge": "NORTHWOODS",
        "woods_camp": "LOGGING CAMP",
        "kiln_overlook": "KILN OVERLOOK",
        "old_shrine": "OLD SHRINE",
        "well": "VILLAGE WELL",
        "river_bridge": "RIVER BRIDGE"
    }
    
    for anchor_name in sign_anchors:
        var pos = anchors.get(anchor_name, [-1, -1])
        if pos[0] >= 0:
            entities.append({
                "kind": "sign",
                "id": anchor_name + "_sign",
                "pos": [pos[0], pos[1] - 1],
                "text": sign_anchors[anchor_name]
            })
    
    return entities

static func validate_projection(area: Dictionary) -> Dictionary:
    var errors: Array = []
    var rows: Array = area.get("rows", [])
    if rows.is_empty():
        return {"valid": false, "errors": ["No rows"]}
    var w: int = rows[0].length()
    for y in range(rows.size()):
        if rows[y].length() != w:
            errors.append("Inconsistent row width at y=%d" % y)
    var ids := {}
    for e in area.get("entities", []):
        var p: Array = e.get("pos", [-1, -1])
        if p[0] < 0 or p[0] >= w or p[1] < 0 or p[1] >= rows.size():
            errors.append("Entity out of bounds: " + str(e.get("id", "?")))
        var eid := str(e.get("id", ""))
        if ids.has(eid):
            errors.append("Duplicate entity id: " + eid)
        ids[eid] = true
    return {"valid": errors.is_empty(), "errors": errors, "width": w, "height": rows.size()}
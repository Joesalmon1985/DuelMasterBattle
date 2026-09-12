extends RefCounted
class_name VillageCompositeProjection

const Profiles = preload("res://sim/world/village_test_profiles.gd")
const DialogueData = preload("res://sim/world/village_test_dialogue.gd")

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

static func project(profile_id: String) -> Dictionary:
    var profile := Profiles.get(profile_id)
    if profile.is_empty():
        push_error("VillageCompositeProjection: unknown profile " + profile_id)
        return {}
    var size: Array = profile["map_size"]
    var w := int(size[0])
    var h := int(size[1])
    var grid: Array = []
    for _y in range(h):
        grid.append(GRASS.repeat(w))

    _build_forest(grid)
    _build_fields(grid)
    _build_mine(grid)
    _build_village(grid)
    _build_roads(grid)

    var dialogue := DialogueData.load_data()
    return {
        "id": "village_test_" + profile_id.to_lower(),
        "name": str(profile["name"]),
        "rows": grid,
        "theme": "village",
        "entities": _entities(dialogue),
        "player_start": profile["player_start"].duplicate(),
        "profile_id": profile_id,
        "regions": profile["regions"].duplicate(true),
        "semantic_anchors": profile["semantic_anchors"].duplicate(true),
        "story_route": profile["story_route"].duplicate(),
    }

static func _set(grid: Array, x: int, y: int, tile: String) -> void:
    if y < 0 or y >= grid.size() or x < 0 or x >= grid[y].length():
        return
    var row: String = grid[y]
    grid[y] = row.substr(0, x) + tile + row.substr(x + 1)

static func _rect(grid: Array, x: int, y: int, w: int, h: int, tile: String) -> void:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            _set(grid, xx, yy, tile)

static func _building(grid: Array, x: int, y: int, w: int, h: int, door_x: int) -> void:
    for xx in range(x, x + w):
        _set(grid, xx, y, WALL)
        _set(grid, xx, y + h - 1, WALL)
    for yy in range(y, y + h):
        _set(grid, x, yy, WALL)
        _set(grid, x + w - 1, yy, WALL)
    for yy in range(y + 1, y + h - 1):
        for xx in range(x + 1, x + w - 1):
            _set(grid, xx, yy, FLOOR)
    _set(grid, door_x, y + h - 1, ROAD)

static func _build_forest(grid: Array) -> void:
    for y in range(0, 20):
        for x in range(0, 24):
            if x in [9, 10, 11] or y in [11, 12, 13]:
                _set(grid, x, y, DIRT)
            elif ((x * 17 + y * 31) % 7) < 4:
                _set(grid, x, y, TREE)
    _rect(grid, 6, 9, 10, 7, DIRT)
    _building(grid, 6, 9, 6, 5, 9)

static func _build_fields(grid: Array) -> void:
    for y in range(32, 52):
        for x in range(38, 60):
            if x in [47, 48, 49] or y in [40, 41] or y % 4 == 0:
                _set(grid, x, y, DIRT)
            else:
                _set(grid, x, y, CROP)
    _building(grid, 45, 34, 8, 6, 48)
    for x in range(39, 59):
        if x not in [47, 48, 49]:
            _set(grid, x, 33, FENCE)

static func _build_mine(grid: Array) -> void:
    for y in range(32, 52):
        for x in range(0, 22):
            if x in [9, 10, 11] or y in [40, 41]:
                _set(grid, x, y, DIRT)
            elif ((x * 13 + y * 11) % 6) < 3:
                _set(grid, x, y, ROCK)
            else:
                _set(grid, x, y, DIRT)
    _rect(grid, 5, 35, 7, 4, STONE)
    _set(grid, 8, 38, DIRT)
    _set(grid, 9, 38, DIRT)

static func _build_village(grid: Array) -> void:
    _rect(grid, 14, 25, 34, 3, ROAD)
    _rect(grid, 29, 14, 3, 27, ROAD)
    _rect(grid, 25, 23, 11, 8, ROAD)
    _building(grid, 24, 16, 7, 6, 27)
    _building(grid, 32, 16, 6, 5, 34)
    _building(grid, 14, 19, 7, 6, 17)
    _building(grid, 37, 18, 7, 6, 39)
    _building(grid, 19, 31, 7, 6, 22)
    _building(grid, 34, 31, 7, 6, 37)
    _building(grid, 30, 30, 6, 6, 33)
    _building(grid, 15, 29, 5, 5, 17)
    _building(grid, 41, 27, 5, 5, 43)

static func _build_roads(grid: Array) -> void:
    for y in range(12, 26):
        for x in range(9, 12):
            _set(grid, x, y, ROAD)
    for x in range(10, 30):
        _set(grid, x, 25, ROAD)
        _set(grid, x, 26, ROAD)
    for x in range(31, 49):
        _set(grid, x, 40, ROAD)
        _set(grid, x, 41, ROAD)
    for y in range(27, 42):
        _set(grid, 30, y, ROAD)
        _set(grid, 31, y, ROAD)
    for x in range(10, 31):
        _set(grid, x, 40, ROAD)
        _set(grid, x, 41, ROAD)

static func _npc(dialogue: Dictionary, npc_id: String, pos: Array, fallback_name: String, fallback_lines: Array, story_meta: Dictionary = {}) -> Dictionary:
    var d := DialogueData.npc(dialogue, npc_id, fallback_name, fallback_lines)
    var entity := {
        "kind": "npc",
        "id": npc_id,
        "pos": pos,
        "name": d["name"],
        "sprite": d["sprite"],
        "lines": d["lines"],
        "locked_lines": d["locked_lines"],
    }
    if not story_meta.is_empty():
        entity["village_test_story"] = story_meta
    return entity

static func _entities(dialogue: Dictionary) -> Array:
    var sid := "e17a_dialogue_story"
    return [
        _npc(dialogue, "reeve", [29, 24], "Reeve", ["A ledger is missing. Start at the logging camp."],
            {"story_id": sid, "beat": "start", "sets": ["start"]}),
        _npc(dialogue, "woodcutter", [13, 12], "Woodcutter", ["I took the tally to the mill."],
            {"story_id": sid, "beat": "wood", "requires": ["start"], "sets": ["wood"]}),
        _npc(dialogue, "miller", [39, 24], "Miller", ["The miner knew about the ledger."],
            {"story_id": sid, "beat": "mill", "requires": ["wood"], "sets": ["mill"]}),
        _npc(dialogue, "miner", [13, 40], "Miner", ["I found it. The numbers prove somebody is stealing."],
            {"story_id": sid, "beat": "mine", "requires": ["mill"], "sets": ["complete"]}),
        _npc(dialogue, "healer", [32, 22], "Healer", ["People bring me splinters, burns and crushed fingers."]),
        _npc(dialogue, "storekeeper", [36, 29], "Storekeeper", ["Wood, grain and ore come through here."]),
        _npc(dialogue, "farmer", [50, 41], "Farmer", ["The grain is nearly ready. Keep to the track."]),
        _npc(dialogue, "blacksmith", [24, 30], "Blacksmith", ["Ore is only useful after somebody gets it hot enough."]),
        _npc(dialogue, "distiller", [39, 30], "Distiller", ["Grain gives us more than bread, if you are patient."]),
        {"kind": "sign", "id": "forest_sign", "pos": [11, 18], "text": "FOREST / LOGGING CAMP"},
        {"kind": "sign", "id": "fields_sign", "pos": [44, 40], "text": "FIELDS / FARMSTEAD"},
        {"kind": "sign", "id": "mine_sign", "pos": [16, 40], "text": "MINE / ORE WORKINGS"},
        {"kind": "sign", "id": "sawmill_sign", "pos": [17, 25], "text": "SAWMILL"},
        {"kind": "sign", "id": "mill_sign", "pos": [39, 25], "text": "MILL"},
        {"kind": "sign", "id": "forge_sign", "pos": [22, 37], "text": "FORGE"},
        {"kind": "sign", "id": "distillery_sign", "pos": [37, 37], "text": "DISTILLERY"},
    ]

static func validate_projection(area: Dictionary) -> Dictionary:
    var errors: Array = []
    var rows: Array = area.get("rows", [])
    if rows.is_empty():
        return {"valid": false, "errors": ["No rows"]}
    var w := rows[0].length()
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

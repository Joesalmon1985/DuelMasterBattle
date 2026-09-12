extends RefCounted
class_name VillageTestCatalog

## Discovers and loads village test fixtures from content/village_tests/
## Each fixture is a directory containing: village.json, cast.json, quest.json, dialogue.json

const VILLAGE_TESTS_ROOT := "res://content/village_tests/"

static var _cache: Dictionary = {}
static var _discovered: Array = []

## Discover all valid village test fixtures
static func discover() -> Array:
    if not _discovered.is_empty():
        return _discovered.duplicate(true)
    
    var dir = DirAccess.open(VILLAGE_TESTS_ROOT)
    if not dir:
        push_error("VillageTestCatalog: Could not open " + VILLAGE_TESTS_ROOT)
        return []
    
    dir.list_dir_begin()
    var name = dir.get_next()
    while name != "":
        if dir.current_is_dir() and not name.begins_with("."):
            var fixture_path = VILLAGE_TESTS_ROOT.path_join(name)
            var result = _validate_fixture(fixture_path, name)
            if result.valid:
                _discovered.append(result.metadata)
            else:
                _discovered.append({
                    "id": name,
                    "name": name + " — INVALID",
                    "valid": false,
                    "errors": result.errors
                })
        name = dir.get_next()
    dir.list_dir_end()
    
    # Sort by ID
    _discovered.sort_custom(func(a, b): return str(a["id"]) < str(b["id"]))
    return _discovered.duplicate(true)

## Get metadata for a specific fixture
static func get_metadata(profile_id: String) -> Dictionary:
    discover()  # Ensure cache is populated
    for m in _discovered:
        if str(m["id"]) == profile_id:
            return m.duplicate(true)
    return {}

## Load a complete fixture (validates all files)
static func load_fixture(profile_id: String) -> Dictionary:
    if _cache.has(profile_id):
        return _cache[profile_id].duplicate(true)
    
    var fixture_path = VILLAGE_TESTS_ROOT.path_join(profile_id)
    var result = _load_fixture_files(fixture_path, profile_id)
    if result.valid:
        _cache[profile_id] = result.data
        return result.data.duplicate(true)
    else:
        push_error("VillageTestCatalog: Failed to load fixture " + profile_id + ": " + str(result.errors))
        return {}

## Clear cache (useful for hot-reload during development)
static func clear_cache() -> void:
    _cache.clear()
    _discovered.clear()

## Internal: validate fixture directory structure
static func _validate_fixture(path: String, profile_id: String) -> Dictionary:
    var required_files = ["village.json", "cast.json", "quest.json", "dialogue.json"]
    var errors: Array = []
    
    for file in required_files:
        var full_path = path.path_join(file)
        if not ResourceLoader.exists(full_path):
            errors.append("Missing required file: " + file)
    
    if not errors.is_empty():
        return {"valid": false, "errors": errors, "metadata": {}}
    
    # Try to load and parse each file
    var village_data = _load_json(path.path_join("village.json"))
    var cast_data = _load_json(path.path_join("cast.json"))
    var quest_data = _load_json(path.path_join("quest.json"))
    var dialogue_data = _load_json(path.path_join("dialogue.json"))
    
    if not village_data or not cast_data or not quest_data or not dialogue_data:
        errors.append("Failed to parse one or more JSON files")
        return {"valid": false, "errors": errors, "metadata": {}}
    
    # Basic validation
    if not village_data.has("id") or str(village_data["id"]) != profile_id:
        errors.append("village.json id mismatch: expected " + profile_id + ", got " + str(village_data.get("id", "null")))
    
    if not cast_data.has("cast") or not cast_data["cast"] is Array:
        errors.append("cast.json missing or invalid 'cast' array")
    
    if not quest_data.has("nodes") or not quest_data["nodes"] is Dictionary:
        errors.append("quest.json missing or invalid 'nodes' dictionary")
    
    if not dialogue_data.has("dialogue") or not dialogue_data["dialogue"] is Array:
        errors.append("dialogue.json missing or invalid 'dialogue' array")
    
    if not errors.is_empty():
        return {"valid": false, "errors": errors, "metadata": {}}
    
    # Build summary metadata for menu display
    var metadata = {
        "id": profile_id,
        "name": village_data.get("name", profile_id),
        "economic_profile": village_data.get("economic_profile", "Unknown"),
        "description": village_data.get("description", ""),
        "valid": true,
        "cast_count": cast_data["cast"].size(),
        "quest_title": quest_data.get("title", "Untitled Quest"),
        "quest_premise": quest_data.get("premise", ""),
        "node_count": quest_data["nodes"].size(),
        "regions": village_data.get("regions", {}).keys(),
        "semantic_anchors": village_data.get("semantic_anchors", {}).keys(),
        "map_size": village_data.get("map", {}),
        "errors": []
    }
    
    return {"valid": true, "errors": [], "metadata": metadata, "data": {
        "village": village_data,
        "cast": cast_data,
        "quest": quest_data,
        "dialogue": dialogue_data
    }}

## Internal: load all fixture files
static func _load_fixture_files(path: String, profile_id: String) -> Dictionary:
    var validation = _validate_fixture(path, profile_id)
    if not validation.valid:
        return {"valid": false, "errors": validation.errors, "data": {}}
    return {"valid": true, "errors": [], "data": validation.data}

## Internal: load and parse JSON
static func _load_json(path: String) -> Variant:
    var file = FileAccess.open(path, FileAccess.READ)
    if not file:
        return null
    var text = file.get_as_text()
    file.close()
    var json_result = JSON.parse_string(text)
    if json_result is Dictionary and json_result.has("error"):
        var err = json_result["error"]
        if err != OK:
            var msg = json_result.get("error_message", "Unknown error")
            push_error("VillageTestCatalog: JSON parse error in " + path + ": " + msg)
            return null
        return json_result.get("data", null)
    return null
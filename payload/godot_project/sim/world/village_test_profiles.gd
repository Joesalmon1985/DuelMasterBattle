extends RefCounted
class_name VillageTestProfile

## Focused deterministic fixture for production-Overworld village dialogue testing.
## All positions and region bounds use ABSOLUTE map coordinates.

const PROFILES := {
    "E17A": {
        "id": "E17A",
        "name": "E17A — Wood + Grain + Ore (Dialogue Story Test)",
        "economic_profile": "E17",
        "description": "Continuous Wood/Grain/Ore village fixture for dialogue and story playtesting.",
        "hexes": ["Wood", "Grain", "Ore"],
        "primary_workers": ["Woodcutter", "Farmer", "Miner"],
        "primary_buildings": ["Logging Camp", "Farmstead", "Mine"],
        "processing_buildings": ["Sawmill", "Mill", "Forge", "Distillery"],
        "generic_cast": ["Reeve", "Healer", "Storekeeper"],
        "map_size": [60, 52],
        "player_start": [30, 26],
        "regions": {
            "forest": {"name": "Forest", "hex_type": "Wood", "bounds": [0, 0, 24, 20]},
            "village": {"name": "Village", "hex_type": "Settlement", "bounds": [12, 14, 36, 26]},
            "fields": {"name": "Fields", "hex_type": "Grain", "bounds": [38, 32, 22, 20]},
            "mine": {"name": "Mine", "hex_type": "Ore", "bounds": [0, 32, 22, 20]},
        },
        "semantic_anchors": {
            "forest": [10, 9],
            "logging_camp": [9, 12],
            "forest_story": [13, 12],
            "village_square": [30, 26],
            "village_hall": [27, 20],
            "sawmill": [17, 22],
            "mill": [39, 21],
            "forge": [22, 33],
            "distillery": [37, 33],
            "healer_house": [34, 19],
            "store": [33, 33],
            "fields": [49, 41],
            "farmstead": [48, 37],
            "fields_story": [45, 40],
            "mine": [10, 41],
            "mine_mouth": [8, 38],
            "mine_story": [13, 39],
        },
        "story_route": ["village_square", "logging_camp", "mill", "mine_mouth"],
        "pilot_stories": [{
            "id": "e17a_dialogue_story",
            "title": "The Missing Ledger",
            "anchors": ["village_square", "logging_camp", "mill", "mine_mouth"],
        }],
    }
}

static func all() -> Array:
    var out: Array = []
    for key in PROFILES:
        out.append(PROFILES[key].duplicate(true))
    return out

static func get(profile_id: String) -> Dictionary:
    return PROFILES.get(profile_id, {}).duplicate(true)

static func get_regions(profile_id: String) -> Dictionary:
    return get(profile_id).get("regions", {})

static func get_semantic_anchors(profile_id: String) -> Dictionary:
    return get(profile_id).get("semantic_anchors", {})

static func get_pilot_stories(profile_id: String) -> Array:
    return get(profile_id).get("pilot_stories", [])

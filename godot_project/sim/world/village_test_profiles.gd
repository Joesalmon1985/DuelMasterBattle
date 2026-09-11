extends RefCounted
class_name VillageTestProfile

## Test village fixtures sourced from the workbook.
## Authoritative source: docs/Duel_Master_Battle_Village_Cast_Matrix_WORLDVIEW_DIALOGUE_PILOT_3_STORIES (1).xlsx
## Sheet: Economic Profiles (E17), Cast Matrix (E17A)

const PROFILES = {
	"E17A": {
		"id": "E17A",
		"name": "E17A — Wood + Grain + Ore",
		"economic_profile": "E17",
		"description": "Village with three resource lands: Forest (Wood), Fields (Grain), Mine (Ore)",
		"hexes": ["Wood", "Grain", "Ore"],
		"primary_workers": ["Woodcutter", "Farmer", "Miner"],
		"primary_buildings": ["Logging Camp", "Farmstead", "Mine"],
		"processing_buildings": ["Sawmill", "Mill", "Forge", "Distillery"],
		"processing_workers": ["Sawmiller", "Miller", "Blacksmith", "Distiller"],
		"generic_cast": ["Reeve", "Healer", "Storekeeper"],
		"cast": {
			# Primary workers (3 per hex)
			"woodcutter_1": {"role": "Woodcutter", "hex": "Wood", "building": "Logging Camp"},
			"woodcutter_2": {"role": "Woodcutter", "hex": "Wood", "building": "Logging Camp"},
			"woodcutter_3": {"role": "Woodcutter", "hex": "Wood", "building": "Logging Camp"},
			"farmer_1": {"role": "Farmer", "hex": "Grain", "building": "Farmstead"},
			"farmer_2": {"role": "Farmer", "hex": "Grain", "building": "Farmstead"},
			"farmer_3": {"role": "Farmer", "hex": "Grain", "building": "Farmstead"},
			"miner_1": {"role": "Miner", "hex": "Ore", "building": "Mine"},
			"miner_2": {"role": "Miner", "hex": "Ore", "building": "Mine"},
			"miner_3": {"role": "Miner", "hex": "Ore", "building": "Mine"},
			# Processing workers
			"sawmiller_1": {"role": "Sawmiller", "building": "Sawmill", "pair": "Wood + Wood"},
			"sawmiller_2": {"role": "Sawmiller", "building": "Sawmill", "pair": "Wood + Wood"},
			"miller_1": {"role": "Miller", "building": "Mill", "pair": "Wood + Grain"},
			"miller_2": {"role": "Miller", "building": "Mill", "pair": "Wood + Grain"},
			"blacksmith_1": {"role": "Blacksmith", "building": "Forge", "pair": "Wood + Ore"},
			"blacksmith_2": {"role": "Blacksmith", "building": "Forge", "pair": "Wood + Ore"},
			"distiller_1": {"role": "Distiller", "building": "Distillery", "pair": "Grain + Ore"},
			"distiller_2": {"role": "Distiller", "building": "Distillery", "pair": "Grain + Ore"},
			# Generic civic cast
			"reeve": {"role": "Reeve", "category": "Authority"},
			"healer": {"role": "Healer", "category": "Care"},
			"storekeeper": {"role": "Storekeeper", "category": "Trade"},
		},
		"regions": {
			# Each region defines its tile bounds and content
			"forest": {
				"name": "Forest",
				"hex_type": "Wood",
				"bounds": {"x": 0, "y": 0, "w": 20, "h": 20},
				"entry_points": {"village": {"x": 10, "y": 19}},
				"content": {
					"trees": true,
					"logging_camp": {"pos": [5, 5], "workers": ["woodcutter_1", "woodcutter_2", "woodcutter_3"]},
					"paths": true,
					"quest_anchor": "forest_quest",
					"story_anchor": "forest_story",
				}
			},
			"village": {
				"name": "Village",
				"hex_type": "Settlement",
				"bounds": {"x": 0, "y": 20, "w": 60, "h": 25},
				"entry_points": {
					"forest": {"x": 20, "y": 20},
					"fields": {"x": 40, "y": 44},
					"mine": {"x": 20, "y": 44},
				},
				"content": {
					"houses": true,
					"village_square": {"pos": [30, 32]},
					"well": {"pos": [30, 30]},
					"shrine": {"pos": [28, 28]},
					"processing": {
						"sawmill": {"pos": [15, 25], "workers": ["sawmiller_1", "sawmiller_2"]},
						"mill": {"pos": [45, 28], "workers": ["miller_1", "miller_2"]},
						"forge": {"pos": [25, 35], "workers": ["blacksmith_1", "blacksmith_2"]},
						"distillery": {"pos": [35, 38], "workers": ["distiller_1", "distiller_2"]},
					},
					"civic": {
						"reeve_house": {"pos": [32, 28], "occupant": "reeve"},
						"healer_house": {"pos": [26, 32], "occupant": "healer"},
						"store": {"pos": [34, 34], "occupant": "storekeeper"},
					},
					"quest_anchors": ["village_quest_1", "village_quest_2"],
					"story_anchors": ["village_story_1", "village_story_2", "village_story_3"],
					"player_start": [30, 32],
				}
			},
			"fields": {
				"name": "Fields",
				"hex_type": "Grain",
				"bounds": {"x": 40, "y": 45, "w": 20, "h": 15},
				"entry_points": {"village": {"x": 40, "y": 45}},
				"content": {
					"crops": true,
					"farmstead": {"pos": [45, 50], "workers": ["farmer_1", "farmer_2", "farmer_3"]},
					"paths": true,
					"quest_anchor": "fields_quest",
					"story_anchor": "fields_story",
				}
			},
			"mine": {
				"name": "Mine",
				"hex_type": "Ore",
				"bounds": {"x": 0, "y": 45, "w": 20, "h": 15},
				"entry_points": {"village": {"x": 20, "y": 45}},
				"content": {
					"rocks": true,
					"mine_mouth": {"pos": [10, 52], "workers": ["miner_1", "miner_2", "miner_3"]},
					"mining_works": {"pos": [12, 50]},
					"paths": true,
					"quest_anchor": "mine_quest",
					"story_anchor": "mine_story",
				}
			},
		},
		"semantic_anchors": {
			# Named location anchors for quest/story placement
			"village_square": {"region": "village", "pos": [30, 32]},
			"village_hall": {"region": "village", "pos": [32, 28]},
			"well": {"region": "village", "pos": [30, 30]},
			"shrine": {"region": "village", "pos": [28, 28]},
			"sawmill": {"region": "village", "pos": [15, 25]},
			"mill": {"region": "village", "pos": [45, 28]},
			"forge": {"region": "village", "pos": [25, 35]},
			"distillery": {"region": "village", "pos": [35, 38]},
			"store": {"region": "village", "pos": [34, 34]},
			"reeve_house": {"region": "village", "pos": [32, 28]},
			"healer_house": {"region": "village", "pos": [26, 32]},
			"forest_entry": {"region": "forest", "pos": [10, 19]},
			"logging_camp": {"region": "forest", "pos": [5, 5]},
			"forest_story": {"region": "forest", "pos": [8, 10]},
			"forest_quest": {"region": "forest", "pos": [12, 8]},
			"farmstead": {"region": "fields", "pos": [45, 50]},
			"fields_story": {"region": "fields", "pos": [48, 48]},
			"fields_quest": {"region": "fields", "pos": [42, 52]},
			"mine_mouth": {"region": "mine", "pos": [10, 52]},
			"mine_story": {"region": "mine", "pos": [8, 50]},
			"mine_quest": {"region": "mine", "pos": [12, 53]},
		},
		"pilot_stories": [
			{
				"id": "E36B",
				"title": "The broken promise",
				"cast": ["Householder", "Potter / Lime Burner 2", "Healer", "Scavenger 2"],
				"anchors": ["village_square", "healer_house", "village_hall"],
				"description": "Separated spouses, promise about child access revoked, coercive dynamics"
			},
			{
				"id": "E53A",
				"title": "The debt triangle",
				"cast": ["Miner 1", "Metalworker 2", "Healer", "Watchkeeper"],
				"anchors": ["mine_mouth", "forge", "healer_house"],
				"description": "Debt chain frame-up, posthumous accusation, financial entanglement"
			},
			{
				"id": "E56A",
				"title": "The person nobody trusts",
				"cast": ["Scavenger 2", "Storekeeper", "Cistern Keeper", "Carter"],
				"anchors": ["store", "village_square", "village_hall"],
				"description": "Second-chance romance, distrusted reunion, boundaries vs ceremony"
			}
		]
	}
}

static func all() -> Array:
	var out: Array = []
	for k in PROFILES:
		out.append(PROFILES[k])
	return out

static func get(profile_id: String) -> Dictionary:
	return PROFILES.get(profile_id, {})

static func get_cast(profile_id: String) -> Dictionary:
	return get(profile_id).get("cast", {})

static func get_regions(profile_id: String) -> Dictionary:
	return get(profile_id).get("regions", {})

static func get_semantic_anchors(profile_id: String) -> Dictionary:
	return get(profile_id).get("semantic_anchors", {})

static func get_pilot_stories(profile_id: String) -> Array:
	return get(profile_id).get("pilot_stories", [])
extends RefCounted
class_name VillageCompositeProjection

## Builds a single large continuous area dictionary from a village test profile.
## Output shape matches DmbWorldData area dicts consumed by Overworld:
## { id, name, rows, theme, entities, ... }

const _Profiles = preload("res://sim/world/village_test_profiles.gd")
const _WorldData = preload("res://client/world/world_data.gd")

# Tile characters matching Overworld's expectations
const TILE_GRASS = "."
const TILE_DIRT = ","
const TILE_STONE = "#"
const TILE_WATER = "~"
const TILE_TREE = "T"
const TILE_CROP = "c"
const TILE_ROCK = "r"
const TILE_WALL = "W"
const TILE_FLOOR = "F"
const TILE_ROAD = "R"
const TILE_BRIDGE = "B"
const TILE_FENCE = "f"
const TILE_HEDGE = "h"

static func project(profile_id: String) -> Dictionary:
	var profile = _Profiles.get(profile_id)
	if profile.is_empty():
		push_error("VillageCompositeProjection: unknown profile " + profile_id)
		return {}
	
	var regions = _Profiles.get_regions(profile_id)
	var anchors = _Profiles.get_semantic_anchors(profile_id)
	var cast = _Profiles.get_cast(profile_id)
	
	# Calculate total map bounds
	var min_x = INF
	var min_y = INF
	var max_x = -INF
	var max_y = -INF
	for r_name in regions:
		var r = regions[r_name]
		var b = r["bounds"]
		min_x = min(min_x, b["x"])
		min_y = min(min_y, b["y"])
		max_x = max(max_x, b["x"] + b["w"])
		max_y = max(max_y, b["y"] + b["h"])
	
	var map_w = max_x - min_x
	var map_h = max_y - min_y
	
	# Build empty grid
	var rows: Array = []
	for y in range(map_h):
		rows.append(_make_row(map_w, TILE_GRASS))
	
	# Fill each region
	for r_name in regions:
		_fill_region(rows, regions[r_name], min_x, min_y, cast)
	
	# Connect regions with paths
	_connect_regions(rows, regions, min_x, min_y)
	
	# Build entities list
	var entities: Array = []
	_add_region_entities(entities, regions, min_x, min_y, cast, anchors)
	_add_anchor_markers(entities, anchors, min_x, min_y)
	
	# Player start
	var player_start = anchors["village_square"]["pos"]
	player_start = [player_start[0] - min_x, player_start[1] - min_y]
	
	return {
		"id": "village_test_" + profile_id.lower(),
		"name": profile["name"],
		"rows": rows,
		"theme": "village",
		"entities": entities,
		"player_start": player_start,
		"bounds": {"x": min_x, "y": min_y, "w": map_w, "h": map_h},
		"profile_id": profile_id,
		"semantic_anchors": anchors,
		"regions": regions,
	}

static func _make_row(width: int, fill_char: String) -> String:
	return fill_char * width

static func _set_tile(rows: Array, x: int, y: int, char: String) -> void:
	if y >= 0 and y < rows.size() and x >= 0 and x < rows[y].length():
		var row = rows[y]
		rows[y] = row.substr(0, x) + char + row.substr(x + 1)

static func _get_tile(rows: Array, x: int, y: int) -> String:
	if y >= 0 and y < rows.size() and x >= 0 and x < rows[y].length():
		return rows[y][x]
	return TILE_GRASS

static func _fill_region(rows: Array, region: Dictionary, offset_x: int, offset_y: int, cast: Dictionary) -> void:
	var b = region["bounds"]
	var rx = b["x"] - offset_x
	var ry = b["y"] - offset_y
	var rw = b["w"]
	var rh = b["h"]
	var hex_type = region["hex_type"]
	var content = region["content"]
	
	# Base terrain by hex type
	if hex_type == "Wood":
		_fill_forest(rows, rx, ry, rw, rh)
	elif hex_type == "Grain":
		_fill_fields(rows, rx, ry, rw, rh)
	elif hex_type == "Ore":
		_fill_mine(rows, rx, ry, rw, rh)
	elif hex_type == "Settlement":
		_fill_village(rows, rx, ry, rw, rh)
	
	# Add content (buildings, work areas, etc.)
	if content.has("logging_camp"):
		_add_logging_camp(rows, rx, ry, content["logging_camp"])
	if content.has("farmstead"):
		_add_farmstead(rows, rx, ry, content["farmstead"])
	if content.has("mine_mouth"):
		_add_mine_mouth(rows, rx, ry, content["mine_mouth"])
	if content.has("mining_works"):
		_add_mining_works(rows, rx, ry, content["mining_works"])
	if content.has("processing"):
		_add_processing_buildings(rows, rx, ry, content["processing"])
	if content.has("civic"):
		_add_civic_buildings(rows, rx, ry, content["civic"])
	if content.has("village_square"):
		_add_village_square(rows, rx, ry, content["village_square"])
	if content.has("well"):
		_add_well(rows, rx, ry, content["well"])
	if content.has("shrine"):
		_add_shrine(rows, rx, ry, content["shrine"])
	if content.has("houses"):
		_add_houses(rows, rx, ry, rw, rh)
	if content.has("trees"):
		_add_scattered_trees(rows, rx, ry, rw, rh)
	if content.has("crops"):
		_add_crops(rows, rx, ry, rw, rh)
	if content.has("rocks"):
		_add_scattered_rocks(rows, rx, ry, rw, rh)
	if content.has("paths"):
		_add_region_paths(rows, rx, ry, rw, rh, hex_type)

static func _fill_forest(rows: Array, x: int, y: int, w: int, h: int) -> void:
	for dy in range(h):
		for dx in range(w):
			var tx = x + dx
			var ty = y + dy
			# Dense forest with some clearings
			if randf() < 0.7:
				_set_tile(rows, tx, ty, TILE_TREE)
			else:
				_set_tile(rows, tx, ty, TILE_GRASS)

static func _fill_fields(rows: Array, x: int, y: int, w: int, h: int) -> void:
	for dy in range(h):
		for dx in range(w):
			var tx = x + dx
			var ty = y + dy
			# Crop rows with dirt paths
			if dy % 4 == 0:
				_set_tile(rows, tx, ty, TILE_DIRT)  # path between crop rows
			elif randf() < 0.8:
				_set_tile(rows, tx, ty, TILE_CROP)
			else:
				_set_tile(rows, tx, ty, TILE_DIRT)

static func _fill_mine(rows: Array, x: int, y: int, w: int, h: int) -> void:
	for dy in range(h):
		for dx in range(w):
			var tx = x + dx
			var ty = y + dy
			# Rocky terrain
			if randf() < 0.6:
				_set_tile(rows, tx, ty, TILE_ROCK)
			elif randf() < 0.3:
				_set_tile(rows, tx, ty, TILE_STONE)
			else:
				_set_tile(rows, tx, ty, TILE_DIRT)

static func _fill_village(rows: Array, x: int, y: int, w: int, h: int) -> void:
	for dy in range(h):
		for dx in range(w):
			var tx = x + dx
			var ty = y + dy
			# Village: mostly grass/dirt with building footprints added later
			if dy < 3 or dy >= h - 3 or dx < 3 or dx >= w - 3:
				_set_tile(rows, tx, ty, TILE_DIRT)  # perimeter
			else:
				_set_tile(rows, tx, ty, TILE_GRASS)

static func _add_logging_camp(rows: Array, rx: int, ry: int, camp: Dictionary) -> void:
	var pos = camp["pos"]
	var bx = rx + pos[0]
	var by = ry + pos[1]
	# 5x4 building footprint
	for dy in range(4):
		for dx in range(5):
			_set_tile(rows, bx + dx, by + dy, TILE_FLOOR)
	# Entrance
	_set_tile(rows, bx + 2, by + 3, TILE_DIRT)

static func _add_farmstead(rows: Array, rx: int, ry: int, farm: Dictionary) -> void:
	var pos = farm["pos"]
	var bx = rx + pos[0]
	var by = ry + pos[1]
	# Main house 6x5
	for dy in range(5):
		for dx in range(6):
			_set_tile(rows, bx + dx, by + dy, TILE_FLOOR)
	# Barn 4x4
	for dy in range(4):
		for dx in range(4):
			_set_tile(rows, bx + 8 + dx, by + 1 + dy, TILE_FLOOR)
	# Fence around
	for i in range(12):
		_set_tile(rows, bx - 1 + i, by - 1, TILE_FENCE)
		_set_tile(rows, bx - 1 + i, by + 5, TILE_FENCE)
	for i in range(7):
		_set_tile(rows, bx - 1, by - 1 + i, TILE_FENCE)
		_set_tile(rows, bx + 10, by - 1 + i, TILE_FENCE)

static func _add_mine_mouth(rows: Array, rx: int, ry: int, mine: Dictionary) -> void:
	var pos = mine["pos"]
	var bx = rx + pos[0]
	var by = ry + pos[1]
	# Mine entrance 4x3
	for dy in range(3):
		for dx in range(4):
			_set_tile(rows, bx + dx, by + dy, TILE_STONE)
	# Opening
	_set_tile(rows, bx + 1, by + 2, TILE_DIRT)
	_set_tile(rows, bx + 2, by + 2, TILE_DIRT)
	# Supports
	_set_tile(rows, bx, by, TILE_WALL)
	_set_tile(rows, bx + 3, by, TILE_WALL)

static func _add_mining_works(rows: Array, rx: int, ry: int, works: Dictionary) -> void:
	var pos = works["pos"]
	var bx = rx + pos[0]
	var by = ry + pos[1]
	# Processing area 6x4
	for dy in range(4):
		for dx in range(6):
			_set_tile(rows, bx + dx, by + dy, TILE_FLOOR)
	# Cart tracks
	for i in range(6):
		_set_tile(rows, bx + i, by + 4, TILE_ROAD)

static func _add_processing_buildings(rows: Array, rx: int, ry: int, processing: Dictionary) -> void:
	# Each processing building is 5x5 with distinct visual marker
	for name in processing:
		var b = processing[name]
		var pos = b["pos"]
		var bx = rx + pos[0]
		var by = ry + pos[1]
		
		# Building footprint
		for dy in range(5):
			for dx in range(5):
				_set_tile(rows, bx + dx, by + dy, TILE_FLOOR)
		
		# Distinctive roof/marker by type
		if name == "sawmill":
			_set_tile(rows, bx + 2, by, TILE_WALL)  # saw blade marker
		elif name == "mill":
			_set_tile(rows, bx + 2, by, TILE_ROCK)  # millstone
		elif name == "forge":
			_set_tile(rows, bx + 2, by, "#")  # anvil
		elif name == "distillery":
			_set_tile(rows, bx + 2, by, "D")  # still
		
		# Entrance
		_set_tile(rows, bx + 2, by + 4, TILE_DIRT)

static func _add_civic_buildings(rows: Array, rx: int, ry: int, civic: Dictionary) -> void:
	for name in civic:
		var b = civic[name]
		var pos = b["pos"]
		var bx = rx + pos[0]
		var by = ry + pos[1]
		
		if name == "store":
			# Store 6x5
			for dy in range(5):
				for dx in range(6):
					_set_tile(rows, bx + dx, by + dy, TILE_FLOOR)
			_set_tile(rows, bx + 3, by + 4, TILE_DIRT)  # entrance
		else:
			# House 5x5
			for dy in range(5):
				for dx in range(5):
					_set_tile(rows, bx + dx, by + dy, TILE_FLOOR)
			_set_tile(rows, bx + 2, by + 4, TILE_DIRT)  # entrance

static func _add_village_square(rows: Array, rx: int, ry: int, square: Dictionary) -> void:
	var pos = square["pos"]
	var bx = rx + pos[0]
	var by = ry + pos[1]
	# 8x6 paved square
	for dy in range(6):
		for dx in range(8):
			_set_tile(rows, bx + dx - 4, by + dy - 3, TILE_ROAD)

static func _add_well(rows: Array, rx: int, ry: int, well: Dictionary) -> void:
	var pos = well["pos"]
	var bx = rx + pos[0]
	var by = ry + pos[1]
	_set_tile(rows, bx, by, "o")  # well
	# Surrounding stones
	for dx in [-1, 0, 1]:
		for dy in [-1, 0, 1]:
			if dx != 0 or dy != 0:
				_set_tile(rows, bx + dx, by + dy, TILE_STONE)

static func _add_shrine(rows: Array, rx: int, ry: int, shrine: Dictionary) -> void:
	var pos = shrine["pos"]
	var bx = rx + pos[0]
	var by = ry + pos[1]
	# Small shrine 3x3
	for dy in range(3):
		for dx in range(3):
			_set_tile(rows, bx + dx - 1, by + dy - 1, TILE_STONE)
	_set_tile(rows, bx, by, "+")  # shrine symbol

static func _add_houses(rows: Array, rx: int, ry: int, w: int, h: int) -> void:
	# Scattered houses in village
	var positions = [
		[8, 8], [18, 8], [42, 8], [52, 8],
		[8, 20], [18, 20], [42, 20], [52, 20],
	]
	for p in positions:
		var bx = rx + p[0]
		var by = ry + p[1]
		for dy in range(5):
			for dx in range(5):
				_set_tile(rows, bx + dx, by + dy, TILE_FLOOR)
		_set_tile(rows, bx + 2, by + 4, TILE_DIRT)

static func _add_scattered_trees(rows: Array, rx: int, ry: int, w: int, h: int) -> void:
	for dy in range(h):
		for dx in range(w):
			if randf() < 0.15:
				_set_tile(rows, rx + dx, ry + dy, TILE_TREE)

static func _add_crops(rows: Array, rx: int, ry: int, w: int, h: int) -> void:
	# Already handled in _fill_fields

static func _add_scattered_rocks(rows: Array, rx: int, ry: int, w: int, h: int) -> void:
	for dy in range(h):
		for dx in range(w):
			if randf() < 0.1:
				_set_tile(rows, rx + dx, ry + dy, TILE_ROCK)

static func _add_region_paths(rows: Array, rx: int, ry: int, w: int, h: int, hex_type: String) -> void:
	# Main path through region
	if hex_type == "Wood":
		# Vertical path through forest
		for dy in range(h):
			_set_tile(rows, rx + w//2, ry + dy, TILE_DIRT)
	elif hex_type == "Grain":
		# Horizontal path through fields
		for dx in range(w):
			_set_tile(rows, rx + dx, ry + h//2, TILE_DIRT)
	elif hex_type == "Ore":
		# Path to mine
		for dy in range(h):
			_set_tile(rows, rx + w//2, ry + dy, TILE_DIRT)

static func _connect_regions(rows: Array, regions: Dictionary, offset_x: int, offset_y: int) -> void:
	# Connect village to forest (north)
	var village = regions["village"]
	var forest = regions["forest"]
	var v_b = village["bounds"]
	var f_b = forest["bounds"]
	var v_entry = village["entry_points"]["forest"]
	var f_entry = forest["entry_points"]["village"]
	
	# Path from forest entry to village entry
	var fx = f_entry["x"] - offset_x
	var fy = f_entry["y"] - offset_y
	var vx = v_entry["x"] - offset_x
	var vy = v_entry["y"] - offset_y
	_draw_path(rows, fx, fy, vx, vy, TILE_ROAD)
	
	# Connect village to fields (east)
	var fields = regions["fields"]
	var v_entry_f = village["entry_points"]["fields"]
	var f_entry_v = fields["entry_points"]["village"]
	_draw_path(rows, v_entry_f["x"] - offset_x, v_entry_f["y"] - offset_y,
		f_entry_v["x"] - offset_x, f_entry_v["y"] - offset_y, TILE_ROAD)
	
	# Connect village to mine (west)
	var mine = regions["mine"]
	var v_entry_m = village["entry_points"]["mine"]
	var m_entry_v = mine["entry_points"]["village"]
	_draw_path(rows, v_entry_m["x"] - offset_x, v_entry_m["y"] - offset_y,
		m_entry_v["x"] - offset_x, m_entry_v["y"] - offset_y, TILE_ROAD)

static func _draw_path(rows: Array, x1: int, y1: int, x2: int, y2: int, tile: String) -> void:
	# Simple L-shaped path
	var cx = x1
	var cy = y1
	while cx != x2:
		_set_tile(rows, cx, cy, tile)
		cx += 1 if x2 > cx else -1
	while cy != y2:
		_set_tile(rows, cx, cy, tile)
		cy += 1 if y2 > cy else -1
	_set_tile(rows, cx, cy, tile)

static func _add_region_entities(entities: Array, regions: Dictionary, offset_x: int, offset_y: int, cast: Dictionary, anchors: Dictionary) -> void:
	# Add NPCs, signs, exits, pickups, etc. as entities
	for r_name in regions:
		var region = regions[r_name]
		var content = region["content"]
		var rx = region["bounds"]["x"] - offset_x
		var ry = region["bounds"]["y"] - offset_y
		
		# Workers at production sites
		if content.has("logging_camp"):
			_add_worker_entities(entities, "logging_camp", content["logging_camp"], rx, ry, cast, "Woodcutter")
		if content.has("farmstead"):
			_add_worker_entities(entities, "farmstead", content["farmstead"], rx, ry, cast, "Farmer")
		if content.has("mine_mouth"):
			_add_worker_entities(entities, "mine_mouth", content["mine_mouth"], rx, ry, cast, "Miner")
		if content.has("processing"):
			for name in content["processing"]:
				_add_worker_entities(entities, name, content["processing"][name], rx, ry, cast, 
					{"sawmill": "Sawmiller", "mill": "Miller", "forge": "Blacksmith", "distillery": "Distiller"}[name])
		if content.has("civic"):
			for name in content["civic"]:
				var b = content["civic"][name]
				if b.has("occupant") and cast.has(b["occupant"]):
					var pos = b["pos"]
					entities.append({
						"kind": "npc",
						"id": b["occupant"],
						"pos": [rx + pos[0] + 2, ry + pos[1] + 2],
						"role": cast[b["occupant"]]["role"],
						"sprite": _role_to_sprite(cast[b["occupant"]]["role"]),
						"dialogue": _npc_dialogue_key(b["occupant"]),
					})
		
		# Signs at region entries
		if r_name != "village":
			var ep = region["entry_points"]["village"]
			entities.append({
				"kind": "sign",
				"id": r_name + "_sign",
				"pos": [rx + ep["x"], ry + ep["y"] - 1],
				"text": "To " + village["name"]
			})
		
		# Quest/story anchors as interaction points
		if content.has("quest_anchor"):
			var anchor_id = content["quest_anchor"]
			if anchors.has(anchor_id):
				var a = anchors[anchor_id]
				entities.append({
					"kind": "interaction",
					"id": anchor_id,
					"pos": [rx + a["pos"][0], ry + a["pos"][1]],
					"type": "quest",
					"prompt": "Investigate",
				})
		if content.has("story_anchor"):
			var anchor_id = content["story_anchor"]
			if anchors.has(anchor_id):
				var a = anchors[anchor_id]
				entities.append({
					"kind": "interaction",
					"id": anchor_id,
					"pos": [rx + a["pos"][0], ry + a["pos"][1]],
					"type": "story",
					"prompt": "Listen",
				})
		if content.has("quest_anchors"):
			for anchor_id in content["quest_anchors"]:
				if anchors.has(anchor_id):
					var a = anchors[anchor_id]
					entities.append({
						"kind": "interaction",
						"id": anchor_id,
						"pos": [a["pos"][0] - offset_x, a["pos"][1] - offset_y],
						"type": "quest",
						"prompt": "Talk",
					})
		if content.has("story_anchors"):
			for anchor_id in content["story_anchors"]:
				if anchors.has(anchor_id):
					var a = anchors[anchor_id]
					entities.append({
						"kind": "interaction",
						"id": anchor_id,
						"pos": [a["pos"][0] - offset_x, a["pos"][1] - offset_y],
						"type": "story",
						"prompt": "Listen",
					})

static func _add_worker_entities(entities: Array, building: String, building_data: Dictionary, rx: int, ry: int, cast: Dictionary, role: String) -> void:
	if not building_data.has("workers"):
		return
	var pos = building_data["pos"]
	var bx = rx + pos[0]
	var by = ry + pos[1]
	for i, worker_id in enumerate(building_data["workers"]):
		if cast.has(worker_id):
			entities.append({
				"kind": "npc",
				"id": worker_id,
				"pos": [bx + 1 + (i % 2) * 2, by + 1 + (i // 2) * 2],
				"role": role,
				"sprite": _role_to_sprite(role),
				"dialogue": _npc_dialogue_key(worker_id),
			})

static func _add_anchor_markers(entities: Array, anchors: Dictionary, offset_x: int, offset_y: int) -> void:
	# These are debug markers added when Location Anchors toggle is on
	# The actual rendering is handled by the test overlay
	pass

static func _role_to_sprite(role: String) -> String:
	match role:
		"Woodcutter": return "npc_woodcutter"
		"Farmer": return "npc_farmer"
		"Miner": return "npc_miner"
		"Sawmiller": return "npc_sawmiller"
		"Miller": return "npc_miller"
		"Blacksmith": return "npc_blacksmith"
		"Distiller": return "npc_distiller"
		"Reeve": return "npc_reeve"
		"Healer": return "npc_healer"
		"Storekeeper": return "npc_storekeeper"
		_: return "npc_villager"

static func _npc_dialogue_key(npc_id: String) -> String:
	# Map NPC to dialogue key in story_events
	return "village_test_" + npc_id

static func validate_projection(area: Dictionary) -> Dictionary:
	var errors: Array = []
	var warnings: Array = []
	
	if not area.has("rows") or area["rows"].is_empty():
		errors.append("No rows in projection")
		return {"valid": false, "errors": errors, "warnings": warnings}
	
	var rows = area["rows"]
	var h = rows.size()
	var w = rows[0].length() if h > 0 else 0
	
	# Check consistent row widths
	for i, row in rows:
		if row.length() != w:
			errors.append("Row " + str(i) + " has inconsistent width: " + str(row.length()) + " vs " + str(w))
	
	# Check dimensions
	if w < 40 or h < 30:
		warnings.append("Map may be too small: " + str(w) + "x" + str(h))
	elif w > 80 or h > 80:
		warnings.append("Map may be too large: " + str(w) + "x" + str(h))
	
	# Check player start
	if not area.has("player_start"):
		errors.append("Missing player_start")
	else:
		var ps = area["player_start"]
		if ps[0] < 0 or ps[0] >= w or ps[1] < 0 or ps[1] >= h:
			errors.append("Player start out of bounds: " + str(ps))
		elif _is_solid(rows[ps[1]][ps[0]]):
			errors.append("Player start on solid tile")
	
	# Check entities
	if area.has("entities"):
		var ids = {}
		for e in area["entities"]:
			if e.has("id"):
				if ids.has(e["id"]):
					errors.append("Duplicate entity ID: " + e["id"])
				ids[e["id"]] = true
	
	return {"valid": errors.is_empty(), "errors": errors, "warnings": warnings, "width": w, "height": h}

static func _is_solid(ch: String) -> bool:
	return ch in [TILE_TREE, TILE_STONE, TILE_WATER, TILE_WALL, TILE_ROCK, TILE_HEDGE, TILE_FENCE]
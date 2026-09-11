extends RefCounted
class_name DmbDungeonMap
## Lays out a generated dungeon as a DmbWorldData-shaped area: four rooms in a
## row, each dressed for its puzzle template, doors between rooms that open when
## the room's puzzle is solved, and a reward plinth in the last room. Read-only
## over dungeon + puzzle state; Overworld renders it like any other area.
##
## Layout: 4 rooms of 9x7 interior stacked north→south, with a corridor tile
## between. Entry at the bottom (south) so the player climbs the tower / descends
## the cave upward on screen.

const PREFIX := "dg_"
const ROOM_W := 11
const ROOM_H := 7
const W := ROOM_W + 2
const ENTRY := [6, 30]


static func area_id(d: Dictionary) -> String:
	return PREFIX + str(d["id"])


static func is_dungeon_area(id: String) -> bool:
	return id.begins_with(PREFIX)


static func dungeon_of(id: String) -> String:
	return id.substr(PREFIX.length())


## room index 0 is the entry room (bottom), room 3 the top.
static func room_origin_y(room: int) -> int:
	return 1 + (3 - room) * (ROOM_H + 1)


static func area_for(d: Dictionary, puzzle_states: Dictionary, world_node_area: String, arrive_pos: Array) -> Dictionary:
	var H := 4 * (ROOM_H + 1) + 1
	var rows: Array = []
	for y in range(H):
		var line := ""
		for x in range(W):
			line += "#"
		rows.append(line)
	for room in range(4):
		var oy := room_origin_y(room)
		for y in range(oy, oy + ROOM_H):
			for x in range(1, W - 1):
				rows[y] = _put(rows[y], x, ".")
	var entities: Array = []
	var aid := area_id(d)
	var tower := str(d["kind"]) == "tower"
	# Entry door back to the world node.
	rows[H - 1] = _put(rows[H - 1], 6, ":")
	entities.append({"kind": "exit", "id": aid + "_out", "pos": [6, H - 1], "to_area": world_node_area, "to_pos": arrive_pos, "facing": "down",
		"travel_text": "Daylight. You had forgotten it was a thing."})
	entities.append({"kind": "sign", "id": aid + "_sign", "pos": [2, room_origin_y(0) + ROOM_H - 1],
		"text": "%s\n\nFour rooms. Each asks one thing. The last gives one thing." % ("The tower's stair is worn in the middle, where every foot before yours went." if tower else "The cave is dressed stone past the first yard. Somebody built this fast, and recently.")})
	for room in range(4):
		var p: Dictionary = d["puzzles"][room]
		var key := "%s/%s" % [d["id"], p["id"]]
		var st: Dictionary = puzzle_states.get(key, DmbPuzzleLogic.fresh_state(p))
		var solved := bool(st.get("solved", false))
		var oy := room_origin_y(room)
		# Door to the next room: open (path tile) once solved, else a stone door.
		if room < 3:
			var door_y := oy - 1
			if solved:
				rows[door_y] = _put(rows[door_y], 6, ":")
			else:
				entities.append({"kind": "door", "id": "%s_%s_door" % [aid, p["id"]], "pos": [6, door_y], "marker": "door_dungeon",
					"text": "Shut. The room has not been answered.", "puzzle_key": key})
		# Room clue plaque.
		entities.append({"kind": "sign", "id": "%s_%s_clue" % [aid, p["id"]], "pos": [1, oy], "text": "%s\n\n%s" % [str(p["title"]), str(p["clue"])], "puzzle_key": key})
		_dress(entities, rows, aid, p, st, oy, key)
	# Reward plinth in the top room.
	var top := room_origin_y(3)
	entities.append({"kind": "pickup", "id": "%s_reward" % aid, "pos": [5, top + 5], "sprite": "diamond", "requires_dungeon_solved": str(d["id"]),
		"dungeon_reward": str(d["id"]), "text": ""})
	# The sigil this dungeon *provides* to the network sits with the reward.
	entities.append({"kind": "pickup", "id": "%s_sigil" % aid, "pos": [7, top + 5], "sprite": "ring", "requires_dungeon_solved": str(d["id"]),
		"grant": {"item": str(d["provides"])}, "text": "%s. Cut here, for a lock somewhere else." % DmbItems.name_of(str(d["provides"]))})
	return {"id": aid, "name": "%s %s" % [DmbFactions.name_of(str(d["faction"])), "tower" if tower else "cave"], "rows": rows, "theme": "dungeon", "entities": entities, "dungeon": d}


static func _dress(entities: Array, rows: Array, aid: String, p: Dictionary, st: Dictionary, oy: int, key: String) -> void:
	var base := {"puzzle_key": key}
	var cx := 6
	var cy := oy + 3
	match str(p["type"]):
		"offerings":
			for i in range(p["slots"].size()):
				var sl: Dictionary = p["slots"][i]
				var filled: bool = st.get("filled", {}).has(str(sl["id"]))
				entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % [aid, sl["id"]], "pos": [cx - 2 + i * 4, oy + 1], "marker": "idol" if filled else "box",
					"puzzle_action": {"kind": "place", "slot": str(sl["id"])}, "text": "A niche" + (" — filled." if filled else ", shaped for something.")}))
			for it in p["items"]:
				entities.append(_m(base, {"kind": "pickup", "id": "%s_%s_item_%s" % [aid, p["id"], it], "pos": [cx + 3, cy + 1], "sprite": DmbItems.sprite_of(it),
					"grant": {"item": it}, "text": DmbItems.describe(it)}))
		"exchange":
			var taken := bool(st.get("key_taken", false))
			entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % [aid, p["pedestal"]], "pos": [cx, cy], "marker": "ring" if not taken else "box",
				"puzzle_action": {"kind": "exchange"}, "text": "A plate on a pedestal." + (" A key rests on it." if not taken else " Bare.")}))
			for it in p["items"]:
				entities.append(_m(base, {"kind": "pickup", "id": "%s_%s_item_%s" % [aid, p["id"], it], "pos": [cx - 3, cy + 1], "sprite": DmbItems.sprite_of(it),
					"grant": {"item": it}, "text": DmbItems.describe(it)}))
		"switch_chain":
			for i in range(3):
				entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % [aid, p["levers"][i]], "pos": [cx - 3 + i * 3, cy], "marker": "staff",
					"puzzle_action": {"kind": "pull", "index": i}, "text": "Lever %s." % ["one", "two", "three"][i]}))
		"plate_hold":
			entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % [aid, p["plate"]], "pos": [cx, cy], "marker": "ring",
				"puzzle_action": {"kind": "place"}, "text": "A pressure plate."}))
			for it in p["items"]:
				entities.append(_m(base, {"kind": "pickup", "id": "%s_%s_item_%s" % [aid, p["id"], it], "pos": [cx - 3, cy + 1], "sprite": DmbItems.sprite_of(it),
					"grant": {"item": it}, "text": DmbItems.describe(it)}))
		"timed_gate":
			entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % [aid, p["lever"]], "pos": [2, cy + 2], "marker": "staff",
				"puzzle_action": {"kind": "pull"}, "text": "A lever, and a rope that runs up into the dark."}))
			entities.append(_m(base, {"kind": "logs", "id": "%s_%s_gate" % [aid, p["id"]], "pos": [cx, oy], "marker": "door_stone",
				"puzzle_action": {"kind": "pass"}, "text": "A gate of iron bars." + (" Lifted — and counting." if bool(st.get("open", false)) else " Down.")}))
		"mosaic":
			for i in range(4):
				entities.append(_m(base, {"kind": "logs", "id": "%s_%s_tile%d" % [aid, p["id"], i], "pos": [cx - 3 + i * 2, cy], "marker": "stone_shard",
					"puzzle_action": {"kind": "tread", "index": i}, "text": "A %s stone, set in the floor." % ["red", "blue", "green", "grey"][i]}))
		"magic_target":
			entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % [aid, p["target"]], "pos": [cx, cy], "marker": "fire_0" if int(p["spell"]) == 1 else ("rock" if int(p["spell"]) == 6 else "mirror"),
				"puzzle_action": {"kind": "cast"}, "text": "The way is blocked by %s." % str(p["desc"])}))
		"two_levers":
			for i in range(2):
				entities.append(_m(base, {"kind": "logs", "id": "%s_%s" % [aid, p["levers"][i]], "pos": [cx - 2 + i * 4, cy], "marker": "staff",
					"puzzle_action": {"kind": "pull", "index": i}, "text": "The %s lever." % ["left", "right"][i]}))


static func _m(a: Dictionary, b: Dictionary) -> Dictionary:
	var out := a.duplicate()
	for k in b:
		out[k] = b[k]
	return out


static func _put(line: String, x: int, ch: String) -> String:
	return line.substr(0, x) + ch + line.substr(x + 1)

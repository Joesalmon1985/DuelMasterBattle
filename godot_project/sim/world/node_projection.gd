extends RefCounted
class_name DmbNodeProjection
## Projects one board Node (a hex corner) into a top-down area dictionary in the
## exact DmbWorldData shape, so Overworld renders it unchanged. Read-only over
## the sim: nothing here mutates world state.
##
## Next Pass §3/§4: roads and tracks are drawn *into* the node (as path tiles of
## the owning faction's kind running to the map edge) rather than being places;
## settlement content (production huts, works, housing, civic buildings, workers,
## quest NPCs, the local dungeon's door) is laid out from DmbSettlementProfile.

const PREFIX := "wn_"
const W := 17
const H := 13
## Exit slots, one per possible neighbour: [exit tile, arrival tile, facing on arrival].
const SLOTS := [
	[[8, 0], [8, 1], "down"],
	[[3, 12], [3, 11], "up"],
	[[13, 12], [13, 11], "up"],
]
## Road tile runs from the map centre toward each exit, so a corner with three
## roads reads as a junction and one with a track reads as a footpath.
const ROAD_RUNS := [
	[[8, 1], [8, 2], [8, 3], [8, 4], [8, 5]],
	[[3, 11], [4, 10], [5, 9], [6, 8], [7, 7]],
	[[13, 11], [12, 10], [11, 9], [10, 8], [9, 7]],
]
const DEMON_SPOTS := [[4, 4], [12, 4], [8, 9]]
const UNIT_SPOTS := [[6, 7], [10, 7], [6, 9], [10, 9], [5, 5], [11, 5]]
const CART_SPOTS := [[7, 10], [9, 10], [6, 10], [10, 10]]
const HOME_DOOR := [3, 4]
const HOME_ARRIVE := [3, 5]
## Building footprints (design doc §19): production huts on the flanks, works
## north-east, houses (roof + door tiles) south and north, civic round the well.
const PRODUCTION_SPOTS := [[2, 5], [14, 5], [2, 7], [14, 7], [6, 2], [10, 2]]
const PROCESSING_SPOTS := [[11, 3], [13, 3], [12, 2]]
const HOUSE_SPOTS := [[3, 9], [13, 9], [2, 9], [14, 9], [6, 3], [10, 3], [7, 3], [9, 3]]
const CIVIC_SPOTS := {"well": [8, 6], "shrine": [6, 5], "hall": [10, 5], "market": [10, 6]}
const WORKER_SPOTS := [[3, 5], [13, 5], [3, 7], [13, 7], [7, 2], [9, 2]]
const QUEST_SPOTS := [[7, 8], [9, 8], [8, 10]]
const DUNGEON_DOOR := [6, 3]
const HEX_WORDS := {"forest": "forest", "hills": "brick hills", "pasture": "sheepwalks",
	"fields": "wheat", "mountains": "ore seams", "desert": "dead ground"}
const BUILDING_MARKER := {
	"woodcutter_hut": "logs", "clay_pit": "rock", "sheepfold": "box", "grain_field": "seed", "mine_mouth": "door_stone",
	"sawmill": "logs", "kiln": "rock", "weaver": "box", "mill": "box", "smithy": "rock", "charcoal_burner": "logs", "brewhouse": "box",
	"well": "ring", "shrine": "idol", "hall": "book_red", "market": "box", "gate_tower": "door_stone",
}
const WORKER_SPRITE := {"woodcutter": "villager_a", "brickmaker": "villager_b", "shepherd": "child", "reaper": "villager_a", "miner": "dwarf"}
const WORKER_LINE := {
	"woodcutter": "Wood. Always wood. The forest gives and the sawyer takes and I am the bit in between.",
	"brickmaker": "Clay, water, fire, patience. The kiln eats the patience first.",
	"shepherd": "Forty head on the high walk. Thirty-nine, if you count properly. I don't.",
	"reaper": "Grain's in. Grain's always in, or it's always coming. Ask me in winter.",
	"miner": "Ore seam runs east under the road. Don't tell the neighbours.",
}
const MOOD_LINE := {
	"grateful": "You're the one who sorted that business. Drink's on the steading.",
	"uneasy": "Things have been quiet. Not the good kind.",
	"watched": "Riders through twice this week. Somebody's paying attention to us now.",
	"mourning": "We buried one. Not the first this year. Mind the well.",
	"wary": "Wizard. We know what you are. Just — do it somewhere else.",
}


static func area_id(nid: int) -> String:
	return PREFIX + str(nid)


static func is_world_area(id: String) -> bool:
	return id.begins_with(PREFIX)


static func node_of(id: String) -> int:
	return int(id.substr(PREFIX.length()))


static func area_for(sim: DmbWorldSim, nid: int, adv_state: Dictionary = {}) -> Dictionary:
	var board: DmbHexBoard = sim.board
	var node: Dictionary = board.nodes[nid]
	var neighbours: Array = board.node_neighbors(nid)
	var home: bool = nid == sim.player_home_node()
	var profile := DmbSettlementProfile.describe(sim, nid)
	var rows: Array = _rows(profile, neighbours.size(), home)
	var entities: Array = []
	var aid := area_id(nid)
	# Exits: one per road/track to a neighbouring node. Arrival lands one tile
	# inside the neighbour's reciprocal slot.
	for i in range(neighbours.size()):
		var other: int = neighbours[i]
		var back: int = board.node_neighbors(other).find(nid)
		var slot: Array = SLOTS[i]
		var back_slot: Array = SLOTS[back]
		var road: String = sim.catan.road_owner(board.edge_between(nid, other))
		var way: String = "the %s road" % DmbFactions.name_of(road) if road != "" else "a rough track"
		entities.append({"kind": "exit", "id": "%s_exit%d" % [aid, i], "pos": slot[0], "to_area": area_id(other),
			"to_pos": back_slot[1], "facing": back_slot[2], "travel_text": "You follow %s to %s." % [way, node_name(sim, other)]})
	if home:
		entities.append({"kind": "exit", "id": "%s_door" % aid, "pos": HOME_DOOR, "to_area": "jane_placeholder", "to_pos": [4, 5], "facing": "up", "travel_text": "Jane's door. It sticks."})
	# Signpost: what this corner is and what the three lands around it are doing.
	entities.append({"kind": "sign", "id": "%s_sign" % aid, "pos": [8, 7] if profile["kind"] != "wild" else [8, 6], "text": _sign_text(sim, nid, profile)})
	# Demons: one encounter per infected hex, form by count.
	var k := 0
	for hid in node["hexes"]:
		var h: Dictionary = board.hexes[hid]
		var demons: int = h["demons"]
		if demons <= 0:
			continue
		var form := DmbUnits.demon_form(demons)
		entities.append({"kind": "creature", "id": "%s_h%d_t%d_n%d" % [aid, hid, sim.turn, demons], "enemy_id": form,
			"pos": DEMON_SPOTS[k], "world_hex": int(hid),
			"intro": "Something has come up out of the %s. %s." % [hex_word(h), "One, so far" if demons == 1 else ("Two of them" if demons == 2 else "The ground is thick with them")]})
		k += 1
	# Rulers sit at their home settlement.
	var spot := 0
	for fid in sim.factions:
		if sim.units.home_node(fid) == nid and spot < UNIT_SPOTS.size():
			var data: Dictionary = DmbFactions.DATA[fid]
			entities.append({"kind": "npc", "id": "%s_ruler_%s" % [aid, fid], "name": str(data.get("ruler", data.get("king", "The ruler"))),
				"sprite": "official", "pos": UNIT_SPOTS[spot], "facing": "down", "lines": _ruler_lines(sim, fid)})
			spot += 1
	# Champions and heroes standing here.
	for u in sim.units.units_at(nid):
		if spot >= UNIT_SPOTS.size():
			break
		var champ: bool = str(u["kind"]) == "champion"
		entities.append({"kind": "npc", "id": "%s_unit%d" % [aid, int(u["id"])], "name": str(u["name"]),
			"sprite": "hedge_mage" if champ else "knight", "pos": UNIT_SPOTS[spot], "facing": "down",
			"lines": ["%s. %s." % [DmbFactions.name_of(str(u["faction"])), "I hold this corner against what comes up out of the ground" if champ else "Mustered for the season. Paid by the head"]]})
		spot += 1
	# Carts resting at the node.
	var c := 0
	for cart in sim.carts.carts_at_node(nid):
		if c >= CART_SPOTS.size():
			break
		entities.append({"kind": "logs", "id": "%s_cart%d" % [aid, int(cart["id"])], "pos": CART_SPOTS[c],
			"text": "A trade cart, lashed and waiting. Bound for %s." % DmbFactions.name_of(str(cart.get("to", "")))})
		c += 1
	if profile["kind"] == "wild":
		var d: Dictionary = profile["dungeon"]
		if not d.is_empty():
			_add_dungeon_door(entities, aid, d, adv_state)
	else:
		_add_settlement(sim, nid, aid, profile, entities, adv_state)
	return {"id": aid, "name": node_name(sim, nid), "rows": rows, "theme": "overworld", "entities": entities, "profile": profile}


## Settlement dressing from the profile: buildings as readable props, workers
## with a line each, the quest's inhabitants, and the door to the local dungeon
## if it stands on this node's ground (it never does — dungeons sit on their own
## node — but the signpost points to it).
static func _add_settlement(sim: DmbWorldSim, nid: int, aid: String, p: Dictionary, entities: Array, adv_state: Dictionary) -> void:
	var i := 0
	for pr in p["production"]:
		for n in range(int(pr["n"])):
			if i >= PRODUCTION_SPOTS.size():
				break
			var spotp: Array = PRODUCTION_SPOTS[i]
			var b := str(pr["building"])
			var txt := "%s%s." % [b.capitalize(), " — standing idle; nothing grows here" if bool(pr.get("idle", false)) else ""]
			entities.append({"kind": "logs", "id": "%s_prod%d" % [aid, i], "pos": spotp, "marker": str(BUILDING_MARKER.get(b, "box")), "text": txt, "building": b})
			i += 1
	for j in range(mini(p["processing"].size(), PROCESSING_SPOTS.size())):
		var b := str(p["processing"][j])
		entities.append({"kind": "logs", "id": "%s_works%d" % [aid, j], "pos": PROCESSING_SPOTS[j], "marker": str(BUILDING_MARKER.get(b, "box")),
			"text": "The %s. Level %d work: %s goes in, something better comes out." % [b.replace("_", " "), int(p["development"]), ", ".join(PackedStringArray(_inputs(b)))], "building": b})
	for cv in p["civic"]:
		if CIVIC_SPOTS.has(cv):
			var pos: Array = CIVIC_SPOTS[cv]
			entities.append({"kind": "logs", "id": "%s_civic_%s" % [aid, cv], "pos": pos, "marker": str(BUILDING_MARKER.get(cv, "box")),
				"text": _civic_text(cv, p), "building": cv})
	# Workers: one per production building type, standing by their works.
	var w := 0
	for pr in p["production"]:
		if w >= WORKER_SPOTS.size():
			break
		var worker := str(pr["worker"])
		var line := str(WORKER_LINE.get(worker, "Work."))
		if p["mood"] != "" and w == 0:
			line = str(MOOD_LINE.get(p["mood"], line))
		entities.append({"kind": "npc", "id": "%s_worker_%s" % [aid, worker], "name": worker.capitalize(), "sprite": str(WORKER_SPRITE.get(worker, "villager_a")),
			"pos": WORKER_SPOTS[w], "facing": "down", "lines": [line], "worker": worker, "workplace": PRODUCTION_SPOTS[mini(w, PRODUCTION_SPOTS.size() - 1)]})
		w += 1
	# Quest inhabitants (§5): the settlement's local story, or its aftermath.
	var q := DmbQuests.build(sim, nid)
	if not q.is_empty():
		var done := str(adv_state.get("quests", {}).get(str(nid), ""))
		for qi in range(mini(q["npcs"].size(), QUEST_SPOTS.size())):
			var npc: Dictionary = q["npcs"][qi]
			var e := {"kind": "npc", "id": "%s_quest_%s" % [aid, npc["id"]], "name": str(npc["name"]), "sprite": str(npc["sprite"]),
				"pos": QUEST_SPOTS[qi], "facing": "down", "quest_id": str(q["id"]), "quest_npc": str(npc["id"]), "quest_node": nid}
			if done != "":
				e["lines"] = [str(q["outcomes"].get(done, {}).get("after", q["outcomes"].get(done, {}).get("text", "It's done.")))]
			else:
				e["lines"] = []
				e["choice_event"] = "settlement_quest"
			entities.append(e)


static func _add_dungeon_door(entities: Array, aid: String, d: Dictionary, adv_state: Dictionary) -> void:
	var solved := 0
	for k in adv_state.get("puzzles", {}):
		if str(k).begins_with(str(d["id"]) + "/") and bool(adv_state["puzzles"][k].get("solved", false)):
			solved += 1
	var tower := str(d["kind"]) == "tower"
	entities.append({"kind": "door", "id": "%s_dungeon" % aid, "pos": DUNGEON_DOOR, "marker": "door_stone",
		"dungeon_id": str(d["id"]), "choice_event": "enter_dungeon",
		"text": "%s. %s %d of 4 rooms answered." % [
			"A tower, older than the steading that stands in its shadow. The door is not locked. It has never needed to be." if tower else "A cave mouth in the hillside, new — the earth opened when they broke ground for the steading, and something has been laying stone inside ever since.",
			"", solved]})


static func node_name(sim: DmbWorldSim, nid: int) -> String:
	var s: Dictionary = sim.catan.settlements.get(nid, {})
	if s.is_empty():
		var d := sim.dungeons.at_node(nid)
		if not d.is_empty():
			return "%s %s" % [DmbFactions.name_of(str(d["faction"])), "tower" if str(d["kind"]) == "tower" else "cave"]
		return "Crossing %d" % nid
	var f := DmbFactions.name_of(str(s["owner"]))
	return "%s %s" % [f, "town" if bool(s.get("city", false)) else "steading"]


static func hex_word(h: Dictionary) -> String:
	return str(HEX_WORDS.get(h["terrain"], h["terrain"]))


static func _sign_text(sim: DmbWorldSim, nid: int, p: Dictionary) -> String:
	var parts: Array = []
	for hid in sim.board.nodes[nid]["hexes"]:
		var h: Dictionary = sim.board.hexes[hid]
		var bit := hex_word(h)
		if int(h["token"]) > 0:
			bit += " (%d)" % int(h["token"])
		var d: int = h["demons"]
		if d >= 3:
			bit += " — overrun"
		elif d == 2:
			bit += " — nothing grows"
		elif d == 1:
			bit += " — uneasy"
		parts.append(bit)
	var text := "%s. Three lands meet here: %s. Turn %d." % [node_name(sim, nid), ", ".join(parts), sim.turn]
	if p["kind"] != "wild":
		text += "\n" + DmbSettlementProfile.summary(p)
		var d: Dictionary = p["dungeon"]
		if not d.is_empty():
			text += "\nA %s stands at %s, %s." % ["tower" if str(d["kind"]) == "tower" else "cave", "Crossing %d" % int(d["node"]), _direction_hint(sim, nid, int(d["node"]))]
	var roads: Array = []
	for r in p["roads"]:
		roads.append("%s to %s" % ["%s road" % DmbFactions.name_of(str(r["owner"])) if r["owner"] != "" else "track", node_name(sim, int(r["to"]))])
	text += "\nWays: %s." % ", ".join(PackedStringArray(roads))
	return text


static func _direction_hint(sim: DmbWorldSim, from: int, to: int) -> String:
	var nbs: Array = sim.board.node_neighbors(from)
	var i := nbs.find(to)
	if i >= 0:
		return ["by the north way", "by the south-west way", "by the south-east way"][i]
	for j in range(nbs.size()):
		if to in sim.board.node_neighbors(int(nbs[j])):
			return "two crossings %s" % ["north", "south-west", "south-east"][j]
	return "some way off"


static func _ruler_lines(sim: DmbWorldSim, fid: String) -> Array:
	var data: Dictionary = DmbFactions.DATA[fid]
	var wts: Dictionary = sim.ai_weights(fid)
	var stance := str(data.get("stance", "guardian"))
	var lines: Array = [str(data.get("blurb", "%s." % DmbFactions.name_of(fid)))]
	if stance == "guardian":
		lines.append("We spend on clearing the ground before we spend on walls. Ask the sheep what happens otherwise.")
	else:
		lines.append("Roads first. Demons are a weather. You do not build for weather.")
	lines.append("Roads %.1f, settlements %.1f, treating the land %.1f, fighting %.1f. That is how I weigh it. For now." % [wts["roads"], wts["settlements"], wts["treat"], wts["fight"]])
	return lines


static func _civic_text(cv: String, p: Dictionary) -> String:
	match cv:
		"well":
			return "The well." + (" The water smells sweet. Sweet is wrong." if int(p["infection"]) > 0 else " Cold and clear.")
		"shrine":
			return "A shrine to whatever the %s pray to. Fresh offerings." % DmbFactions.name_of(p["owner"])
		"hall":
			return "The town hall. Ledgers, arguments, and a fire that never goes out."
		"market":
			return "Market stalls. %s." % (", ".join(PackedStringArray(p["products"])).capitalize() + " for sale" if not p["products"].is_empty() else "Nothing much for sale")
	return cv.capitalize()


static func _inputs(b: String) -> Array:
	for rule in DmbSettlementProfile.PROCESSING:
		if str(rule[0]) == b:
			return rule[1]
	return []


static func _exit_count(p: Dictionary) -> int:
	return p["roads"].size()


## Tile rows: forest border, terrain family floor, road runs to each exit, the
## home house, and for towns a ring of wall marking the upgrade.
static func _rows(p: Dictionary, exits: int, home: bool) -> Array:
	var rows: Array = []
	var floor := "."
	match str(p["family"]):
		"hills":
			floor = ","
		"desert":
			floor = "a"
		"fields":
			floor = "."
	for y in range(H):
		var line := ""
		for x in range(W):
			var edge: bool = x == 0 or y == 0 or x == W - 1 or y == H - 1
			var ch := floor
			if edge:
				ch = "T" if str(p["family"]) != "desert" else "t"
			elif str(p["family"]) == "forest" and ((x * 5 + y * 3) % 11 == 0) and x > 1 and x < W - 2 and y > 1 and y < H - 2:
				ch = ","
			line += ch
		rows.append(line)
	# Roads and tracks drawn into the node (§3): owned roads are paved ":" all
	# the way; tracks only reach two tiles in, as a worn footpath.
	for i in range(mini(exits, SLOTS.size())):
		var pexit: Array = SLOTS[i][0]
		rows[pexit[1]] = _put(rows[pexit[1]], pexit[0], ":")
		var run: Array = ROAD_RUNS[i]
		var owned: bool = i < p["roads"].size() and str(p["roads"][i]["owner"]) != ""
		var length: int = run.size() if owned else 2
		for j in range(length):
			var q: Array = run[j]
			rows[q[1]] = _put(rows[q[1]], q[0], ":")
	# Housing (design doc §7): a roof tile over a door tile per household, capped
	# by the spots available; towns fill every spot.
	for i in range(mini(int(p.get("housing", 0)), HOUSE_SPOTS.size())):
		var hs: Array = HOUSE_SPOTS[i]
		rows[hs[1]] = _put(rows[hs[1]], hs[0], "R")
		rows[hs[1] + 1] = _put(rows[hs[1] + 1], hs[0], "D")
	if p["kind"] == "town":
		# Town wall (design doc: city upgrade adds enclosure), gaps at the exits.
		for x in range(1, W - 1):
			if rows[1][x] != ":":
				rows[1] = _put(rows[1], x, "#")
			if rows[H - 2][x] != ":":
				rows[H - 2] = _put(rows[H - 2], x, "#")
		for y in range(1, H - 1):
			rows[y] = _put(rows[y], 1, "#")
			rows[y] = _put(rows[y], W - 2, "#")
	if home:
		for y in [1, 2]:
			for x in range(2, 6):
				rows[y] = _put(rows[y], x, "R")
		for x in range(2, 6):
			rows[3] = _put(rows[3], x, "#")
	return rows


static func _put(line: String, x: int, ch: String) -> String:
	return line.substr(0, x) + ch + line.substr(x + 1)

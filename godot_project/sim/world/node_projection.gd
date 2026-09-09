extends RefCounted
class_name DmbNodeProjection
## Projects one board Node (a hex corner) into a top-down area dictionary in the
## exact DmbWorldData shape, so Overworld renders it unchanged. Read-only over
## the sim: nothing here mutates world state.

const PREFIX := "wn_"
const W := 17
const H := 13
## Exit slots, one per possible neighbour: [exit tile, arrival tile, facing on arrival].
const SLOTS := [
	[[8, 0], [8, 1], "down"],
	[[3, 12], [3, 11], "up"],
	[[13, 12], [13, 11], "up"],
]
const DEMON_SPOTS := [[4, 4], [12, 4], [8, 9]]
const UNIT_SPOTS := [[6, 7], [10, 7], [6, 9], [10, 9], [5, 5], [11, 5]]
const CART_SPOTS := [[2, 8], [14, 8], [2, 10], [14, 10]]
const HOME_DOOR := [3, 4]
const HOME_ARRIVE := [3, 5]
const HEX_WORDS := {"forest": "forest", "hills": "brick hills", "pasture": "sheepwalks",
	"fields": "wheat", "mountains": "ore seams", "desert": "dead ground"}


static func area_id(nid: int) -> String:
	return PREFIX + str(nid)


static func is_world_area(id: String) -> bool:
	return id.begins_with(PREFIX)


static func node_of(id: String) -> int:
	return int(id.substr(PREFIX.length()))


static func area_for(sim: DmbWorldSim, nid: int) -> Dictionary:
	var board: DmbHexBoard = sim.board
	var node: Dictionary = board.nodes[nid]
	var neighbours: Array = board.node_neighbors(nid)
	var home: bool = nid == sim.player_home_node()
	var rows: Array = _rows(neighbours.size(), home)
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
	# Signpost: what the three lands around this corner are doing.
	entities.append({"kind": "sign", "id": "%s_sign" % aid, "pos": [8, 6], "text": _sign_text(sim, nid)})
	# Demons: one encounter per infected hex, form by count. The id carries the
	# turn and count so a re-infected hex is a fresh encounter, not a "defeated" ghost.
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
	return {"id": aid, "name": node_name(sim, nid), "rows": rows, "theme": "overworld", "entities": entities}


static func node_name(sim: DmbWorldSim, nid: int) -> String:
	var s: Dictionary = sim.catan.settlements.get(nid, {})
	if s.is_empty():
		return "Crossing %d" % nid
	var f := DmbFactions.name_of(str(s["owner"]))
	return "%s %s" % [f, "town" if bool(s.get("city", false)) else "steading"]


static func hex_word(h: Dictionary) -> String:
	return str(HEX_WORDS.get(h["terrain"], h["terrain"]))


static func _sign_text(sim: DmbWorldSim, nid: int) -> String:
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
	return "%s. Three lands meet here: %s. Turn %d." % [node_name(sim, nid), ", ".join(parts), sim.turn]


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


static func _rows(exits: int, home: bool) -> Array:
	var rows: Array = []
	for y in range(H):
		var line := ""
		for x in range(W):
			var edge: bool = x == 0 or y == 0 or x == W - 1 or y == H - 1
			line += "T" if edge else "."
		rows.append(line)
	for i in range(mini(exits, SLOTS.size())):
		var p: Array = SLOTS[i][0]
		rows[p[1]] = _put(rows[p[1]], p[0], ":")
		var q: Array = SLOTS[i][1]
		rows[q[1]] = _put(rows[q[1]], q[0], ":")
	if home:
		for y in [1, 2]:
			for x in range(2, 6):
				rows[y] = _put(rows[y], x, "R")
		for x in range(2, 6):
			rows[3] = _put(rows[3], x, "#")
	return rows


static func _put(line: String, x: int, ch: String) -> String:
	return line.substr(0, x) + ch + line.substr(x + 1)

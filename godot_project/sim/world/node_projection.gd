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
## Legacy fixed size, kept for the wild crossing; settlements size themselves
## from the profile (DmbSettlementLayout.dims).
const W := DmbSettlementLayout.WILD_W
const H := DmbSettlementLayout.WILD_H
const HEX_WORDS := {"forest": "forest", "hills": "brick hills", "pasture": "sheepwalks",
	"fields": "wheat", "mountains": "ore seams", "desert": "dead ground"}
const BUILDING_MARKER := {
	"woodcutter_hut": "woodcutter_hut", "clay_pit": "rock", "sheepfold": "box", "grain_field": "seed", "mine_mouth": "miner_house",
	"sawmill": "logs", "kiln": "rock", "weaver": "box", "mill": "box", "smithy": "rock", "charcoal_burner": "logs", "brewhouse": "box",
	"well": "ring", "shrine": "idol", "hall": "book_red", "market": "box", "gate_tower": "door_tower",
}
const WORKER_SPRITE := {"woodcutter": "woodcutter", "brickmaker": "villager_b", "shepherd": "child", "reaper": "reaper", "miner": "dwarf"}
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
	var hex_terrains := {}
	var hex_demons := {}
	for hid in node["hexes"]:
		hex_terrains[int(hid)] = str(board.hexes[hid]["terrain"])
		hex_demons[int(hid)] = int(board.hexes[hid]["demons"])
	var layout := DmbSettlementLayout.build(sim.seed, nid, profile, neighbours.size(), home, node["hexes"], hex_terrains, hex_demons)
	var rows: Array = layout["rows"]
	var entities: Array = []
	var aid := area_id(nid)
	# Exits: one per road/track to a neighbouring node. Arrival lands one tile
	# inside the neighbour's reciprocal slot — sized for *that* neighbour's map.
	for i in range(neighbours.size()):
		var other: int = neighbours[i]
		var back: int = board.node_neighbors(other).find(nid)
		var slot: Array = layout["exits"][i]
		var back_slot: Array = DmbSettlementLayout.exit_slots(DmbSettlementLayout.dims(DmbSettlementProfile.describe(sim, other)))[back]
		var road: String = sim.catan.road_owner(board.edge_between(nid, other))
		var way: String = "the %s road" % DmbFactions.name_of(road) if road != "" else "a rough track"
		entities.append({"kind": "exit", "id": "%s_exit%d" % [aid, i], "pos": slot[0], "to_area": area_id(other),
			"to_pos": back_slot[1], "facing": back_slot[2], "travel_text": "You follow %s to %s." % [way, node_name(sim, other)]})
	if home:
		entities.append({"kind": "exit", "id": "%s_door" % aid, "pos": layout["home_door"], "to_area": "jane_placeholder", "to_pos": [4, 5], "facing": "up", "travel_text": "Jane's door. It sticks."})
	# Signpost: what this corner is and what the three lands around it are doing.
	entities.append({"kind": "sign", "id": "%s_sign" % aid, "pos": layout["sign"], "text": _sign_text(sim, nid, profile)})
	# Demons: one encounter per infected hex, form by count, standing in the
	# sector of the land they came out of.
	for hid in node["hexes"]:
		var h: Dictionary = board.hexes[hid]
		var demons: int = h["demons"]
		if demons <= 0 or not layout["demon_spots"].has(int(hid)):
			continue
		var form := DmbUnits.demon_form(demons)
		entities.append({"kind": "creature", "id": "%s_h%d_t%d_n%d" % [aid, hid, sim.turn, demons], "enemy_id": form,
			"pos": layout["demon_spots"][int(hid)], "world_hex": int(hid),
			"intro": "Something has come up out of the %s. %s." % [hex_word(h), "One, so far" if demons == 1 else ("Two of them" if demons == 2 else "The ground is thick with them")]})
	# Rulers, champions, heroes and quest folk share the standing room beside
	# the roads, nearest the plaza first.
	var spots: Array = layout["npc_spots"]
	var spot := 0
	for fid in sim.factions:
		if sim.units.home_node(fid) == nid and spot < spots.size():
			var data: Dictionary = DmbFactions.DATA[fid]
			entities.append({"kind": "npc", "id": "%s_ruler_%s" % [aid, fid], "name": str(data.get("ruler", data.get("king", "The ruler"))),
				"sprite": "official", "pos": spots[spot], "facing": "down", "lines": _ruler_lines(sim, fid)})
			spot += 1
	for u in sim.units.units_at(nid):
		if spot >= spots.size() - 3:
			break   # keep room for the quest's people
		var champ: bool = str(u["kind"]) == "champion"
		entities.append({"kind": "npc", "id": "%s_unit%d" % [aid, int(u["id"])], "name": str(u["name"]),
			"sprite": "hedge_mage" if champ else "knight", "pos": spots[spot], "facing": "down",
			"lines": ["%s. %s." % [DmbFactions.name_of(str(u["faction"])), "I hold this corner against what comes up out of the ground" if champ else "Mustered for the season. Paid by the head"]]})
		spot += 1
	# Carts resting at the node.
	var c := 0
	var cart_spots: Array = layout["cart_spots"]
	for cart in sim.carts.carts_at_node(nid):
		if c >= cart_spots.size():
			break
		entities.append({"kind": "logs", "id": "%s_cart%d" % [aid, int(cart["id"])], "pos": cart_spots[c],
			"text": "A trade cart, lashed and waiting. Bound for %s." % DmbFactions.name_of(str(cart.get("to", "")))})
		c += 1
	if profile["kind"] == "wild":
		var d: Dictionary = profile["dungeon"]
		if not d.is_empty():
			_add_dungeon_door(entities, aid, d, adv_state, layout)
	else:
		_add_settlement(sim, nid, aid, profile, entities, adv_state, layout, spot)
	return {"id": aid, "name": node_name(sim, nid), "rows": rows, "theme": "overworld", "entities": entities, "profile": profile,
		"player_start": layout["player_start"], "layout": {"w": layout["w"], "h": layout["h"], "plaza": [layout["plaza"].position.x, layout["plaza"].position.y, layout["plaza"].size.x, layout["plaza"].size.y]}}


## Settlement dressing from the profile: every laid-out building gets a readable
## prop at its door, production huts get their worker standing beside them, the
## quest's inhabitants stand in the plaza, and the signpost points at the local
## dungeon (which sits on its own node).
static func _add_settlement(sim: DmbWorldSim, nid: int, aid: String, p: Dictionary, entities: Array, adv_state: Dictionary, layout: Dictionary, spot: int) -> void:
	var prod_i := 0
	var works_i := 0
	var house_i := 0
	var first_worker := true
	for b in layout["buildings"]:
		var kind := str(b["kind"])
		var bid := str(b["building"])
		var front: Array = b["front"]
		match kind:
			"production":
				var idle: bool = bool(b.get("idle", false))
				var txt := "%s%s." % [bid.capitalize(), " — standing idle; nothing grows here" if idle else ""]
				entities.append({"kind": "logs", "id": "%s_prod%d" % [aid, prod_i], "pos": front, "marker": str(BUILDING_MARKER.get(bid, "box")), "text": txt, "building": bid, "world_hex": int(b["hex"])})
				var worker := str(b.get("worker", ""))
				var stand: Array = b["stand"]
				if worker != "" and not stand.is_empty():
					var line := str(WORKER_LINE.get(worker, "Work."))
					if idle:
						line = "Nothing to do. Nothing grows. We stand here so the works are not empty."
					elif p["mood"] != "" and first_worker:
						line = str(MOOD_LINE.get(p["mood"], line))
					first_worker = false
					entities.append({"kind": "npc", "id": "%s_worker_%s%d" % [aid, worker, prod_i], "name": worker.capitalize(), "sprite": str(WORKER_SPRITE.get(worker, "villager_a")),
						"pos": stand, "facing": "down", "lines": [line], "worker": worker, "workplace": front})
				prod_i += 1
			"processing":
				entities.append({"kind": "logs", "id": "%s_works%d" % [aid, works_i], "pos": front, "marker": str(BUILDING_MARKER.get(bid, "box")),
					"text": "The %s. Level %d work: %s goes in, something better comes out." % [bid.replace("_", " "), int(p["development"]), ", ".join(PackedStringArray(_inputs(bid)))], "building": bid})
				works_i += 1
			"civic":
				entities.append({"kind": "logs", "id": "%s_civic_%s" % [aid, bid], "pos": front, "marker": str(BUILDING_MARKER.get(bid, "box")),
					"text": _civic_text(bid, p), "building": bid})
			"house":
				entities.append({"kind": "door", "id": "%s_house%d" % [aid, house_i], "pos": front, "building": "house",
					"text": _house_text(p, house_i)})
				house_i += 1
	# The well stands in the plaza itself.
	if "well" in p["civic"]:
		entities.append({"kind": "logs", "id": "%s_civic_well" % aid, "pos": layout["well"], "marker": str(BUILDING_MARKER["well"]), "text": _civic_text("well", p), "building": "well"})
	# Quest inhabitants (§5): the settlement's local story, or its aftermath.
	var q := DmbQuests.build(sim, nid)
	if not q.is_empty():
		var spots: Array = layout["npc_spots"]
		var done := str(adv_state.get("quests", {}).get(str(nid), ""))
		for qi in range(q["npcs"].size()):
			if spot >= spots.size():
				break
			var npc: Dictionary = q["npcs"][qi]
			var e := {"kind": "npc", "id": "%s_quest_%s" % [aid, npc["id"]], "name": str(npc["name"]), "sprite": str(npc["sprite"]),
				"pos": spots[spot], "facing": "down", "quest_id": str(q["id"]), "quest_npc": str(npc["id"]), "quest_node": nid}
			spot += 1
			if done != "":
				e["lines"] = [str(q["outcomes"].get(done, {}).get("after", q["outcomes"].get(done, {}).get("text", "It's done.")))]
			else:
				e["lines"] = []
				e["choice_event"] = "settlement_quest"
			entities.append(e)


static func _house_text(p: Dictionary, i: int) -> String:
	var owner := DmbFactions.name_of(p["owner"])
	var lines := [
		"A %s house. Shut. Smoke from the chimney." % owner,
		"A house. Someone is singing inside, badly.",
		"A house with a new door. The old one is stacked round the side for firewood.",
		"A house. A child watches you from the window and does not wave.",
		"A house. Washing on the line: %s." % ("wool, mostly" if "wool" in p["products"] else "linen, patched"),
		"A house. The step is swept. The step is always swept.",
	]
	var t := str(lines[i % lines.size()])
	if int(p["infection"]) >= 2 and i % 3 == 0:
		t += " A mark on the lintel: someone in here is sick."
	return t


static func _add_dungeon_door(entities: Array, aid: String, d: Dictionary, adv_state: Dictionary, layout: Dictionary) -> void:
	var solved := 0
	for k in adv_state.get("puzzles", {}):
		if str(k).begins_with(str(d["id"]) + "/") and bool(adv_state["puzzles"][k].get("solved", false)):
			solved += 1
	var tower := str(d["kind"]) == "tower"
	var pos: Array = [layout["well"][0], layout["well"][1] - 2]
	for b in layout["buildings"]:
		if str(b["kind"]) == "dungeon":
			pos = b["front"]
	entities.append({"kind": "door", "id": "%s_dungeon" % aid, "pos": pos, "marker": "door_dungeon",
		"dungeon_id": str(d["id"]), "choice_event": "enter_dungeon",
		"text": "%s. %s %d of 4 rooms answered." % [
			"A tower, older than the steading that stands in its shadow. The door is not locked. It has never needed to be." if tower else "A cave mouth in the hillside, new — the earth opened when they broke ground for the steading, and something has been laying stone inside ever since.",
			"", solved]})


## Where John stands after climbing back out of the node's dungeon: the tile
## in front of the projected dungeon door (the door itself is an entity tile).
static func dungeon_arrive(sim: DmbWorldSim, nid: int) -> Array:
	var a := area_for(sim, nid)
	for e in a["entities"]:
		if e["kind"] == "door" and str(e["id"]) == "%s_dungeon" % a["id"]:
			return [int(e["pos"][0]), int(e["pos"][1]) + 1]
	return a["player_start"].duplicate()


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

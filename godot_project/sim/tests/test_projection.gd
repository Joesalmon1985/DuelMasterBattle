extends DmbTestCase
## Node → area projection must produce exactly the DmbWorldData shape Overworld
## already renders: uniform rows, exits on walkable tiles pointing at real
## neighbour areas with reciprocal exits, one bestiary creature per infected hex.


func run() -> void:
	var sim := DmbWorldSim.new(5)
	sim.setup()
	for i in range(30):
		sim.advance_turn()
	var home := sim.player_home_node()
	var infected_total := 0
	var creatures_total := 0
	for nid in range(sim.board.nodes.size()):
		var a := DmbNodeProjection.area_for(sim, nid)
		assert_eq(a["id"], "wn_%d" % nid, "area id")
		for key in ["name", "rows", "theme", "entities"]:
			assert_true(a.has(key), "area has %s" % key)
		var rows: Array = a["rows"]
		assert_eq(rows.size(), DmbNodeProjection.H, "row count")
		for r in rows:
			assert_eq(str(r).length(), DmbNodeProjection.W, "uniform width")
		var exits := 0
		var creatures := 0
		for e in a["entities"]:
			assert_true(e.has("kind") and e.has("id") and e.has("pos"), "entity shape")
			var p: Array = e["pos"]
			var ch: String = str(rows[p[1]])[p[0]]
			if e["kind"] == "exit":
				exits += 1
				assert_true(ch in [":", ".", ",", "a"], "exit %s stands on walkable tile" % e["id"])
				var to := str(e["to_area"])
				if to == "jane_placeholder":
					assert_eq(nid, home, "only the home node opens onto Jane's house")
				else:
					assert_true(to.begins_with("wn_"), "exit targets a world node")
					var back := DmbNodeProjection.area_for(sim, DmbNodeProjection.node_of(to))
					var reciprocal := false
					for f in back["entities"]:
						if f["kind"] == "exit" and str(f["to_area"]) == a["id"]:
							reciprocal = true
					assert_true(reciprocal, "%s → %s has a way back" % [a["id"], to])
			elif e["kind"] == "creature":
				creatures += 1
				assert_true(DmbBestiary.has(str(e["enemy_id"])), "demon is a real bestiary creature")
				assert_true(sim.board.hexes[int(e["world_hex"])]["demons"] > 0, "creature stands for an infected hex")
				assert_true(ch in [".", ",", "a", ":"], "creature on open ground (%s)" % ch)
		var expected_exits: int = sim.board.node_neighbors(nid).size() + (1 if nid == home else 0)
		assert_eq(exits, expected_exits, "one exit per neighbour (+door at home) for node %d" % nid)
		var infected := 0
		for hid in sim.board.nodes[nid]["hexes"]:
			if sim.board.hexes[hid]["demons"] > 0:
				infected += 1
		assert_eq(creatures, infected, "one creature per infected hex at node %d" % nid)
		infected_total += infected
		creatures_total += creatures
	assert_true(creatures_total > 0, "after 30 turns something is infected somewhere (%d)" % infected_total)
	# Home node: Jane's house and a ruler to talk to.
	var ha := DmbNodeProjection.area_for(sim, home)
	var has_door := false
	var has_ruler := false
	for e in ha["entities"]:
		if e["kind"] == "exit" and str(e["to_area"]) == "jane_placeholder":
			has_door = true
		if e["kind"] == "npc" and str(e["id"]).contains("ruler"):
			has_ruler = true
			assert_true(e["lines"].size() >= 2, "ruler has something to say")
	assert_true(has_door, "home node has Jane's door")
	assert_true(has_ruler, "home node has its ruler")
	assert_true(str(ha["rows"][1]).contains("RRRR"), "home node draws the house")
	# Pure function of sim state.
	assert_eq(str(DmbNodeProjection.area_for(sim, 7)), str(DmbNodeProjection.area_for(sim, 7)), "projection is deterministic")
	_check_settlements_and_dungeons(sim)
	# Treating a hex removes its creature from the projection.
	var target := -1
	for hid in range(sim.board.hexes.size()):
		if sim.board.hexes[hid]["demons"] == 1:
			target = hid
			break
	if target >= 0:
		var nid: int = sim.board.hexes[target]["nodes"][0]
		var before := _creatures(DmbNodeProjection.area_for(sim, nid))
		sim.infection.treat(target)
		assert_eq(_creatures(DmbNodeProjection.area_for(sim, nid)), before - 1, "treating a hex clears its encounter")


func _creatures(a: Dictionary) -> int:
	var n := 0
	for e in a["entities"]:
		if e["kind"] == "creature":
			n += 1
	return n


## §4/§6: settlement nodes show buildings, workers and quest folk from the
## profile; towns draw a wall; dungeon nodes show a door; every entity stands on
## a walkable tile and no two solid entities share one.
func _check_settlements_and_dungeons(sim: DmbWorldSim) -> void:
	var settlements := 0
	var towns := 0
	var dungeon_doors := 0
	for nid in range(sim.board.nodes.size()):
		var a := DmbNodeProjection.area_for(sim, nid)
		var rows: Array = a["rows"]
		var occupied := {}
		for e in a["entities"]:
			if e["kind"] in ["exit", "trigger"]:
				continue
			var p: Array = e["pos"]
			var key := "%d,%d" % [p[0], p[1]]
			assert_true(not occupied.has(key), "no two entities share %s at node %d (%s vs %s)" % [key, nid, e["id"], occupied.get(key, "")])
			occupied[key] = e["id"]
			var ch: String = str(rows[p[1]])[p[0]]
			assert_true(ch in [".", ",", "a", ":"], "%s stands on walkable %s at node %d" % [e["id"], ch, nid])
		var s: Dictionary = sim.catan.settlements.get(nid, {})
		if not s.is_empty():
			settlements += 1
			var prof: Dictionary = a["profile"]
			assert_true(prof["kind"] in ["steading", "town"], "settlement profile kind")
			var buildings := 0
			var workers := 0
			var quest_npcs := 0
			for e in a["entities"]:
				if e.has("building"):
					buildings += 1
				if e.has("worker"):
					workers += 1
				if e.has("quest_id"):
					quest_npcs += 1
			assert_true(buildings >= 2, "settlement %d has buildings (%d)" % [nid, buildings])
			assert_true(workers >= 1, "settlement %d has a worker" % nid)
			assert_true(quest_npcs >= 2, "settlement %d has quest inhabitants (%d)" % [nid, quest_npcs])
			assert_true(str(a["name"]).ends_with("steading") or str(a["name"]).ends_with("town"), "settlement name")
			if bool(s["city"]):
				towns += 1
				assert_true(str(rows[1]).contains("#"), "town %d draws a wall" % nid)
				assert_true(prof["housing"] > DmbSettlementProfile.describe(sim, nid)["development"], "town has more housing than a steading")
		elif not sim.dungeons.at_node(nid).is_empty():
			var found := false
			for e in a["entities"]:
				if e.has("dungeon_id"):
					found = true
					assert_eq(str(e["choice_event"]), "enter_dungeon", "dungeon door is enterable")
			assert_true(found, "dungeon node %d shows its door" % nid)
			dungeon_doors += 1
			assert_true(str(a["name"]).ends_with("tower") or str(a["name"]).ends_with("cave"), "dungeon node named for it")
	assert_true(settlements >= 8, "eight or more settlements projected (%d)" % settlements)
	assert_eq(dungeon_doors, sim.dungeons.dungeons.size(), "every dungeon has a door on its node")
	# A settlement→city upgrade changes the map visibly.
	var nid := -1
	for k in sim.catan.settlements:
		if not bool(sim.catan.settlements[k]["city"]):
			nid = int(k)
			break
	if nid >= 0:
		var before := DmbNodeProjection.area_for(sim, nid)
		sim.catan.settlements[nid]["city"] = true
		var after := DmbNodeProjection.area_for(sim, nid)
		assert_true(str(before["rows"]) != str(after["rows"]), "city upgrade changes the tiles")
		assert_true(after["entities"].size() > before["entities"].size(), "city upgrade adds buildings")
		sim.catan.settlements[nid]["city"] = false

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
				assert_true(ch == ":" or ch == ".", "exit %s stands on walkable tile" % e["id"])
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
				assert_true(ch == ".", "creature on open ground")
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

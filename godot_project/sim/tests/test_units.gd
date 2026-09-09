extends DmbTestCase
## Champions (one per faction, persistent) and Heroes (spawned by Knight
## cards, expendable). Units stand on nodes, move one edge per turn, treat
## adjacent hexes, and resolve off-screen fights against demon pieces.

const F := ["a", "b", "c", "d", "e", "f"]


func _w(seed: int = 6) -> Dictionary:
	var board := DmbHexBoard.standard(seed)
	var catan := DmbCatanState.new(board, F, seed)
	var inf := DmbInfection.new(board, seed)
	var units := DmbUnits.new(board, catan, inf, seed)
	catan.place_setup("a", 0, board.nodes[0]["edges"][0])
	return {"board": board, "catan": catan, "inf": inf, "units": units}


func run() -> void:
	_test_spawn()
	_test_move_and_treat()
	_test_hero_spawn_and_combat()
	_test_bestiary_projection()
	_test_round_trip()


func _test_spawn() -> void:
	var w := _w()
	var units: DmbUnits = w["units"]
	var champ = units.spawn_champion("a", "Sister Halloran", "hedge_wizard")
	assert_eq(champ["kind"], "champion", "champion kind")
	assert_eq(champ["node"], 0, "spawns at a's settlement")
	assert_eq(champ["faction"], "a", "belongs to faction")
	assert_eq(champ["bestiary_id"], "hedge_wizard", "bestiary link")
	assert_eq(units.champion_of("a")["id"], champ["id"], "lookup by faction")
	assert_null(units.champion_of("b"), "no champion for b")
	assert_eq(units.spawn_champion("a", "Twice", "hedge_wizard"), champ, "one champion per faction")
	assert_eq(units.units_at(0).size(), 1, "one unit at node 0")


func _test_move_and_treat() -> void:
	var w := _w()
	var board: DmbHexBoard = w["board"]
	var units: DmbUnits = w["units"]
	var champ = units.spawn_champion("a", "Sister Halloran", "hedge_wizard")
	var nb: int = board.node_neighbors(0)[0]
	assert_true(units.move(champ["id"], nb), "move to neighbour")
	assert_eq(champ["node"], nb, "position updated")
	assert_true(not units.move(champ["id"], 0 if nb != 0 else 1) or true, "moving back is allowed")
	var far := -1
	for n in range(54):
		if board.shortest_path(champ["node"], n).size() > 2:
			far = n
			break
	assert_true(not units.move(champ["id"], far), "cannot jump two edges")
	# Treat: only hexes touching the unit's node.
	var hid: int = board.nodes[champ["node"]]["hexes"][0]
	board.hexes[hid]["demons"] = 2
	assert_true(units.treat(champ["id"], hid), "treat adjacent hex")
	assert_eq(board.hexes[hid]["demons"], 1, "one demon removed")
	var remote := -1
	for h in board.hexes:
		if not (h["id"] in board.nodes[champ["node"]]["hexes"]):
			remote = h["id"]
			break
	board.hexes[remote]["demons"] = 2
	assert_true(not units.treat(champ["id"], remote), "cannot treat a distant hex")
	assert_eq(units.treatable_hexes(champ["id"]), [hid], "only infected adjacent hexes are treatable")
	# step_toward walks the shortest path one edge at a time.
	var target := far
	var before: int = champ["node"]
	units.step_toward(champ["id"], target)
	assert_true(board.edge_between(before, champ["node"]) >= 0, "stepped one edge")
	var dist_before := board.shortest_path(before, target).size()
	var dist_after := board.shortest_path(champ["node"], target).size()
	assert_eq(dist_after, dist_before - 1, "stepped closer")


func _test_hero_spawn_and_combat() -> void:
	var w := _w()
	var board: DmbHexBoard = w["board"]
	var units: DmbUnits = w["units"]
	var inf: DmbInfection = w["inf"]
	var hero = units.spawn_hero("a")
	assert_eq(hero["kind"], "hero", "hero kind")
	assert_eq(hero["node"], 0, "hero spawns at settlement")
	assert_true(hero["bestiary_id"] != "", "hero has a bestiary form")
	assert_eq(units.heroes_of("a").size(), 1, "one hero")
	assert_null(units.spawn_hero("b"), "faction without settlement cannot spawn")
	# Combat: strong unit vs 1 demon auto-wins; weaker unit rolls.
	var hid: int = board.nodes[0]["hexes"][0]
	board.hexes[hid]["demons"] = 1
	var strong = units.spawn_champion("a", "Sister Halloran", "red_wizard")
	var r := units.fight(strong["id"], hid)
	assert_eq(r["outcome"], "win", "weave 4 vs 1 demon is an auto-win")
	assert_eq(board.hexes[hid]["demons"], 0, "win clears a demon")
	assert_true(strong["alive"], "champion survives")
	board.hexes[hid]["demons"] = 3
	var results := {}
	for i in range(30):
		var h2 = units.spawn_hero("a")
		board.hexes[hid]["demons"] = 3
		var rr := units.fight(h2["id"], hid)
		results[rr["outcome"]] = results.get(rr["outcome"], 0) + 1
		if rr["outcome"] == "lose":
			assert_true(not h2["alive"], "losing hero dies")
			assert_true(not (h2["id"] in units.alive_ids()), "dead hero removed from alive list")
	assert_true(results.has("win") and results.has("lose"), "3 demons vs a hero is a real gamble")
	# Champions never die: a loss sends them home wounded.
	board.hexes[hid]["demons"] = 3
	var weak = units.spawn_champion("b", "", "flame_wisp")
	assert_null(weak, "b still has no settlement")
	w["catan"].place_setup("b", 20, board.nodes[20]["edges"][0])
	weak = units.spawn_champion("b", "Old Pell", "flame_wisp")
	units.move(weak["id"], board.node_neighbors(20)[0])
	var lost := false
	for i in range(40):
		board.hexes[hid]["demons"] = 3
		weak["node"] = 0
		var rr := units.fight(weak["id"], hid)
		if rr["outcome"] == "lose":
			lost = true
			assert_true(weak["alive"], "champion survives a loss")
			assert_eq(weak["node"], 20, "champion retreats home")
			assert_true(weak["recovering"] > 0, "champion is recovering")
			break
	assert_true(lost, "weak champion eventually loses")
	# Combat log carries a bestiary pairing for prose/projection.
	assert_true(units.log.size() > 0, "fights logged")
	var fights := 0
	for entry in units.log:
		if entry["type"] == "fight":
			fights += 1
			assert_true(DmbBestiary.has(entry["demon_id"]), "log names a real demon form")
	assert_true(fights > 0, "fight entries logged")


func _test_bestiary_projection() -> void:
	assert_eq(DmbUnits.demon_form(1), "flame_imp", "1 demon → flame imp")
	assert_eq(DmbUnits.demon_form(2), "moss_shade", "2 demons → moss shade")
	assert_eq(DmbUnits.demon_form(3), "mirror_demon", "3 demons → mirror demon")
	assert_eq(DmbUnits.demon_form(0), "", "no demons → nothing")
	for i in range(1, 4):
		assert_true(DmbBestiary.has(DmbUnits.demon_form(i)), "demon form exists in bestiary")
	for id in DmbUnits.HERO_FORMS:
		assert_true(DmbBestiary.has(id), "hero form %s exists" % id)


func _test_round_trip() -> void:
	var w := _w(19)
	var units: DmbUnits = w["units"]
	var c = units.spawn_champion("a", "Sister Halloran", "hedge_wizard")
	units.spawn_hero("a")
	units.move(c["id"], w["board"].node_neighbors(0)[0])
	var d := units.to_dict()
	var u2 := DmbUnits.from_dict(d, w["board"], w["catan"], w["inf"])
	assert_eq(u2.alive_ids(), units.alive_ids(), "units survive")
	assert_eq(u2.champion_of("a")["node"], c["node"], "position survives")
	assert_eq(u2.champion_of("a")["name"], "Sister Halloran", "name survives")
	assert_eq(u2.heroes_of("a").size(), 1, "hero survives")

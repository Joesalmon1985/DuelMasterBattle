extends DmbTestCase
## Settlement dungeons (brief §6–§7): one tower per founding settlement on a
## reserved nearby node, caves for later settlements, four puzzles each, one
## dependency per dungeon pointing strictly backwards, all solvable, save-safe.


func run() -> void:
	_test_towers_at_setup()
	_test_reserved_blocks_catan()
	_test_caves_follow_new_settlements()
	_test_dependencies_form_dag()
	_test_every_puzzle_solvable()
	_test_rewards_progress()
	_test_save_roundtrip()
	_test_determinism()


func _test_towers_at_setup() -> void:
	var sim := DmbWorldSim.new(11)
	sim.setup()
	var n_settle := sim.catan.settlements.size()
	assert_eq(sim.dungeons.dungeons.size(), n_settle, "one tower per founding settlement")
	for d in sim.dungeons.dungeons:
		assert_eq(str(d["kind"]), "tower", "founding dungeons are towers")
		assert_true(not sim.catan.settlements.has(int(d["node"])), "tower not on a settlement node")
		assert_true(sim.dungeons.is_reserved(int(d["node"])), "tower node reserved")
		assert_eq(d["puzzles"].size(), 4, "four puzzles")
		assert_true(sim.catan.settlements.has(int(d["settlement"])), "tower tied to a real settlement")
		# Nearby: within 3 node steps of its settlement.
		var dist := _node_dist(sim.board, int(d["settlement"]), int(d["node"]))
		assert_true(dist >= 1 and dist <= 3, "tower %s within 3 steps of its settlement (got %d)" % [d["id"], dist])
	var nodes := {}
	for d in sim.dungeons.dungeons:
		assert_true(not nodes.has(int(d["node"])), "no two dungeons share a node")
		nodes[int(d["node"])] = true


func _test_reserved_blocks_catan() -> void:
	var sim := DmbWorldSim.new(11)
	sim.setup()
	for f in sim.factions:
		for nid in sim.catan.legal_settlement_nodes(f, true):
			assert_true(not sim.dungeons.is_reserved(int(nid)), "reserved node %d never legal for settlement" % int(nid))
		for nid in sim.catan.legal_settlement_nodes(f, false):
			assert_true(not sim.dungeons.is_reserved(int(nid)), "reserved node %d never legal for settlement (roads)" % int(nid))
	for i in range(60):
		sim.advance_turn()
	for nid in sim.catan.settlements:
		assert_true(not sim.dungeons.is_reserved(int(nid)), "no settlement ever built on a reserved node after 60 turns")


func _test_caves_follow_new_settlements() -> void:
	var found_cave := false
	for seed in [3, 5, 11, 21]:
		var sim := DmbWorldSim.new(seed)
		sim.setup()
		var towers := sim.dungeons.dungeons.size()
		for i in range(80):
			var events := sim.advance_turn()
			for e in events:
				if str(e["type"]) == "cave":
					found_cave = true
					var d := sim.dungeons.at_node(int(e["node"]))
					assert_eq(str(d["kind"]), "cave", "later settlement spawns a cave")
					assert_eq(int(d["settlement"]), int(e["settlement"]), "cave tied to the new settlement")
					assert_true(e.has("text") and str(e["text"]).contains("cave"), "cave event has prose")
		assert_true(sim.dungeons.dungeons.size() >= towers + sim.founded.size() - 2, "most founded settlements got a cave (%d founded, %d dungeons, %d towers)" % [sim.founded.size(), sim.dungeons.dungeons.size(), towers])
	assert_true(found_cave, "at least one cave appeared across seeds")


func _test_dependencies_form_dag() -> void:
	for seed in [1, 7, 11, 42]:
		var sim := DmbWorldSim.new(seed)
		sim.setup()
		for i in range(60):
			sim.advance_turn()
		assert_eq(sim.dungeons.validate(), [], "seed %d: dependency graph valid" % seed)
		for d in sim.dungeons.dungeons:
			var need: Dictionary = d["needs"]
			var has_dep_room := false
			for p in d["puzzles"]:
				if str(p["type"]) == "offerings":
					has_dep_room = true
					var wants: Array = []
					for s in p["slots"]:
						wants.append(str(s["item"]))
					assert_true(str(need["item"]) in wants, "%s's offerings room asks for its dependency %s" % [d["id"], need["item"]])
			assert_true(has_dep_room, "%s has a dependency room" % d["id"])
			if int(d["index"]) == 0:
				assert_eq(str(need["from"]), "settlement", "first dungeon depends on its settlement")
			else:
				assert_true(str(need["from"]) != str(d["id"]), "no self dependency")


func _test_every_puzzle_solvable() -> void:
	var sim := DmbWorldSim.new(9)
	sim.setup()
	var types := {}
	for d in sim.dungeons.dungeons:
		for p in d["puzzles"]:
			types[str(p["type"])] = true
			var st := DmbPuzzleLogic.fresh_state(p)
			var inv: Array = ["grey_stone", "iron_key"]
			for it in p.get("items", []):
				inv.append(it)
			for s in p.get("slots", []):
				inv.append(str(s["item"]))
			var ctx := {"items": inv, "spells": [1, 6, 0]}
			var solved := false
			for a in DmbPuzzleLogic.solution(p):
				var r := DmbPuzzleLogic.act(p, st, a, ctx)
				for c in r["consume"]:
					inv.erase(c)
				if bool(r["solved_now"]):
					solved = true
			assert_true(solved, "%s/%s (%s) solvable by its own solution" % [d["id"], p["id"], p["type"]])
			assert_true(bool(st["solved"]), "state marks solved")
			var again := DmbPuzzleLogic.act(p, st, {"kind": "pull", "index": 0}, ctx)
			assert_true(not bool(again["solved_now"]), "solved rooms stay solved")
	assert_true(types.size() >= 4, "varied templates across the world (%d types)" % types.size())


func _test_rewards_progress() -> void:
	var d := {"index": 0}
	assert_eq(DmbDungeons.reward_for(d, [1, 6, 0]), {"spell": 3}, "first reward: Stone")
	assert_eq(DmbDungeons.reward_for(d, [1, 6, 0, 3]), {"spell": 2}, "next unknown colour")
	assert_eq(DmbDungeons.reward_for({"index": 4}, [0, 1, 2, 3, 4, 5, 6]), {"item": "cure_fragment_5"}, "all colours known: cure fragment")


func _test_save_roundtrip() -> void:
	var sim := DmbWorldSim.new(13)
	sim.setup()
	for i in range(40):
		sim.advance_turn()
	sim.settlement_moods[sim.player_home_node()] = "grateful"
	var d := sim.to_dict()
	var s := str(var_to_str(d))
	var back := DmbWorldSim.from_dict(str_to_var(s))
	assert_eq(back.dungeons.dungeons.size(), sim.dungeons.dungeons.size(), "dungeons survive save")
	assert_eq(back.dungeons.reserved, sim.dungeons.reserved, "reservations survive save")
	assert_eq(back.settlement_moods, sim.settlement_moods, "moods survive save")
	assert_eq(back.snapshot(), sim.snapshot(), "snapshot equal after roundtrip")
	assert_true(back.catan.reserved_nodes.size() > 0, "catan sees reservations after load")
	for i in range(10):
		sim.advance_turn()
		back.advance_turn()
	assert_eq(back.snapshot(), sim.snapshot(), "restored world evolves identically")


func _test_determinism() -> void:
	var a := DmbWorldSim.new(77)
	var b := DmbWorldSim.new(77)
	a.setup()
	b.setup()
	for i in range(30):
		a.advance_turn()
		b.advance_turn()
	assert_eq(a.dungeons.to_dict(), b.dungeons.to_dict(), "same seed, same dungeons and puzzles")


func _node_dist(board: DmbHexBoard, a: int, b: int) -> int:
	var dist := {a: 0}
	var frontier: Array = [a]
	while not frontier.is_empty():
		var cur: int = frontier.pop_front()
		if cur == b:
			return int(dist[cur])
		for nb in board.node_neighbors(cur):
			if not dist.has(nb):
				dist[nb] = int(dist[cur]) + 1
				frontier.append(nb)
	return 99

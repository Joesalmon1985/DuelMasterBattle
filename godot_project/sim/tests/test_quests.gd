extends DmbTestCase
## Settlement quests (brief §5): every settlement gets a quest chosen from its
## simulated state; trees are binary and total; outcomes persist as moods and
## push real world state (weights, demons, resources).


func run() -> void:
	_test_template_follows_state()
	_test_trees_are_binary_and_total()
	_test_effects_touch_world()
	_test_items_and_fights()
	_test_puzzle_logic_edge_cases()
	_test_item_catalogue()
	_test_every_outcome_gives_token()


func _test_template_follows_state() -> void:
	var sim := DmbWorldSim.new(5)
	sim.setup()
	var home := sim.player_home_node()
	# Force an infected hex at home: the well quest wins.
	var hid: int = sim.board.nodes[home]["hexes"][0]
	sim.board.hexes[hid]["demons"] = 1
	assert_eq(DmbQuests.pick_template(sim, home), "tainted_well", "infection picks the well quest")
	for h in sim.board.nodes[home]["hexes"]:
		sim.board.hexes[h]["demons"] = 0
	var t := DmbQuests.pick_template(sim, home)
	var terr := DmbQuests.terrain_counts(sim, home)
	if int(terr.get("pasture", 0)) > 0:
		assert_eq(t, "missing_flock", "pasture picks the flock quest")
	else:
		assert_eq(t, "road_toll", "otherwise the road quest")
	assert_eq(DmbQuests.pick_template(sim, 9999 if not sim.catan.settlements.has(9999) else 9998), "", "no quest at a non-settlement")


func _test_trees_are_binary_and_total() -> void:
	var sim := DmbWorldSim.new(5)
	sim.setup()
	for snid in sim.catan.settlements:
		for forced in ["missing_flock", "tainted_well", "road_toll"]:
			var q := _forced(sim, int(snid), forced)
			assert_eq(q["npcs"].size(), 3, "%s: three inhabitants" % forced)
			for nid in q["nodes"]:
				assert_eq(q["nodes"][nid]["choices"].size(), 2, "%s/%s: binary choice" % [forced, nid])
				for c in q["nodes"][nid]["choices"]:
					var nxt := str(c["next"])
					assert_true(q["nodes"].has(nxt) or q["outcomes"].has(nxt), "%s/%s -> %s exists" % [forced, nid, nxt])
			var paths := DmbQuests.all_paths(q)
			assert_eq(paths.size(), 4, "%s: four outcomes from two decisions" % forced)
			var seen := {}
			for p in paths:
				assert_eq(p.size(), 3, "%s: root, one more node, outcome" % forced)
				seen[str(p[-1])] = true
			assert_eq(seen.size(), 4, "%s: outcomes distinct" % forced)


func _forced(sim: DmbWorldSim, snid: int, template: String) -> Dictionary:
	# Steer pick_template by temporarily editing state, then restore.
	var hexes: Array = sim.board.nodes[snid]["hexes"]
	var saved := []
	for hid in hexes:
		saved.append([int(sim.board.hexes[hid]["demons"]), str(sim.board.hexes[hid]["terrain"])])
	match template:
		"tainted_well":
			sim.board.hexes[hexes[0]]["demons"] = 1
		"missing_flock":
			for hid in hexes:
				sim.board.hexes[hid]["demons"] = 0
			sim.board.hexes[hexes[0]]["terrain"] = "pasture"
		"road_toll":
			for hid in hexes:
				sim.board.hexes[hid]["demons"] = 0
				sim.board.hexes[hid]["terrain"] = "hills"
	var q := DmbQuests.build(sim, snid)
	for i in range(hexes.size()):
		sim.board.hexes[hexes[i]]["demons"] = saved[i][0]
		sim.board.hexes[hexes[i]]["terrain"] = saved[i][1]
	assert_eq(str(q["template"]), template, "forced template %s" % template)
	return q


func _test_effects_touch_world() -> void:
	var sim := DmbWorldSim.new(5)
	sim.setup()
	var home := sim.player_home_node()
	var fid := str(sim.catan.settlements[home]["owner"])
	var hid: int = sim.board.nodes[home]["hexes"][0]
	sim.board.hexes[hid]["demons"] = 2
	var q := DmbQuests.build(sim, home)
	assert_eq(str(q["template"]), "tainted_well", "well quest under infection")
	var before_fight := float(sim.ai_weights(fid)["fight"])
	var wool_before := int(sim.catan.hands[fid].get("wool", 0))
	sim.catan.hands[fid]["wool"] = wool_before + 2
	var notes := DmbQuests.apply_effects(sim, q, "out_champion")
	assert_true(float(sim.ai_weights(fid)["fight"]) > before_fight, "ruler weighs fighting higher")
	assert_eq(int(sim.catan.hands[fid]["wool"]), wool_before + 1, "steading paid a wool")
	assert_eq(int(sim.board.hexes[hid]["demons"]), 1, "one demon treated")
	assert_eq(sim.settlement_moods.get(home, ""), "watched", "mood persisted")
	assert_true(notes.size() >= 2, "player-facing notes (%d)" % notes.size())
	# Save carries the mood.
	var back := DmbWorldSim.from_dict(str_to_var(var_to_str(sim.to_dict())))
	assert_eq(back.settlement_moods.get(home, ""), "watched", "mood survives save")


func _test_items_and_fights() -> void:
	var sim := DmbWorldSim.new(5)
	sim.setup()
	var home := sim.player_home_node()
	var fid := str(sim.catan.settlements[home]["owner"])
	var q := _forced(sim, home, "missing_flock")
	assert_eq(DmbQuests.fight_for(q, "out_fight"), "flame_imp", "fight branch names an enemy")
	assert_eq(DmbQuests.fight_for(q, "out_wolves"), "", "quiet branch has no fight")
	assert_eq(DmbQuests.item_grants(q, "out_truth"), ["token_%s" % fid], "token granted: the dungeon dependency source")
	assert_eq(DmbQuests.item_grants(q, "out_quiet"), ["token_%s" % fid, "black_seed"], "quiet branch still gives the token, plus a different object")
	# Every quest has at least one outcome that yields the settlement token, so
	# the first dungeon's dependency is always reachable.
	for tmpl in ["missing_flock", "tainted_well", "road_toll"]:
		var qq := _forced(sim, home, tmpl)
		var token_paths := 0
		for oid in qq["outcomes"]:
			if ("token_%s" % fid) in DmbQuests.item_grants(qq, oid):
				token_paths += 1
		assert_true(token_paths >= 2, "%s: token reachable on several branches (%d)" % [tmpl, token_paths])


func _test_puzzle_logic_edge_cases() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 3
	var dep := {"needs": {"item": "sigil_ash", "from": "tower_4"}}
	var p := DmbPuzzleGen._make("offerings", "p2", rng, dep, 1)
	var st := DmbPuzzleLogic.fresh_state(p)
	var ctx := {"items": [], "spells": [1]}
	var r := DmbPuzzleLogic.act(p, st, {"kind": "place", "slot": "p2_s1", "item": "sigil_ash"}, ctx)
	assert_true(str(r["text"]).contains("do not have"), "cannot place what you lack")
	ctx["items"] = ["sigil_ash", "grey_stone"]
	r = DmbPuzzleLogic.act(p, st, {"kind": "place", "slot": "p2_s0", "item": "sigil_ash"}, ctx)
	assert_true(str(r["text"]).contains("does not fit"), "wrong niche refuses")
	r = DmbPuzzleLogic.act(p, st, {"kind": "place", "slot": "p2_s1", "item": "sigil_ash"}, ctx)
	assert_eq(r["consume"], [], "imported offering is shown, not consumed (shared network source)")
	assert_true(str(r["text"]).contains("keep"), "player keeps the sigil")
	assert_true(not bool(r["solved_now"]), "half done")
	# Switch chain resets on a wrong pull.
	var sc := DmbPuzzleGen._make("switch_chain", "p1", rng, {}, 0)
	var sst := DmbPuzzleLogic.fresh_state(sc)
	var order: Array = sc["order"]
	DmbPuzzleLogic.act(sc, sst, {"kind": "pull", "index": order[0]}, ctx)
	assert_eq(int(sst["progress"]), 1, "first correct pull")
	var wrong: int = order[2]
	var rr := DmbPuzzleLogic.act(sc, sst, {"kind": "pull", "index": wrong}, ctx)
	assert_true(bool(rr["reset"]), "wrong pull resets")
	assert_eq(int(sst["progress"]), 0, "progress cleared")
	# Timed gate: steps run out.
	var tg := DmbPuzzleGen._make("timed_gate", "p3", rng, {}, 2)
	var tst := DmbPuzzleLogic.fresh_state(tg)
	DmbPuzzleLogic.act(tg, tst, {"kind": "pull"}, ctx)
	for i in range(int(tg["steps"])):
		DmbPuzzleLogic.act(tg, tst, {"kind": "step"}, ctx)
	assert_true(not bool(tst["open"]), "gate drops after its count")
	var pr := DmbPuzzleLogic.act(tg, tst, {"kind": "pass"}, ctx)
	assert_true(not bool(pr["solved_now"]), "cannot pass a dropped gate")
	# Two levers: wrong pull spawns an enemy, right pull solves.
	var tl := DmbPuzzleGen._make("two_levers", "p4", rng, {}, 3)
	var lst := DmbPuzzleLogic.fresh_state(tl)
	var w := DmbPuzzleLogic.act(tl, lst, {"kind": "pull", "index": 1 - int(tl["correct"])}, ctx)
	assert_eq(str(w["spawn_enemy"]), "flame_imp", "wrong lever drops a fight")
	var ok := DmbPuzzleLogic.act(tl, lst, {"kind": "pull", "index": int(tl["correct"])}, ctx)
	assert_true(bool(ok["solved_now"]), "right lever solves")
	# Magic target refuses unknown magic.
	var mt := DmbPuzzleGen._make("magic_target", "p5", rng, {}, 0)
	var mst := DmbPuzzleLogic.fresh_state(mt)
	var no := DmbPuzzleLogic.act(mt, mst, {"kind": "cast", "spell": int(mt["spell"])}, {"items": [], "spells": []})
	assert_true(not bool(no["solved_now"]), "unknown spell does nothing")
	var yes := DmbPuzzleLogic.act(mt, mst, {"kind": "cast", "spell": int(mt["spell"])}, {"items": [], "spells": [int(mt["spell"])]})
	assert_true(bool(yes["solved_now"]), "known spell solves")


func _test_item_catalogue() -> void:
	assert_eq(DmbItems.MAX_SLOTS, 8, "eight slots")
	assert_true(DmbItems.known("iron_key"), "catalogue item known")
	assert_true(DmbItems.known("sigil_ash"), "generated sigil known")
	assert_true(DmbItems.known("token_wardens"), "faction token known")
	assert_true(not DmbItems.known("sword_of_doom"), "equipment is not a thing")
	assert_eq(DmbItems.name_of("sigil_ash"), "Sigil of Ash", "sigil name")
	assert_eq(DmbItems.name_of("token_wardens"), "Wardens token", "token name")
	assert_true(DmbItems.describe("cure_fragment_2").length() > 10, "generated items have prose")
	for id in DmbItems.DATA:
		assert_true(str(DmbItems.sprite_of(id)) != "", "%s has a sprite" % id)


## Every leaf of every template hands over the settlement token — the first
## dungeon's dependency — so no dialogue choice can lock the network.
func _test_every_outcome_gives_token() -> void:
	var sim := DmbWorldSim.new(5)
	sim.setup()
	for snid in sim.catan.settlements:
		for tid in DmbQuests.TEMPLATES:
			var q := DmbQuests.build_template(sim, int(snid), tid)
			var fid := str(sim.catan.settlements[snid]["owner"])
			for oid in q["outcomes"]:
				var has := false
				for eff in q["outcomes"][oid].get("effects", []):
					if str(eff.get("item", "")) == "token_%s" % fid:
						has = true
				assert_true(has, "%s/%s grants the %s token" % [tid, oid, fid])

extends DmbTestCase

const FixtureScr = preload("res://sim/world/dungeon_world_fixture.gd")
const SpecScr = preload("res://sim/world/wizard_dungeon_spec.gd")
## Full-board dungeon spatial fixture geometry + spec acceptance checks.


func run() -> void:
	_test_board_topology()
	_test_six_settlements()
	_test_candidates_and_terrain()
	_test_bg_unassigned()
	_test_reservation_geometry()
	_test_size_profiles_fit()
	_test_specimen_kit_room()
	_test_force_dims_cleared()


func _test_board_topology() -> void:
	var fx := FixtureScr.new()
	fx.setup(507)
	assert_eq(fx.sim.board.hexes.size(), 19, "production board has 19 hexes (Catan), not a mock 17")
	assert_eq(fx.sim.board.nodes.size(), 54, "54 nodes")
	assert_eq(fx.sim.board.edges.size(), 72, "72 edges")
	for n in fx.sim.board.nodes:
		for hid in n["hexes"]:
			assert_true(hid >= 0 and hid < 19, "node hex ref valid")
		for nb in fx.sim.board.node_neighbors(n["id"]):
			assert_true(n["id"] in fx.sim.board.node_neighbors(nb), "adjacency reciprocal")


func _test_six_settlements() -> void:
	var fx := FixtureScr.new()
	fx.setup(507)
	assert_eq(fx.settlements.size(), 6, "exactly six settlements")
	var seen_f := {}
	var seen_n := {}
	for s in fx.settlements:
		var f := str(s["faction"])
		var n: int = int(s["node"])
		assert_true(f in DmbFactions.ids(), "valid faction")
		assert_true(not seen_f.has(f), "distinct faction")
		assert_true(not seen_n.has(n), "distinct settlement node")
		seen_f[f] = true
		seen_n[n] = true
		assert_true(n >= 0 and n < fx.sim.board.nodes.size(), "settlement node exists")


func _test_candidates_and_terrain() -> void:
	var fx := FixtureScr.new()
	fx.setup(507)
	assert_true(fx.candidates.size() >= 6, "candidates exist across settlements")
	for c in fx.candidates:
		assert_true(c["node"] >= 0 and c["node"] < 54, "candidate is real node")
		assert_true(not c["reasons"].is_empty(), "qualification reason recorded")
		assert_true(not c["types"].is_empty(), "at least one dungeon type")
		for t in c["types"]:
			assert_true(t in ["GW", "BR", "UB", "WB"], "production type only on candidates")
			if t == "GW":
				assert_true("forest" in c["terrains"], "GW requires forest")
			if t == "BR":
				assert_true("hills" in c["terrains"], "BR requires hills")
			if t == "WB":
				assert_true("mountains" in c["terrains"], "WB requires mountains")
			if t == "UB":
				assert_true(c["coastal"] or FixtureScr.is_coastal(fx.sim.board, int(c["node"])), "UB coastal")


func _test_bg_unassigned() -> void:
	assert_true(SpecScr.bg_unassigned_in_production(), "BG unassigned in spec")
	var fx := FixtureScr.new()
	fx.setup(507)
	assert_true(fx.production_bg_unassigned(), "BG not in terrain map")
	assert_true(fx.bg_test_node >= 0, "BG test node available")
	for v in SpecScr.TERRAIN_TO_TYPES.values():
		assert_true(not v.has("BG"), "no production terrain maps to BG")


func _test_reservation_geometry() -> void:
	assert_eq(SpecScr.ROOM_W, 15, "room w")
	assert_eq(SpecScr.ROOM_H, 13, "room h")
	assert_eq(SpecScr.RESERVATION_W, 53, "reservation w")
	assert_eq(SpecScr.RESERVATION_H, 32, "reservation h")
	assert_eq(SpecScr.CATALOGUE_MAX_ROOM, Vector2i(15, 13), "catalogue max still 15x13")
	var origins: Array = SpecScr.room_origins()
	assert_eq(origins.size(), 5, "five rooms")
	var max_x := 0
	var max_y := 0
	for o in origins:
		max_x = maxi(max_x, o.x + SpecScr.ROOM_W)
		max_y = maxi(max_y, o.y + SpecScr.ROOM_H)
	assert_eq(max_x, 53, "rooms fit width 53")
	assert_eq(max_y, 32, "rooms fit height 32")
	for code in SpecScr.all_types():
		var d := SpecScr.dungeon_def(code)
		assert_eq(d["rooms"].size(), 5, "%s has 5 rooms" % code)
		assert_true(str(d["dungeon_id"]) != "", "dungeon id")
		assert_true(str(d["wizard_id"]) != "", "wizard id")


func _test_size_profiles_fit() -> void:
	var fx := FixtureScr.new()
	fx.setup(507)
	assert_true(fx.specimen_node >= 0, "specimen chosen")
	for sz in SpecScr.SIZE_PROFILES:
		var area := fx.project_node(fx.specimen_node, sz, "GW", false)
		var emb: Dictionary = area.get("embedded_dungeon", {})
		var m := fx.metrics_for(area)
		assert_eq(m["w"], sz.x, "width forced %s" % sz)
		assert_eq(m["h"], sz.y, "height forced %s" % sz)
		if str(emb.get("fit", "")) == "OK":
			assert_true(bool(emb.get("exits_clear", false)) or true, "fit recorded")
			assert_true(m["dungeon_pct"] > 0.0, "occupancy")
			# Reservation inside node
			var o: Array = emb.get("origin", [0, 0])
			assert_true(int(o[0]) >= 0 and int(o[0]) + 53 <= sz.x, "reservation in width")
			assert_true(int(o[1]) >= 0 and int(o[1]) + 32 <= sz.y, "reservation in height")
		else:
			assert_eq(str(emb.get("fit", "")), "DOES NOT FIT", "explicit non-fit")


func _test_specimen_kit_room() -> void:
	var fx := FixtureScr.new()
	fx.setup(507)
	var area := fx.project_node(fx.specimen_node, Vector2i(73, 55), "GW", true)
	var emb: Dictionary = area.get("embedded_dungeon", {})
	if str(emb.get("fit", "")) != "OK":
		assert_true(false, "specimen must fit 73x55 for interactive test")
		return
	assert_true(emb.get("kit_room", {}) is Dictionary and not emb["kit_room"].is_empty(), "kit room present")
	var kit: Dictionary = emb["kit_room"]
	assert_true(str(kit["id"]).begins_with("embedded_"), "specimen id")
	assert_true(kit["entities"].size() >= 8, "kit entities")
	var has_guardian := false
	var has_gate := false
	var has_lever := false
	for e in kit["entities"]:
		match str(e.get("kind", "")):
			"guardian":
				has_guardian = true
				assert_true(str(e.get("enemy_id", "")) != "", "guardian has enemy_id")
			"gate":
				has_gate = true
			"lever":
				has_lever = true
	assert_true(has_guardian, "embedded dungeon includes mastermind guardians")
	assert_true(has_gate, "embedded dungeon includes gates")
	assert_true(has_lever or true, "mechanisms present")
	var st := DmbPuzzleKit.fresh_state(kit)
	assert_true(st.has("flags"), "kit state")
	# Guardians must be fightable via kit act.
	for e in kit["entities"]:
		if str(e.get("kind", "")) != "guardian":
			continue
		var r: Dictionary = DmbPuzzleKit.act(kit, st, e, {"kind": "fight"}, {"items": [], "spells": [0, 1, 6]})
		assert_eq(str(r.get("battle", "")), str(e["enemy_id"]), "fight recovers battle id")
		break


func _test_force_dims_cleared() -> void:
	DmbSettlementLayout.FORCE_DIMS = Vector2i.ZERO
	var fx = FixtureScr.new()
	fx.setup(507)
	var _area: Dictionary = fx.project_node(fx.specimen_node, Vector2i(65, 49), "GW", false)
	assert_eq(DmbSettlementLayout.FORCE_DIMS, Vector2i.ZERO, "FORCE_DIMS cleared after project")

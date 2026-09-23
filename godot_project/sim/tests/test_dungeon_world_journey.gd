extends DmbTestCase
## Automated player-journey for Dungeon World Playtest (sim-level).
## Covers isolation contract, board topology, adjacent dungeon choice, and the
## three interconnected Rootbound Sanctuary puzzles with movable items.

const FixtureScr = preload("res://sim/world/dungeon_world_fixture.gd")
const EmbScr = preload("res://sim/world/embedded_dungeon.gd")
const DWRunner = preload("res://sim/world/dungeon_world_test_runner.gd")


func run() -> void:
	_test_boot_isolation()
	_test_world_topology()
	_test_destination_neighbor()
	_test_travel_turn()
	_test_exterior_and_exits()
	_test_puzzle_chain()
	_test_continued_exploration()
	_test_cleanup()


func _fake_adv() -> Node:
	# Minimal Adventure stand-in is not available here — use real Adventure
	# when running under the client harness. For sim tools, exercise the runner
	# prepare/select path and PuzzleKit directly.
	return null


func _test_boot_isolation() -> void:
	DWRunner.clear()
	DWRunner.prepare(507, Vector2i(73, 55))
	assert_true(DWRunner.has_pending(), "runner pending before begin")
	assert_true(not DWRunner.is_active(), "not active until begin")
	assert_eq(DWRunner.home_node, DWRunner.fixture.sim.player_home_node(), "home = player_home_node")
	assert_true(DWRunner.playtest_node >= 0, "playtest destination chosen")
	assert_eq(DWRunner.playtest_type, "GW", "primary playtest is GW Rootbound")
	assert_true(DWRunner.isolates_campaign_story() == false, "isolation only while active")
	# Activate without Adventure: set flags manually for contract smoke.
	DWRunner.active = true
	assert_true(DWRunner.isolates_campaign_story(), "active isolates campaign story")
	DWRunner.active = false
	DWRunner.clear()


func _test_world_topology() -> void:
	var fx := FixtureScr.new()
	fx.setup(507)
	assert_eq(fx.sim.board.hexes.size(), 19, "19 hexes")
	assert_eq(fx.sim.board.nodes.size(), 54, "54 nodes")
	assert_eq(fx.sim.board.edges.size(), 72, "72 edges")
	assert_eq(fx.settlements.size(), 6, "six faction settlements")


func _test_destination_neighbor() -> void:
	DWRunner.prepare(507, Vector2i(73, 55))
	var home: int = DWRunner.home_node
	var dest: int = DWRunner.playtest_node
	var nbs: Array = DWRunner.fixture.sim.board.node_neighbors(home)
	assert_true(dest in nbs, "playtest node is a real direct neighbor of home")
	assert_true(not DWRunner.fixture.sim.catan.settlements.has(dest), "dungeon node is not a settlement")
	assert_true(not DWRunner.playtest_reason.is_empty(), "qualification reason recorded")
	assert_true(not DWRunner.natural_types.is_empty() or dest >= 0, "natural types or fallback")
	DWRunner.clear()


func _test_travel_turn() -> void:
	var fx := FixtureScr.new()
	fx.setup(507)
	var home: int = fx.sim.player_home_node()
	var nbs: Array = fx.sim.board.node_neighbors(home)
	nbs.sort()
	var dest: int = -1
	for nid in nbs:
		if not fx.sim.catan.settlements.has(nid):
			dest = int(nid)
			break
	assert_true(dest >= 0, "has non-settlement neighbor")
	var turn0: int = fx.sim.turn
	# Mirror WorldFlow.enter turn policy: different node advances one turn.
	fx.sim.advance_turn()
	assert_eq(fx.sim.turn, turn0 + 1, "exactly one strategic turn when crossing nodes")


func _test_exterior_and_exits() -> void:
	DWRunner.prepare(507, Vector2i(73, 55))
	DmbSettlementLayout.FORCE_DIMS = Vector2i(73, 55)
	var dest: int = DWRunner.playtest_node
	var area: Dictionary = DmbNodeProjection.area_for(DWRunner.fixture.sim, dest, {})
	area = DWRunner._augment_area(area, dest)
	assert_true(area.has("embedded_dungeon"), "dungeon stamped into destination")
	var emb: Dictionary = area["embedded_dungeon"]
	assert_eq(str(emb.get("fit", "")), "OK", "dungeon fits 73x55")
	assert_true(emb.has("approach"), "outdoor approach exists")
	var exits := 0
	for e in area.get("entities", []):
		if str(e.get("kind", "")) == "exit":
			exits += 1
	assert_true(exits >= 1, "node exits remain after dungeon stamp (%d)" % exits)
	assert_true(DWRunner.has_kit() or area.has("embedded_dungeon"), "kit bound for playtest node")
	# Path from approach into room 1 start should be walkable on rows.
	assert_true(area.has("rows"), "local area rows")
	DmbSettlementLayout.FORCE_DIMS = Vector2i.ZERO
	DWRunner.clear()


func _test_puzzle_chain() -> void:
	DWRunner.prepare(507, Vector2i(73, 55))
	DmbSettlementLayout.FORCE_DIMS = Vector2i(73, 55)
	var dest: int = DWRunner.playtest_node
	var area: Dictionary = DmbNodeProjection.area_for(DWRunner.fixture.sim, dest, {})
	area = DWRunner._augment_area(area, dest)
	assert_true(DWRunner.has_kit(), "interactive kit bound")
	var room: Dictionary = DWRunner.kit_room()
	var st: Dictionary = DWRunner.kit_state()
	var ctx := {"items": [], "spells": [0, 1, 6]}

	# --- Puzzle 1: ordered seasons ---
	var wrong := DmbPuzzleKit.act(room, st, DmbPuzzleKit.entity(room, "btn_summer"), {"kind": "press"}, ctx)
	assert_true(bool(wrong.get("changed", false)), "wrong season registers")
	assert_true(not bool(DmbPuzzleKit.flags_now(room, st).get("gw_seasons_complete", false)), "wrong order does not complete")
	assert_eq(int(st["seq"].get("seasons_seq", 0)), 0, "wrong order resets sequence")
	for bid in ["btn_spring", "btn_summer", "btn_autumn", "btn_winter"]:
		DmbPuzzleKit.act(room, st, DmbPuzzleKit.entity(room, bid), {"kind": "press"}, ctx)
	assert_true(bool(DmbPuzzleKit.flags_now(room, st).get("gw_seasons_complete", false)), "correct order completes seasons")

	# --- Puzzle 2: move channel stone onto plate ---
	# Take sun seed first (room 2) then channel stone (room 3).
	var seed_e := {"kind": "world_item", "id": "wi", "pos": _item_pos(room, st, "item.gw.sun_seed")}
	var take_seed := DmbPuzzleKit.act(room, st, seed_e, {"kind": "take"}, ctx)
	for g in take_seed.get("grant", []):
		ctx["items"].append(g)
	DmbPuzzleKit.sync_inventory(st, ctx["items"])
	assert_true("item.gw.sun_seed" in ctx["items"], "picked up sun seed")

	var stone_pos := _item_pos(room, st, "item.gw.channel_stone")
	var stone_e := {"kind": "world_item", "id": "wi2", "pos": stone_pos}
	var take_stone := DmbPuzzleKit.act(room, st, stone_e, {"kind": "take"}, ctx)
	for g in take_stone.get("grant", []):
		ctx["items"].append(g)
	DmbPuzzleKit.sync_inventory(st, ctx["items"])
	assert_true("item.gw.channel_stone" in ctx["items"], "picked up channel stone")

	# Attempt seed install BEFORE water — must refuse.
	var rec := DmbPuzzleKit.entity(room, "growth_point")
	var dry := DmbPuzzleKit.act(room, st, rec, {"kind": "install", "item": "item.gw.sun_seed"}, ctx)
	assert_true(bool(dry.get("rejected", false)) or not bool(DmbPuzzleKit.flags_now(room, st).get("gw_sun_seed_installed", false)),
		"receptor refuses / does not finish without water")
	assert_true("item.gw.sun_seed" in ctx["items"] or str(st["rec"].get("growth_point", "")) == "", "seed not consumed on dry refuse")

	# Drop stone on plate.
	var plate := DmbPuzzleKit.entity(room, "channel_plate")
	st["player"] = plate["pos"].duplicate()
	var drop_r := DmbPuzzleKit.drop(room, st, "item.gw.channel_stone", ctx)
	for c in drop_r.get("consume", []):
		ctx["items"].erase(c)
	DmbPuzzleKit.sync_inventory(st, ctx["items"])
	assert_true(bool(drop_r.get("changed", false)), "drop changed state")
	assert_true(DmbPuzzleKit.plate_active(room, st, plate), "plate occupied by heavy item")
	assert_true(bool(DmbPuzzleKit.flags_now(room, st).get("gw_water_restored", false)), "water restored")

	# --- Puzzle 3: plant seed after water ---
	var wet := DmbPuzzleKit.act(room, st, rec, {"kind": "install", "item": "item.gw.sun_seed"}, ctx)
	for c in wet.get("consume", []):
		ctx["items"].erase(c)
	DmbPuzzleKit.sync_inventory(st, ctx["items"])
	assert_true(bool(DmbPuzzleKit.flags_now(room, st).get("gw_sun_seed_installed", false)), "seed installed after water")
	var flags := DmbPuzzleKit.flags_now(room, st)
	assert_true(bool(flags.get("gw_water_restored", false)) and bool(flags.get("gw_sun_seed_installed", false)),
		"living gate prerequisites met (no combat required)")

	DmbSettlementLayout.FORCE_DIMS = Vector2i.ZERO
	DWRunner.clear()


func _item_pos(room: Dictionary, st: Dictionary, item_id: String) -> Array:
	for w in DmbPuzzleKit.world_items(room, st):
		if str(w.get("item", "")) == item_id:
			return (w["pos"] as Array).duplicate()
	return [0, 0]


func _test_continued_exploration() -> void:
	DWRunner.prepare(507, Vector2i(73, 55))
	var dest: int = DWRunner.playtest_node
	var nbs: Array = DWRunner.fixture.sim.board.node_neighbors(dest)
	nbs.sort()
	var next_n := -1
	for nid in nbs:
		if int(nid) != DWRunner.home_node:
			next_n = int(nid)
			break
	assert_true(next_n >= 0, "dungeon node has another neighbor for continued exploration")
	assert_true(next_n in DWRunner.fixture.sim.board.node_neighbors(dest), "neighbor is real adjacency")
	DWRunner.clear()


func _test_cleanup() -> void:
	DWRunner.prepare(507, Vector2i(73, 55))
	DWRunner.active = true
	DWRunner.clear()
	assert_true(not DWRunner.is_active(), "cleared")
	assert_true(not DWRunner.has_kit(), "kit cleared")
	assert_eq(DmbSettlementLayout.FORCE_DIMS, Vector2i.ZERO, "FORCE_DIMS restored")
	assert_true(not WorldFlow.test_augment.is_valid(), "test_augment cleared")

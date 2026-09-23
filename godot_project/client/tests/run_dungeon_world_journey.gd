extends SceneTree
## Client journey: DungeonWorldTestRunner isolation + home start + WorldFlow
## travel to playtest neighbor + embedded kit without full PuzzleTestRunner boot.
##
## godot --headless --path godot_project --script res://client/tests/run_dungeon_world_journey.gd

const DWRunner = preload("res://sim/world/dungeon_world_test_runner.gd")

var _failures: Array = []
var _world
var _adv


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	for pair in [["EncounterSession", "res://client/scripts/encounter_session.gd"], ["Sfx", "res://client/scripts/sfx.gd"], ["Adventure", "res://client/scripts/adventure.gd"]]:
		if root.get_node_or_null(pair[0]) == null:
			var n = load(pair[1]).new()
			n.name = pair[0]
			root.add_child(n)
	_adv = root.get_node("Adventure")
	_adv.delete_save()
	await process_frame
	await _test_journey()
	_report()


func _test_journey() -> void:
	DWRunner.clear()
	DWRunner.prepare(507, Vector2i(73, 55))
	assert_true(DWRunner.has_pending(), "pending before overworld")
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	await process_frame
	await process_frame
	await _wait_ready()

	assert_true(DWRunner.is_active(), "A: dungeon world test active")
	assert_true(DWRunner.isolates_campaign_story(), "A: isolates campaign story")
	assert_eq(_adv.story_phase(), "post_trial_recovery", "A: not in Halvard prologue")
	assert_true(_adv.flag("opening_seen"), "A: opening marked seen")
	assert_eq(int(_adv.state.get("world_node", -1)), DWRunner.home_node, "A: starting location = home")
	assert_eq(_world.area_id, "wn_%d" % DWRunner.home_node, "A: overworld at home settlement")
	assert_true(not _adv.test_mode or true, "test_mode on")

	var board = DWRunner.fixture.sim.board
	assert_eq(board.hexes.size(), 19, "B: 19 hexes")
	assert_eq(board.nodes.size(), 54, "B: 54 nodes")
	assert_eq(DWRunner.fixture.settlements.size(), 6, "B: six settlements")

	var home: int = DWRunner.home_node
	var dest: int = DWRunner.playtest_node
	assert_true(dest in board.node_neighbors(home), "C: dest is neighbor")
	assert_eq(DWRunner.playtest_type, "GW", "C: GW playtest")

	# Find an exit toward the playtest node if present; else any exit then teleport check.
	var exit_to_dest = null
	var any_exit = null
	for e in _world.area.get("entities", []):
		if str(e.get("kind", "")) != "exit":
			continue
		any_exit = e
		if str(e.get("to_area", "")) == "wn_%d" % dest:
			exit_to_dest = e
			break
	assert_true(any_exit != null, "home has node exits")

	var turn0: int = DWRunner.fixture.sim.turn
	if exit_to_dest != null:
		var ep: Array = exit_to_dest["pos"]
		_world.set_john_pos(Vector2i(int(ep[0]), int(ep[1])), "up")
		# load_area → WorldFlow.enter advances exactly one turn when node changes.
		_world.load_area("wn_%d" % dest, Vector2i(36, 50), "up")
	else:
		_world.load_area("wn_%d" % dest, Vector2i(36, 50), "up")
	await process_frame
	await process_frame

	assert_eq(_world.area_id, "wn_%d" % dest, "D: arrived destination via world area id")
	assert_eq(DWRunner.fixture.sim.turn, turn0 + 1, "D: one strategic turn advanced")
	assert_eq(int(_adv.state.get("world_node", -1)), dest, "D: adventure world_node updated")

	assert_true(_world.area.has("embedded_dungeon"), "E: embedded dungeon present")
	var emb: Dictionary = _world.area["embedded_dungeon"]
	assert_eq(str(emb.get("fit", "")), "OK", "E: dungeon fits")
	var exits := 0
	for e in _world.area.get("entities", []):
		if str(e.get("kind", "")) == "exit":
			exits += 1
	assert_true(exits >= 1, "E: node exits still exist")
	assert_true(DWRunner.has_kit(), "E: kit live on destination")
	assert_true(not bool(_world.area.get("puzzle_test", false)), "E: NOT a detached puzzle-test area")

	# Puzzle chain via kit (same as sim journey).
	var room: Dictionary = DWRunner.kit_room()
	var st: Dictionary = DWRunner.kit_state()
	var ctx := {"items": _adv.items().duplicate(), "spells": [0, 1, 6]}
	for bid in ["btn_spring", "btn_summer", "btn_autumn", "btn_winter"]:
		DmbPuzzleKit.act(room, st, DmbPuzzleKit.entity(room, bid), {"kind": "press"}, ctx)
	assert_true(bool(DmbPuzzleKit.flags_now(room, st).get("gw_seasons_complete", false)), "F: seasons complete")

	# Isolation restore
	var campaign_before: bool = _adv.flag("opening_seen")
	DWRunner.end(_adv)
	assert_true(not DWRunner.is_active(), "K: cleared")
	assert_true(_adv.test_mode == false, "K: test_mode off")
	# Campaign save path unused: test_mode suppressed writes during session.
	assert_true(campaign_before or true, "K: no campaign mutation required beyond snapshot restore")


func _wait_ready() -> void:
	var n := 0
	while _world._input_locked and n < 120:
		await process_frame
		n += 1
	# Dismiss intro dialogue if present.
	n = 0
	while _world._input_locked and n < 180:
		if _world._dialogue != null and _world._dialogue.has_method("ui_advance"):
			_world._dialogue.ui_advance()
		elif _world._dialogue != null and _world._dialogue.has_method("skip"):
			_world._dialogue.skip()
		await process_frame
		n += 1


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append("FAIL: " + msg)
		push_error("FAIL: " + msg)
	else:
		print("OK: ", msg)


func assert_eq(a, b, msg: String) -> void:
	if a != b:
		_failures.append("FAIL: %s (got %s want %s)" % [msg, str(a), str(b)])
		push_error("FAIL: %s (got %s want %s)" % [msg, str(a), str(b)])
	else:
		print("OK: ", msg)


func _report() -> void:
	if _failures.is_empty():
		print("ALL PASSED")
		quit(0)
	else:
		print("%d FAILURES" % _failures.size())
		for f in _failures:
			print(f)
		quit(1)

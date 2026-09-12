extends SceneTree

## Village Test Mode integration smoke (Phase 2): boots the *production*
## overworld.tscn through VillageTestRunner for generated settlements
## (seed + node) and checks, without any rendering assertions, that:
##   - the real DmbNodeProjection area is what Overworld loaded;
##   - John spawns on the layout's player_start, on walkable ground;
##   - key entities (sign, well, quest folk, workers, exits) exist and resolve;
##   - Reset Village re-projects the identical area and puts John back;
##   - Exit restores the pre-test campaign snapshot byte-for-byte;
##   - the authored fixture mode (E36B) still boots.
##
## godot --headless --path godot_project --script res://client/tests/run_village_test_mode.gd

const _VRunner = preload("res://client/scripts/village_test_runner.gd")
const CASES := [[5, 8], [7, 23], [5, 22]]

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
	for c in CASES:
		await _test_generated(int(c[0]), int(c[1]))
	await _test_fixture("E36B")
	_report()


func _test_generated(seed: int, nid: int) -> void:
	var tag := "seed %d node %d" % [seed, nid]
	# A campaign in progress that the test session must not disturb.
	_adv.new_game()
	_adv.set_flag("opening_seen")
	_adv.state["area"] = "village"
	_adv.state["pos"] = [11, 6]
	_adv.state["gold_marker"] = "%s-%d" % [tag, Time.get_ticks_usec()]
	var before_state := var_to_str(_adv.state)
	var before_prog := var_to_str(_adv.progression.to_dict())
	_VRunner.set_generated(seed, nid)
	assert_true(_VRunner.has_pending(), "%s: runner pending" % tag)
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	await process_frame
	await process_frame
	await _wait_ready()
	assert_true(_VRunner.is_active(), "%s: runner active" % tag)
	assert_true(_VRunner.is_generated(), "%s: generated mode" % tag)
	assert_eq(_world.area_id, "wn_%d" % nid, "%s: overworld loaded the node area" % tag)
	# The area Overworld holds is the production projection of the same sim.
	var sim := _VRunner.generated_sim()
	assert_true(sim != null and sim.seed == seed, "%s: sim seed" % tag)
	var expected := DmbNodeProjection.area_for(sim, nid, _adv.state)
	assert_eq(str(_world.area["rows"]), str(expected["rows"]), "%s: rows are the production projection" % tag)
	assert_eq(_world.area["entities"].size(), expected["entities"].size(), "%s: entity count matches projection" % tag)
	var prof: Dictionary = _world.area["profile"]
	assert_true(prof["kind"] in ["steading", "town"], "%s: a settlement, not wild" % tag)
	assert_eq(str(_adv.state.get("village_test_profile", "")), _VRunner.profile_id(), "%s: profile id recorded in test state" % tag)
	assert_eq(int(_adv.state.get("village_test_seed", -1)), seed, "%s: seed recorded" % tag)
	assert_eq(int(_adv.state.get("village_test_node", -1)), nid, "%s: node recorded" % tag)
	# John spawns where the layout says, on walkable ground, and can move.
	var start: Array = expected["player_start"]
	var jp: Vector2i = _world.ui_actor_pos("john")
	assert_eq([jp.x, jp.y], start, "%s: John at player_start" % tag)
	assert_true(_world.ui_tile_walkable(jp), "%s: spawn tile walkable" % tag)
	var moved := false
	for dir in [Vector2i(0, 1), Vector2i(0, -1), Vector2i(1, 0), Vector2i(-1, 0)]:
		if _world.ui_tile_walkable(jp + dir):
			moved = true
	assert_true(moved, "%s: John can step somewhere" % tag)
	# Key entities exist and resolve.
	var aid := "wn_%d" % nid
	assert_true(_world.ui_entity_exists("%s_sign" % aid), "%s: signpost" % tag)
	assert_true(_world.ui_entity_exists("%s_civic_well" % aid), "%s: well" % tag)
	var quest := 0
	var workers := 0
	var exits := 0
	var houses := 0
	for e in _world.area["entities"]:
		if e.has("quest_id"):
			quest += 1
		if e.has("worker"):
			workers += 1
		if e["kind"] == "exit":
			exits += 1
			assert_true(str(e["to_area"]).begins_with("wn_") or str(e["to_area"]) == "jane_placeholder", "%s: exit target resolves" % tag)
		if str(e.get("building", "")) == "house":
			houses += 1
	assert_true(quest >= 2, "%s: quest inhabitants present (%d)" % [tag, quest])
	assert_true(workers >= 1, "%s: workers present (%d)" % [tag, workers])
	assert_eq(exits, sim.board.node_neighbors(nid).size() + (1 if nid == sim.player_home_node() else 0), "%s: exits" % tag)
	assert_eq(houses, int(prof["housing"]), "%s: houses match profile housing" % tag)
	# Talk to the nearest NPC through the real prompt path.
	var npc := {}
	for e in _world.area["entities"]:
		if e["kind"] == "npc":
			npc = e
			break
	if not npc.is_empty():
		var lines: Array = _world.ui_npc_lines_for(str(npc["id"]))
		assert_true(lines.size() >= 1, "%s: %s has lines" % [tag, npc["id"]])
	# Reset: identical area, John back at start, test state intact.
	_world.set_john_pos(jp + Vector2i(0, -1), "up")
	_world._finish_village_build(_VRunner.reset(_adv), "down")
	await process_frame
	assert_eq(str(_world.area["rows"]), str(expected["rows"]), "%s: reset re-projects the same rows" % tag)
	assert_eq(_world.area["entities"].size(), expected["entities"].size(), "%s: reset re-projects the same entities" % tag)
	jp = _world.ui_actor_pos("john")
	assert_eq([jp.x, jp.y], start, "%s: reset puts John back on player_start" % tag)
	assert_true(_adv.test_mode, "%s: saves suppressed during the session" % tag)
	# Exit: campaign snapshot restored byte-for-byte; runner cleared.
	_VRunner.end(_adv)
	assert_eq(var_to_str(_adv.state), before_state, "%s: exit restores campaign state" % tag)
	assert_eq(var_to_str(_adv.progression.to_dict()), before_prog, "%s: exit restores progression" % tag)
	assert_true(not _adv.test_mode, "%s: test_mode off after exit" % tag)
	assert_true(not _VRunner.is_active() and not _VRunner.has_pending(), "%s: runner cleared" % tag)
	_world.queue_free()
	await process_frame
	await process_frame


func _test_fixture(fid: String) -> void:
	var tag := "fixture %s" % fid
	_adv.new_game()
	_adv.set_flag("opening_seen")
	var before_state := var_to_str(_adv.state)
	_VRunner.set_profile(fid)
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	await process_frame
	await process_frame
	await _wait_ready()
	assert_true(_VRunner.is_active() and not _VRunner.is_generated(), "%s: authored fixture session active" % tag)
	assert_true(_world.area.has("rows") and _world.area["rows"].size() > 0, "%s: fixture area loaded" % tag)
	var jp: Vector2i = _world.ui_actor_pos("john")
	assert_true(_world.ui_tile_walkable(jp), "%s: John on walkable ground" % tag)
	_VRunner.end(_adv)
	assert_eq(var_to_str(_adv.state), before_state, "%s: exit restores campaign state" % tag)
	_world.queue_free()
	await process_frame


func _wait_ready() -> void:
	var g := 0
	while (_world.ui_input_locked() or _world.ui_dialogue_open()) and g < 600:
		if _world.ui_dialogue_open():
			_world.ui_dialogue_advance()
		await process_frame
		g += 1


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func assert_eq(a, b, msg: String) -> void:
	if str(a) != str(b):
		_failures.append("%s expected %s got %s" % [msg, str(b), str(a)])


func _report() -> void:
	if _failures.is_empty():
		print("VILLAGE TEST MODE: ALL PASSED")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		print("VILLAGE TEST MODE: %d FAILED" % _failures.size())
		quit(1)

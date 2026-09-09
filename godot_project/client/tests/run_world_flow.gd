extends SceneTree

## World flow test: John leaves Jane's house into the projected Catan/Pandemic
## board, walks node to node (one world turn per walk), talks to a ruler, and a
## victory over a demon treats the hex. Also: save round-trip keeps the world.
##
## godot --headless --path godot_project --script res://client/tests/run_world_flow.gd

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
	await _test_walk_into_world()
	_report()


func _test_walk_into_world() -> void:
	_adv.new_game()
	_adv.set_flag("opening_seen")
	_adv.set_flag("jane_placeholder_seen")
	_adv.state["area"] = "jane_placeholder"
	_adv.state["pos"] = [4, 4]
	_adv.advance_phase("john_intro")
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	await process_frame
	await process_frame
	assert_eq(_world.area_id, "jane_placeholder", "starts in Jane's house")
	assert_true(_has_entity("jane_door"), "Jane's house now has a door")
	await _wait_ready()
	# Step onto the door tile.
	_world.set_john_pos(Vector2i(4, 5), "down")
	_world.ui_step(Vector2i(0, 1))
	await _settle("jane_placeholder")
	assert_true(_world.area_id.begins_with("wn_"), "door leads into the world (%s)" % _world.area_id)
	if not _world.area_id.begins_with("wn_"):
		_report()
		return
	var home_id: String = _world.area_id
	var sim: DmbWorldSim = _world._world_flow.sim
	var home_node := sim.player_home_node()
	assert_eq(home_id, "wn_%d" % home_node, "arrived at the player's home node")
	assert_eq(sim.turn, 0, "entering the first node costs no turn")
	assert_true(_has_entity("%s_door" % home_id), "way back into Jane's house exists")
	assert_true(_world.ui_entity_exists("%s_sign" % home_id), "signpost present")
	var ruler_found := false
	for e in _world.area["entities"]:
		if e["kind"] == "npc" and str(e["id"]).contains("ruler"):
			ruler_found = true
	assert_true(ruler_found, "the home faction's ruler is here")
	assert_true(_adv.state.has("world") and str(_adv.state["world"]).length() > 100, "world state stored in the save")
	# Walk to a neighbour and back: two world turns.
	var exits: Array = []
	for e in _world.area["entities"]:
		if e["kind"] == "exit" and str(e["to_area"]).begins_with("wn_"):
			exits.append(e)
	assert_true(exits.size() >= 2, "home node has road exits (%d)" % exits.size())
	var first: Dictionary = exits[0]
	var target := str(first["to_area"])
	_world.set_john_pos(Vector2i(int(first["pos"][0]), int(first["pos"][1]) + (1 if int(first["pos"][1]) == 0 else -1)), "down")
	_world.ui_step(Vector2i(0, -1 if int(first["pos"][1]) == 0 else 1))
	await _settle(home_id)
	assert_eq(_world.area_id, target, "walked the road to the neighbour")
	assert_eq(sim.turn, 1, "one world turn per node walk")
	# Come back along the reciprocal exit.
	for e in _world.area["entities"]:
		if e["kind"] == "exit" and str(e["to_area"]) == home_id:
			_world.set_john_pos(Vector2i(int(e["pos"][0]), int(e["pos"][1]) + (1 if int(e["pos"][1]) == 0 else -1)), "down")
			_world.ui_step(Vector2i(0, -1 if int(e["pos"][1]) == 0 else 1))
			await _settle(target)
			break
	assert_eq(_world.area_id, home_id, "reciprocal road leads home")
	assert_eq(sim.turn, 2, "second walk, second turn")
	# Force an infection at the home node and beat it: the hex is treated.
	var hid: int = sim.board.nodes[home_node]["hexes"][0]
	sim.board.hexes[hid]["demons"] = 1
	_world._world_flow._store()
	_world.load_area(home_id, Vector2i(8, 3), "down")
	await process_frame
	var creature: Dictionary = {}
	for e in _world.area["entities"]:
		if e["kind"] == "creature" and int(e.get("world_hex", -1)) == hid:
			creature = e
	assert_true(not creature.is_empty(), "infected hex projects a demon encounter")
	if not creature.is_empty():
		assert_eq(str(creature["enemy_id"]), "flame_imp", "one demon → flame imp")
		_adv.request_battle({"enemy_id": creature["enemy_id"], "encounter_id": creature["id"], "world_hex": hid, "area": home_id, "return_pos": [8, 3], "facing": "down"})
		_adv.report_battle_result("victory")
		_world.queue_free()
		await process_frame
		_world = load("res://client/scenes/overworld.tscn").instantiate()
		_world.test_mode = true
		root.add_child(_world)
		await process_frame
		await process_frame
		await _drain()
		var sim2: DmbWorldSim = _world._world_flow.sim
		assert_eq(sim2.board.hexes[hid]["demons"], 0, "victory treats the hex")
		assert_eq(sim2.turn, 2, "returning from battle costs no turn")
		var still := false
		for e in _world.area["entities"]:
			if e["kind"] == "creature" and int(e.get("world_hex", -1)) == hid:
				still = true
		assert_true(not still, "the demon is gone from the node")
	# Save round trip.
	_adv.save()
	var snap: String = _world._world_flow.sim.snapshot()
	_world.queue_free()
	await process_frame
	_adv.load_game()
	var wf := WorldFlow.new()
	wf.setup(_adv)
	assert_eq(wf.sim.snapshot(), snap, "world survives save/load")
	assert_eq(int(_adv.state["version"]), 4, "save v4")


func _settle(prev_area: String = "") -> void:
	# Travel = step tween -> travel text dialogue -> fade tween -> load_area.
	# The input lock drops when the dialogue closes, before load_area runs,
	# so when a travel is expected wait for the area id to actually change.
	await process_frame
	await process_frame
	var guard := 0
	while guard < 900:
		guard += 1
		await process_frame
		if _world.ui_dialogue_open():
			_world.ui_dialogue_advance()
			continue
		if prev_area != "" and _world.area_id == prev_area:
			continue
		if not _world.ui_input_locked() and not _world.ui_is_moving():
			await process_frame
			return
	_failures.append("travel did not settle")


func _drain() -> void:
	for i in range(240):
		await process_frame
		if _world.ui_dialogue_open():
			_world.ui_dialogue_advance()
		elif not _world.ui_input_locked():
			return


func _has_entity(id: String) -> bool:
	for e in _world.area["entities"]:
		if str(e.get("id", "")) == id:
			return true
	return false


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
	if a != b:
		_failures.append("%s expected %s got %s" % [msg, str(b), str(a)])


func _report() -> void:
	if _failures.is_empty():
		print("WORLD FLOW: ALL PASSED")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		print("WORLD FLOW: %d FAILED" % _failures.size())
		quit(1)

extends SceneTree

## E17A dialogue presentation: the production Overworld path, not the quest runner alone.
## Boots fixture E17A through Village Test Mode, faces an NPC, and talks via ui_action().
##
## godot --headless --path godot_project --script res://client/tests/run_e17a_dialogue.gd

const _VRunner = preload("res://client/scripts/village_test_runner.gd")
const _Catalog = preload("res://sim/world/village_test_catalog.gd")

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
	await _test_miner_choice_and_aside()
	_report()


func _test_miner_choice_and_aside() -> void:
	var tag := "E17A dialogue UI"
	var branch_line := _authored_turn("a", "scene_01_a", "branch_a")
	var aside_line := _authored_turn("d", "scene_04_d", "default")
	assert_true(branch_line != "", "%s: fixture has Miner's branch_a line" % tag)
	assert_true(aside_line != "", "%s: fixture has Storekeeper's default line" % tag)
	_adv.new_game()
	_VRunner.set_profile("E17A")
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	for _i in 12:
		await process_frame
	assert_true(_VRunner.is_active() and not _VRunner.is_generated(), "%s: fixture session active" % tag)
	assert_true(not _world.ui_input_locked(), "%s: input free after boot" % tag)

	var before_aside: Dictionary = _VRunner.quest_state()
	_face_npc("d")
	assert_true(not _world.ui_prompt_visible(), "%s: Storekeeper does not show Talk" % tag)
	assert_true(not _world.ui_action_button_visible(), "%s: Action button is hidden" % tag)
	var key := _semantic_key_for("d")
	assert_true(key != "", "%s: Storekeeper has a semantic label" % tag)
	_world.ui_tap_semantic(key)
	await process_frame
	var aside_seen := await _drain_semantic(key)
	assert_true(not _world.ui_dialogue_open(), "%s: Storekeeper speech stayed off DialogueBox" % tag)
	assert_true(aside_seen.contains(aside_line), "%s: Storekeeper spoke authored default dialogue (saw %s)" % [tag, aside_seen.left(180)])
	var after_aside: Dictionary = _VRunner.quest_state()
	assert_eq(str(after_aside.get("current_node", "")), str(before_aside.get("current_node", "")), "%s: aside talk did not advance the quest" % tag)
	assert_eq(str(after_aside.get("flags", {})), str(before_aside.get("flags", {})), "%s: aside talk did not set quest flags" % tag)

	_face_npc("a")
	assert_true(not _world.ui_prompt_visible(), "%s: semantic Miner does not show Talk" % tag)
	assert_true(not _world.ui_dialogue_open(), "%s: facing Miner did not open DialogueBox" % tag)
	_world.ui_tap_semantic("person:e17a:a")
	await process_frame
	var opening := ""
	for raw in _world.ui_semantic_labels():
		if str(raw.get("key", "")) == "person:e17a:a":
			opening = str(raw.get("text", ""))
			assert_eq(str(raw.get("state", "")), "SPEECH", "%s: nearby label tap starts speech" % tag)
	assert_true(opening.strip_edges() != "", "%s: visible dialogue text is non-empty" % tag)
	assert_true(not _world.ui_dialogue_open(), "%s: semantic speech stays off DialogueBox" % tag)
	_world.ui_tap_semantic("person:e17a:a")
	await process_frame
	var choices: Array = _world.ui_semantic_responses("person:e17a:a")
	assert_true(choices.size() >= 2, "%s: Miner's first choice is offered" % tag)
	_world.ui_tap_semantic_response("person:e17a:a", 0)
	await process_frame
	var seen := ""
	for raw in _world.ui_semantic_labels():
		if str(raw.get("key", "")) == "person:e17a:a":
			seen = str(raw.get("text", ""))
	assert_true(seen.contains(branch_line), "%s: authored branch response is displayed (saw %s)" % [tag, seen.left(220)])
	assert_true(not _world.ui_dialogue_open(), "%s: branch speech stays off DialogueBox" % tag)
	_world.queue_free()
	await process_frame


func _authored_turn(npc_id: String, node_id: String, variant: String) -> String:
	var fixture: Dictionary = _Catalog.load_fixture("E17A")
	for raw in fixture.get("dialogue", {}).get("dialogue", []):
		if not (raw is Dictionary):
			continue
		var d: Dictionary = raw
		if str(d.get("npc_id", "")) != npc_id or str(d.get("node_id", "")) != node_id or str(d.get("variant", "")) != variant:
			continue
		for turn in d.get("turns", []):
			if turn is Dictionary and str((turn as Dictionary).get("text", "")) != "":
				return str((turn as Dictionary).get("text", ""))
	return ""


func _semantic_key_for(entity_id: String) -> String:
	for raw in _world.ui_semantic_labels():
		if str(raw.get("entity_id", "")) == entity_id:
			return str(raw.get("key", ""))
	return ""


func _drain_semantic(key: String) -> String:
	var seen := ""
	for _i in 24:
		var entry := {}
		for raw in _world.ui_semantic_labels():
			if str(raw.get("key", "")) == key:
				entry = raw
		var state := str(entry.get("state", ""))
		var text := str(entry.get("text", ""))
		if state != "SPEECH":
			return seen
		if text != "" and not seen.contains(text):
			seen += text + "\n"
		_world.ui_tap_semantic(key)
		await process_frame
	return seen


func _face_npc(npc_id: String) -> void:
	var pos := Vector2i.ZERO
	var found := false
	for e in _world.area["entities"]:
		if str(e.get("kind", "")) == "npc" and str(e.get("id", "")) == npc_id:
			pos = Vector2i(int(e["pos"][0]), int(e["pos"][1]))
			found = true
			break
	assert_true(found, "npc %s is in the loaded area" % npc_id)
	_world._john_pos = pos + Vector2i(0, 1)
	_world._john_facing = "up"
	_world._moving = false
	_world._john.position = Vector2(_world._john_pos) * 64 + Vector2(0, -32)
	_world._update_prompt()


func _advance_until_choice() -> bool:
	for _i in 80:
		if _world.ui_dialogue_waiting_choice():
			return true
		if _world.ui_dialogue_open():
			_world.ui_dialogue_advance()
		await process_frame
	return false


func _drain_speech(already_open: bool) -> String:
	var seen := ""
	var opened := already_open
	for _i in 160:
		if _world.ui_dialogue_open():
			opened = true
			var text: String = _world._dialogue.ui_visible_text()
			if text != "" and not seen.contains(text):
				seen += text + "\n"
			if not _world.ui_dialogue_waiting_choice():
				_world.ui_dialogue_advance()
		elif opened:
			return seen
		await process_frame
	return seen


func _finish_speech() -> void:
	for _i in 80:
		if not _world.ui_dialogue_open() and not _world.ui_input_locked():
			return
		if _world.ui_dialogue_waiting_choice():
			_world.ui_dialogue_choose_index(0)
		elif _world.ui_dialogue_open():
			_world.ui_dialogue_advance()
		await process_frame


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func assert_eq(a, b, msg: String) -> void:
	if str(a) != str(b):
		_failures.append("%s expected %s got %s" % [msg, str(b), str(a)])


func _report() -> void:
	if _failures.is_empty():
		print("E17A DIALOGUE UI: ALL PASSED")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		print("E17A DIALOGUE UI: %d FAILED" % _failures.size())
		quit(1)

extends SceneTree

## WU-10: conversation hold, fresh movement, fresh pointer, and focus clutter.
## State and routing only. Not a claim that the motion feels good.
## godot --headless --path godot_project --script res://client/tests/run_semantic_conversation_ux.gd

const _VRunner = preload("res://client/scripts/village_test_runner.gd")

const MINER := "person:e17a:a"
const BRANCH_B := "scene_01_branch_b"

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
	await _boot()
	await _test_responses_persist()
	await _test_held_touch()
	await _test_held_key()
	await _test_fresh_gesture()
	await _test_explicit_choice()
	await _test_clutter()
	await _test_one_conversation()
	_VRunner.end(_adv)
	if is_instance_valid(_world):
		_world.queue_free()
	await process_frame
	_report()


func _boot() -> void:
	_adv.new_game()
	_VRunner.set_profile("E17A")
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	for _i in 12:
		await process_frame
	assert_true(_VRunner.is_active(), "E17A session active")
	var miner := _tile("a")
	var john: Vector2i = _world.ui_actor_pos("john")
	var steps := absi(john.x - miner.x) + absi(john.y - miner.y)
	assert_eq(steps, 1, "review opens beside Miner")


func _test_responses_persist() -> void:
	var tag := "Persistent responses"
	await _open_responses()
	var before: String = str(_VRunner.quest_state().get("current_node", ""))
	for _i in 180:
		await process_frame
	await create_timer(2.0).timeout
	assert_eq(_state(MINER), "RESPONSES", "%s: still waiting" % tag)
	assert_eq(_world.ui_semantic_selected(MINER), -1, "%s: nothing selected" % tag)
	assert_true(_world.ui_semantic_responses(MINER).size() >= 3, "%s: choices still visible" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), before, "%s: quest unchanged" % tag)


func _test_held_touch() -> void:
	await _held_move(false)


func _test_held_key() -> void:
	await _held_move(true)


func _held_move(keyboard: bool) -> void:
	var tag := "Held key" if keyboard else "Held touch"
	await _reset()
	_place("a", Vector2i(0, 1))
	await process_frame
	var hold := _walkable_dir()
	assert_true(hold != Vector2i.ZERO, "%s: a walkable direction exists" % tag)
	_hold(hold, keyboard)
	_world.ui_tap_semantic(MINER)
	await process_frame
	assert_eq(_state(MINER), "SPEECH", "%s: speech survives the carried direction" % tag)
	assert_true(not _world.ui_move_dismiss_armed(), "%s: dismissal stays disarmed while held" % tag)
	assert_eq(_world.ui_actor_pos("john"), _tile("a") + Vector2i(0, 1), "%s: carried direction does not step" % tag)
	_world.ui_tap_semantic(MINER)
	await process_frame
	assert_eq(_state(MINER), "RESPONSES", "%s: responses open while the direction is still held" % tag)
	for _i in 8:
		await process_frame
	assert_eq(_state(MINER), "RESPONSES", "%s: held direction does not dismiss responses" % tag)
	assert_eq(_world.ui_semantic_selected(MINER), -1, "%s: held direction selects nothing" % tag)
	_hold(Vector2i.ZERO, keyboard)
	await process_frame
	assert_true(_world.ui_move_dismiss_armed(), "%s: neutral input arms dismissal" % tag)
	assert_eq(_state(MINER), "RESPONSES", "%s: releasing movement does not dismiss" % tag)
	var before: Vector2i = _world.ui_actor_pos("john")
	_hold(hold, keyboard)
	await process_frame
	assert_eq(_state(MINER), "LABEL", "%s: a new direction dismisses" % tag)
	assert_true(_world.ui_actor_pos("john") != before, "%s: the new direction moves John" % tag)
	_hold(Vector2i.ZERO, keyboard)


func _test_fresh_gesture() -> void:
	var tag := "Fresh gesture"
	await _reset()
	_place("a", Vector2i(0, 1))
	await process_frame
	var lbl = _world.ui_semantic_label(MINER)
	assert_true(lbl != null and lbl.visible, "%s: label visible" % tag)
	if lbl == null:
		return
	var speech: Rect2 = lbl.presentation_rect()
	await _pointer(speech, true, true)
	await process_frame
	assert_eq(_state(MINER), "SPEECH", "%s: speech press opens speech" % tag)
	speech = lbl.presentation_rect()
	await _pointer(speech, true, false)
	await process_frame
	assert_eq(_state(MINER), "RESPONSES", "%s: speech press opens responses before release" % tag)
	assert_true(not lbl.responses_input_armed(), "%s: originating gesture is not input-ready" % tag)
	var choice: Rect2 = lbl.response_rect(1)
	await _pointer(choice, false, true)
	await process_frame
	assert_eq(_world.ui_semantic_selected(MINER), -1, "%s: finishing the gesture selects nothing" % tag)
	assert_eq(_state(MINER), "RESPONSES", "%s: responses remain after the originating release" % tag)
	assert_true(lbl.responses_input_armed(), "%s: a completed gesture arms the choices" % tag)
	await _pointer(choice, true, true)
	await process_frame
	assert_eq(_world.ui_semantic_selected(MINER), 1, "%s: a new touch selects that response" % tag)
	assert_true(lbl.choice_locked(), "%s: the selected response locks further clicks" % tag)


func _test_explicit_choice() -> void:
	var tag := "Explicit choice"
	await _open_responses()
	var lbl = _world.ui_semantic_label(MINER)
	var choice: Rect2 = lbl.response_rect(1)
	await _pointer(choice, true, true)
	await process_frame
	assert_eq(_world.ui_semantic_selected(MINER), 1, "%s: response B is the selected index" % tag)
	assert_true(lbl.choice_locked(), "%s: response B is locked" % tag)
	assert_eq(_state(MINER), "RESPONSES", "%s: the chosen wording stays visible briefly" % tag)
	assert_true(_VRunner.quest_state().get("flags", {}).has(BRANCH_B), "%s: branch B commits immediately" % tag)
	assert_true(not _VRunner.quest_state().get("flags", {}).has("scene_01_branch_a"), "%s: branch A is not committed" % tag)
	await _pointer(lbl.response_rect(0), true, true)
	await process_frame
	assert_eq(_world.ui_semantic_selected(MINER), 1, "%s: a second click does not change the choice" % tag)
	await create_timer(0.45).timeout
	assert_eq(_state(MINER), "SPEECH", "%s: NPC reply follows the acknowledgement" % tag)


func _test_clutter() -> void:
	var tag := "Clutter"
	await _reset()
	_place("a", Vector2i(0, 1))
	await process_frame
	var other = _world.ui_semantic_label("person:e17a:g")
	var node := _node("g")
	assert_true(other != null and node != null, "%s: a second label exists" % tag)
	if other == null or node == null:
		return
	node.global_position = _node("a").global_position + Vector2(80, 0)
	await process_frame
	other.refresh_presentation()
	assert_true(other.visible, "%s: neighbour is visible before conversation" % tag)
	_world.ui_tap_semantic(MINER)
	await process_frame
	assert_eq(_state(MINER), "SPEECH", "%s: speech is active" % tag)
	assert_true(not other.visible, "%s: neighbour is hidden during speech" % tag)
	_world.ui_tap_semantic(MINER)
	await process_frame
	assert_eq(_state(MINER), "RESPONSES", "%s: responses are active" % tag)
	assert_true(not other.visible, "%s: neighbour stays hidden during responses" % tag)
	var lbl = _world.ui_semantic_label(MINER)
	lbl.collapse()
	await process_frame
	other.refresh_presentation()
	assert_true(other.visible, "%s: neighbour returns when the conversation ends" % tag)
	assert_eq(other.interaction_state(), "LABEL", "%s: neighbour state was not rewritten" % tag)


func _test_one_conversation() -> void:
	var tag := "One conversation"
	await _reset()
	_place("a", Vector2i(0, 1))
	var node := _node("g")
	if node != null and _node("a") != null:
		node.global_position = _node("a").global_position + Vector2(96, 0)
	await process_frame
	_world.ui_tap_semantic(MINER)
	await process_frame
	assert_eq(_state(MINER), "SPEECH", "%s: miner is speaking" % tag)
	_world.ui_tap_semantic("person:e17a:g")
	await process_frame
	assert_eq(_state(MINER), "LABEL", "%s: starting another interaction collapses the first" % tag)
	var expanded := 0
	for raw in _world.ui_semantic_labels():
		if str(raw.get("state", "")) != "LABEL":
			expanded += 1
	assert_eq(expanded, 1, "%s: exactly one expanded interaction" % tag)


func _open_responses() -> void:
	await _reset()
	_place("a", Vector2i(0, 1))
	await process_frame
	_world.ui_tap_semantic(MINER)
	await process_frame
	_world.ui_tap_semantic(MINER)
	await process_frame
	assert_eq(_state(MINER), "RESPONSES", "responses opened")
	assert_true(_world.ui_semantic_responses(MINER).size() >= 3, "at least three choices")


func _reset() -> void:
	_hold(Vector2i.ZERO, false)
	_hold(Vector2i.ZERO, true)
	_world._finish_village_build(_VRunner.reset(_adv), _VRunner.session_facing())
	for _i in 8:
		await process_frame
	_world._present_cancelled = false


func _hold(dir: Vector2i, keyboard: bool) -> void:
	if keyboard:
		_world.ui_hold_key_direction(dir)
		_world.ui_hold_touch_direction(Vector2i.ZERO)
	else:
		_world.ui_hold_touch_direction(dir)
		_world.ui_hold_key_direction(Vector2i.ZERO)


func _pointer(rect: Rect2, press: bool, release: bool) -> void:
	var pos := root.get_final_transform() * rect.get_center()
	if press:
		var down := InputEventScreenTouch.new()
		down.index = 0
		down.pressed = true
		down.position = pos
		root.push_input(down)
		await process_frame
	if release:
		var up := InputEventScreenTouch.new()
		up.index = 0
		up.pressed = false
		up.position = pos
		root.push_input(up)
		await process_frame


func _walkable_dir() -> Vector2i:
	for dir in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		var dest: Vector2i = _world.ui_actor_pos("john") + dir
		if _world.ui_tile_walkable(dest) and not _world.ui_is_exit(dest):
			return dir
	return Vector2i.ZERO


func _place(npc_id: String, offset: Vector2i) -> void:
	var pos := _tile(npc_id)
	_world._john_pos = pos + offset
	_world._john_facing = "up"
	_world._moving = false
	_world._john.position = Vector2(_world._john_pos) * 64 + Vector2(0, -32)
	_world._camera.position_smoothing_enabled = false
	_world._camera.position = _world._john.position + Vector2(32, 32)
	_world._camera.reset_smoothing()
	_world._update_prompt()


func _tile(id: String) -> Vector2i:
	for e in _world.area["entities"]:
		if str(e.get("id", "")) == id:
			return Vector2i(int(e["pos"][0]), int(e["pos"][1]))
	return Vector2i.ZERO


func _node(id: String) -> Node2D:
	for e in _world._entities:
		if str(e.get("id", "")) != id:
			continue
		var node = e.get("node")
		if node is Node2D and is_instance_valid(node):
			return node
	return null


func _state(key: String) -> String:
	for raw in _world.ui_semantic_labels():
		if str(raw.get("key", "")) == key:
			return str(raw.get("state", ""))
	return ""


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func assert_eq(a, b, msg: String) -> void:
	if str(a) != str(b):
		_failures.append("%s (got %s expected %s)" % [msg, str(a), str(b)])


func _report() -> void:
	if _failures.is_empty():
		print("PASS semantic conversation ux")
		quit(0)
		return
	print("FAIL semantic conversation ux")
	for item in _failures:
		print("  - %s" % item)
	quit(1)

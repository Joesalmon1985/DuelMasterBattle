extends SceneTree

## WU-11: an explicit response click must show the authored NPC reply.
## Uses the real pointer path. Does not call ui_tap_semantic_response,
## press_response, or _on_semantic_response.
## godot --headless --path godot_project --script res://client/tests/run_semantic_post_choice_reply.gd

const _VRunner = preload("res://client/scripts/village_test_runner.gd")

const MINER := "person:e17a:a"
const BRANCH_A := [
	"Miner is unsettled by your detachment from the reality of their proposal.",
	"Exactly. I need Distiller to hear the plan, not my age.",
	"God's will is in our plan. Let Distiller hear it from the heart.",
	"Distiller bows their head, touched by your faith.",
]
const BRANCH_B := [
	"Miner is moved by your connection to the earth and its wisdom.",
	"Fine. I don't need their money to know whether they love me.",
	"Money can't buy love. But it could fund my next script rewrite.",
	"The townsfolk exchange confused glances, unsure of your sanity.",
]
const INQUIRY := "Miner asks Distiller to join the new workshop venture."

var _failures: Array = []
var _world
var _adv
var _rows: Array = []


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
	await _test_branch(0, "scene_01_branch_a", BRANCH_A)
	await _test_branch(1, "scene_01_branch_b", BRANCH_B)
	await _test_inquiry()
	await _test_ack_blocks_fresh_move()
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
	_quiet_camera()
	assert_true(_VRunner.is_active(), "E17A session active")


func _test_branch(index: int, flag: String, expected: Array) -> void:
	var tag := "Miner option %d" % index
	var committed := false
	var visible := false
	var first_ok := false
	var all_ok := false
	await _open_responses(tag)
	var lbl = _world.ui_semantic_label(MINER)
	if lbl == null:
		_rows.append({"title": tag, "committed": false, "visible": false, "first": false, "all": false})
		return
	assert_true(lbl.response_labels().size() >= 3, "%s: three choices" % tag)
	assert_eq(_world.ui_semantic_selected(MINER), -1, "%s: nothing preselected" % tag)
	await _pointer_click(lbl.response_rect(index), false)
	committed = _VRunner.quest_state().get("flags", {}).has(flag)
	assert_true(committed, "%s: choice committed" % tag)
	assert_eq(_world.ui_semantic_selected(MINER), index, "%s: that response was selected" % tag)
	assert_true(lbl.choice_locked(), "%s: further response clicks are locked" % tag)
	assert_eq(lbl.interaction_state(), "RESPONSES", "%s: selected wording stays up before the reply" % tag)
	assert_true(_trace_accepted_without_label(lbl.choice_trace()), "%s: choice did not collapse to LABEL" % tag)
	await _pointer_click(lbl.response_rect(0 if index != 0 else 1), false)
	assert_eq(_world.ui_semantic_selected(MINER), index, "%s: a second click does not duplicate the choice" % tag)
	await _wait_for_speech(lbl)
	visible = lbl.interaction_state() == "SPEECH" and lbl.display_text().strip_edges() != ""
	first_ok = visible and lbl.display_text() == str(expected[0])
	assert_true(visible, "%s: reply became SPEECH (saw %s / %s)" % [tag, lbl.interaction_state(), lbl.display_text()])
	assert_true(first_ok, "%s: first reply text" % tag)
	assert_true(_reply_followed_accept(lbl.choice_trace()), "%s: trace is CHOICE_ACCEPTED then SPEECH" % tag)
	assert_true(not _went_label_after_accept(lbl.choice_trace()), "%s: committed choice did not fall back to LABEL" % tag)
	all_ok = await _play_authored(lbl, expected, tag)
	_rows.append({"title": tag, "committed": committed, "visible": visible, "first": first_ok, "all": all_ok})


func _test_inquiry() -> void:
	var tag := "Miner inquiry"
	var unchanged := false
	var visible := false
	var returned := false
	await _open_responses(tag)
	var lbl = _world.ui_semantic_label(MINER)
	if lbl == null:
		_rows.append({"title": tag, "unchanged": false, "visible": false, "returned": false, "inquiry": true})
		return
	var before: Array = lbl.response_labels()
	await _pointer_click(lbl.response_rect(2), false)
	var flags: Dictionary = _VRunner.quest_state().get("flags", {})
	unchanged = str(_VRunner.quest_state().get("current_node", "")) == "scene_01_a" and not flags.has("scene_01_branch_a") and not flags.has("scene_01_branch_b")
	assert_true(unchanged, "%s: branch unchanged" % tag)
	assert_true(lbl.choice_locked(), "%s: inquiry click locks further choices" % tag)
	await _wait_for_speech(lbl)
	visible = lbl.interaction_state() == "SPEECH" and lbl.display_text() == INQUIRY
	assert_true(visible, "%s: inquiry reply visible (saw %s / %s)" % [tag, lbl.interaction_state(), lbl.display_text()])
	assert_true(_reply_followed_accept(lbl.choice_trace()), "%s: inquiry trace reached SPEECH" % tag)
	await _pointer_click(lbl.presentation_rect(), false)
	await process_frame
	returned = lbl.interaction_state() == "RESPONSES" and _world.ui_semantic_selected(MINER) == -1 and not lbl.choice_locked()
	assert_true(returned, "%s: returns to unresolved responses" % tag)
	assert_eq(lbl.response_labels(), before, "%s: the same choices return" % tag)
	flags = _VRunner.quest_state().get("flags", {})
	assert_true(not flags.has("scene_01_branch_a") and not flags.has("scene_01_branch_b"), "%s: returning did not commit a branch" % tag)
	_rows.append({"title": tag, "unchanged": unchanged, "visible": visible, "returned": returned, "inquiry": true})


func _test_ack_blocks_fresh_move() -> void:
	var tag := "Ack movement"
	await _open_responses(tag)
	var lbl = _world.ui_semantic_label(MINER)
	if lbl == null:
		return
	var hold := _walkable_dir()
	assert_true(hold != Vector2i.ZERO, "%s: a walkable direction exists" % tag)
	var before: Vector2i = _world.ui_actor_pos("john")
	await _pointer_click(lbl.response_rect(1), false)
	_world.ui_hold_key_direction(hold)
	for _i in 6:
		await process_frame
	assert_eq(lbl.interaction_state(), "RESPONSES", "%s: fresh movement during acknowledgement does not dismiss" % tag)
	assert_eq(_world.ui_actor_pos("john"), before, "%s: acknowledgement does not step" % tag)
	await _wait_for_speech(lbl)
	assert_eq(lbl.interaction_state(), "SPEECH", "%s: reply still appears after the held direction" % tag)
	assert_eq(lbl.display_text(), str(BRANCH_B[0]), "%s: held direction did not replace the reply" % tag)
	assert_eq(_world.ui_actor_pos("john"), before, "%s: John stays put until the reply is showing" % tag)
	_world.ui_hold_key_direction(Vector2i.ZERO)


func _play_authored(lbl, expected: Array, tag: String) -> bool:
	var ok: bool = lbl.interaction_state() == "SPEECH" and lbl.display_text() == str(expected[0])
	for i in range(1, expected.size()):
		await _pointer_click(lbl.presentation_rect(), false)
		await process_frame
		if lbl.interaction_state() != "SPEECH" or lbl.display_text() != str(expected[i]):
			ok = false
			assert_true(false, "%s: turn %d (saw %s / %s)" % [tag, i, lbl.interaction_state(), lbl.display_text()])
			return false
	assert_true(ok, "%s: all authored turns played" % tag)
	return ok


func _open_responses(tag: String) -> void:
	await _reset()
	_place("a", Vector2i(0, 1))
	await process_frame
	_park_except("a")
	await process_frame
	var lbl = _world.ui_semantic_label(MINER)
	assert_true(lbl != null and lbl.visible, "%s: miner label visible" % tag)
	if lbl == null:
		return
	await _pointer_click(lbl.presentation_rect(), false)
	await process_frame
	assert_eq(lbl.interaction_state(), "SPEECH", "%s: label click starts speech" % tag)
	await _pointer_click(lbl.presentation_rect(), false)
	await process_frame
	assert_eq(lbl.interaction_state(), "RESPONSES", "%s: speech click reveals choices" % tag)
	assert_true(lbl.response_labels().size() >= 3, "%s: three choices visible" % tag)


func _wait_for_speech(lbl) -> void:
	var waited := 0.0
	while waited < 0.6:
		if lbl.interaction_state() == "SPEECH" and lbl.display_text().strip_edges() != "":
			return
		if lbl.interaction_state() == "LABEL":
			return
		await create_timer(0.05).timeout
		waited += 0.05


func _trace_accepted_without_label(trace: Array) -> bool:
	var accepted := false
	for step in trace:
		if str(step) == "CHOICE_ACCEPTED":
			accepted = true
		elif accepted and str(step) == "LABEL":
			return false
	return accepted


func _reply_followed_accept(trace: Array) -> bool:
	var accepted := false
	for step in trace:
		if str(step) == "CHOICE_ACCEPTED":
			accepted = true
		elif accepted and str(step) == "SPEECH":
			return true
		elif accepted and str(step) == "LABEL":
			return false
	return false


func _went_label_after_accept(trace: Array) -> bool:
	var accepted := false
	var spoke := false
	for step in trace:
		if str(step) == "CHOICE_ACCEPTED":
			accepted = true
			spoke = false
		elif accepted and str(step) == "SPEECH":
			spoke = true
		elif accepted and str(step) == "LABEL" and not spoke:
			return true
	return false


func _reset() -> void:
	_world.ui_hold_key_direction(Vector2i.ZERO)
	_world.ui_hold_touch_direction(Vector2i.ZERO)
	_world._finish_village_build(_VRunner.reset(_adv), _VRunner.session_facing())
	for _i in 8:
		await process_frame
	_quiet_camera()
	_world._present_cancelled = false


func _pointer_click(rect: Rect2, touch: bool) -> void:
	var pos := root.get_final_transform() * rect.get_center()
	if rect.size.x < 4.0 or rect.size.y < 4.0:
		assert_true(false, "click rect is empty %s" % str(rect))
		return
	if touch:
		var down := InputEventScreenTouch.new()
		down.index = 0
		down.pressed = true
		down.position = pos
		root.push_input(down)
		await process_frame
		var up := InputEventScreenTouch.new()
		up.index = 0
		up.pressed = false
		up.position = pos
		root.push_input(up)
		await process_frame
		return
	var motion := InputEventMouseMotion.new()
	motion.position = pos
	motion.global_position = pos
	root.push_input(motion)
	await process_frame
	var press := InputEventMouseButton.new()
	press.button_index = MOUSE_BUTTON_LEFT
	press.pressed = true
	press.position = pos
	press.global_position = pos
	press.button_mask = MOUSE_BUTTON_MASK_LEFT
	root.push_input(press)
	await process_frame
	var release := InputEventMouseButton.new()
	release.button_index = MOUSE_BUTTON_LEFT
	release.pressed = false
	release.position = pos
	release.global_position = pos
	root.push_input(release)
	await process_frame


func _place(npc_id: String, offset: Vector2i) -> void:
	var pos := Vector2i.ZERO
	for e in _world.area["entities"]:
		if str(e.get("kind", "")) == "npc" and str(e.get("id", "")) == npc_id:
			pos = Vector2i(int(e["pos"][0]), int(e["pos"][1]))
			break
	_world._john_pos = pos + offset
	_world._john_facing = "up"
	_world._moving = false
	_world._john.position = Vector2(_world._john_pos) * 64 + Vector2(0, -8 * 4)
	_world._camera.position = _world._john.position + Vector2(32, 32)
	_world._update_prompt()


func _quiet_camera() -> void:
	_world._camera.position_smoothing_enabled = false
	_world._camera.reset_smoothing()
	if _world._camera.has_method("force_update_scroll"):
		_world._camera.force_update_scroll()


func _park_except(keep_id: String) -> void:
	for e in _world._entities:
		var id := str(e.get("id", ""))
		if id == keep_id:
			continue
		var node = e.get("node")
		if node is Node2D and is_instance_valid(node):
			node.global_position = Vector2(-4000, -4000)


func _walkable_dir() -> Vector2i:
	for dir in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		var dest: Vector2i = _world.ui_actor_pos("john") + dir
		if _world.ui_tile_walkable(dest) and not _world.ui_is_exit(dest):
			return dir
	return Vector2i.ZERO


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func assert_eq(a, b, msg: String) -> void:
	if str(a) != str(b):
		_failures.append("%s (got %s expected %s)" % [msg, str(a), str(b)])


func _mark(ok: bool) -> String:
	return "PASS" if ok else "FAIL"


func _report() -> void:
	print("POST_CHOICE_REPLY_BEGIN")
	for row in _rows:
		print("%s:" % str(row.get("title", "")))
		if bool(row.get("inquiry", false)):
			print("branch unchanged: %s" % _mark(bool(row.get("unchanged", false))))
			print("reply visible: %s" % _mark(bool(row.get("visible", false))))
			print("returns to responses: %s" % _mark(bool(row.get("returned", false))))
		else:
			print("choice committed: %s" % _mark(bool(row.get("committed", false))))
			print("reply visible: %s" % _mark(bool(row.get("visible", false))))
			print("first reply text: %s" % _mark(bool(row.get("first", false))))
			print("all reply turns playable: %s" % _mark(bool(row.get("all", false))))
	print("POST_CHOICE_REPLY_END")
	if _failures.is_empty():
		print("PASS semantic post-choice reply")
		quit(0)
		return
	print("FAIL semantic post-choice reply")
	for item in _failures:
		print("  - %s" % item)
	quit(1)

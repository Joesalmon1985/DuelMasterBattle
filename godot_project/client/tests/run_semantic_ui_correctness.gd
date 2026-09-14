extends SceneTree

## WU-09: semantic visibility, stacking and real response clicks.
## Geometry and input routing only. Not a visual-quality claim.
## godot --headless --path godot_project --script res://client/tests/run_semantic_ui_correctness.gd

const _VRunner = preload("res://client/scripts/village_test_runner.gd")

const MINER := "person:e17a:a"
const INQUIRY := "What exactly are you asking Distiller to risk?"

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
	await _test_visibility()
	await _test_response_layout()
	await _test_real_click(0, "scene_01_branch_a", "scene_02_b", false)
	await _test_real_click(1, "scene_01_branch_b", "scene_02_b", false)
	await _test_real_click(2, "", "scene_01_a", true)
	await _test_real_touch(0, "scene_01_branch_a", "scene_02_b")
	await _test_offscreen_conversation()
	await _test_held_conversation_survives_offscreen()
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


func _test_visibility() -> void:
	var tag := "Visibility"
	var lbl = _world.ui_semantic_label(MINER)
	var node := _node_for("a")
	assert_true(lbl != null and node != null, "%s: miner label and sprite" % tag)
	if lbl == null or node == null:
		return
	var saved: Vector2 = node.global_position
	_quiet_camera()
	lbl.refresh_presentation()
	var home: Rect2 = lbl.target_screen_rect()
	var view: Rect2 = _world.ui_visible_rect()
	assert_true(view.intersects(home), "%s: miner starts on screen %s" % [tag, str(home)])
	assert_true(lbl.visible, "%s: on-screen miner label is visible" % tag)
	await _assert_edge(tag, lbl, node, "left", Vector2(-20, 400), Vector2(-120, 400))
	await _assert_edge(tag, lbl, node, "right", Vector2(view.size.x - 28, 400), Vector2(view.size.x + 40, 400))
	await _assert_edge(tag, lbl, node, "top", Vector2(200, -16), Vector2(200, -120))
	await _assert_edge(tag, lbl, node, "bottom", Vector2(200, view.size.y - 28), Vector2(200, view.size.y + 40))
	node.global_position = saved
	await process_frame
	lbl.refresh_presentation()
	assert_true(lbl.target_on_screen(), "%s: restored miner is on screen" % tag)
	assert_true(lbl.visible, "%s: label returns when the miner re-enters" % tag)
	var shown: Rect2 = lbl.presentation_rect()
	assert_true(_inside(view, shown), "%s: returned label is on-screen %s" % [tag, str(shown)])


func _assert_edge(tag: String, lbl, node: Node2D, side: String, partial: Vector2, gone: Vector2) -> void:
	_set_sprite_topleft(node, partial)
	await process_frame
	lbl.refresh_presentation()
	var target: Rect2 = lbl.target_screen_rect()
	var view: Rect2 = _world.ui_visible_rect()
	assert_true(view.intersects(target), "%s: %s partial target still intersects (%s)" % [tag, side, str(target)])
	assert_true(lbl.visible, "%s: %s partial target keeps the label" % [tag, side])
	var shown: Rect2 = lbl.presentation_rect()
	assert_true(shown.size.x > 8.0 and shown.size.y > 8.0, "%s: %s partial label has a rect" % [tag, side])
	assert_true(_inside(view, shown), "%s: %s overflowing label is clamped inside (%s)" % [tag, side, str(shown)])
	_set_sprite_topleft(node, gone)
	await process_frame
	lbl.refresh_presentation()
	target = lbl.target_screen_rect()
	assert_true(not view.intersects(target), "%s: %s target is fully off-screen (%s)" % [tag, side, str(target)])
	assert_true(not lbl.visible, "%s: %s off-screen label is hidden, not pinned" % [tag, side])


func _test_response_layout() -> void:
	var tag := "Response layout"
	var lbl = _world.ui_semantic_label(MINER)
	assert_true(lbl != null, "%s: miner label" % tag)
	if lbl == null:
		return
	var options: Array = []
	for i in 30:
		options.append({"index": i, "label": "A long inquiry that must wrap onto several lines before it can be tapped %d" % i})
	lbl.present_choices(options)
	_world._sync_semantic_stack()
	await process_frame
	lbl.refresh_presentation()
	var view: Rect2 = _world.ui_visible_rect()
	var panel: Rect2 = lbl.presentation_rect()
	assert_true(panel.size.y <= view.size.y - 8.0, "%s: tall set is constrained (%s)" % [tag, str(panel.size)])
	assert_true(_inside(view, panel), "%s: constrained panel stays in the viewport" % tag)
	var prev := Rect2()
	for i in 3:
		var rect: Rect2 = lbl.response_rect(i)
		assert_true(rect.size.y >= 56.0, "%s: response %d is touch sized (%s)" % [tag, i, str(rect.size)])
		if i > 0:
			assert_true(rect.position.y >= prev.end.y + 4.0, "%s: response %d does not overlap the one above" % [tag, i])
		prev = rect
	lbl.collapse()
	_world._present_cancelled = false
	await process_frame


func _test_real_click(index: int, flag: String, node_id: String, inquiry: bool) -> void:
	var tag := "Mouse response %d" % index
	await _open_responses(tag)
	var lbl = _world.ui_semantic_label(MINER)
	if lbl == null:
		return
	var choices: Array = _world.ui_semantic_responses(MINER)
	assert_true(choices.size() >= 3, "%s: three responses visible (got %d)" % [tag, choices.size()])
	assert_eq(_world.ui_semantic_selected(MINER), -1, "%s: nothing preselected" % tag)
	if inquiry and choices.size() > 2:
		assert_eq(str(choices[2]), INQUIRY, "%s: third response is the inquiry" % tag)
	var rival = await _overlap_rival(lbl, index)
	var rival_id := ""
	if rival != null:
		rival_id = str(rival.entity_id())
	var pos_before: Vector2i = _world.ui_actor_pos("john")
	var rect: Rect2 = lbl.response_rect(index)
	assert_true(rect.size.x > 8.0 and rect.size.y > 8.0, "%s: response rect is real (%s)" % [tag, str(rect)])
	var hit = await _pointer_hit(rect)
	var expected: Button = lbl.response_button(index)
	assert_true(hit == expected, "%s: pointer hits response %d, not a neighbour (hit %s)" % [tag, index, _ctrl_name(hit)])
	await _pointer_click(rect, false)
	await process_frame
	assert_eq(_world.ui_semantic_selected(MINER), index, "%s: clicked response was selected" % tag)
	assert_eq(_world.ui_actor_pos("john"), pos_before, "%s: click did not move John" % tag)
	assert_true(not _world.ui_action_button_visible(), "%s: hidden action route stayed hidden" % tag)
	assert_true(not _world.ui_dialogue_open(), "%s: click did not open DialogueBox" % tag)
	if rival != null and is_instance_valid(rival):
		assert_eq(rival.interaction_state(), "LABEL", "%s: overlapping label was not activated" % tag)
		assert_true(not rival.visible or rival.is_foreground() == false, "%s: rival did not take foreground" % tag)
	var flags: Dictionary = _VRunner.quest_state().get("flags", {})
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), node_id, "%s: quest node follows the clicked option" % tag)
	if inquiry:
		assert_true(not flags.has("scene_01_branch_a"), "%s: inquiry did not commit A" % tag)
		assert_true(not flags.has("scene_01_branch_b"), "%s: inquiry did not commit B" % tag)
		await create_timer(0.45).timeout
		assert_eq(str(_world.ui_semantic_label(MINER).interaction_state()), "SPEECH", "%s: inquiry returns to speech" % tag)
	else:
		assert_true(flags.has(flag), "%s: clicked branch was committed" % tag)
		var other := "scene_01_branch_b" if flag == "scene_01_branch_a" else "scene_01_branch_a"
		assert_true(not flags.has(other), "%s: the other branch was not committed" % tag)
	if rival_id != "":
		assert_eq(_entry_state(rival.knowledge_key()), "LABEL", "%s: rival stayed a passive label" % tag)


func _test_real_touch(index: int, flag: String, node_id: String) -> void:
	var tag := "Touch response %d" % index
	await _open_responses(tag)
	var lbl = _world.ui_semantic_label(MINER)
	if lbl == null:
		return
	await _overlap_rival(lbl, index)
	var pos_before: Vector2i = _world.ui_actor_pos("john")
	var rect: Rect2 = lbl.response_rect(index)
	await _pointer_click(rect, true)
	await process_frame
	assert_eq(_world.ui_semantic_selected(MINER), index, "%s: touch selected that response" % tag)
	assert_eq(_world.ui_actor_pos("john"), pos_before, "%s: touch did not move John" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), node_id, "%s: touch consequences match the option" % tag)
	assert_true(_VRunner.quest_state().get("flags", {}).has(flag), "%s: touch committed the clicked branch" % tag)


func _test_offscreen_conversation() -> void:
	var tag := "Off-screen conversation"
	await _open_responses(tag)
	var lbl = _world.ui_semantic_label(MINER)
	var node := _node_for("a")
	if lbl == null or node == null:
		return
	var saved: Vector2 = node.global_position
	assert_eq(lbl.interaction_state(), "RESPONSES", "%s: responses were open" % tag)
	assert_eq(_world.ui_semantic_selected(MINER), -1, "%s: nothing selected before leaving" % tag)
	_set_sprite_topleft(node, Vector2(-200, 400))
	await process_frame
	lbl.refresh_presentation()
	assert_true(not lbl.target_on_screen(), "%s: miner left the viewport" % tag)
	assert_eq(lbl.interaction_state(), "LABEL", "%s: off-screen conversation collapsed" % tag)
	assert_true(not lbl.visible, "%s: collapsed label stays hidden while off-screen" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_01_a", "%s: collapse chose nothing" % tag)
	node.global_position = saved
	await process_frame
	lbl.refresh_presentation()
	assert_true(lbl.visible, "%s: passive label returns with the miner" % tag)
	assert_eq(lbl.interaction_state(), "LABEL", "%s: return is the label, not a resumed choice" % tag)


func _test_held_conversation_survives_offscreen() -> void:
	var tag := "Held conversation"
	await _open_responses(tag)
	var lbl = _world.ui_semantic_label(MINER)
	var node := _node_for("a")
	if lbl == null or node == null:
		return
	var saved: Vector2 = node.global_position
	lbl.set_dismiss_on_move(false)
	_set_sprite_topleft(node, Vector2(-200, 400))
	await process_frame
	lbl.refresh_presentation()
	assert_true(not lbl.visible, "%s: held conversation is not pinned to the edge" % tag)
	assert_eq(lbl.interaction_state(), "RESPONSES", "%s: dismiss_on_move false did not collapse" % tag)
	assert_eq(_world.ui_semantic_selected(MINER), -1, "%s: held conversation selected nothing" % tag)
	node.global_position = saved
	await process_frame
	lbl.refresh_presentation()
	lbl.set_dismiss_on_move(true)
	assert_true(lbl.visible, "%s: held conversation returns with the target" % tag)
	assert_eq(lbl.interaction_state(), "RESPONSES", "%s: returned still waiting for an explicit choice" % tag)


func _open_responses(tag: String) -> void:
	await _reset()
	_place("a", Vector2i(0, 1))
	await process_frame
	_park_except("a")
	await process_frame
	var lbl = _world.ui_semantic_label(MINER)
	assert_true(lbl != null and lbl.visible, "%s: miner label visible before conversation" % tag)
	if lbl == null:
		return
	assert_true(_world.ui_action_button_visible() == false, "%s: action button hidden" % tag)
	var opened := await _click_control_rect(lbl.presentation_rect())
	assert_true(opened, "%s: real label click landed" % tag)
	await process_frame
	assert_eq(lbl.interaction_state(), "SPEECH", "%s: nearby label click starts speech" % tag)
	var advanced := await _click_control_rect(lbl.presentation_rect())
	assert_true(advanced, "%s: real speech click landed" % tag)
	await process_frame
	assert_eq(lbl.interaction_state(), "RESPONSES", "%s: speech click reaches responses" % tag)
	assert_true(lbl.is_foreground(), "%s: conversation owns the foreground" % tag)
	assert_eq(_world.ui_semantic_selected(MINER), -1, "%s: responses are not preselected" % tag)
	for _i in 4:
		await process_frame
	assert_eq(_world.ui_semantic_selected(MINER), -1, "%s: waiting does not auto-select" % tag)


func _overlap_rival(active, index: int):
	var rival = _world.ui_semantic_label("person:e17a:g")
	var node := _node_for("g")
	if rival == null or node == null:
		assert_true(false, "overlap rival missing")
		return null
	var target: Rect2 = active.response_rect(index)
	_set_sprite_topleft(node, target.get_center())
	for _i in 6:
		rival.refresh_presentation()
		var placed: Rect2 = rival.passive_placement_rect()
		var delta: Vector2 = target.get_center() - placed.get_center()
		if delta.length() < 6.0:
			break
		node.global_position += delta / _world._camera.zoom
	await process_frame
	_world._sync_semantic_stack()
	rival.refresh_presentation()
	active.refresh_presentation()
	var natural: Rect2 = rival.passive_placement_rect()
	var response: Rect2 = active.response_rect(index)
	assert_true(natural.intersects(response), "rival natural rect overlaps response %d (%s vs %s)" % [index, str(natural), str(response)])
	assert_true(not rival.visible, "overlapping passive label is suppressed during responses")
	assert_true(active.is_foreground(), "active responses stay foreground")
	assert_true(not rival.is_foreground(), "rival is not foreground")
	assert_true(active.focus_rank() > rival.focus_rank(), "active stacking rank is above the rival")
	return rival


func _reset() -> void:
	_world._finish_village_build(_VRunner.reset(_adv), _VRunner.session_facing())
	for _i in 8:
		await process_frame
	_quiet_camera()
	_world._present_cancelled = false


func _click_control_rect(rect: Rect2) -> bool:
	if rect.size.x < 4.0 or rect.size.y < 4.0:
		return false
	await _pointer_click(rect, false)
	return true


func _pointer_hit(rect: Rect2):
	var pos := _event_pos(rect.get_center())
	var motion := InputEventMouseMotion.new()
	motion.position = pos
	motion.global_position = pos
	root.push_input(motion)
	await process_frame
	return root.gui_get_hovered_control()


func _pointer_click(rect: Rect2, touch: bool) -> void:
	var pos := _event_pos(rect.get_center())
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


func _event_pos(canvas: Vector2) -> Vector2:
	return root.get_final_transform() * canvas


func _set_sprite_topleft(node: Node2D, screen: Vector2) -> void:
	_quiet_camera()
	var current: Vector2 = _world.ui_world_to_screen(node.global_position)
	node.global_position += (screen - current) / _world._camera.zoom


func _park_except(keep_id: String) -> void:
	for e in _world._entities:
		var id := str(e.get("id", ""))
		if id == keep_id:
			continue
		var node = e.get("node")
		if node is Node2D and is_instance_valid(node):
			node.global_position = Vector2(-4000, -4000)


func _node_for(id: String) -> Node2D:
	for e in _world._entities:
		if str(e.get("id", "")) != id:
			continue
		var node = e.get("node")
		if node is Node2D and is_instance_valid(node):
			return node
	return null


func _place(npc_id: String, offset: Vector2i) -> void:
	var pos := Vector2i.ZERO
	for e in _world.area["entities"]:
		if str(e.get("kind", "")) == "npc" and str(e.get("id", "")) == npc_id:
			pos = Vector2i(int(e["pos"][0]), int(e["pos"][1]))
			break
	_world._john_pos = pos + offset
	_world._john_facing = "up"
	_world._moving = false
	_world._john.position = Vector2(_world._john_pos) * 64 + Vector2(0, -32)
	_world._camera.position = _world._john.position + Vector2(32, 32)
	_world._update_prompt()


func _quiet_camera() -> void:
	_world._camera.position_smoothing_enabled = false
	_world._camera.reset_smoothing()
	if _world._camera.has_method("force_update_scroll"):
		_world._camera.force_update_scroll()


func _entry_state(key: String) -> String:
	for raw in _world.ui_semantic_labels():
		if str(raw.get("key", "")) == key:
			return str(raw.get("state", ""))
	return ""


func _ctrl_name(ctrl) -> String:
	if ctrl == null:
		return "null"
	return str(ctrl.name)


func _inside(view: Rect2, rect: Rect2) -> bool:
	return view.grow(1.0).encloses(rect)


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func assert_eq(a, b, msg: String) -> void:
	if str(a) != str(b):
		_failures.append("%s (got %s expected %s)" % [msg, str(a), str(b)])


func _report() -> void:
	if _failures.is_empty():
		print("PASS semantic ui correctness")
		quit(0)
		return
	print("FAIL semantic ui correctness")
	for item in _failures:
		print("  - %s" % item)
	quit(1)

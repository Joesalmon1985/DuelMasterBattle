extends SceneTree

## WU-13: selected replies are exact, and every villager offers choice-driven talk.
## Main acceptance uses real pointer input on WorldInteractionLabel.
## Does not call ui_tap_semantic_response, press_response, or _on_semantic_response.
## godot --headless --path godot_project --script res://client/tests/run_e17a_choice_conversations.gd

const _VRunner = preload("res://client/scripts/village_test_runner.gd")
const _Quest = preload("res://sim/world/village_quest_runner.gd")

const CAST := [
	["a", "Miner"],
	["b", "Distiller"],
	["c", "Reeve"],
	["d", "Storekeeper"],
	["e", "Woodcutter"],
	["f", "Farmer"],
	["g", "Miller"],
	["h", "Blacksmith"],
	["i", "Healer"],
	["j", "Watchkeeper"],
	["k", "Householder"],
	["l", "Shrine Keeper"],
]

var _failures: Array = []
var _world
var _adv
var _matrix: Array = []
var _miner_opening := ""
var _miner_replies: Array = ["", "", ""]
var _blacksmith: Array = []


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
	_test_contract()
	await test_miner_selected_reply_is_not_opening()
	await _test_blacksmith_topics()
	await _test_cast_matrix()
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


func _test_contract() -> void:
	var errors: Array = _Quest.progression_choice_errors()
	assert_true(errors.is_empty(), "progression choices have exact replies (%s)" % str(errors))
	var missing := _Quest.lookup_exact("d", "scene_04_d", "branch_b")
	var present := _Quest.lookup_exact("d", "scene_04_d", "default")
	assert_true(missing.is_empty(), "missing variant does not resolve")
	assert_true(not present.is_empty(), "storekeeper default still exists for the fallback proof")
	var before := _snapshot()
	for pair in CAST:
		var id := str(pair[0])
		if id == "a":
			continue
		var offered: Dictionary = _Quest.conversation_for(id)
		var options: Array = offered.get("options", [])
		assert_true(options.size() >= 3, "%s: at least three ambient topics" % pair[1])
		var seen: Dictionary = {}
		for option in options:
			var reply := _first_text(_Quest.lookup_exact(id, "__conversation__", str(option.get("id", ""))))
			assert_true(reply != "", "%s: topic has a reply" % pair[1])
			assert_true(not seen.has(reply), "%s: topic replies are distinct" % pair[1])
			seen[reply] = true
			var result: Dictionary = _Quest.respond_to(id, int(option.get("index", -1)))
			assert_true(bool(result.get("success", false)), "%s: ambient response succeeds" % pair[1])
			assert_eq(_snapshot(), before, "%s: ambient response did not change the quest" % pair[1])
			assert_true(bool(result.get("return_options", false)), "%s: ambient reply returns the menu" % pair[1])


func test_miner_selected_reply_is_not_opening() -> void:
	var tag := "test_miner_selected_reply_is_not_opening"
	var expected := [
		_first_text(_Quest.lookup_exact("a", "scene_01_a", "branch_a")),
		_first_text(_Quest.lookup_exact("a", "scene_01_a", "branch_b")),
		_first_text(_Quest.lookup_exact("a", "scene_01_a", "inquiry")),
	]
	var authored := [
		_texts(_Quest.lookup_exact("a", "scene_01_a", "branch_a")),
		_texts(_Quest.lookup_exact("a", "scene_01_a", "branch_b")),
		_texts(_Quest.lookup_exact("a", "scene_01_a", "inquiry")),
	]
	var opening := ""
	for index in range(3):
		await _reset()
		await _open_responses("a", tag)
		var lbl = _label("a")
		if opening == "":
			opening = await _opening_before_choices(lbl, tag)
		else:
			assert_eq(await _opening_before_choices(lbl, tag), opening, "%s: opening is stable" % tag)
		assert_true(lbl.response_labels().size() >= 3, "%s: three miner choices" % tag)
		assert_true(not _world.ui_dialogue_open(), "%s: DialogueBox stays closed" % tag)
		assert_true(not _world.ui_action_button_visible(), "%s: Action button stays hidden" % tag)
		await _pointer_click(lbl.response_rect(index), false)
		assert_eq(_world.ui_semantic_selected(_key("a")), index, "%s: selected index %d" % [tag, index])
		var flags: Dictionary = _VRunner.quest_state().get("flags", {})
		var node := str(_VRunner.quest_state().get("current_node", ""))
		if index == 0:
			assert_true(flags.has("scene_01_branch_a"), "%s: branch A set" % tag)
			assert_true(not flags.has("scene_01_branch_b"), "%s: branch B not set" % tag)
			assert_eq(node, "scene_02_b", "%s: choice advances the quest" % tag)
		elif index == 1:
			assert_true(flags.has("scene_01_branch_b"), "%s: branch B set" % tag)
			assert_true(not flags.has("scene_01_branch_a"), "%s: branch A not set" % tag)
			assert_eq(node, "scene_02_b", "%s: choice advances the quest" % tag)
		else:
			assert_true(not flags.has("scene_01_branch_a") and not flags.has("scene_01_branch_b"), "%s: inquiry sets no branch" % tag)
			assert_eq(node, "scene_01_a", "%s: inquiry stays on the choice" % tag)
		await _wait_for_speech(lbl)
		var reply: String = lbl.display_text().strip_edges()
		_miner_replies[index] = reply
		assert_true(reply != "", "%s: option %d reply is visible" % [tag, index])
		assert_true(reply != opening, "%s: option %d is not the opening" % [tag, index])
		assert_eq(reply, expected[index], "%s: option %d matches the exact authored reply" % [tag, index])
		if index < 2:
			assert_true(await _play_lines(lbl, authored[index], tag), "%s: option %d turns play in order" % [tag, index])
		else:
			await _pointer_click(lbl.presentation_rect(), false)
			await process_frame
			assert_eq(lbl.interaction_state(), "RESPONSES", "%s: inquiry returns the menu" % tag)
			assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_01_a", "%s: returned menu is still unresolved" % tag)
	_miner_opening = opening
	assert_true(_miner_replies[0] != _miner_replies[1], "%s: branch replies differ" % tag)
	_matrix.append({
		"name": "Miner",
		"options": 3,
		"distinct": _miner_replies[0] != _miner_replies[1] and _miner_replies[1] != _miner_replies[2] and _miner_replies[0] != _miner_replies[2],
		"safe": "progression",
	})


func _test_blacksmith_topics() -> void:
	var tag := "Blacksmith topics"
	var offered: Dictionary = _Quest.conversation_for("h")
	var options: Array = offered.get("options", [])
	assert_true(options.size() >= 3, "%s: at least three topics" % tag)
	var replies: Array = []
	for index in range(mini(3, options.size())):
		var option: Dictionary = options[index]
		await _reset()
		var before := _snapshot()
		await _open_responses("h", tag)
		var lbl = _label("h")
		var opening: String = await _opening_before_choices(lbl, tag)
		assert_true(lbl.response_labels().size() >= 3, "%s: response buttons" % tag)
		assert_eq(str(lbl.response_labels()[index]), str(option.get("label", "")), "%s: button %d is the authored topic" % [tag, index])
		await _pointer_click(lbl.response_rect(index), false)
		assert_eq(_world.ui_semantic_selected(_key("h")), index, "%s: selected index %d" % [tag, index])
		await _wait_for_speech(lbl)
		var reply: String = lbl.display_text().strip_edges()
		var expected: String = _first_text(_Quest.lookup_exact("h", "__conversation__", str(option.get("id", ""))))
		assert_true(reply != "", "%s: reply %d is non-empty" % [tag, index])
		assert_true(reply != opening, "%s: reply %d is not the opening" % [tag, index])
		assert_eq(reply, expected, "%s: reply %d is the authored topic" % [tag, index])
		assert_eq(_snapshot(), before, "%s: topic %d did not change the quest" % [tag, index])
		await _pointer_click(lbl.presentation_rect(), false)
		await process_frame
		assert_eq(lbl.interaction_state(), "RESPONSES", "%s: topic menu returns" % tag)
		assert_eq(_snapshot(), before, "%s: returning did not change the quest" % tag)
		replies.append(reply)
		_blacksmith.append({"topic": str(option.get("label", "")), "reply": reply})
	assert_true(replies.size() >= 3, "%s: three replies captured" % tag)
	if replies.size() >= 3:
		assert_true(replies[0] != replies[1] and replies[1] != replies[2] and replies[0] != replies[2], "%s: replies differ" % tag)


func _test_cast_matrix() -> void:
	for pair in CAST:
		var id := str(pair[0])
		var name := str(pair[1])
		if id == "a":
			continue
		var offered: Dictionary = _Quest.conversation_for(id)
		var options: Array = offered.get("options", [])
		await _reset()
		var before := _snapshot()
		await _open_responses(id, name)
		var lbl = _label(id)
		var opening: String = lbl.display_text().strip_edges() if lbl.interaction_state() == "SPEECH" else ""
		if lbl.interaction_state() == "SPEECH":
			opening = await _opening_before_choices(lbl, name)
		assert_true(opening != "", "%s: opening speech present" % name)
		assert_true(lbl.response_labels().size() >= 3, "%s: at least three responses" % name)
		assert_eq(_snapshot(), before, "%s: opening did not change the quest" % name)
		await _pointer_click(lbl.response_rect(0), false)
		assert_eq(_world.ui_semantic_selected(_key(id)), 0, "%s: pointer selected option 0" % name)
		await _wait_for_speech(lbl)
		var reply: String = lbl.display_text().strip_edges()
		var expected := _first_text(_Quest.lookup_exact(id, "__conversation__", str(options[0].get("id", ""))))
		assert_true(reply != "" and reply != opening, "%s: visible reply is not the opening" % name)
		assert_eq(reply, expected, "%s: visible reply is the authored topic" % name)
		assert_eq(_snapshot(), before, "%s: selected topic did not change the quest" % name)
		await _pointer_click(lbl.presentation_rect(), false)
		await process_frame
		assert_eq(lbl.interaction_state(), "RESPONSES", "%s: topics return after the reply" % name)
		var distinct := true
		var seen: Dictionary = {}
		for option in options:
			var line := _first_text(_Quest.lookup_exact(id, "__conversation__", str(option.get("id", ""))))
			if line == "" or seen.has(line):
				distinct = false
			seen[line] = true
		_matrix.append({
			"name": name,
			"options": options.size(),
			"distinct": distinct and reply != opening,
			"safe": "ambient at opening" if id in ["b", "c"] else "YES",
		})


func _opening_before_choices(lbl, tag: String) -> String:
	assert_eq(lbl.interaction_state(), "SPEECH", "%s: conversation starts in speech" % tag)
	var opening: String = lbl.display_text().strip_edges()
	var guard := 0
	while lbl.interaction_state() == "SPEECH" and guard < 8:
		await _pointer_click(lbl.presentation_rect(), false)
		await process_frame
		guard += 1
	assert_eq(lbl.interaction_state(), "RESPONSES", "%s: speech reaches responses" % tag)
	return opening


func _open_responses(npc_id: String, tag: String) -> void:
	_place(npc_id, Vector2i(0, 1))
	await process_frame
	_park_except(npc_id)
	await process_frame
	var lbl = _label(npc_id)
	assert_true(lbl != null and lbl.visible, "%s: label visible" % tag)
	if lbl == null:
		return
	await _pointer_click(lbl.presentation_rect(), false)
	await process_frame
	assert_eq(lbl.interaction_state(), "SPEECH", "%s: label click starts speech" % tag)


func _play_lines(lbl, expected: Array, tag: String) -> bool:
	var ok: bool = lbl.interaction_state() == "SPEECH" and lbl.display_text() == str(expected[0])
	for i in range(1, expected.size()):
		await _pointer_click(lbl.presentation_rect(), false)
		await process_frame
		if lbl.interaction_state() != "SPEECH" or lbl.display_text() != str(expected[i]):
			assert_true(false, "%s: turn %d (saw %s / %s)" % [tag, i, lbl.interaction_state(), lbl.display_text()])
			return false
	return ok


func _wait_for_speech(lbl) -> void:
	var waited := 0.0
	while waited < 0.8:
		if lbl.interaction_state() == "SPEECH" and lbl.display_text().strip_edges() != "":
			return
		await create_timer(0.05).timeout
		waited += 0.05


func _first_text(entry: Dictionary) -> String:
	var lines := _texts(entry)
	return str(lines[0]) if not lines.is_empty() else ""


func _texts(entry: Dictionary) -> Array:
	var out: Array = []
	for raw in entry.get("turns", []):
		if raw is Dictionary and str(raw.get("text", "")).strip_edges() != "":
			out.append(str(raw.get("text", "")))
	return out


func _reset() -> void:
	_world.ui_hold_key_direction(Vector2i.ZERO)
	_world.ui_hold_touch_direction(Vector2i.ZERO)
	_world._finish_village_build(_VRunner.reset(_adv), _VRunner.session_facing())
	for _i in 8:
		await process_frame
	_quiet_camera()
	_world._present_cancelled = false


func _pointer_click(rect: Rect2, _touch: bool) -> void:
	var pos := root.get_final_transform() * rect.get_center()
	if rect.size.x < 4.0 or rect.size.y < 4.0:
		assert_true(false, "click rect is empty %s" % str(rect))
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
	_world._john.position = Vector2(_world._john_pos) * 64 + Vector2(0, -32)
	_world._camera.position = _world._john.position + Vector2(32, 32)
	_world._camera.reset_smoothing()
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


func _label(npc_id: String):
	return _world.ui_semantic_label(_key(npc_id))


func _key(npc_id: String) -> String:
	return "person:e17a:" + npc_id


func _snapshot() -> String:
	var state: Dictionary = _VRunner.quest_state()
	return str(state.get("current_node", "")) + "|" + str(state.get("flags", {})) + "|" + str(state.get("complete", false))


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func assert_eq(a, b, msg: String) -> void:
	if str(a) != str(b):
		_failures.append("%s (got %s expected %s)" % [msg, str(a), str(b)])


func _mark(ok: bool) -> String:
	return "PASS" if ok else "FAIL"


func _report() -> void:
	print("CHOICE_CONVERSATION_BEGIN")
	print("Miner opening text:")
	print(_miner_opening)
	print("Miner option 0 first reply:")
	print(str(_miner_replies[0]))
	print("Miner option 1 first reply:")
	print(str(_miner_replies[1]))
	print("Miner option 2/inquiry first reply:")
	print(str(_miner_replies[2]))
	for i in range(_blacksmith.size()):
		var row: Dictionary = _blacksmith[i]
		print("Blacksmith topic %d:" % i)
		print(str(row.get("topic", "")))
		print("Blacksmith reply %d:" % i)
		print(str(row.get("reply", "")))
	print("NPC            options   distinct replies   quest-safe")
	for row in _matrix:
		print("%-14s %-9s %-18s %s" % [
			str(row.get("name", "")),
			str(row.get("options", 0)) + "+",
			_mark(bool(row.get("distinct", false))),
			str(row.get("safe", "")),
		])
	if _failures.is_empty():
		print("CHOICE_CONVERSATION_RESULT PASS")
	else:
		print("CHOICE_CONVERSATION_RESULT FAIL")
		for failure in _failures:
			print("FAIL: " + str(failure))
	quit(0 if _failures.is_empty() else 1)

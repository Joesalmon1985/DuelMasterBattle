extends SceneTree

## WU-12: every E17A villager can be spoken to without being the quest node.
## godot --headless --path godot_project --script res://client/tests/run_e17a_village_conversation.gd

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
const WALK := ["a", "g", "f", "h", "d", "i", "j", "l"]

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
	await _cover_phase("opening")
	await _cover_phase("scene_02_b")
	await _cover_phase("scene_03_c")
	await _cover_phase("aftermath/complete")
	await _test_progression_scene_02()
	await _test_progression_scene_03()
	await _test_walkaround()
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


func _cover_phase(phase: String) -> void:
	await _enter_phase(phase)
	for pair in CAST:
		var id := str(pair[0])
		var name := str(pair[1])
		var tag := "%s %s" % [phase, name]
		var key := _key(id)
		var row := {
			"phase": phase,
			"id": id,
			"name": name,
			"label": false,
			"near": false,
			"speech": false,
			"dialogue": false,
			"action": false,
			"quest": false,
		}
		var lbl = _world.ui_semantic_label(key)
		row["label"] = lbl != null
		assert_true(row["label"], "%s: semantic label exists" % tag)
		if lbl == null:
			_rows.append(row)
			continue
		if phase == "opening":
			await _observe_far(id, tag)
		var before := _snapshot()
		await _speak(id)
		lbl = _world.ui_semantic_label(key)
		var text := ""
		var state := ""
		if lbl != null:
			text = lbl.display_text().strip_edges()
			state = lbl.interaction_state()
		row["near"] = state == "SPEECH"
		row["speech"] = text != "" and text != "..." and not text.begins_with("Situation:")
		row["dialogue"] = not _world.ui_dialogue_open()
		row["action"] = not _world.ui_action_button_visible()
		var unchanged: bool = _snapshot() == before
		var ambient: bool = id != _expected_id() or _expected_id() == ""
		row["quest"] = unchanged if ambient else true
		if ambient:
			assert_true(unchanged, "%s: ambient talk did not change the quest" % tag)
		else:
			assert_true(unchanged, "%s: opening speech does not commit the choice" % tag)
		assert_true(row["near"], "%s: near tap starts speech (saw %s)" % [tag, state])
		assert_true(row["speech"], "%s: visible speech is authored (saw %s)" % [tag, text])
		assert_true(row["dialogue"], "%s: DialogueBox stays closed" % tag)
		assert_true(row["action"], "%s: Action button not required" % tag)
		if phase == "opening":
			await _walk_away(id, tag)
			await _speak(id)
			lbl = _world.ui_semantic_label(key)
			var again := ""
			if lbl != null:
				again = lbl.display_text().strip_edges()
			assert_true(again != "", "%s: a second talk is not silence" % tag)
			assert_true(_snapshot() == before or id == _expected_id(), "%s: repeating talk did not add progression" % tag)
		if lbl != null and is_instance_valid(lbl):
			lbl.collapse()
		await process_frame
		_rows.append(row)


func _observe_far(id: String, tag: String) -> void:
	_place(id, Vector2i(0, 2))
	await process_frame
	var lbl = _world.ui_semantic_label(_key(id))
	assert_true(lbl != null and lbl.visible, "%s: distant label visible" % tag)
	_world.ui_tap_semantic(_key(id))
	await process_frame
	lbl = _world.ui_semantic_label(_key(id))
	var text := ""
	if lbl != null:
		text = lbl.display_text().strip_edges()
		assert_eq(lbl.interaction_state(), "OBSERVATION", "%s: distant tap is observation" % tag)
	assert_true(text != "", "%s: distant observation has text" % tag)
	if lbl != null:
		lbl.collapse()
	await process_frame


func _speak(id: String) -> void:
	_place(id, Vector2i(0, 1))
	await process_frame
	_world.ui_tap_semantic(_key(id))
	await process_frame


func _walk_away(id: String, tag: String) -> void:
	await process_frame
	var before: Vector2i = _world.ui_actor_pos("john")
	var stepped := false
	for dir in [Vector2i(0, 1), Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1)]:
		var dest: Vector2i = before + dir
		if _world.ui_tile_walkable(dest) and not _world.ui_is_exit(dest):
			_world.ui_step(dir)
			stepped = true
			break
	await process_frame
	assert_true(stepped, "%s: a walk-away step exists" % tag)
	assert_eq(_state(_key(id)), "LABEL", "%s: walking away restores the label" % tag)


func _test_progression_scene_02() -> void:
	var tag := "scene_02 progression"
	await _enter_phase("scene_02_b")
	var before := _snapshot()
	for id in ["a", "c", "h"]:
		await _speak(id)
		assert_eq(_state(_key(id)), "SPEECH", "%s: %s speaks" % [tag, id])
		assert_true(_spoken(_key(id)) != "", "%s: %s speech is non-empty" % [tag, id])
		assert_eq(_snapshot(), before, "%s: %s did not progress" % [tag, id])
		var live = _world.ui_semantic_label(_key(id))
		if live != null:
			live.collapse()
		await process_frame
	await _speak("b")
	assert_eq(_state(_key("b")), "SPEECH", "%s: Distiller starts the progression beat" % tag)
	_world.ui_tap_semantic(_key("b"))
	await process_frame
	assert_eq(_state(_key("b")), "RESPONSES", "%s: Distiller offers the progression choice" % tag)
	assert_true(_world.ui_semantic_responses(_key("b")).size() >= 2, "%s: Distiller has choices" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_02_b", "%s: opening the choice does not advance" % tag)


func _test_progression_scene_03() -> void:
	var tag := "scene_03 progression"
	await _enter_phase("scene_03_c")
	var before := _snapshot()
	for id in ["a", "b", "d", "h", "l"]:
		await _speak(id)
		assert_eq(_state(_key(id)), "SPEECH", "%s: %s speaks" % [tag, id])
		assert_true(_spoken(_key(id)) != "", "%s: %s speech is non-empty" % [tag, id])
		assert_eq(_snapshot(), before, "%s: %s did not progress" % [tag, id])
		var live = _world.ui_semantic_label(_key(id))
		if live != null:
			live.collapse()
		await process_frame
	await _speak("c")
	assert_eq(_state(_key("c")), "SPEECH", "%s: Reeve starts the progression beat" % tag)
	_world.ui_tap_semantic(_key("c"))
	await process_frame
	assert_eq(_state(_key("c")), "RESPONSES", "%s: Reeve offers the progression choice" % tag)
	assert_true(_world.ui_semantic_responses(_key("c")).size() >= 2, "%s: Reeve has choices" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_03_c", "%s: opening the choice does not advance" % tag)


func _test_walkaround() -> void:
	var tag := "Walkaround"
	await _enter_phase("opening")
	var start := str(_VRunner.quest_state().get("current_node", ""))
	for id in WALK:
		await _speak(id)
		assert_eq(_state(_key(id)), "SPEECH", "%s: %s speaks" % [tag, id])
		assert_true(_spoken(_key(id)) != "" and _spoken(_key(id)) != "...", "%s: %s speech is visible" % [tag, id])
		assert_eq(str(_VRunner.quest_state().get("current_node", "")), start, "%s: %s did not advance the beat" % [tag, id])
		var live = _world.ui_semantic_label(_key(id))
		if live != null:
			live.collapse()
		await process_frame
	await _speak("a")
	_world.ui_tap_semantic(_key("a"))
	await process_frame
	assert_eq(_state(_key("a")), "RESPONSES", "%s: Miner still owns the choice" % tag)
	_world.ui_tap_semantic_response(_key("a"), 1)
	await create_timer(0.4).timeout
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_02_b", "%s: the correct NPC advances the quest exactly once" % tag)
	assert_true(_VRunner.quest_state().get("flags", {}).has("scene_01_branch_b"), "%s: the chosen branch committed" % tag)
	assert_true(not _VRunner.quest_state().get("flags", {}).has("scene_01_branch_a"), "%s: the other branch was not committed" % tag)


func _enter_phase(phase: String) -> void:
	await _reset()
	if phase == "opening":
		return
	_Quest.make_choice(1)
	if phase == "scene_02_b":
		assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_02_b", "entered scene_02_b")
		return
	_Quest.make_choice(0)
	if phase == "scene_03_c":
		assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_03_c", "entered scene_03_c")
		return
	_Quest.make_choice(0)
	assert_true(bool(_VRunner.quest_state().get("complete", false)), "aftermath settles the authored ending")


func _reset() -> void:
	_world._finish_village_build(_VRunner.reset(_adv), _VRunner.session_facing())
	for _i in 8:
		await process_frame
	_world._camera.position_smoothing_enabled = false
	_world._camera.reset_smoothing()


func _place(npc_id: String, offset: Vector2i) -> void:
	var pos := Vector2i.ZERO
	for e in _world.area["entities"]:
		if str(e.get("id", "")) == npc_id:
			pos = Vector2i(int(e["pos"][0]), int(e["pos"][1]))
			break
	_world._john_pos = pos + offset
	_world._john_facing = "up"
	_world._moving = false
	_world._john.position = Vector2(_world._john_pos) * 64 + Vector2(0, -32)
	_world._camera.position = _world._john.position + Vector2(32, 32)
	_world._camera.reset_smoothing()
	_world._update_prompt()


func _key(id: String) -> String:
	return "person:e17a:" + id


func _expected_id() -> String:
	return str(_Quest.expected_npc())


func _snapshot() -> String:
	var state: Dictionary = _VRunner.quest_state()
	return str(state.get("current_node", "")) + "|" + str(state.get("flags", {})) + "|" + str(state.get("complete", false))


func _state(key: String) -> String:
	var lbl = _world.ui_semantic_label(key)
	if lbl == null:
		return ""
	return str(lbl.interaction_state())


func _spoken(key: String) -> String:
	var lbl = _world.ui_semantic_label(key)
	if lbl == null:
		return ""
	return lbl.display_text().strip_edges()


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func assert_eq(a, b, msg: String) -> void:
	if str(a) != str(b):
		_failures.append("%s (got %s expected %s)" % [msg, str(a), str(b)])


func _mark(ok: bool) -> String:
	return "PASS" if ok else "FAIL"


func _report() -> void:
	print("E17A_VILLAGE_CONVERSATION_BEGIN")
	for row in _rows:
		print("%s %s (%s)" % [str(row.get("id", "")), str(row.get("name", "")), str(row.get("phase", ""))])
		print("semantic label exists       %s" % _mark(bool(row.get("label", false))))
		print("near interaction starts     %s" % _mark(bool(row.get("near", false))))
		print("visible speech non-empty    %s" % _mark(bool(row.get("speech", false))))
		print("DialogueBox remains closed  %s" % _mark(bool(row.get("dialogue", false))))
		print("Action button not required  %s" % _mark(bool(row.get("action", false))))
		print("quest unchanged if ambient  %s" % _mark(bool(row.get("quest", false))))
	print("E17A_VILLAGE_CONVERSATION_END")
	if _failures.is_empty():
		print("PASS e17a village conversation")
		quit(0)
		return
	print("FAIL e17a village conversation")
	for item in _failures:
		print("  - %s" % item)
	quit(1)

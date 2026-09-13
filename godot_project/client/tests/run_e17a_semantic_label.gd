extends SceneTree

## WU-03: E17A Miner has one LABEL-state WorldInteractionLabel.
## godot --headless --path godot_project --script res://client/tests/run_e17a_semantic_label.gd

const _VRunner = preload("res://client/scripts/village_test_runner.gd")
const _Knowledge = preload("res://sim/world/world_knowledge.gd")

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
	await _test_miner_label()
	_report()


func _test_miner_label() -> void:
	var tag := "E17A miner label"
	_adv.new_game()
	assert_eq(_Knowledge.get_level(_adv, "person:e17a:a"), 0, "%s: campaign does not start knowing Miner" % tag)
	var quest_before := ""
	_VRunner.set_profile("E17A")
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	for _i in 12:
		await process_frame
	var labels: Array = _world.ui_semantic_labels()
	assert_eq(labels.size(), 1, "%s: exactly one semantic label" % tag)
	if labels.size() == 1:
		assert_eq(str(labels[0]["key"]), "person:e17a:a", "%s: bound to person:e17a:a" % tag)
		assert_eq(str(labels[0]["entity_id"]), "a", "%s: internal id stays a" % tag)
		assert_eq(str(labels[0]["text"]), "Miner", "%s: role label" % tag)
		assert_eq(str(labels[0]["state"]), "LABEL", "%s: LABEL state only" % tag)
	var semantic_npcs := 0
	for e in _world.area["entities"]:
		if str(e.get("kind", "")) != "npc":
			continue
		if e.has("semantic"):
			semantic_npcs += 1
			assert_eq(str(e.get("id", "")), "a", "%s: only Miner is semantic" % tag)
	assert_eq(semantic_npcs, 1, "%s: non-semantic NPCs have no semantic block" % tag)
	assert_true(not _world.ui_dialogue_open(), "%s: creating the label did not open DialogueBox" % tag)
	quest_before = str(_VRunner.quest_state().get("current_node", ""))
	assert_eq(quest_before, "scene_01_a", "%s: quest not advanced by the label" % tag)
	var lbl = _world.ui_semantic_label("person:e17a:a")
	assert_true(lbl != null, "%s: label node available" % tag)
	if lbl != null:
		var before_world: Vector2 = lbl.tracked_world_position()
		lbl._anchor.position += Vector2(24, 0)
		await process_frame
		var after_world: Vector2 = lbl.tracked_world_position()
		assert_true(after_world.x > before_world.x, "%s: label follows the entity" % tag)
		_world._camera.position_smoothing_enabled = false
		_world._camera.reset_smoothing()
		var before_screen: Vector2 = lbl.screen_anchor()
		_world._camera.position += Vector2(80, 0)
		_world._camera.reset_smoothing()
		if _world._camera.has_method("force_update_scroll"):
			_world._camera.force_update_scroll()
		lbl._follow()
		var after_screen: Vector2 = lbl.screen_anchor()
		assert_true(after_screen.distance_to(before_screen) > 1.0, "%s: label tracks the camera (before %s after %s)" % [tag, str(before_screen), str(after_screen)])
	_Knowledge.learn(_adv, "person:e17a:a", 2)
	labels = _world.ui_semantic_labels()
	assert_eq(str(labels[0]["text"]), "Bren", "%s: knowledge change updates the label" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), quest_before, "%s: knowledge change did not advance the quest" % tag)
	assert_true(not _world.ui_dialogue_open(), "%s: knowledge change did not open DialogueBox" % tag)
	await _test_label_tap_does_not_act(tag)
	_world.queue_free()
	await process_frame


func _test_label_tap_does_not_act(tag: String) -> void:
	var miner := Vector2i.ZERO
	for e in _world.area["entities"]:
		if str(e.get("kind", "")) == "npc" and str(e.get("id", "")) == "a":
			miner = Vector2i(int(e["pos"][0]), int(e["pos"][1]))
	_world._john_pos = miner + Vector2i(0, 1)
	_world._john_facing = "up"
	_world._update_prompt()
	var pos_before: Vector2i = _world.ui_actor_pos("john")
	var quest_before := str(_VRunner.quest_state().get("current_node", ""))
	assert_eq(_world.ui_prompt(), "Talk to Miner", "%s: ordinary action would talk if it fired" % tag)
	_world.ui_tap_semantic("person:e17a:a")
	await process_frame
	assert_eq(_world.ui_semantic_focus(), "person:e17a:a", "%s: tap focuses Miner" % tag)
	assert_eq(_world.ui_actor_pos("john"), pos_before, "%s: tap does not move John" % tag)
	assert_true(not _world.ui_dialogue_open(), "%s: tap does not open DialogueBox" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), quest_before, "%s: tap does not advance the quest" % tag)
	assert_eq(str(_world.ui_semantic_labels()[0]["state"]), "LABEL", "%s: tap does not leave LABEL yet" % tag)
	_world.ui_clear_semantic_focus()
	assert_eq(_world.ui_semantic_focus(), "", "%s: focus can clear" % tag)
	_world.ui_tap_semantic("person:e17a:a")
	assert_eq(_world.ui_semantic_focus(), "person:e17a:a", "%s: a later tap focuses Miner again" % tag)


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func assert_eq(a, b, msg: String) -> void:
	if str(a) != str(b):
		_failures.append("%s expected %s got %s" % [msg, str(b), str(a)])


func _report() -> void:
	if _failures.is_empty():
		print("E17A SEMANTIC LABEL: ALL PASSED")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		print("E17A SEMANTIC LABEL: %d FAILED" % _failures.size())
		quit(1)

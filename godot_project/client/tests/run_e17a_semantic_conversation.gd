extends SceneTree

## WU-07: semantic NPC labels own ordinary conversation.
## Geometry and state only. Not visual acceptance.
## godot --headless --path godot_project --script res://client/tests/run_e17a_semantic_conversation.gd

const _VRunner = preload("res://client/scripts/village_test_runner.gd")

const MILLER := "person:e17a:g"
const MINER := "person:e17a:a"
const MILLER_LINES := [
	"Miner has announced being eighteen to everyone except the chickens.",
	"Miner's announcement is a scripted event in this grand play. Let the story unfold.",
	"The Seer raises an eyebrow at John's peculiar remark.",
]
const MINER_OPENING := "Miner asks Distiller to join the new workshop venture."
const BRANCH_B_LABEL := "The land doesn't need more workshops. It needs us to love each other."
const BRANCH_B_LINE := "Miner is moved by your connection to the earth and its wisdom."

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
	await _test_miller()
	await _test_miner_choice()
	_VRunner.end(_adv)
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


func _test_miller() -> void:
	var tag := "Miller ordinary speech"
	_place("g", Vector2i(0, 3))
	_world.ui_tap_semantic(MILLER)
	await process_frame
	var far := _entry(MILLER)
	assert_eq(str(far.get("state", "")), "OBSERVATION", "%s: distant tap is observation" % tag)
	assert_eq(str(far.get("text", "")), "A mill worker stands beside the mill road.", "%s: distant text is the authored observation" % tag)
	assert_true(not _world.ui_dialogue_open(), "%s: distant tap did not open DialogueBox" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_01_a", "%s: distant tap did not advance the quest" % tag)
	_world.ui_tap_semantic(MILLER)
	await process_frame
	assert_eq(str(_entry(MILLER).get("state", "")), "LABEL", "%s: tapping the observation returns the label" % tag)
	_place("g", Vector2i(0, 1))
	assert_true(not _world.ui_prompt_visible(), "%s: nearby semantic NPC does not show Talk" % tag)
	assert_true(not _world.ui_action_button_visible(), "%s: Action button stays hidden" % tag)
	var pos_before: Vector2i = _world.ui_actor_pos("john")
	_world.ui_tap_semantic(MILLER)
	await process_frame
	var speech := _entry(MILLER)
	assert_eq(str(speech.get("state", "")), "SPEECH", "%s: nearby tap starts speech" % tag)
	assert_eq(str(speech.get("text", "")), MILLER_LINES[0], "%s: first authored line" % tag)
	assert_eq(_world.ui_semantic_responses(MILLER).size(), 0, "%s: ordinary speech has no invented responses" % tag)
	assert_eq(_world.ui_actor_pos("john"), pos_before, "%s: speech tap did not move John" % tag)
	assert_true(not _world.ui_dialogue_open(), "%s: speech did not open DialogueBox" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_01_a", "%s: ordinary speech did not advance the quest" % tag)
	_world.ui_tap_semantic(MILLER)
	await process_frame
	assert_eq(str(_entry(MILLER).get("text", "")), MILLER_LINES[1], "%s: speech tap advances one line" % tag)
	assert_eq(_world.ui_semantic_responses(MILLER).size(), 0, "%s: advancing speech did not invent responses" % tag)
	_step_away()
	await process_frame
	assert_eq(str(_entry(MILLER).get("state", "")), "LABEL", "%s: walking away from speech returns the label" % tag)
	assert_eq(str(_entry(MILLER).get("text", "")), "Miller", "%s: collapsed label is Miller" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_01_a", "%s: walking away did not advance the quest" % tag)
	assert_true(not _world.ui_dialogue_open(), "%s: walking away did not open DialogueBox" % tag)
	_place("g", Vector2i(0, 1))
	_world.ui_tap_semantic(MILLER)
	await process_frame
	for line in MILLER_LINES:
		assert_eq(str(_entry(MILLER).get("state", "")), "SPEECH", "%s: line stays speech (%s)" % [tag, line])
		assert_eq(str(_entry(MILLER).get("text", "")), line, "%s: authored line in order" % tag)
		_world.ui_tap_semantic(MILLER)
		await process_frame
	assert_eq(str(_entry(MILLER).get("state", "")), "RESPONSES", "%s: finished opening offers topics" % tag)
	assert_true(_world.ui_semantic_responses(MILLER).size() >= 3, "%s: ordinary conversation has topic choices" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_01_a", "%s: topic menu did not advance the quest" % tag)


func _test_miner_choice() -> void:
	var tag := "Miner explicit choice"
	_place("a", Vector2i(0, 3))
	_world.ui_tap_semantic(MINER)
	await process_frame
	assert_eq(str(_entry(MINER).get("state", "")), "OBSERVATION", "%s: distant miner tap is observation" % tag)
	_world.ui_tap_semantic(MINER)
	await process_frame
	_place("a", Vector2i(0, 1))
	var pos_before: Vector2i = _world.ui_actor_pos("john")
	_world.ui_tap_semantic(MINER)
	await process_frame
	assert_eq(str(_entry(MINER).get("state", "")), "SPEECH", "%s: nearby tap starts speech without Talk" % tag)
	assert_eq(str(_entry(MINER).get("text", "")), MINER_OPENING, "%s: opening speech is the authored beat" % tag)
	assert_true(not _world.ui_prompt_visible(), "%s: Talk is not shown" % tag)
	assert_true(not _world.ui_action_button_visible(), "%s: Talk is not required" % tag)
	assert_true(not _world.ui_dialogue_open(), "%s: opening speech did not open DialogueBox" % tag)
	assert_eq(_world.ui_actor_pos("john"), pos_before, "%s: opening tap did not move John" % tag)
	_world.ui_tap_semantic(MINER)
	await process_frame
	var choices: Array = _world.ui_semantic_responses(MINER)
	assert_eq(str(_entry(MINER).get("state", "")), "RESPONSES", "%s: tapping speech opens responses" % tag)
	assert_true(choices.size() >= 2, "%s: more than one authored response" % tag)
	assert_eq(str(choices[1]), BRANCH_B_LABEL, "%s: second response is the authored branch" % tag)
	assert_eq(_world.ui_semantic_selected(MINER), -1, "%s: displaying responses does not select one" % tag)
	for _i in 8:
		await process_frame
	assert_eq(_world.ui_semantic_selected(MINER), -1, "%s: responses still waiting after several frames" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_01_a", "%s: waiting did not advance the quest" % tag)
	assert_true(not _VRunner.quest_state().get("flags", {}).has("scene_01_branch_a"), "%s: waiting did not commit branch A" % tag)
	assert_true(not _VRunner.quest_state().get("flags", {}).has("scene_01_branch_b"), "%s: waiting did not commit branch B" % tag)
	assert_true(not _world.ui_dialogue_open(), "%s: responses did not open DialogueBox" % tag)
	_step_away()
	await process_frame
	assert_eq(str(_entry(MINER).get("state", "")), "LABEL", "%s: walking away from responses restores the label" % tag)
	assert_eq(str(_entry(MINER).get("text", "")), "Miner", "%s: walked-away label is Miner" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_01_a", "%s: walking away chose nothing" % tag)
	assert_true(not _VRunner.quest_state().get("flags", {}).has("scene_01_branch_b"), "%s: dismissed responses committed nothing" % tag)
	_place("a", Vector2i(0, 1))
	_world.ui_tap_semantic(MINER)
	await process_frame
	_world.ui_tap_semantic(MINER)
	await process_frame
	assert_eq(str(_entry(MINER).get("state", "")), "RESPONSES", "%s: responses return without a choice" % tag)
	pos_before = _world.ui_actor_pos("john")
	_world.ui_tap_semantic_response(MINER, 1)
	await process_frame
	assert_eq(_world.ui_semantic_selected(MINER), 1, "%s: the tapped response is the one selected" % tag)
	assert_eq(_world.ui_actor_pos("john"), pos_before, "%s: response tap did not move John" % tag)
	assert_eq(str(_VRunner.quest_state().get("current_node", "")), "scene_02_b", "%s: quest advances only after the explicit choice" % tag)
	assert_true(_VRunner.quest_state().get("flags", {}).has("scene_01_branch_b"), "%s: the selected branch was committed" % tag)
	assert_true(not _VRunner.quest_state().get("flags", {}).has("scene_01_branch_a"), "%s: the other branch was not committed" % tag)
	await create_timer(0.45).timeout
	assert_eq(str(_entry(MINER).get("state", "")), "SPEECH", "%s: the chosen branch returns to speech" % tag)
	assert_eq(str(_entry(MINER).get("text", "")), BRANCH_B_LINE, "%s: branch speech is the authored response" % tag)
	assert_true(not _world.ui_dialogue_open(), "%s: branch speech did not open DialogueBox" % tag)


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
	_world._update_prompt()


func _step_away() -> void:
	for dir in [Vector2i(0, 1), Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1)]:
		var dest: Vector2i = _world.ui_actor_pos("john") + dir
		if _world.ui_tile_walkable(dest) and not _world.ui_is_exit(dest):
			_world.ui_step(dir)
			return


func _entry(key: String) -> Dictionary:
	for raw in _world.ui_semantic_labels():
		if str(raw.get("key", "")) == key:
			return raw
	return {}


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func assert_eq(a, b, msg: String) -> void:
	if str(a) != str(b):
		_failures.append("%s expected %s got %s" % [msg, str(b), str(a)])


func _report() -> void:
	if _failures.is_empty():
		print("E17A SEMANTIC CONVERSATION: ALL PASSED")
		quit(0)
	else:
		for f in _failures:
			print("FAIL: ", f)
		print("E17A SEMANTIC CONVERSATION: %d FAILED" % _failures.size())
		quit(1)

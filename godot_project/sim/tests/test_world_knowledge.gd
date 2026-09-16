extends DmbTestCase
## WU-01: persistent WorldKnowledge lives in Adventure.state["knowledge"].
## Learning is monotonic. Missing saves gain an empty bag. Village Test
## reset/exit restore the disposable-session snapshot, not session learning.

const _AdvScript = preload("res://client/scripts/adventure.gd")
const _Knowledge = preload("res://sim/world/world_knowledge.gd")
const _VRunner = preload("res://client/scripts/village_test_runner.gd")

const KEY_A := "person:e17a:a"
const KEY_B := "building:e17a:forge"


func _fresh() -> Node:
	var adv = _AdvScript.new()
	adv.new_game()
	return adv


func run() -> void:
	_test_unknown_is_zero()
	_test_learn_stores_and_upgrades()
	_test_learn_does_not_reduce()
	_test_keys_are_independent()
	_test_unchanged_learn_does_not_emit()
	_test_save_load_preserves_and_migrates()
	_test_village_test_reset_and_exit()


func _test_unknown_is_zero() -> void:
	var adv := _fresh()
	assert_true(adv.state.get("knowledge") is Dictionary, "new game initialises knowledge")
	assert_eq(_Knowledge.get_level(adv, KEY_A), 0, "unknown key is level 0")
	assert_true(not _Knowledge.knows(adv, KEY_A, 1), "unknown key is not known at 1")


func _test_learn_stores_and_upgrades() -> void:
	var adv := _fresh()
	assert_true(_Knowledge.learn(adv, KEY_A, 1), "learning 1 changes knowledge")
	assert_eq(_Knowledge.get_level(adv, KEY_A), 1, "level 1 stored")
	assert_true(_Knowledge.knows(adv, KEY_A, 1), "knows level 1")
	assert_true(_Knowledge.learn(adv, KEY_A, 2), "learning 2 upgrades")
	assert_eq(_Knowledge.get_level(adv, KEY_A), 2, "level 2 stored")
	assert_true(_Knowledge.knows(adv, KEY_A, 2), "knows level 2")
	assert_eq(int(adv.state["knowledge"][KEY_A]), 2, "canonical state holds the level")


func _test_learn_does_not_reduce() -> void:
	var adv := _fresh()
	_Knowledge.learn(adv, KEY_A, 2)
	assert_true(not _Knowledge.learn(adv, KEY_A, 1), "lower learn does not change")
	assert_eq(_Knowledge.get_level(adv, KEY_A), 2, "level stays 2")
	assert_true(not _Knowledge.learn(adv, KEY_A, 2), "equal learn does not change")
	assert_eq(_Knowledge.get_level(adv, KEY_A), 2, "equal learn keeps 2")


func _test_keys_are_independent() -> void:
	var adv := _fresh()
	_Knowledge.learn(adv, KEY_A, 2)
	_Knowledge.learn(adv, KEY_B, 1)
	assert_eq(_Knowledge.get_level(adv, KEY_A), 2, "first key unchanged")
	assert_eq(_Knowledge.get_level(adv, KEY_B), 1, "second key stored")
	assert_true(not _Knowledge.knows(adv, KEY_B, 2), "second key is not at level 2")


func _test_unchanged_learn_does_not_emit() -> void:
	var adv := _fresh()
	var emits := [0]
	adv.state_changed.connect(func(): emits[0] += 1)
	_Knowledge.learn(adv, KEY_A, 1)
	assert_eq(emits[0], 1, "raising knowledge emits once")
	_Knowledge.learn(adv, KEY_A, 1)
	_Knowledge.learn(adv, KEY_A, 0)
	assert_eq(emits[0], 1, "unchanged learn does not emit")
	_Knowledge.learn(adv, KEY_A, 2)
	assert_eq(emits[0], 2, "a real upgrade emits again")


func _test_save_load_preserves_and_migrates() -> void:
	var adv := _fresh()
	_Knowledge.learn(adv, KEY_A, 2)
	_Knowledge.learn(adv, KEY_B, 1)
	adv.save()
	var loaded = _AdvScript.new()
	assert_true(loaded.load_game(), "save with knowledge loads")
	assert_eq(_Knowledge.get_level(loaded, KEY_A), 2, "loaded level 2")
	assert_eq(_Knowledge.get_level(loaded, KEY_B), 1, "loaded independent key")

	adv.state.erase("knowledge")
	adv.save()
	var migrated = _AdvScript.new()
	assert_true(migrated.load_game(), "save without knowledge still loads")
	assert_true(migrated.state.get("knowledge") is Dictionary, "missing knowledge becomes a dictionary")
	assert_eq(migrated.state["knowledge"].size(), 0, "migrated knowledge is empty")
	assert_eq(_Knowledge.get_level(migrated, KEY_A), 0, "migrated save does not invent levels")
	adv.delete_save()


func _test_village_test_reset_and_exit() -> void:
	var adv := _fresh()
	_Knowledge.learn(adv, "person:campaign:keeper", 1)
	var campaign: Dictionary = (adv.state["knowledge"] as Dictionary).duplicate(true)
	_VRunner.set_profile("E36B")
	_VRunner.begin(adv)
	assert_true(_VRunner.is_active(), "village test session started")
	assert_true(_Knowledge.learn(adv, "person:campaign:keeper", 3), "session may raise knowledge")
	assert_true(_Knowledge.learn(adv, "person:session:note", 1), "session may learn a new key")
	assert_eq(_Knowledge.get_level(adv, "person:campaign:keeper"), 3, "session sees the raised level")
	_VRunner.reset(adv)
	assert_eq(_Knowledge.get_level(adv, "person:campaign:keeper"), 1, "reset restores the session baseline")
	assert_eq(_Knowledge.get_level(adv, "person:session:note"), 0, "reset drops session-only knowledge")
	assert_eq(adv.state["knowledge"], campaign, "reset knowledge matches the baseline bag")
	_Knowledge.learn(adv, "person:campaign:keeper", 4)
	_Knowledge.learn(adv, "person:session:note", 2)
	_VRunner.end(adv)
	assert_eq(adv.state["knowledge"], campaign, "exit restores campaign knowledge exactly")
	assert_eq(_Knowledge.get_level(adv, "person:campaign:keeper"), 1, "exit restores the campaign level")
	assert_eq(_Knowledge.get_level(adv, "person:session:note"), 0, "exit drops session-only knowledge")
	assert_true(not _VRunner.is_active(), "exit clears the test session")

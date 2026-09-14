extends DmbTestCase
## WU-02: generic semantic contract and a pure resolver.
## No rendering. No fixture-specific branches. Knowledge is read, never written.

const _AdvScript = preload("res://client/scripts/adventure.gd")
const _Resolver = preload("res://sim/world/world_interaction_resolver.gd")
const _Knowledge = preload("res://sim/world/world_knowledge.gd")

const KEY := "person:sample:worker"


func _fresh() -> Node:
	var adv = _AdvScript.new()
	adv.new_game()
	return adv


func _semantic() -> Dictionary:
	return {
		"knowledge_key": KEY,
		"labels": [
			{"level": 0, "text": "Stranger"},
			{"level": 1, "text": "Worker"},
			{"level": 3, "text": "Keeper"},
		],
		"observe_far": "A figure stands by the road.",
		"observe_near": "Dust covers the sleeves.",
		"interaction": "npc",
	}


func run() -> void:
	_test_level_zero_label()
	_test_intermediate_and_thresholds()
	_test_gaps_and_above_highest()
	_test_missing_observation_and_dismiss_default()
	_test_interaction_unchanged_and_no_mutation()
	_test_no_fixture_dependency()


func _test_level_zero_label() -> void:
	var adv := _fresh()
	var result: Dictionary = _Resolver.resolve(_semantic(), adv)
	assert_eq(result["label"], "Stranger", "level 0 uses the unknown label")


func _test_intermediate_and_thresholds() -> void:
	var adv := _fresh()
	_Knowledge.learn(adv, KEY, 1)
	assert_eq(_Resolver.resolve(_semantic(), adv)["label"], "Worker", "intermediate role label")
	_Knowledge.learn(adv, KEY, 3)
	assert_eq(_Resolver.resolve(_semantic(), adv)["label"], "Keeper", "highest reached threshold")


func _test_gaps_and_above_highest() -> void:
	var adv := _fresh()
	_Knowledge.learn(adv, KEY, 2)
	assert_eq(_Resolver.resolve(_semantic(), adv)["label"], "Worker", "gap uses the highest threshold at or below knowledge")
	_Knowledge.learn(adv, KEY, 9)
	assert_eq(_Resolver.resolve(_semantic(), adv)["label"], "Keeper", "above the highest label stays on that label")
	var high_only := {
		"knowledge_key": KEY,
		"labels": [
			{"level": 2, "text": "Named"},
			{"level": 4, "text": "Known"},
		],
	}
	var unknown := _fresh()
	assert_eq(_Resolver.resolve(high_only, unknown)["label"], "Named", "no qualifying threshold uses the lowest label")


func _test_missing_observation_and_dismiss_default() -> void:
	var adv := _fresh()
	var bare := {"knowledge_key": KEY, "labels": [{"level": 0, "text": "Thing"}], "interaction": "object"}
	var result: Dictionary = _Resolver.resolve(bare, adv)
	assert_eq(result["observe_far"], "", "missing far observation is empty")
	assert_eq(result["observe_near"], "", "missing near observation is empty")
	assert_true(bool(result["dismiss_on_move"]), "dismiss_on_move defaults to true")
	var held := _semantic()
	held["dismiss_on_move"] = false
	assert_true(not bool(_Resolver.resolve(held, adv)["dismiss_on_move"]), "explicit dismiss_on_move is kept")


func _test_interaction_unchanged_and_no_mutation() -> void:
	var adv := _fresh()
	_Knowledge.learn(adv, KEY, 1)
	adv.state["quest_probe"] = "scene_01"
	var before := var_to_str(adv.state)
	var result: Dictionary = _Resolver.resolve(_semantic(), adv)
	assert_eq(result["interaction"], "npc", "interaction type returned unchanged")
	assert_eq(var_to_str(adv.state), before, "resolve does not mutate knowledge or quest state")
	assert_eq(_Knowledge.get_level(adv, KEY), 1, "knowledge level unchanged")
	assert_eq(result["mode"], "observe", "out of range stays an observation")
	var near: Dictionary = _Resolver.resolve(_semantic(), adv, true)
	assert_eq(near["mode"], "interact", "an in-range NPC can be talked to")
	var object_near: Dictionary = _Resolver.resolve({"knowledge_key": KEY, "labels": [{"level": 0, "text": "Thing"}], "interaction": "object"}, adv, true)
	assert_eq(object_near["mode"], "interact", "in-range objects can be used")
	var object_far: Dictionary = _Resolver.resolve({"knowledge_key": KEY, "labels": [{"level": 0, "text": "Thing"}], "interaction": "object"}, adv, false)
	assert_eq(object_far["mode"], "observe", "out-of-range objects are observed")


func _test_no_fixture_dependency() -> void:
	var src := FileAccess.get_file_as_string("res://sim/world/world_interaction_resolver.gd")
	assert_true(not src.contains("E17A") and not src.contains("e17a"), "resolver has no E17A dependency")
	assert_true(not src.contains("Miner"), "resolver has no Miner-specific text")

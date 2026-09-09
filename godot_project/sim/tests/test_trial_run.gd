extends DmbTestCase
## Trial-attempt state: one attempt, no reset semantics. Start/resume, gems,
## conditions → duel-modifier mapping, discovery knowledge.
## See docs/CORRECTIVE_PASS_PLAN.md D6.

const _AdvScript = preload("res://client/scripts/adventure.gd")


func _fresh() -> Node:
	var adv = _AdvScript.new()
	adv.new_game()
	return adv


func run() -> void:
	_test_start_run()
	_test_resume_run()
	_test_knowledge()
	_test_condition_mods()


func _test_start_run() -> void:
	var adv := _fresh()
	adv.learn_spell(1)
	adv.grow_weave(1)
	adv.start_run()
	assert_true(adv.run_active(), "run active after start")
	assert_eq(str(adv.state.get("area", "")), "dd_entrance", "attempt starts at entrance")
	assert_true(adv.run_state().has("gems"), "run has gems")
	assert_true(adv.run_state().has("conditions"), "run has conditions")
	assert_true(adv.run_state().has("contestants"), "run has contestants")
	assert_eq(str(adv.run_state()["contestants"].get("throm", "")), "ahead", "Throm starts ahead")


func _test_resume_run() -> void:
	var adv := _fresh()
	adv.start_run()
	adv.set_location("dd_fork", 5, 5, "down")
	adv.save()
	var adv2 = _AdvScript.new()
	assert_true(adv2.load_game(), "reload with active run")
	assert_true(adv2.run_active(), "run still active after reload")
	assert_eq(str(adv2.state.get("area", "")), "dd_fork", "run position persists")


func _test_knowledge() -> void:
	var adv := _fresh()
	adv.start_run()
	assert_eq(adv.knowledge_status("dd_fork"), "unknown", "unseen area unknown")
	adv.mark_visited("dd_fork")
	assert_eq(adv.knowledge_status("dd_fork"), "seen", "visited area seen")
	assert_true("Footprint Fork" in adv.notebook_text(), "journal lists discovered ground")


func _test_condition_mods() -> void:
	var adv := _fresh()
	assert_eq(adv.player_mods(), {}, "no mods when healthy")
	adv.start_run()
	adv.add_condition("wounded")
	adv.add_condition("wounded")
	assert_eq(int(adv.player_mods().get("max_casts", -1)), 8, "two wounds −2 casts")
	adv.add_condition("wounded")
	adv.add_condition("wounded")
	adv.add_condition("wounded")
	assert_eq(int(adv.player_mods().get("max_casts", -1)), 6, "wounds floor at 6 casts")
	adv.clear_conditions()
	adv.add_condition("poisoned")
	assert_eq(int(adv.player_mods().get("min_cast_bonus", -1)), 2, "poison +2s min cast")
	adv.clear_conditions()
	adv.add_condition("slowed")
	assert_eq(int(adv.player_mods().get("max_cast_bonus", -1)), -10, "slowed −10s max window")

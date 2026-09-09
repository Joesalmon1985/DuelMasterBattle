extends DmbTestCase
## P2 run-state unit tests: start/fail/resume semantics, what a failed run keeps
## vs resets, v1 → v2 save migration, and condition → duel-modifier mapping.
## See docs/DEATHTRAP_OVERHAUL_PLAN.md P2 and DD/ report §13.

const _AdvScript = preload("res://client/scripts/adventure.gd")


func _fresh() -> Node:
	var adv = _AdvScript.new()
	adv.new_game()
	return adv


func run() -> void:
	_test_start_run()
	_test_fail_run_resets_run_state()
	_test_fail_run_keeps_permanent_stuff()
	_test_resume_run()
	_test_v1_migration()
	_test_condition_mods()


func _test_start_run() -> void:
	var adv := _fresh()
	adv.learn_spell(1)
	adv.grow_weave(1)
	adv.start_run()
	assert_true(adv.run_active(), "run active after start")
	assert_eq(str(adv.run_state().get("area", "")), "dd_entrance", "run starts at entrance")
	assert_true(adv.run_state().has("gems"), "run has gems")
	assert_true(adv.run_state().has("conditions"), "run has conditions")
	assert_true(adv.run_state().has("contestants"), "run has contestants")
	assert_eq(str(adv.run_state()["contestants"].get("throm", "")), "ahead", "Throm starts ahead")


func _test_fail_run_resets_run_state() -> void:
	var adv := _fresh()
	adv.start_run()
	adv.add_gem("emerald")
	adv.add_condition("wounded")
	adv.set_contestant("throm", "met")
	adv.set_run_flag("pit_crossed")
	adv.mark_visited("dd_fork")
	adv.fail_run("troll")
	assert_true(not adv.run_active(), "run inactive after fail")
	assert_eq(adv.run_state().get("gems", ["x"]), [], "gems reset on fail")
	assert_eq(adv.run_state().get("conditions", ["x"]), [], "conditions reset on fail")
	assert_eq(adv.run_state().get("flags", {"x": 1}), {}, "run flags reset on fail")
	assert_eq(str(adv.run_state()["contestants"].get("throm", "")), "ahead", "contestants reset on fail")
	assert_eq(str(adv.state.get("area", "")), "trial_gate", "fail restarts at the gate")


func _test_fail_run_keeps_permanent_stuff() -> void:
	var adv := _fresh()
	adv.learn_spell(1)
	adv.grow_weave(1)
	adv.start_run()
	adv.mark_visited("dd_fork")
	adv.set_flag("entered_trial")
	adv.fail_run("troll")
	assert_true(adv.progression.knows(1), "spells survive fail")
	assert_eq(adv.progression.weave_size, 1, "weave survives fail")
	assert_true(adv.flag("entered_trial"), "world flags survive fail")
	assert_eq(str(adv.knowledge_status("dd_fork")), "entered", "visited area remembered")


func _test_resume_run() -> void:
	var adv := _fresh()
	adv.start_run()
	adv.set_location("dd_fork", 5, 5, "down")
	adv.save()
	var adv2 = _AdvScript.new()
	assert_true(adv2.load_game(), "reload with active run")
	assert_true(adv2.run_active(), "run still active after reload")
	assert_eq(str(adv2.state.get("area", "")), "dd_fork", "run position persists")


func _test_v1_migration() -> void:
	var adv := _fresh()
	# Simulate a v1 save payload (no run, no knowledge).
	adv.state.erase("run")
	adv.state.erase("dungeon_knowledge")
	adv.state["version"] = 1
	adv.save()
	var adv2 = _AdvScript.new()
	assert_true(adv2.load_game(), "v1 save loads")
	assert_eq(int(adv2.state.get("version", 0)), 2, "migrated to v2")
	assert_true(adv2.state.has("run"), "run key exists after migration")
	assert_true(adv2.state.has("dungeon_knowledge"), "knowledge key exists after migration")
	assert_true(not adv2.run_active(), "no active run after migration")


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

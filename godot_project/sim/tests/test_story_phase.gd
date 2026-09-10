extends DmbTestCase
## P0 corrective pass: authoritative story state machine, save v3 invalidation,
## trial_ready(), battle-result policy categories, defeat counters and the
## deterministic every-third-battle encounter sequence.
## See docs/CORRECTIVE_PASS_PLAN.md Phase 0.

const _AdvScript = preload("res://client/scripts/adventure.gd")


func _fresh() -> Node:
	var adv = _AdvScript.new()
	adv.new_game()
	return adv


func run() -> void:
	_test_new_game_phase()
	_test_phase_transitions()
	_test_save_v2_invalidated()
	_test_trial_ready()
	_test_battle_policy()
	_test_defeat_counters()
	_test_encounter_sequence()
	_test_fail_run_no_teleport()


func _test_new_game_phase() -> void:
	var adv := _fresh()
	assert_eq(adv.story_phase(), "halvard_prologue", "new game starts in the prologue")
	assert_eq(adv.protagonist(), "halvard", "player controls Halvard first")
	assert_eq(int(adv.state.get("version", 0)), 4, "save v4")


func _test_phase_transitions() -> void:
	var adv := _fresh()
	assert_true(adv.advance_phase("john_intro"), "prologue -> john_intro")
	assert_eq(adv.protagonist(), "john", "John after the pivot")
	assert_true(not adv.advance_phase("halvard_prologue"), "cannot go back to the prologue")
	assert_true(not adv.advance_phase("trial"), "cannot skip to the Trial from john_intro")
	assert_true(adv.advance_phase("ashby_training"), "john_intro -> ashby_training")
	assert_true(adv.advance_phase("pre_trial"), "ashby_training -> pre_trial")
	assert_true(adv.advance_phase("trial"), "pre_trial -> trial")
	assert_true(adv.advance_phase("post_trial_recovery"), "trial -> post_trial_recovery")
	assert_true(not adv.advance_phase("nonsense"), "unknown phase rejected")


func _test_save_v2_invalidated() -> void:
	var adv := _fresh()
	adv.state["version"] = 2
	adv.state.erase("story")
	adv.save()
	var adv2 = _AdvScript.new()
	assert_true(not adv2.load_game(), "v2 save refuses to load")
	assert_true(not adv2.has_save(), "stale save deleted")


func _test_trial_ready() -> void:
	var adv := _fresh()
	assert_true(not adv.trial_ready(), "nothing known: not ready")
	adv.set_flag("has_staff")
	adv.learn_spell(1)
	adv.grow_weave(1)
	assert_true(not adv.trial_ready(), "Water + weave 1: not ready")
	adv.learn_spell(6)
	adv.learn_spell(0)
	adv.grow_weave(3)
	assert_true(not adv.trial_ready(), "three spells + weave 3: not ready")
	adv.learn_spell(3)
	assert_true(adv.trial_ready(), "four spells + weave 3 + staff: ready")
	var adv2 := _fresh()
	adv2.set_flag("has_staff")
	for s in [1, 6, 0, 3]:
		adv2.learn_spell(s)
	adv2.grow_weave(2)
	assert_true(not adv2.trial_ready(), "four spells + weave 2: not ready")


func _test_battle_policy() -> void:
	var adv := _fresh()
	assert_eq(adv.battle_policy_for({"policy": "PROLOGUE_FORCED_DEFEAT"}), "PROLOGUE_FORCED_DEFEAT", "explicit policy wins")
	assert_eq(adv.battle_policy_for({"training": true}), "TRAINING_CONTINUE", "training request")
	adv.advance_phase("john_intro")
	adv.advance_phase("ashby_training")
	adv.advance_phase("pre_trial")
	assert_eq(adv.battle_policy_for({"enemy_id": "flame_imp"}), "STORY_DEFEAT_TRANSITION", "post-training story battle")
	adv.advance_phase("trial")
	assert_eq(adv.battle_policy_for({"enemy_id": "cave_troll"}), "STORY_DEFEAT_TRANSITION", "trial battle uses story defeat policy")
	assert_eq(adv.battle_policy_for({}), "STORY_DEFEAT_TRANSITION", "empty request in trial")
	var quick = _AdvScript.new()
	assert_eq(quick.battle_policy_for({}), "QUICK_DUEL", "no active adventure -> quick duel")


func _test_defeat_counters() -> void:
	var adv := _fresh()
	adv.advance_phase("john_intro")
	adv.advance_phase("ashby_training")
	adv.advance_phase("pre_trial")
	adv.learn_spell(1)
	adv.learn_spell(6)
	adv.grow_weave(2)
	# Two colours: the forest is a school. Defeats do not count towards Jane.
	assert_eq(adv.record_story_defeat(), "wait", "two-colour defeat waits")
	assert_eq(adv.record_story_defeat(), "wait", "still waits")
	assert_eq(int(adv.state["story"]["story_defeats"]), 0, "no story defeats recorded before the third colour")
	assert_true(not adv.left_for_dead_used(), "wake not spent")
	adv.learn_spell(0)
	adv.grow_weave(3)
	assert_eq(adv.record_story_defeat(), "left_for_dead", "first real defeat: left for dead")
	assert_true(adv.left_for_dead_used(), "wake used")
	assert_true(not adv.post_trial_recovery_pending(), "not yet Jane")
	assert_eq(adv.record_story_defeat(), "recovery", "second real defeat: recovery")
	assert_true(adv.post_trial_recovery_pending(), "Jane pending")
	assert_eq(adv.story_phase(), "post_trial_recovery", "phase moves to recovery")
	# Never reached the Trial: still allowed (brief: regardless of the Trial).
	var adv2 := _fresh()
	adv2.advance_phase("john_intro")
	adv2.advance_phase("ashby_training")
	adv2.learn_spell(1)
	adv2.learn_spell(6)
	adv2.learn_spell(0)
	adv2.grow_weave(3)
	adv2.record_story_defeat()
	assert_eq(adv2.record_story_defeat(), "recovery", "second defeat during training-phase also goes to Jane")
	assert_eq(adv2.story_phase(), "post_trial_recovery", "phase jumps straight from ashby_training")
	# Inventory: eight meaningful items, no duplicates, no equipment.
	assert_true(adv2.add_item("iron_key"), "add item")
	assert_true(not adv2.add_item("iron_key"), "no duplicate")
	assert_true(not adv2.add_item("sword_of_doom"), "unknown item refused")
	for i in range(7):
		adv2.add_item("cure_fragment_%d" % i)
	assert_eq(adv2.items().size(), 8, "eight slots")
	assert_true(adv2.inventory_full(), "full")
	assert_true(not adv2.add_item("black_seed"), "ninth refused")
	assert_true(adv2.remove_item("iron_key"), "remove")
	assert_true(adv2.add_item("black_seed"), "slot freed")
	adv2.set_puzzle_state("tower_1/p0", {"solved": true})
	adv2.set_quest_outcome(4, "out_truth")
	adv2.save()
	var adv3 = _AdvScript.new()
	assert_true(adv3.load_game(), "reload")
	assert_eq(adv3.items(), adv2.items(), "items persist")
	assert_true(bool(adv3.puzzle_state("tower_1/p0").get("solved", false)), "puzzle state persists")
	assert_eq(adv3.quest_outcome(4), "out_truth", "quest outcome persists")
	assert_eq(adv3.dungeon_solved_count("tower_1"), 1, "solved count")


func _test_encounter_sequence() -> void:
	var adv := _fresh()
	adv.advance_phase("john_intro")
	adv.advance_phase("ashby_training")
	assert_eq(adv.begin_encounter("ashby_duel1"), 1, "first John battle is #1")
	assert_eq(adv.begin_encounter("ashby_duel2"), 2, "second is #2")
	assert_eq(adv.begin_encounter("ashby_duel3"), 3, "third is #3")
	assert_true(adv.is_optimal_encounter("ashby_duel3"), "#3 is the optimal-tier battle")
	assert_eq(adv.begin_encounter("ashby_duel3"), 3, "retrying keeps its number")
	assert_eq(adv.begin_encounter("fly_road1"), 4, "next new encounter is #4")
	assert_true(not adv.is_optimal_encounter("fly_road1"), "#4 not optimal")
	adv.begin_encounter("imp_d1")
	assert_eq(adv.begin_encounter("imp_d2"), 6, "#6")
	assert_true(adv.is_optimal_encounter("imp_d2"), "#6 optimal")
	var adv2 := _fresh()
	assert_eq(adv2.begin_encounter("halvard_vs_red"), 0, "prologue battle does not count")
	assert_true(not adv2.is_optimal_encounter("halvard_vs_red"), "prologue never optimal")


func _test_fail_run_no_teleport() -> void:
	var adv := _fresh()
	adv.advance_phase("john_intro")
	adv.advance_phase("ashby_training")
	adv.advance_phase("pre_trial")
	adv.advance_phase("trial")
	adv.start_run()
	adv.set_location("dd_lower", 5, 5, "left")
	adv.add_gem("emerald")
	adv.mark("defeated", "troll_lower1")
	adv.record_story_defeat()
	assert_eq(str(adv.state.get("area", "")), "dd_lower", "no teleport to the gate on defeat")
	assert_true(adv.run_active(), "the single Trial attempt continues")
	assert_true(adv.has_gem("emerald"), "gems kept")
	assert_true(adv.marked("defeated", "troll_lower1"), "fights are not reset")
	assert_true(not adv.has_method("fail_run"), "retry plumbing removed")

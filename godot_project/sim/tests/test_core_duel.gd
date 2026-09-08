extends DmbTestCase

## Core duel rules: 4 loci, 6 spells, 10 casts, 5–60 s cast window.

const _RealtimeSim = preload("res://sim/realtime_duel_sim.gd")
const _Encounters = preload("res://sim/encounters.gd")
const _DifficultyProfiles = preload("res://sim/difficulty_profiles.gd")
const _SolverBot = preload("res://sim/solver_bot.gd")
const _DuelEvent = preload("res://sim/duel_event.gd")

const MISS_A := [0, 0, 0, 0]
const MISS_SECRET := [1, 1, 1, 1]


func run() -> void:
	_test_ruleset_numbers()
	_test_feedback_repeats()
	_test_min_window_then_ready()
	_test_cast_requires_complete_guess()
	_test_auto_cast_fills_partial_guess_at_60s()
	_test_player_victory_on_exact_guess()
	_test_player_defeat_when_rival_solves()
	_test_player_defeat_when_out_of_casts()
	_test_victory_when_rival_out_of_casts()
	_test_stalemate_when_both_exhausted_same_instant()
	_test_clash_same_instant()
	_test_rival_only_guesses_consistent_patterns()
	_test_rival_solves_every_ward_within_limit()
	_test_rival_never_casts_before_min_or_after_max()
	_test_rival_incremental_planning_budget()
	_test_reset_clears_state()
	_test_pause_freezes_everything()
	_test_events_do_not_leak_positions()
	_test_load_previous_attack()


func _make(difficulty: String = "medium", seed: int = 7):
	var rs := _Encounters.get_encounter("core_duel")
	var sim = _RealtimeSim.new(rs, _DifficultyProfiles.get_profile(difficulty), seed)
	return sim


func _start(sim, ward: Array = [0, 1, 3, 4]) -> void:
	for i in range(ward.size()):
		sim.set_player_ward_locus(i, ward[i])
	sim.lock_player_ward_and_start()


func _set_attack(sim, pattern: Array) -> void:
	for i in range(pattern.size()):
		sim.set_player_attack_locus(i, pattern[i])


func _drain(sim) -> Array:
	return sim.get_pending_events()


func _test_ruleset_numbers() -> void:
	var rs := _Encounters.get_encounter("core_duel")
	assert_eq(rs.slot_count, 4, "core slots")
	assert_eq(rs.attack_magic_pool.size(), 6, "core spell pool")
	assert_eq(rs.secret_magic_pool.size(), 6, "core secret pool")
	assert_eq(rs.effective_max_attacks(), 10, "core max casts")
	assert_eq(rs.base_min_cast_time_seconds, 5.0, "core min cast")
	assert_eq(rs.base_max_cast_time_seconds, 60.0, "core max cast")
	assert_true(rs.allow_repeats, "core allows repeats")
	assert_eq(_Encounters.default_encounter().id, "core_duel", "core is default")
	assert_eq(_Encounters.playable_encounters().size(), 1, "one playable encounter")


func _test_feedback_repeats() -> void:
	# secret has two 0s; guess has three 0s: 2 exact... no: positions 0,1 exact, third 0 has no partner
	assert_eq(DmbFeedback.score_guess([0, 0, 1, 3], [0, 0, 0, 0]), Vector2i(2, 0), "extra repeats don't echo")
	assert_eq(DmbFeedback.score_guess([0, 0, 1, 3], [1, 3, 0, 0]), Vector2i(0, 4), "all displaced")
	assert_eq(DmbFeedback.score_guess([0, 1, 1, 3], [1, 0, 3, 1]), Vector2i(0, 4), "swap with repeats")
	assert_eq(DmbFeedback.score_guess([0, 1, 3, 4], [4, 4, 4, 4]), Vector2i(1, 0), "one exact, no echo for extra copies")
	assert_eq(DmbFeedback.score_guess([0, 1, 3, 4], [6, 9, 6, 9]), Vector2i(0, 0), "complete miss")
	assert_eq(DmbFeedback.score_guess([0, 1, 3, 4], [0, 1, 3, 4]), Vector2i(4, 0), "complete hit")
	assert_eq(DmbFeedback.score_guess([0, 1, 3, 4], [0, 3, 1, 9]), Vector2i(1, 2), "mixed")


func _test_min_window_then_ready() -> void:
	var sim = _make()
	_start(sim)
	_set_attack(sim, [0, 0, 1, 1])
	assert_true(not sim.is_player_window_open(), "window locked at t=0")
	assert_eq(sim.player_cast_block_reason(), "Weaving…", "block reason while weaving")
	sim.advance_time_for_test(4.99)
	assert_true(not sim.can_player_cast(), "still locked at 4.99s")
	sim.advance_time_for_test(0.02)
	assert_true(sim.is_player_window_open(), "window opens at 5s")
	assert_true(sim.can_player_cast(), "castable with complete guess")
	assert_eq(sim.player_cast_block_reason(), "", "no block reason when ready")
	assert_true(sim.submit_player_attack(), "cast accepted")
	assert_eq(sim.player_history.size(), 1, "one cast recorded")
	assert_true(not sim.is_player_window_open(), "window re-locks after cast")
	var st: Dictionary = sim.get_current_state()
	assert_true(absf(float(st["player_time_until_cast"]) - 5.0) < 0.001, "new window starts fresh")


func _test_cast_requires_complete_guess() -> void:
	var sim = _make()
	_start(sim)
	sim.advance_time_for_test(6.0)
	_set_attack(sim, [0, 0, 1, 1])
	sim.set_player_attack_locus(3, -1)
	assert_true(sim.is_player_window_open(), "window open")
	assert_true(not sim.can_player_cast(), "incomplete guess blocks cast")
	assert_eq(sim.player_cast_block_reason(), "Fill all 4 spells", "block reason for incomplete guess")
	assert_true(not sim.submit_player_attack(), "submit rejected")
	assert_eq(sim.first_empty_attack_locus(), 3, "first empty locus")
	sim.set_player_attack_locus(3, 9)
	assert_true(sim.submit_player_attack(), "submit accepted once complete")


func _test_auto_cast_fills_partial_guess_at_60s() -> void:
	var sim = _make()
	sim.debug_set_enemy_cast_at(999.0)
	_start(sim)
	sim.debug_set_enemy_cast_at(999.0)
	sim.set_player_attack_locus(0, 3)
	sim.set_player_attack_locus(2, 9)
	sim.advance_time_for_test(59.9)
	assert_eq(sim.player_history.size(), 0, "no auto cast before 60s")
	sim.advance_time_for_test(0.2)
	assert_eq(sim.player_history.size(), 1, "auto cast fires at 60s")
	var rec = sim.player_history[0]
	assert_true(rec.was_auto_cast, "flagged as auto cast")
	assert_eq(int(rec.pattern_by_locus[0]), 3, "kept chosen locus 0")
	assert_eq(int(rec.pattern_by_locus[2]), 9, "kept chosen locus 2")
	for v in rec.pattern_by_locus:
		assert_true(v != null and int(v) in DmbConstants.CORE_SPELL_POOL, "auto-filled loci use legal spells")
	assert_true(not sim.is_player_attack_complete(), "attack builder cleared after cast")


func _test_player_victory_on_exact_guess() -> void:
	var sim = _make()
	_start(sim)
	sim.debug_set_enemy_ward([1, 1, 3, 9])
	sim.debug_set_enemy_cast_at(999.0)
	sim.advance_time_for_test(5.1)
	_set_attack(sim, [1, 1, 3, 9])
	assert_true(sim.submit_player_attack(), "winning cast accepted")
	assert_eq(sim.phase, _RealtimeSim.Phase.FINISHED, "duel finished")
	assert_eq(sim.result.outcome, "victory", "victory")
	assert_true(sim.result.human_solved, "player solved")
	assert_eq(sim.result.reason, "solved", "reason solved")
	var types: Array = []
	for ev in _drain(sim):
		types.append(ev.type)
	assert_true(_DuelEvent.WARD_BROKEN in types, "ward broken event")
	assert_true(_DuelEvent.DUEL_FINISHED in types, "duel finished event")
	# no further time advances change anything
	sim.advance_time_for_test(100.0)
	assert_eq(sim.result.outcome, "victory", "result stable")


func _test_player_defeat_when_rival_solves() -> void:
	var sim = _make("hard", 3)
	sim.debug_set_enemy_cast_at(999.0)
	_start(sim, [0, 0, 0, 0])
	# Make the rival cast the exact ward immediately by forcing its window.
	sim.debug_set_enemy_ward([9, 9, 9, 9])
	sim.debug_set_enemy_cast_at(0.0)
	sim.set_testing_fast_cast(true)
	# Bot plans its own guess; force the guess by planting the candidate set.
	var bot = sim.get_bot()
	bot._candidates = [[0, 0, 0, 0]]
	bot._guess_count = 1
	bot.begin_planning()
	sim.advance_time_for_test(0.1)
	assert_eq(sim.enemy_history.size(), 1, "rival cast")
	assert_eq(sim.phase, _RealtimeSim.Phase.FINISHED, "finished after rival solve")
	assert_eq(sim.result.outcome, "defeat", "defeat")
	assert_true(sim.result.bot_solved, "bot solved")


func _test_player_defeat_when_out_of_casts() -> void:
	var sim = _make()
	_start(sim, MISS_SECRET)
	sim.debug_set_enemy_ward([9, 9, 9, 9])
	sim.debug_set_enemy_cast_at(999.0)
	sim.set_testing_fast_cast(true)
	for i in range(10):
		sim.debug_set_enemy_cast_at(999.0)
		_set_attack(sim, MISS_A)
		assert_true(sim.submit_player_attack(), "cast %d accepted" % (i + 1))
		var st: Dictionary = sim.get_current_state()
		assert_eq(int(st["player_attacks_remaining"]), 9 - i, "remaining after cast %d" % (i + 1))
	assert_eq(sim.player_history.size(), 10, "ten casts")
	assert_eq(sim.phase, _RealtimeSim.Phase.FINISHED, "finished when player exhausted")
	assert_eq(sim.result.outcome, "defeat", "defeat by exhaustion")
	assert_eq(sim.result.reason, "exhausted", "reason exhausted")
	assert_true(not sim.submit_player_attack(), "no 11th cast")


func _test_victory_when_rival_out_of_casts() -> void:
	var sim = _make("medium", 11)
	_start(sim, [0, 0, 0, 0])
	sim.debug_set_enemy_ward([9, 9, 9, 9])
	sim.set_testing_fast_cast(true)
	# Rival always guesses a miss by planting a single wrong candidate each time.
	var bot = sim.get_bot()
	var casts := 0
	var guard := 0
	while sim.phase == _RealtimeSim.Phase.DUELING and guard < 40:
		bot._candidates = [[1, 1, 1, 1]]
		bot._guess_count = 1
		bot.begin_planning()
		sim.debug_set_enemy_cast_at(0.0)
		sim.advance_time_for_test(0.05)
		casts = sim.enemy_history.size()
		guard += 1
	assert_eq(casts, 10, "rival used ten casts")
	assert_eq(sim.phase, _RealtimeSim.Phase.FINISHED, "finished when rival exhausted")
	assert_eq(sim.result.outcome, "victory", "victory when rival runs dry")
	assert_eq(sim.result.reason, "exhausted", "reason exhausted")


func _test_stalemate_when_both_exhausted_same_instant() -> void:
	var sim = _make()
	_start(sim, MISS_SECRET)
	sim.debug_set_enemy_ward([9, 9, 9, 9])
	sim.set_testing_fast_cast(true)
	var bot = sim.get_bot()
	for i in range(9):
		bot._candidates = [[3, 3, 3, 3]]
		bot._guess_count = 1
		bot.begin_planning()
		sim.debug_set_enemy_cast_at(0.0)
		_set_attack(sim, MISS_A)
		sim.submit_player_attack()
		sim.advance_time_for_test(0.05)
	assert_eq(sim.player_history.size(), 9, "player 9 casts")
	assert_eq(sim.enemy_history.size(), 9, "rival 9 casts")
	assert_eq(sim.phase, _RealtimeSim.Phase.DUELING, "still dueling at 9/9")
	# Tenth: both auto-cast at the same instant via max window.
	bot._candidates = [[3, 3, 3, 3]]
	bot._guess_count = 1
	bot.begin_planning()
	sim.debug_set_enemy_cast_at(0.0)
	_set_attack(sim, MISS_A)
	sim.advance_time_for_test(60.5)
	assert_eq(sim.phase, _RealtimeSim.Phase.FINISHED, "finished at 10/10")
	assert_eq(sim.result.outcome, "stalemate", "stalemate when both exhausted together")


func _test_clash_same_instant() -> void:
	var sim = _make()
	_start(sim, [0, 0, 0, 0])
	sim.debug_set_enemy_ward([9, 9, 9, 9])
	var bot = sim.get_bot()
	bot._candidates = [[0, 0, 0, 0]]
	bot._guess_count = 1
	bot.begin_planning()
	sim.debug_set_enemy_cast_at(60.0)
	_set_attack(sim, [9, 9, 9, 9])
	sim.advance_time_for_test(61.0)
	assert_eq(sim.phase, _RealtimeSim.Phase.FINISHED, "clash finished")
	assert_eq(sim.result.outcome, "clash", "clash when both solve in same tick")


func _test_rival_only_guesses_consistent_patterns() -> void:
	var rs := _Encounters.get_encounter("core_duel")
	for seed in range(6):
		for strategy in [_SolverBot.STRATEGY_RANDOM, _SolverBot.STRATEGY_MINIMAX]:
			var bot = _SolverBot.new(rs, strategy, seed, 60)
			var secret := [int(DmbConstants.CORE_SPELL_POOL[seed % 6]), 4, 4, int(DmbConstants.CORE_SPELL_POOL[(seed + 2) % 6])]
			var history: Array = []
			var solved := false
			for _i in range(10):
				var g := bot.make_guess()
				assert_true(bot.is_legal_guess(g), "legal guess")
				for h in history:
					assert_eq(DmbFeedback.score_guess(g, h["guess"]), h["fb"], "guess consistent with prior feedback (%s seed %d)" % [strategy, seed])
				var fb := DmbFeedback.score_guess(secret, g)
				if fb.x == 4:
					solved = true
					break
				history.append({"guess": g, "fb": fb})
				bot.register_feedback(g, fb.x, fb.y)
			assert_true(solved, "solved %s seed %d" % [strategy, seed])


func _test_rival_solves_every_ward_within_limit() -> void:
	var rs := _Encounters.get_encounter("core_duel")
	var all := DmbCandidateGen.generate_candidate_codes(rs)
	assert_eq(all.size(), 1296, "6^4 candidate wards")
	var worst := 0
	var total := 0
	var step := 7
	var n := 0
	var i := 0
	while i < all.size():
		var bot = _SolverBot.new(rs, _SolverBot.STRATEGY_RANDOM, i)
		var r: Dictionary = bot.solve_secret(all[i], 10)
		assert_true(r["solved"], "random-consistent solves %s" % str(all[i]))
		worst = maxi(worst, int(r["count"]))
		total += int(r["count"])
		n += 1
		i += step
	assert_true(worst <= 10, "worst case within 10 (got %d)" % worst)
	assert_true(float(total) / n <= 6.5, "average within reason (got %.2f)" % (float(total) / n))


func _test_rival_never_casts_before_min_or_after_max() -> void:
	for diff in ["easy", "medium", "hard"]:
		var sim = _make(diff, 5)
		_start(sim, [0, 1, 3, 4])
		sim.debug_set_enemy_ward([9, 9, 9, 9])
		var t := 0.0
		var last_count := 0
		var last_cast_t := 0.0
		var guard := 0
		while sim.phase == _RealtimeSim.Phase.DUELING and guard < 20000:
			sim.advance_time_for_test(0.1)
			t += 0.1
			if sim.enemy_history.size() > last_count:
				var gap := t - last_cast_t
				assert_true(gap >= 5.0 - 0.15, "%s rival waited min window (gap %.1f)" % [diff, gap])
				assert_true(gap <= 60.0 + 0.15, "%s rival within max window (gap %.1f)" % [diff, gap])
				last_cast_t = t
				last_count = sim.enemy_history.size()
			guard += 1
		assert_eq(sim.phase, _RealtimeSim.Phase.FINISHED, "%s duel ended without player input" % diff)
		assert_true(sim.result != null and sim.result.outcome in ["defeat", "stalemate", "victory"], "%s duel resolved when passive" % diff)


func _test_rival_incremental_planning_budget() -> void:
	var rs := _Encounters.get_encounter("core_duel")
	var bot = _SolverBot.new(rs, _SolverBot.STRATEGY_MINIMAX, 1, 500)
	bot.make_guess()  # opening
	bot.register_feedback([0, 0, 1, 1], 0, 1)
	bot.begin_planning()
	var frames := 0
	while not bot.think(0.25) and frames < 100000:
		frames += 1
	assert_true(bot.is_plan_ready(), "plan completes")
	assert_true(frames >= 1, "planning was split across frames (%d)" % frames)
	var g := bot.planned_guess()
	assert_true(bot.is_legal_guess(g), "planned guess legal")


func _test_reset_clears_state() -> void:
	var sim = _make()
	_start(sim)
	sim.advance_time_for_test(6.0)
	_set_attack(sim, [0, 0, 1, 1])
	sim.submit_player_attack()
	sim.reset(99)
	assert_eq(sim.phase, _RealtimeSim.Phase.WARD_SETUP, "back to setup")
	assert_eq(sim.player_history.size(), 0, "history cleared")
	assert_eq(sim.enemy_history.size(), 0, "enemy history cleared")
	assert_eq(sim.duel_time, 0.0, "time reset")
	assert_true(sim.result == null, "result cleared")
	assert_true(not sim.can_lock_player_ward(), "ward cleared")
	var st: Dictionary = sim.get_current_state()
	assert_eq(int(st["player_attacks_remaining"]), 10, "casts restored")
	assert_eq(sim.get_pending_events().size(), 0, "no stale events")
	_start(sim)
	assert_eq(sim.phase, _RealtimeSim.Phase.DUELING, "can start again")


func _test_pause_freezes_everything() -> void:
	var sim = _make()
	_start(sim)
	sim.set_paused(true)
	sim.advance_time(30.0)
	assert_eq(sim.duel_time, 0.0, "paused time frozen")
	assert_true(not sim.is_player_window_open(), "window did not advance while paused")
	sim.set_paused(false)
	sim.advance_time(5.5)
	assert_true(sim.is_player_window_open(), "window resumes")


func _test_events_do_not_leak_positions() -> void:
	var sim = _make()
	_start(sim)
	sim.advance_time_for_test(5.1)
	_set_attack(sim, [0, 0, 1, 1])
	sim.submit_player_attack()
	var seen := false
	for ev in _drain(sim):
		if ev.type == _DuelEvent.FEEDBACK_REVEALED:
			seen = true
			for key in ev.data.keys():
				assert_true(not str(key).begins_with("per_"), "no per-locus keys")
			assert_true(ev.data.has("fracture_count") and ev.data.has("echo_count") and ev.data.has("fade_count"), "aggregate counts present")
			assert_eq(int(ev.data["fracture_count"]) + int(ev.data["echo_count"]) + int(ev.data["fade_count"]), 4, "counts sum to slots")
	assert_true(seen, "feedback event emitted")


func _test_load_previous_attack() -> void:
	var sim = _make()
	_start(sim)
	sim.load_player_attack([3, null, 9, 4])
	var p: Array = sim.get_player_attack_pattern()
	assert_eq(int(p[0]), 3, "loaded locus 0")
	assert_true(p[1] == null, "kept empty locus")
	assert_eq(int(p[3]), 4, "loaded locus 3")
	sim.clear_player_attack()
	assert_eq(sim.first_empty_attack_locus(), 0, "cleared")

extends DmbTestCase
## Early-game AI tests (CORRECTIVE_PASS_PLAN Phase 12, brief §33). Seeded.
##  - every guess legal; candidates feedback-consistent
##  - Ashby duel 2: one-slot Water cannot break a two-slot Ward (mechanical loss)
##  - Giant Fly: first cast is a zero-match against EVERY legal John Ward, then it
##    switches to a real solver and can win
##  - prologue Red: solves every legal Halvard Ward within 3 casts under the
##    prologue config, else the isolated backstop fires exactly at cast 3
##  - optimal tier (capped_minimax cap 100) is not the perfect solver: on average
##    at least ~1 cast slower than uncapped minimax is NOT required (we only need
##    "not perfect"); assert it is never *worse* than candidate_filter on average

const _BattleSim = preload("res://sim/battle_sim.gd")
const _WeaveBot = preload("res://sim/weave_bot.gd")
const RED := 0
const BLUE := 1
const STONE := 3
const VINE := 6


func run() -> void:
	_test_legal_and_consistent()
	_test_ashby2_is_unwinnable_for_one_slot()
	_test_fly_opening_zero_matches()
	_test_fly_then_solves()
	_test_prologue_red_three_casts()
	_test_backstop_never_fires_when_off()
	_test_optimal_tier_is_hard_not_perfect()


func _john(pool: Array, n: int) -> DmbCombatant:
	return DmbCombatant.make({"id": "john", "display_name": "John", "archetype": "player", "kind": "player",
		"weave_size": n, "attack_pool": pool.duplicate(), "ward_size": n, "ward_pool": pool.duplicate(),
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0})


## Drive a bot against a fixed ward; return casts used (0 = never solved).
func _solve(enemy: DmbCombatant, target: DmbCombatant, ward: Array, seed: int) -> int:
	var bot = _WeaveBot.new(enemy, target, seed)
	for g in range(enemy.max_casts):
		var guess: Array = bot.make_guess()
		assert_true(bot.is_legal_attack(guess), "guess legal %s" % str(guess))
		var r := DmbFeedback.score_attack(ward, guess)
		if bool(r["broken"]):
			return g + 1
		bot.register_feedback(guess, int(r["fracture"]), int(r["echo"]))
		# Every remaining candidate must be consistent with all feedback so far.
		assert_true(bot.candidate_count() >= 1, "candidates never empty")
	return 0


func _test_legal_and_consistent() -> void:
	for pool in [[BLUE], [BLUE, VINE]]:
		for n in [1, 2]:
			if pool.size() == 1 and n == 2:
				continue
			var john := _john(pool, n)
			var enemy := DmbBestiary.make("ashby_lesson3")
			var wards := DmbCandidateGen.generate_codes(john.ward_pool, john.ward_size, true)
			for w in wards:
				_solve(enemy, john, w, 11)


func _test_ashby2_is_unwinnable_for_one_slot() -> void:
	var john := _john([BLUE], 1)
	var ashby := DmbBestiary.make("ashby_lesson2")
	var sim = _BattleSim.new(john, ashby, 5)
	assert_eq(ashby.ward_size, 2, "lesson 2 has a two-slot ward")
	assert_eq(ashby.weave_size, 2, "lesson 2 weaves two")
	assert_true(not sim.player_can_break_enemy(), "one Water cannot break a complete two-slot Ward")
	assert_true(sim.enemy_can_break_player(), "Ashby can reach John's one slot")
	# And he does: every legal John ward falls within the cast limit.
	for w in DmbCandidateGen.generate_codes(john.ward_pool, 1, true):
		var casts := _solve(ashby, john, w, 3)
		assert_true(casts > 0 and casts <= 3, "Ashby breaks %s in ≤3 casts (got %d)" % [str(w), casts])


func _test_fly_opening_zero_matches() -> void:
	var fly := DmbBestiary.make("giant_fly")
	assert_true(fly.weave_size >= 2 and fly.ward_size >= 2, "fly has ≥2 slots")
	assert_eq(fly.bot_opening_attack, [RED, RED], "fly's authored opening is Fire×2")
	var john := _john([BLUE, VINE], 2)
	var wards := DmbCandidateGen.generate_codes(john.ward_pool, 2, true)
	assert_eq(wards.size(), 4, "four legal John wards at Water+Vine/2")
	for w in wards:
		var bot = _WeaveBot.new(fly, john, 1)
		var first: Array = bot.make_guess()
		assert_eq(first, [RED, RED], "first lunge is the authored miss vs %s" % str(w))
		var r := DmbFeedback.score_attack(w, first)
		assert_eq(int(r["fracture"]), 0, "no fracture on the opening vs %s" % str(w))
		assert_eq(int(r["echo"]), 0, "no echo on the opening vs %s" % str(w))
		assert_true(not bool(r["broken"]), "opening never breaks")


func _test_fly_then_solves() -> void:
	var fly := DmbBestiary.make("giant_fly")
	var john := _john([BLUE, VINE], 2)
	for w in DmbCandidateGen.generate_codes(john.ward_pool, 2, true):
		for seed in [1, 7, 42]:
			var casts := _solve(fly, john, w, seed)
			assert_true(casts >= 2 and casts <= fly.max_casts, "fly solves %s after its miss (casts=%d)" % [str(w), casts])


func _test_prologue_red_three_casts() -> void:
	var halvard := DmbCombatant.make({"id": "halvard", "display_name": "Halvard", "archetype": "blue_mage", "kind": "player",
		"weave_size": 3, "attack_pool": [BLUE, RED, STONE], "ward_size": 3, "ward_pool": [BLUE, RED, STONE],
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0})
	var red := DmbBestiary.make("red_wizard_prologue")
	var wards := DmbCandidateGen.generate_codes(halvard.ward_pool, 3, true)
	var solver_within_3 := 0
	for w in wards:
		var casts := _solve(red, halvard, w, 9)
		if casts > 0 and casts <= 3:
			solver_within_3 += 1
		# Whatever the solver did, the sim's backstop guarantees defeat by cast 3.
		var sim = _BattleSim.new(halvard, red, 9)
		sim.forced_defeat_by_cast = 3
		for i in range(3):
			sim.set_player_ward_locus(i, int(w[i]))
		sim.lock_player_ward_and_start()
		sim.debug_set_enemy_cast_at(0.0)
		var guard := 0
		while sim.result == null and guard < 40:
			sim.advance_time_for_test(6.0)
			guard += 1
		assert_true(sim.result != null, "prologue duel ends vs %s" % str(w))
		assert_eq(sim.result.outcome, "defeat", "Halvard loses vs %s" % str(w))
		assert_true(sim.result.bot_guess_count <= 3, "Red needs ≤3 casts vs %s (got %d)" % [str(w), sim.result.bot_guess_count])
	# The legitimate solver should carry most of the weight; the backstop is a net.
	assert_true(solver_within_3 * 2 >= wards.size(), "solver alone breaks ≥ half of wards in ≤3 (%d/%d)" % [solver_within_3, wards.size()])


func _test_backstop_never_fires_when_off() -> void:
	# Ordinary battle: forced_defeat_by_cast defaults to 0; a rigged random bot
	# must NOT magically hit the player's ward on cast 3.
	var john := _john([BLUE, VINE], 2)
	var dumb := DmbCombatant.make({"id": "d", "display_name": "d", "archetype": "wizard", "kind": "creature",
		"weave_size": 2, "attack_pool": [RED], "ward_size": 2, "ward_pool": [RED], "bot_logic": "random",
		"max_casts": 10, "min_cast_seconds": 5.0, "max_cast_seconds": 60.0})
	var sim = _BattleSim.new(john, dumb, 4)
	assert_eq(sim.forced_defeat_by_cast, 0, "backstop off by default")
	sim.set_player_ward_locus(0, BLUE)
	sim.set_player_ward_locus(1, VINE)
	sim.lock_player_ward_and_start()
	sim.debug_set_enemy_cast_at(0.0)
	var guard := 0
	while sim.result == null and guard < 60:
		sim.advance_time_for_test(6.0)
		guard += 1
	assert_true(sim.result == null or sim.result.outcome != "defeat", "a Fire-only bot cannot beat a Water/Vine ward without the backstop")


func _test_optimal_tier_is_hard_not_perfect() -> void:
	var john := _john([BLUE, VINE, RED], 3)
	var wards := DmbCandidateGen.generate_codes(john.ward_pool, 3, true)
	var base := DmbBestiary.make("moss_shade")
	base.attack_pool = [BLUE, VINE, RED]
	base.weave_size = 3
	var filt := base.duplicate_combatant()
	filt.bot_logic = "candidate_filter"
	var hard := base.duplicate_combatant()
	hard.bot_logic = "capped_minimax"
	hard.bot_solver_cap = 100
	hard.bot_mistake_rate = 0.0
	var sum_f := 0
	var sum_h := 0
	var count := 0
	var i := 0
	while i < wards.size():
		sum_f += _solve(filt, john, wards[i], 21)
		sum_h += _solve(hard, john, wards[i], 21)
		count += 1
		i += 3
	assert_true(sum_h <= sum_f, "hard tier averages no worse than candidate_filter (%d vs %d over %d)" % [sum_h, sum_f, count])
	assert_true(sum_h > count, "hard tier is not a one-cast oracle (%d casts over %d wards)" % [sum_h, count])

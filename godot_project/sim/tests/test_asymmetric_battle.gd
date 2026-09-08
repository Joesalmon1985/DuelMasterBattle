extends DmbTestCase

## Asymmetric weave battles: unequal weave/ward sizes, wrapping, bestiary, progression.

const _BattleSim = preload("res://sim/battle_sim.gd")
const _WeaveBot = preload("res://sim/weave_bot.gd")

const RED := 0
const BLUE := 1
const STONE := 3
const VINE := 6


func run() -> void:
	_test_wrap_targets()
	_test_score_attack_equal_matches_score_guess()
	_test_score_attack_larger_attacker()
	_test_score_attack_smaller_attacker_cannot_break()
	_test_echo_semantics_with_wrap()
	_test_bestiary_loads()
	_test_progression_model()
	_test_1v1_flame_wisp_guaranteed()
	_test_2v1_player_advantage()
	_test_2v2()
	_test_underpowered_john_vs_4slot_wizard()
	_test_bot_consistency_asymmetric()
	_test_bot_solves_within_limit_variety()
	_test_core_duel_via_battle_sim()


func _john(spells: Array, weave: int) -> DmbCombatant:
	var p := DmbProgression.new()
	for s in spells:
		p.learn_spell(s)
	p.grow_weave(weave)
	return p.to_combatant()


func _start(sim, ward: Array) -> void:
	for i in range(ward.size()):
		sim.set_player_ward_locus(i, ward[i])
	sim.lock_player_ward_and_start()


func _set_attack(sim, a: Array) -> void:
	for i in range(a.size()):
		sim.set_player_attack_locus(i, a[i])


func _test_wrap_targets() -> void:
	assert_eq(DmbFeedback.targets_by_ward_slot(5, 3), [[0, 3], [1, 4], [2]], "5 vs 3 wrap")
	assert_eq(DmbFeedback.targets_by_ward_slot(4, 2), [[0, 2], [1, 3]], "4 vs 2 wrap")
	assert_eq(DmbFeedback.targets_by_ward_slot(2, 4), [[0], [1], [], []], "2 vs 4 leaves slots untargeted")
	assert_eq(DmbFeedback.targets_by_ward_slot(1, 1), [[0]], "1 vs 1")


func _test_score_attack_equal_matches_score_guess() -> void:
	var cases := [[[0, 1, 3, 4], [0, 3, 1, 9]], [[0, 0, 1, 3], [0, 0, 0, 0]], [[0, 1, 1, 3], [1, 0, 3, 1]], [[1], [1]], [[1], [0]]]
	for c in cases:
		var g := DmbFeedback.score_guess(c[0], c[1])
		var r := DmbFeedback.score_attack(c[0], c[1])
		assert_eq(Vector2i(int(r["fracture"]), int(r["echo"])), g, "equal-size parity %s" % str(c))
		assert_eq(bool(r["broken"]), g.x == c[0].size(), "broken parity %s" % str(c))


func _test_score_attack_larger_attacker() -> void:
	# 4 attempts vs 2-slot ward [RED, BLUE]: slot1 gets attempts 0,2; slot2 gets 1,3
	var r := DmbFeedback.score_attack([RED, BLUE], [RED, RED, BLUE, BLUE])
	assert_eq(int(r["fracture"]), 2, "one fracture per slot (attempt 0 → slot 1, attempt 3 → slot 2)")
	assert_true(bool(r["broken"]), "both slots fractured → broken")
	r = DmbFeedback.score_attack([RED, BLUE], [RED, RED, RED, RED])
	assert_eq(int(r["fracture"]), 2, "attempts 0 and 2 hit slot 1")
	assert_true(not bool(r["broken"]), "slot 2 never fractured")
	assert_eq(int(r["echo"]), 0, "no echo: RED only exists in a fractured slot")
	r = DmbFeedback.score_attack([RED, BLUE], [BLUE, RED, BLUE, RED])
	assert_eq(int(r["fracture"]), 0, "all displaced")
	assert_eq(int(r["echo"]), 2, "echo limited to ward multiset (one RED, one BLUE)")
	# 5 vs 3
	r = DmbFeedback.score_attack([RED, BLUE, STONE], [RED, BLUE, STONE, BLUE, RED])
	assert_true(bool(r["broken"]), "5v3 breaks when first three exact")
	assert_eq(int(r["fracture"]), 3, "fractures counted once per attempt")
	assert_eq(int(r["echo"]), 0, "extra attempts on fractured slots don't echo")


func _test_score_attack_smaller_attacker_cannot_break() -> void:
	var r := DmbFeedback.score_attack([RED, BLUE, STONE, RED], [RED, BLUE])
	assert_eq(int(r["fracture"]), 2, "two exact")
	assert_true(not bool(r["broken"]), "2v4 can never break")
	r = DmbFeedback.score_attack([RED, BLUE, STONE, RED], [STONE, RED])
	assert_eq(int(r["fracture"]), 0, "none exact")
	assert_eq(int(r["echo"]), 2, "both present elsewhere")


func _test_echo_semantics_with_wrap() -> void:
	# ward [RED, BLUE]; attack [BLUE, BLUE, RED, RED]: attempt1 BLUE→slot2 fracture, attempt2 RED→slot1 fracture
	var r := DmbFeedback.score_attack([RED, BLUE], [BLUE, BLUE, RED, RED])
	assert_eq(int(r["fracture"]), 2, "wrapped attempts can fracture")
	assert_true(bool(r["broken"]), "broken via wrapped attempts")
	assert_eq(int(r["echo"]), 0, "remaining attempts have no unfractured slot to echo")
	assert_eq(int(r["fade"]), 2, "fade = attempts - fracture - echo")


func _test_bestiary_loads() -> void:
	for id in DmbBestiary.ids():
		var c := DmbBestiary.make(id)
		assert_true(c.weave_size >= 1 and c.ward_size >= 1, "bestiary %s sizes" % id)
		assert_true(not c.attack_pool.is_empty(), "bestiary %s attack pool" % id)
	var wisp := DmbBestiary.make("flame_wisp")
	assert_eq(wisp.attack_pool, [RED], "wisp attacks RED only")
	assert_eq(wisp.fixed_ward, [BLUE], "wisp ward is BLUE (attack ≠ ward magic)")


func _test_progression_model() -> void:
	var p := DmbProgression.new()
	assert_true(not p.has_magic(), "starts with no magic")
	assert_true(p.learn_spell(BLUE), "learn blue")
	assert_true(not p.learn_spell(BLUE), "no duplicate learn")
	assert_true(p.grow_weave(1), "weave 1")
	assert_true(not p.grow_weave(1), "no shrink/same")
	assert_true(p.has_magic(), "has magic")
	var c := p.to_combatant()
	assert_eq(c.weave_size, 1, "combatant weave")
	assert_eq(c.attack_pool, [BLUE], "combatant pool")
	var d := p.to_dict()
	var p2 := DmbProgression.from_dict(d)
	assert_eq(p2.spells_known, [BLUE], "roundtrip spells")
	assert_eq(p2.weave_size, 1, "roundtrip weave")
	p.learn_spell(RED)
	p.grow_weave(2)
	p.learn_spell(STONE)
	p.grow_weave(3)
	p.learn_spell(VINE)
	p.grow_weave(4)
	assert_eq(p.spells_known.size(), 4, "four spells")
	assert_eq(p.weave_size, 4, "four slots")


func _test_1v1_flame_wisp_guaranteed() -> void:
	var sim = _BattleSim.new(_john([BLUE], 1), DmbBestiary.make("flame_wisp"), 3)
	_start(sim, [BLUE])
	assert_eq(sim.get_enemy_ward(), [BLUE], "wisp ward fixed BLUE")
	sim.debug_set_enemy_cast_at(999.0)
	sim.advance_time_for_test(5.1)
	_set_attack(sim, [BLUE])
	assert_true(sim.submit_player_attack(), "cast")
	assert_eq(sim.result.outcome, "victory", "first fight is guaranteed")
	assert_eq(sim.player_history[0].fracture_count, 1, "1 fracture")


func _test_2v1_player_advantage() -> void:
	var sim = _BattleSim.new(_john([BLUE, RED], 2), DmbBestiary.make("steam_sprite"), 5)
	_start(sim, [RED, BLUE])
	sim.debug_set_enemy_cast_at(999.0)
	sim.advance_time_for_test(5.1)
	# Two attempts cover both possibilities of a 1-slot ward at once.
	_set_attack(sim, [RED, BLUE])
	assert_true(sim.submit_player_attack(), "cast 2v1")
	assert_eq(sim.result.outcome, "victory", "2 attempts vs 1 slot: guaranteed break")
	var rec = sim.player_history[0]
	assert_eq(rec.fracture_count, 1, "exactly one attempt fractured")
	assert_eq(rec.fade_count, 1, "other attempt faded (its spell isn't in an unfractured slot)")


func _test_2v2() -> void:
	var sim = _BattleSim.new(_john([BLUE, RED], 2), DmbBestiary.make("steam_brute"), 7)
	_start(sim, [RED, RED])
	sim.debug_set_enemy_ward([BLUE, RED])
	sim.debug_set_enemy_cast_at(999.0)
	sim.advance_time_for_test(5.1)
	_set_attack(sim, [RED, BLUE])
	sim.submit_player_attack()
	var rec = sim.player_history[0]
	assert_eq(rec.fracture_count, 0, "swap → 0 fracture")
	assert_eq(rec.echo_count, 2, "swap → 2 echo")
	assert_eq(sim.phase, _BattleSim.Phase.DUELING, "still dueling")
	sim.debug_set_enemy_cast_at(999.0)
	sim.advance_time_for_test(5.1)
	_set_attack(sim, [BLUE, RED])
	sim.submit_player_attack()
	assert_eq(sim.result.outcome, "victory", "2v2 solved")


func _test_underpowered_john_vs_4slot_wizard() -> void:
	var sim = _BattleSim.new(_john([BLUE, RED], 2), DmbBestiary.make("red_wizard"), 9)
	assert_true(not sim.player_can_break_enemy(), "2 weave cannot cover 4-slot ward")
	assert_true(sim.enemy_can_break_player(), "wizard can cover john's 2-slot ward")
	_start(sim, [RED, BLUE])
	sim.debug_set_enemy_ward([RED, BLUE, STONE, RED])
	var guard := 0
	while sim.phase == _BattleSim.Phase.DUELING and guard < 5000:
		if sim.is_player_window_open():
			_set_attack(sim, [RED, BLUE])  # exactly right for slots 1-2
			sim.submit_player_attack()
		sim.advance_time_for_test(0.5)
		guard += 1
	assert_eq(sim.phase, _BattleSim.Phase.FINISHED, "unwinnable battle still ends")
	assert_eq(sim.result.outcome, "defeat", "outmatched John loses")
	for rec in sim.player_history:
		assert_true(not rec.broke_ward, "john never breaks a 4-slot ward with 2 slots")
		assert_eq(rec.fracture_count, 2, "john's perfect partial guess reports 2 fractures")
	# wizard gets 2 attempts per John slot → very fast
	assert_true(sim.enemy_history.size() <= 4, "4-slot wizard breaks 2-slot ward quickly (%d casts)" % sim.enemy_history.size())


func _test_bot_consistency_asymmetric() -> void:
	# Enemy with 4 weave vs John's 2 ward: every guess consistent with prior feedback.
	var john := _john([BLUE, RED, STONE], 2)
	var wiz := DmbBestiary.make("red_wizard")
	for seed in range(5):
		var bot = _WeaveBot.new(wiz, john, seed)
		var secret := [int([BLUE, RED, STONE][seed % 3]), int([RED, STONE, BLUE][seed % 3])]
		var hist: Array = []
		var solved := false
		for _i in range(10):
			var g: Array = bot.make_guess()
			assert_eq(g.size(), 4, "wizard weaves 4")
			assert_true(bot.is_legal_attack(g), "legal attack")
			var res := DmbFeedback.score_attack(secret, g)
			if bool(res["broken"]):
				solved = true
				break
			hist.append({"g": g, "f": int(res["fracture"]), "e": int(res["echo"])})
			bot.register_feedback(g, int(res["fracture"]), int(res["echo"]))
			# consistency: the true secret must remain a candidate
			assert_true(bot.candidate_count() >= 1, "candidates remain")
		assert_true(solved, "4-weave bot solves 2-slot ward seed %d" % seed)


func _test_bot_solves_within_limit_variety() -> void:
	var pairs := [
		["flame_imp", [BLUE], 1], ["steam_sprite", [BLUE, RED], 2], ["steam_brute", [BLUE, RED], 2],
		["cinder_golem", [BLUE, RED], 2], ["moss_shade", [BLUE, RED, STONE], 3],
		["hedge_wizard", [BLUE, RED, STONE], 3], ["red_wizard", [BLUE, RED, STONE, VINE], 4],
	]
	for p in pairs:
		var enemy := DmbBestiary.make(p[0])
		var john := _john(p[1], p[2])
		var all := DmbCandidateGen.generate_codes(john.ward_pool, john.ward_size, true)
		var step := maxi(1, all.size() / 12)
		var i := 0
		while i < all.size():
			var bot = _WeaveBot.new(enemy, john, i)
			var solved := false
			for _g in range(enemy.max_casts):
				var g: Array = bot.make_guess()
				var r := DmbFeedback.score_attack(all[i], g)
				if bool(r["broken"]):
					solved = true
					break
				bot.register_feedback(g, int(r["fracture"]), int(r["echo"]))
			var covers := true
			for s in john.ward_pool:
				if not (int(s) in enemy.attack_pool):
					covers = false
			if enemy.weave_size >= john.ward_size and enemy.bot_logic != "random" and covers:
				assert_true(solved, "%s solves john ward %s" % [p[0], str(all[i])])
			i += step


func _test_core_duel_via_battle_sim() -> void:
	# Regression anchor: 4x6x10 duel through the generalised sim.
	var john := DmbCombatant.make({
		"id": "john", "display_name": "John", "weave_size": 4, "attack_pool": DmbConstants.CORE_SPELL_POOL.duplicate(),
		"ward_size": 4, "ward_pool": DmbConstants.CORE_SPELL_POOL.duplicate(), "max_casts": 10,
	})
	var sim = _BattleSim.new(john, DmbBestiary.make("rival_wizard"), 21)
	_start(sim, [0, 1, 3, 4])
	sim.debug_set_enemy_ward([9, 9, 6, 1])
	sim.debug_set_enemy_cast_at(999.0)
	sim.advance_time_for_test(5.1)
	_set_attack(sim, [9, 6, 9, 1])
	sim.submit_player_attack()
	var rec = sim.player_history[0]
	assert_eq(Vector2i(rec.fracture_count, rec.echo_count), Vector2i(2, 2), "4x4 mixed feedback parity")
	sim.debug_set_enemy_cast_at(999.0)
	sim.advance_time_for_test(5.1)
	_set_attack(sim, [9, 9, 6, 1])
	sim.submit_player_attack()
	assert_eq(sim.result.outcome, "victory", "4x4 victory through battle sim")

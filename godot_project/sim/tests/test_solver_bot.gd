extends DmbTestCase

const _SolverBot = preload("res://sim/solver_bot.gd")
const _BotFactory = preload("res://sim/bot_factory.gd")


func run() -> void:
	var archmage := DmbEncounters.get_encounter("archmage_duel")
	var data := DmbFixtureLoader.load_json("solver_cases.json")
	assert_eq(data["candidate_count"], 10000, "candidate count")
	var og: Array = data["opening_guess"]
	assert_eq(int(og[0]), 0, "fixture opening 0")
	assert_eq(int(og[1]), 0, "fixture opening 1")
	assert_eq(int(og[2]), 1, "fixture opening 2")
	assert_eq(int(og[3]), 1, "fixture opening 3")
	var bot = _SolverBot.new(archmage)
	assert_eq(bot.all_code_count(), 10000, "godot archmage all codes")
	var opening: Array = bot.make_guess()
	assert_eq(opening.size(), 4, "opening length")
	assert_true(bot.is_legal_guess(opening), "opening legal")
	assert_eq(int(opening[0]), int(opening[1]), "opening pairs first two")
	assert_eq(int(opening[2]), int(opening[3]), "opening pairs last two")
	assert_true(int(opening[0]) != int(opening[2]), "opening uses two spells")
	var secret := [2, 5, 8, 1]
	bot.register_feedback(opening, DmbFeedback.score_guess(secret, opening).x,
		DmbFeedback.score_guess(secret, opening).y)
	assert_true(_contains_candidate(bot, secret), "preserves secret")
	var b = _SolverBot.new(archmage)
	var result: Dictionary = b.solve_secret([0, 1, 2, 3])
	assert_true(result["solved"], "solves representative secret")
	assert_true(int(result["count"]) <= DmbConstants.MAX_GUESSES, "within 12")
	var blue := DmbEncounters.get_encounter("blue_apprentice")
	var blue_bot = _SolverBot.new(blue)
	assert_eq(blue_bot.all_code_count(), 3, "blue candidate count")
	var thorn := DmbEncounters.get_encounter("thorn_adept")
	assert_eq(_SolverBot.new(thorn).all_code_count(), 12, "thorn candidate count")
	for _i in range(3):
		var b2 = _SolverBot.new(archmage)
		assert_true(b2.is_legal_guess(b2.make_guess()), "legal opening guess")
	for enc_id in ["blue_apprentice", "archmage_duel"]:
		var rs = DmbEncounters.get_encounter(enc_id)
		var rb = _BotFactory.make_bot(rs, null, 42)
		assert_true(rb.is_legal_guess(rb.make_guess()), "legal opening %s" % enc_id)


func _contains_candidate(bot, secret: Array) -> bool:
	for c in bot._candidates:
		if c == secret:
			return true
	return false

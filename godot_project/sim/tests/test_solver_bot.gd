extends DmbTestCase

const _SolverBot = preload("res://sim/solver_bot.gd")
const _BotFactory = preload("res://sim/bot_factory.gd")


func run() -> void:
	var data := DmbFixtureLoader.load_json("solver_cases.json")
	assert_eq(data["candidate_count"], 10000, "candidate count")
	var og: Array = data["opening_guess"]
	assert_eq(int(og[0]), 0, "fixture opening 0")
	assert_eq(int(og[1]), 0, "fixture opening 1")
	assert_eq(int(og[2]), 1, "fixture opening 2")
	assert_eq(int(og[3]), 1, "fixture opening 3")
	assert_eq(_SolverBot.all_code_count(), 10000, "godot all codes")
	var bot = _SolverBot.new()
	var opening: Array = bot.make_guess()
	assert_eq(int(opening[0]), 0, "opening 0")
	assert_eq(int(opening[1]), 0, "opening 1")
	assert_eq(int(opening[2]), 1, "opening 2")
	assert_eq(int(opening[3]), 1, "opening 3")
	var secret := [2, 5, 8, 1]
	bot.register_feedback([0, 0, 1, 1], DmbFeedback.score_guess(secret, [0, 0, 1, 1]).x,
		DmbFeedback.score_guess(secret, [0, 0, 1, 1]).y)
	assert_true(_contains_candidate(bot, secret), "preserves secret")
	# Full solve loop is expensive in GDScript; verify one representative case.
	var b = _SolverBot.new()
	var result: Dictionary = b.solve_secret([0, 1, 2, 3])
	assert_true(result["solved"], "solves representative secret")
	assert_true(int(result["count"]) <= DmbConstants.MAX_GUESSES, "within 12")
	for _i in range(20):
		var b2 = _SolverBot.new()
		assert_true(b2.is_legal_guess(b2.make_guess()), "legal guess")
	for level in ["easy", "normal", "hard", "expert"]:
		var rb = _BotFactory.make_bot(level, 42)
		for _j in range(5):
			assert_true(rb.is_legal_guess(rb.make_guess()), "difficulty legal %s" % level)


func _contains_candidate(bot, secret: Array) -> bool:
	for c in bot._candidates:
		if c == secret:
			return true
	return false

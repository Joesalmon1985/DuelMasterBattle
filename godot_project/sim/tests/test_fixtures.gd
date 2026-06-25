extends DmbTestCase

func run() -> void:
	_test_file("feedback_cases.json", "feedback")
	_test_file("duplicate_edge_cases.json", "duplicate")
	_test_illegal()
	_test_bot()
	_test_win_draw()


func _test_file(filename: String, _label: String) -> void:
	var data := DmbFixtureLoader.load_json(filename)
	for case in data["cases"]:
		var secret: Array = case["secret"]
		var guess: Array = case["guess"]
		var fb := DmbFeedback.score_guess(secret, guess)
		assert_eq(fb.x, int(case["exact"]), "%s exact" % filename)
		assert_eq(fb.y, int(case["colour_only"]), "%s colour" % filename)


func _test_illegal() -> void:
	var data := DmbFixtureLoader.load_json("illegal_guesses.json")
	for case in data["cases"]:
		var guess: Array = case["guess"]
		assert_eq(DmbCode.is_valid_code(guess), case["valid"], "illegal guess")


func _test_bot() -> void:
	var data := DmbFixtureLoader.load_json("bot_legal_guesses.json")
	for g in data["guesses"]:
		assert_true(DmbCode.is_valid_code(g), "fixture guess legal")
	assert_true(DmbCode.is_valid_code(data["code"]), "fixture code legal")
	var bot := DmbRandomBot.new(DmbEncounters.default_encounter(), 42)
	for _i in range(50):
		assert_true(bot.is_legal_guess(bot.make_guess()))
	assert_true(bot.is_legal_guess(bot.generate_code()))


func _test_win_draw() -> void:
	var data := DmbFixtureLoader.load_json("win_draw_states.json")
	for case in data["cases"]:
		var hg: Array = []
		for g in case.get("human_guesses", []):
			hg.append(DmbGuessRecord.new(g["guess"], g["exact"], g["colour_only"]))
		var bg: Array = []
		for g in case.get("bot_guesses", []):
			bg.append(DmbGuessRecord.new(g["guess"], g["exact"], g["colour_only"]))
		var r := DmbGameLogic.compute_result(
			case["human_solved"], case["bot_solved"],
			case["human_guess_count"], case["bot_guess_count"],
			hg, bg
		)
		assert_eq(r.outcome, case["expected_outcome"], "win/draw outcome")

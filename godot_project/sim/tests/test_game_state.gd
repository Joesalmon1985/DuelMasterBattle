extends DmbTestCase

const _SolverBot = preload("res://sim/solver_bot.gd")


func run() -> void:
	_test_setup_starts_human_turn()
	_test_human_then_bot_alternation()
	_test_human_win()
	_test_draw_at_twelve_each()
	_test_bot_memory_persists()


func _setup_human(g: DmbSequentialDuelGame, code: Array) -> void:
	for i in range(code.size()):
		g.set_human_secret_peg(i, code[i])
	g.lock_human_secret()


func _test_setup_starts_human_turn() -> void:
	var g := DmbSequentialDuelGame.new(1)
	assert_eq(g.phase, DmbSequentialDuelGame.GamePhase.HUMAN_SETUP)
	_setup_human(g, [0, 1, 2, 3])
	assert_eq(g.phase, DmbSequentialDuelGame.GamePhase.HUMAN_TURN)
	assert_true(g.get_bot_secret().size() == DmbConstants.CODE_LENGTH)


func _test_human_then_bot_alternation() -> void:
	var g := DmbSequentialDuelGame.new(5)
	_setup_human(g, [0, 1, 2, 3])
	g.submit_human_guess([1, 1, 1, 1])
	assert_eq(g.phase, DmbSequentialDuelGame.GamePhase.BOT_TURN)
	assert_eq(g.human_guesses.size(), 1)
	g.bot_make_guess()
	assert_eq(g.phase, DmbSequentialDuelGame.GamePhase.HUMAN_TURN)
	assert_eq(g.bot_guesses.size(), 1)


func _test_human_win() -> void:
	var g := DmbSequentialDuelGame.new(99)
	_setup_human(g, [5, 5, 5, 5])
	# bot secret is generated at lock; override for deterministic test
	g.submit_human_guess(g.get_bot_secret())
	assert_eq(g.phase, DmbSequentialDuelGame.GamePhase.FINISHED)
	assert_true(g.result.human_solved)


func _test_draw_at_twelve_each() -> void:
	var g := DmbSequentialDuelGame.new(2, "easy")
	_setup_human(g, [0, 0, 0, 0])
	g._bot_secret = [9, 9, 9, 9]
	var miss := [1, 1, 1, 1]
	var safety := 0
	while g.phase != DmbSequentialDuelGame.GamePhase.FINISHED and safety < 30:
		if g.phase == DmbSequentialDuelGame.GamePhase.HUMAN_TURN:
			g.submit_human_guess(miss)
		elif g.phase == DmbSequentialDuelGame.GamePhase.BOT_TURN:
			g.bot_make_guess()
		safety += 1
	assert_eq(g.phase, DmbSequentialDuelGame.GamePhase.FINISHED)
	assert_eq(g.result.outcome, "draw")
	assert_eq(g.human_guesses.size(), DmbConstants.MAX_GUESSES)
	assert_eq(g.bot_guesses.size(), DmbConstants.MAX_GUESSES)


func _test_bot_memory_persists() -> void:
	var g := DmbSequentialDuelGame.new(7, "normal")
	_setup_human(g, [2, 5, 8, 1])
	g.submit_human_guess([0, 0, 0, 0])
	assert_eq(g.phase, DmbSequentialDuelGame.GamePhase.BOT_TURN)
	var bot = g._bot
	assert_true(bot is DmbSolverBot)
	var before: int = bot.candidate_count()
	g.bot_make_guess()
	assert_true(bot.candidate_count() < before)

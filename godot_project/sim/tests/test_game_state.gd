extends DmbTestCase

func run() -> void:
	var g := DmbSequentialDuelGame.new(1)
	assert_eq(g.phase, DmbSequentialDuelGame.GamePhase.HUMAN_SETUP)
	for i in range(4):
		g.set_human_secret_peg(i, i)
	assert_true(g.can_lock_human_secret())
	g.lock_human_secret()
	assert_eq(g.phase, DmbSequentialDuelGame.GamePhase.BOT_GUESSING)
	g.run_all_bot_guesses()
	assert_eq(g.phase, DmbSequentialDuelGame.GamePhase.HUMAN_GUESSING)
	assert_true(g.bot_guesses.size() <= DmbConstants.MAX_GUESSES)

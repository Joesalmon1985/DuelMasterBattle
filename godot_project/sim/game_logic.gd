class_name DmbGameLogic
extends RefCounted


static func compute_result(
	human_solved: bool,
	bot_solved: bool,
	human_guess_count: int,
	bot_guess_count: int,
	human_guesses: Array,
	bot_guesses: Array,
	max_attacks: int = DmbConstants.MAX_GUESSES
) -> DmbGameResult:
	if human_solved and not bot_solved:
		return DmbGameResult.new("human_win", true, false, human_guess_count, bot_guess_count,
			"You solved the bot's code in %d guesses!" % human_guess_count)
	if bot_solved and not human_solved:
		return DmbGameResult.new("bot_win", false, true, human_guess_count, bot_guess_count,
			"Bot solved your code in %d guesses!" % bot_guess_count)
	if human_solved and bot_solved:
		if human_guess_count < bot_guess_count:
			return DmbGameResult.new("human_win", true, true, human_guess_count, bot_guess_count,
				"Both solved! You used fewer guesses (%d vs %d)." % [human_guess_count, bot_guess_count])
		if bot_guess_count < human_guess_count:
			return DmbGameResult.new("bot_win", true, true, human_guess_count, bot_guess_count,
				"Both solved! Bot used fewer guesses (%d vs %d)." % [bot_guess_count, human_guess_count])
		return DmbGameResult.new("draw", true, true, human_guess_count, bot_guess_count,
			"Both solved in %d guesses — draw!" % human_guess_count)
	if (
		not human_solved
		and not bot_solved
		and human_guess_count >= max_attacks
		and bot_guess_count >= max_attacks
	):
		return DmbGameResult.new(
			"draw", false, false, human_guess_count, bot_guess_count,
			"Neither solved after %d attacks each — draw!" % max_attacks
		)
	var h_best := _best_progress(human_guesses)
	var b_best := _best_progress(bot_guesses)
	if h_best > b_best:
		return DmbGameResult.new("human_win", false, false, human_guess_count, bot_guess_count,
			"Neither solved. You had better progress — you win!")
	if b_best > h_best:
		return DmbGameResult.new("bot_win", false, false, human_guess_count, bot_guess_count,
			"Neither solved. Bot had better progress — bot wins!")
	return DmbGameResult.new("draw", false, false, human_guess_count, bot_guess_count,
		"Neither solved. Draw!")


static func _best_progress(guesses: Array) -> Vector2i:
	if guesses.is_empty():
		return Vector2i(0, 0)
	var best := Vector2i(0, 0)
	for g in guesses:
		var rec: DmbGuessRecord = g
		var score := Vector2i(rec.exact, rec.colour_only)
		if score.x > best.x or (score.x == best.x and score.y > best.y):
			best = score
	return best

class_name DmbSequentialDuelGame
extends RefCounted

const _BotFactory = preload("res://sim/bot_factory.gd")

enum GamePhase { HUMAN_SETUP, HUMAN_TURN, BOT_TURN, FINISHED }

var phase: int = GamePhase.HUMAN_SETUP
var human_setup_pegs: Array = []
var current_human_guess: Array = []
var bot_guesses: Array = []
var human_guesses: Array = []
var result: DmbGameResult = null

var _ruleset: DmbDuelRuleset
var _bot_seed: int = 42
var _bot: RefCounted
var _human_secret: Array = []
var _bot_secret: Array = []
var _bot_solved := false
var _human_solved := false


func _init(ruleset: DmbDuelRuleset = null, bot_seed: int = 42) -> void:
	_ruleset = ruleset if ruleset != null else DmbEncounters.default_encounter()
	_bot_seed = bot_seed
	reset()


func reset(bot_seed: int = -1, ruleset: DmbDuelRuleset = null) -> void:
	if bot_seed >= 0:
		_bot_seed = bot_seed
	if ruleset != null:
		_ruleset = ruleset
	_bot = _BotFactory.make_bot(_ruleset, _bot_seed)
	phase = GamePhase.HUMAN_SETUP
	human_setup_pegs = _empty_pegs()
	current_human_guess = _empty_pegs()
	bot_guesses = []
	human_guesses = []
	result = null
	_human_secret = []
	_bot_secret = []
	_bot_solved = false
	_human_solved = false


func get_ruleset() -> DmbDuelRuleset:
	return _ruleset


func _empty_pegs() -> Array:
	var arr: Array = []
	for _i in range(_ruleset.slot_count):
		arr.append(null)
	return arr


func get_bot_secret() -> Array:
	return _bot_secret.duplicate()


func get_difficulty() -> String:
	return _ruleset.enemy_difficulty


func can_lock_human_secret() -> bool:
	if phase != GamePhase.HUMAN_SETUP:
		return false
	for p in human_setup_pegs:
		if p == null:
			return false
	return true


func set_human_secret_peg(slot: int, colour: int) -> void:
	assert(phase == GamePhase.HUMAN_SETUP, "not in human setup")
	assert(slot >= 0 and slot < _ruleset.slot_count)
	DmbCode.validate_colour_in_pool(colour, _ruleset.secret_magic_pool)
	human_setup_pegs[slot] = colour


func lock_human_secret() -> void:
	assert(can_lock_human_secret(), "all pegs required")
	DmbCode.validate_code_for_ruleset(human_setup_pegs, _ruleset, _ruleset.secret_magic_pool)
	_human_secret = human_setup_pegs.duplicate()
	_bot_secret = _bot.generate_code()
	phase = GamePhase.HUMAN_TURN


func bot_guesses_remaining() -> int:
	return _ruleset.effective_max_attacks() - bot_guesses.size()


func human_guesses_remaining() -> int:
	return _ruleset.effective_max_attacks() - human_guesses.size()


func bot_make_guess() -> DmbGuessRecord:
	assert(phase == GamePhase.BOT_TURN, "not in bot turn")
	var max_attacks := _ruleset.effective_max_attacks()
	if _bot_solved or bot_guesses.size() >= max_attacks:
		return null
	var guess: Array = _bot.make_guess()
	var fb := DmbFeedback.score_guess(_human_secret, guess)
	var rec := DmbGuessRecord.new(guess, fb.x, fb.y)
	bot_guesses.append(rec)
	if _bot.has_method("register_feedback"):
		_bot.register_feedback(guess, fb.x, fb.y)
	if _ruleset.is_solved(fb.x):
		_bot_solved = true
		_finish_game()
	elif _both_exhausted():
		_finish_game()
	else:
		phase = GamePhase.HUMAN_TURN
	return rec


func set_human_guess_peg(slot: int, colour: int) -> void:
	assert(phase == GamePhase.HUMAN_TURN, "not in human turn")
	assert(slot >= 0 and slot < _ruleset.slot_count)
	DmbCode.validate_colour_in_pool(colour, _ruleset.attack_magic_pool)
	current_human_guess[slot] = colour


func can_submit_human_guess() -> bool:
	if phase != GamePhase.HUMAN_TURN:
		return false
	for p in current_human_guess:
		if p == null:
			return false
	return true


func submit_human_guess(guess: Array = []) -> DmbGuessRecord:
	assert(phase == GamePhase.HUMAN_TURN, "not in human turn")
	var max_attacks := _ruleset.effective_max_attacks()
	assert(human_guesses.size() < max_attacks)
	if guess.is_empty():
		assert(can_submit_human_guess())
		guess = current_human_guess.duplicate()
	DmbCode.validate_code_for_ruleset(guess, _ruleset, _ruleset.attack_magic_pool)
	var fb := DmbFeedback.score_guess(_bot_secret, guess)
	var rec := DmbGuessRecord.new(guess, fb.x, fb.y)
	human_guesses.append(rec)
	current_human_guess = _empty_pegs()
	if _ruleset.is_solved(fb.x):
		_human_solved = true
		_finish_game()
	elif _both_exhausted():
		_finish_game()
	else:
		phase = GamePhase.BOT_TURN
	return rec


func _both_exhausted() -> bool:
	var max_attacks := _ruleset.effective_max_attacks()
	return (
		not _human_solved
		and not _bot_solved
		and human_guesses.size() >= max_attacks
		and bot_guesses.size() >= max_attacks
	)


func _finish_game() -> void:
	phase = GamePhase.FINISHED
	result = DmbGameLogic.compute_result(
		_human_solved, _bot_solved,
		human_guesses.size(), bot_guesses.size(),
		human_guesses, bot_guesses,
		_ruleset.effective_max_attacks()
	)

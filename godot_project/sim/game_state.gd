class_name DmbSequentialDuelGame
extends RefCounted

const _BotFactory = preload("res://sim/bot_factory.gd")

enum GamePhase { HUMAN_SETUP, BOT_GUESSING, HUMAN_GUESSING, FINISHED }

var phase: int = GamePhase.HUMAN_SETUP
var human_setup_pegs: Array = [null, null, null, null]
var current_human_guess: Array = [null, null, null, null]
var bot_guesses: Array = []
var human_guesses: Array = []
var result: DmbGameResult = null

var _bot_seed: int = 42
var _difficulty: String = "expert"
var _bot: RefCounted
var _human_secret: Array = []
var _bot_secret: Array = []
var _bot_solved := false
var _human_solved := false


func _init(bot_seed: int = 42, difficulty: String = "expert") -> void:
	_bot_seed = bot_seed
	_difficulty = difficulty
	reset()


func reset(bot_seed: int = -1, difficulty: String = "") -> void:
	if bot_seed >= 0:
		_bot_seed = bot_seed
	if difficulty != "":
		_difficulty = difficulty
	_bot = _BotFactory.make_bot(_difficulty, _bot_seed)
	phase = GamePhase.HUMAN_SETUP
	human_setup_pegs = [null, null, null, null]
	current_human_guess = [null, null, null, null]
	bot_guesses = []
	human_guesses = []
	result = null
	_human_secret = []
	_bot_secret = []
	_bot_solved = false
	_human_solved = false


func get_bot_secret() -> Array:
	return _bot_secret.duplicate()


func get_difficulty() -> String:
	return _difficulty


func can_lock_human_secret() -> bool:
	if phase != GamePhase.HUMAN_SETUP:
		return false
	for p in human_setup_pegs:
		if p == null:
			return false
	return true


func set_human_secret_peg(slot: int, colour: int) -> void:
	assert(phase == GamePhase.HUMAN_SETUP, "not in human setup")
	assert(slot >= 0 and slot < DmbConstants.CODE_LENGTH)
	DmbCode.validate_colour(colour)
	human_setup_pegs[slot] = colour


func lock_human_secret() -> void:
	assert(can_lock_human_secret(), "all 4 pegs required")
	_human_secret = human_setup_pegs.duplicate()
	phase = GamePhase.BOT_GUESSING


func bot_guesses_remaining() -> int:
	return DmbConstants.MAX_GUESSES - bot_guesses.size()


func human_guesses_remaining() -> int:
	return DmbConstants.MAX_GUESSES - human_guesses.size()


func bot_make_guess() -> DmbGuessRecord:
	assert(phase == GamePhase.BOT_GUESSING)
	if _bot_solved or bot_guesses.size() >= DmbConstants.MAX_GUESSES:
		return null
	var guess: Array = _bot.make_guess()
	var fb := DmbFeedback.score_guess(_human_secret, guess)
	var rec := DmbGuessRecord.new(guess, fb.x, fb.y)
	bot_guesses.append(rec)
	if _bot.has_method("register_feedback"):
		_bot.register_feedback(guess, fb.x, fb.y)
	if fb.x == DmbConstants.CODE_LENGTH:
		_bot_solved = true
		_finish_bot_guessing()
	elif bot_guesses.size() >= DmbConstants.MAX_GUESSES:
		_finish_bot_guessing()
	return rec


func _finish_bot_guessing() -> void:
	_bot_secret = _bot.generate_code()
	phase = GamePhase.HUMAN_GUESSING


func set_human_guess_peg(slot: int, colour: int) -> void:
	assert(phase == GamePhase.HUMAN_GUESSING)
	assert(slot >= 0 and slot < DmbConstants.CODE_LENGTH)
	DmbCode.validate_colour(colour)
	current_human_guess[slot] = colour


func can_submit_human_guess() -> bool:
	if phase != GamePhase.HUMAN_GUESSING:
		return false
	for p in current_human_guess:
		if p == null:
			return false
	return true


func submit_human_guess(guess: Array = []) -> DmbGuessRecord:
	assert(phase == GamePhase.HUMAN_GUESSING)
	assert(human_guesses.size() < DmbConstants.MAX_GUESSES)
	if guess.is_empty():
		assert(can_submit_human_guess())
		guess = current_human_guess.duplicate()
	DmbCode.validate_code(guess)
	var fb := DmbFeedback.score_guess(_bot_secret, guess)
	var rec := DmbGuessRecord.new(guess, fb.x, fb.y)
	human_guesses.append(rec)
	current_human_guess = [null, null, null, null]
	if fb.x == DmbConstants.CODE_LENGTH:
		_human_solved = true
		_finish_game()
	elif human_guesses.size() >= DmbConstants.MAX_GUESSES:
		_finish_game()
	return rec


func _finish_game() -> void:
	phase = GamePhase.FINISHED
	result = DmbGameLogic.compute_result(
		_human_solved, _bot_solved,
		human_guesses.size(), bot_guesses.size(),
		human_guesses, bot_guesses
	)


func run_all_bot_guesses() -> Array:
	var records: Array = []
	while phase == GamePhase.BOT_GUESSING:
		var r := bot_make_guess()
		if r == null:
			break
		records.append(r)
	return records

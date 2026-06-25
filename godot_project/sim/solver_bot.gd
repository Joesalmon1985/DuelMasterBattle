class_name DmbSolverBot
extends RefCounted

const OPENING_GUESS := [0, 0, 1, 1]
const STRATEGY_RANDOM := "random"
const STRATEGY_MINIMAX := "minimax"
const MAX_MINIMAX_POOL_HARD := 100
const MAX_MINIMAX_POOL_EXPERT := 500

var _strategy: String = STRATEGY_MINIMAX
var _seed: int = 0
var _candidates: Array = []
var _guess_count: int = 0
var _all_codes: Array = []
var _max_minimax_pool: int = MAX_MINIMAX_POOL_HARD


func _init(strategy: String = STRATEGY_MINIMAX, seed: int = 0, max_minimax_pool: int = MAX_MINIMAX_POOL_HARD) -> void:
	_strategy = strategy
	_seed = seed
	_max_minimax_pool = max_minimax_pool
	_all_codes = _generate_all_codes()
	_reset_candidates()


static func all_code_count() -> int:
	return 10_000


func candidate_count() -> int:
	return _candidates.size()


func register_feedback(guess: Array, exact: int, colour_only: int) -> void:
	var target := Vector2i(exact, colour_only)
	var kept: Array = []
	for c in _candidates:
		var fb := DmbFeedback.score_guess(c, guess)
		if fb == target:
			kept.append(c)
	_candidates = kept


func make_guess() -> Array:
	var guess: Array
	if _guess_count == 0:
		guess = OPENING_GUESS.duplicate()
	elif _strategy == STRATEGY_RANDOM:
		var idx := (_seed + _guess_count) % _candidates.size()
		guess = _candidates[idx].duplicate()
	else:
		guess = _pick_minimax_guess()
	_guess_count += 1
	return _as_int_array(guess)


static func _as_int_array(arr: Array) -> Array:
	var out: Array = []
	for v in arr:
		out.append(int(v))
	return out


func _pick_minimax_guess() -> Array:
	if _candidates.size() == 1:
		return _candidates[0].duplicate()
	var best_guess: Array = []
	var best_worst := 10000
	var best_is_candidate := false
	var pool: Array = _candidates
	if pool.size() > _max_minimax_pool:
		pool = pool.slice(0, _max_minimax_pool)
	for guess in pool:
		var partitions: Dictionary = {}
		for secret in _candidates:
			var fb := DmbFeedback.score_guess(secret, guess)
			var key := "%d,%d" % [fb.x, fb.y]
			partitions[key] = partitions.get(key, 0) + 1
		var worst := 0
		for k in partitions:
			worst = maxi(worst, int(partitions[k]))
		var is_cand := _array_in(guess, _candidates)
		if best_guess.is_empty() \
			or worst < best_worst \
			or (worst == best_worst and is_cand and not best_is_candidate) \
			or (worst == best_worst and is_cand == best_is_candidate and _array_lt(guess, best_guess)):
			best_guess = guess.duplicate()
			best_worst = worst
			best_is_candidate = is_cand
	if best_guess.is_empty():
		return _candidates[0].duplicate()
	return best_guess


func generate_code() -> Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = _seed + 999
	var code: Array = []
	for _i in range(DmbConstants.CODE_LENGTH):
		code.append(rng.randi_range(DmbConstants.MIN_COLOUR, DmbConstants.MAX_COLOUR))
	return code


func is_legal_guess(guess: Array) -> bool:
	return DmbCode.is_valid_code(guess)


func solve_secret(secret: Array, max_guesses: int = 12) -> Dictionary:
	_reset_candidates()
	_guess_count = 0
	var guesses: Array = []
	for _i in range(max_guesses):
		var g := make_guess()
		guesses.append(g)
		var fb := DmbFeedback.score_guess(secret, g)
		if fb.x == DmbConstants.CODE_LENGTH:
			return {"solved": true, "count": guesses.size(), "guesses": guesses}
		register_feedback(g, fb.x, fb.y)
	return {"solved": false, "count": guesses.size(), "guesses": guesses}


func _reset_candidates() -> void:
	_candidates = []
	for c in _all_codes:
		_candidates.append(c.duplicate())


static func _generate_all_codes() -> Array:
	var codes: Array = []
	for a in range(DmbConstants.NUM_COLOURS):
		for b in range(DmbConstants.NUM_COLOURS):
			for c in range(DmbConstants.NUM_COLOURS):
				for d in range(DmbConstants.NUM_COLOURS):
					codes.append([a, b, c, d])
	return codes


static func _array_in(arr: Array, list: Array) -> bool:
	for item in list:
		if _arrays_equal(arr, item):
			return true
	return false


static func _array_lt(a: Array, b: Array) -> bool:
	for i in range(mini(a.size(), b.size())):
		if int(a[i]) < int(b[i]):
			return true
		if int(a[i]) > int(b[i]):
			return false
	return false


static func _arrays_equal(a: Array, b: Array) -> bool:
	if a.size() != b.size():
		return false
	for i in range(a.size()):
		if int(a[i]) != int(b[i]):
			return false
	return true

class_name DmbSolverBot
extends RefCounted

const STRATEGY_RANDOM := "random"
const STRATEGY_MINIMAX := "minimax"
const MAX_MINIMAX_POOL_HARD := 100
const MAX_MINIMAX_POOL_EXPERT := 500

var _ruleset: DmbDuelRuleset
var _strategy: String = STRATEGY_MINIMAX
var _seed: int = 0
var _candidates: Array = []
var _guess_count: int = 0
var _all_codes: Array = []
var _max_minimax_pool: int = MAX_MINIMAX_POOL_HARD


func _init(
	ruleset: DmbDuelRuleset = null,
	strategy: String = STRATEGY_MINIMAX,
	seed: int = 0,
	max_minimax_pool: int = MAX_MINIMAX_POOL_HARD
) -> void:
	_ruleset = ruleset if ruleset != null else DmbEncounters.default_encounter()
	_strategy = strategy
	_seed = seed
	_max_minimax_pool = max_minimax_pool
	_all_codes = DmbCandidateGen.generate_candidate_codes(_ruleset)
	_reset_candidates()


func all_code_count() -> int:
	return _all_codes.size()


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
		guess = DmbCandidateGen.opening_guess_for_ruleset(_ruleset).duplicate()
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
	var pool: Array = _ruleset.secret_magic_pool
	var code: Array = []
	if _ruleset.allow_repeats:
		for _i in range(_ruleset.slot_count):
			code.append(int(pool[rng.randi_range(0, pool.size() - 1)]))
	else:
		var indices: Array = []
		for i in range(pool.size()):
			indices.append(i)
		indices.shuffle()
		for i in range(_ruleset.slot_count):
			code.append(int(pool[indices[i]]))
	return code


func is_legal_guess(guess: Array) -> bool:
	return DmbCode.is_valid_code_for_ruleset(guess, _ruleset, _ruleset.attack_magic_pool)


func solve_secret(secret: Array, max_guesses: int = -1) -> Dictionary:
	if max_guesses < 0:
		max_guesses = _ruleset.effective_max_attacks()
	_reset_candidates()
	_guess_count = 0
	var guesses: Array = []
	for _i in range(max_guesses):
		var g := make_guess()
		guesses.append(g)
		var fb := DmbFeedback.score_guess(secret, g)
		if _ruleset.is_solved(fb.x):
			return {"solved": true, "count": guesses.size(), "guesses": guesses}
		register_feedback(g, fb.x, fb.y)
	return {"solved": false, "count": guesses.size(), "guesses": guesses}


func _reset_candidates() -> void:
	_candidates = []
	for c in _all_codes:
		_candidates.append(c.duplicate())


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

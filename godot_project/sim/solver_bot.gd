class_name DmbSolverBot
extends RefCounted

## Deduction bot for the rival wizard.
##
## Keeps the set of all wards consistent with the feedback it has received and
## always casts one of them ("candidate_filter"), or — for the minimax strategy —
## the consistent guess that best splits the remaining candidates.
##
## Planning is incremental: call `begin_planning()` once per cast window, then
## `think(budget_msec)` each frame until it returns true, then `planned_guess()`.
## This keeps the rival's turn from ever stalling a frame on a phone.
## `make_guess()` remains as a synchronous convenience (tests, sequential sim).

const STRATEGY_RANDOM := "random"
const STRATEGY_MINIMAX := "minimax"
const MAX_MINIMAX_POOL_HARD := 100
const MAX_MINIMAX_POOL_EXPERT := 500

var _ruleset: DmbDuelRuleset
var _strategy: String = STRATEGY_MINIMAX
var _seed: int = 0
var _rng := RandomNumberGenerator.new()
var _candidates: Array = []
var _guess_count: int = 0
var _all_codes: Array = []
var _max_minimax_pool: int = MAX_MINIMAX_POOL_HARD
var _mistake_rate: float = 0.0

# Incremental planning state.
var _planned: Array = []
var _plan_ready: bool = false
var _plan_pool: Array = []
var _plan_index: int = 0
var _plan_best: Array = []
var _plan_best_worst: int = 1 << 30
var _plan_best_is_cand: bool = false


func _init(
	ruleset: DmbDuelRuleset = null,
	strategy: String = STRATEGY_MINIMAX,
	seed: int = 0,
	max_minimax_pool: int = MAX_MINIMAX_POOL_HARD,
	mistake_rate: float = 0.0
) -> void:
	_ruleset = ruleset if ruleset != null else DmbEncounters.default_encounter()
	_strategy = strategy
	_seed = seed
	_rng.seed = seed
	_max_minimax_pool = max_minimax_pool
	_mistake_rate = clampf(mistake_rate, 0.0, 1.0)
	_all_codes = DmbCandidateGen.generate_candidate_codes(_ruleset)
	_reset_candidates()


func all_code_count() -> int:
	return _all_codes.size()


func candidate_count() -> int:
	return _candidates.size()


func guess_count() -> int:
	return _guess_count


## Narrow the candidate set using the feedback for one of our own guesses.
func register_feedback(guess: Array, exact: int, colour_only: int) -> void:
	var target := Vector2i(exact, colour_only)
	var kept: Array = []
	for c in _candidates:
		if DmbFeedback.score_guess(c, guess) == target:
			kept.append(c)
	# A consistent opponent can never empty this set; guard anyway so the bot
	# keeps producing legal guesses if state is ever corrupted.
	if kept.is_empty():
		_reset_candidates()
	else:
		_candidates = kept
	_plan_ready = false
	_planned = []


# --- Incremental planning -------------------------------------------------

func begin_planning() -> void:
	_plan_ready = false
	_planned = []
	if _guess_count == 0:
		_planned = _opening_guess()
		_plan_ready = true
		return
	if _mistake_rate > 0.0 and _rng.randf() < _mistake_rate:
		# "Forgetful" cast: a legal guess that need not be consistent. Keeps the
		# easy rival beatable without ever violating deduction bookkeeping.
		_planned = _random_legal_guess()
		_plan_ready = true
		return
	if _candidates.size() <= 2 or _strategy == STRATEGY_RANDOM:
		_planned = _candidates[_rng.randi_range(0, _candidates.size() - 1)].duplicate()
		_plan_ready = true
		return
	_plan_pool = _candidates.duplicate()
	_plan_pool.shuffle()
	if _plan_pool.size() > _max_minimax_pool:
		_plan_pool = _plan_pool.slice(0, _max_minimax_pool)
	_plan_index = 0
	_plan_best = []
	_plan_best_worst = 1 << 30
	_plan_best_is_cand = false


## Advance planning for at most `budget_msec`. Returns true when a guess is ready.
func think(budget_msec: float = 4.0) -> bool:
	if _plan_ready:
		return true
	if _plan_pool.is_empty():
		begin_planning()
		if _plan_ready:
			return true
	var start := Time.get_ticks_usec()
	var budget_usec := int(budget_msec * 1000.0)
	while _plan_index < _plan_pool.size():
		_evaluate_plan_candidate(_plan_pool[_plan_index])
		_plan_index += 1
		if Time.get_ticks_usec() - start > budget_usec:
			break
	if _plan_index >= _plan_pool.size():
		_planned = _plan_best.duplicate() if not _plan_best.is_empty() else _candidates[0].duplicate()
		_plan_ready = true
	return _plan_ready


func is_plan_ready() -> bool:
	return _plan_ready


## Consume the planned guess. Finishes planning synchronously if needed.
func planned_guess() -> Array:
	if not _plan_ready:
		if _plan_pool.is_empty() and _planned.is_empty():
			begin_planning()
		while not think(1000.0):
			pass
	var g := _as_int_array(_planned)
	_guess_count += 1
	_plan_ready = false
	_planned = []
	_plan_pool = []
	return g


func _evaluate_plan_candidate(guess: Array) -> void:
	var partitions: Dictionary = {}
	for secret in _candidates:
		var fb := DmbFeedback.score_guess(secret, guess)
		var key := fb.x * 16 + fb.y
		partitions[key] = partitions.get(key, 0) + 1
	var worst := 0
	for k in partitions:
		worst = maxi(worst, int(partitions[k]))
	var is_cand := true  # pool is drawn from candidates
	if _plan_best.is_empty() or worst < _plan_best_worst \
		or (worst == _plan_best_worst and is_cand and not _plan_best_is_cand):
		_plan_best = guess.duplicate()
		_plan_best_worst = worst
		_plan_best_is_cand = is_cand


# --- Synchronous API ------------------------------------------------------

func make_guess() -> Array:
	begin_planning()
	return planned_guess()


func _opening_guess() -> Array:
	var pool: Array = _ruleset.attack_magic_pool
	if pool.is_empty():
		return []
	if _ruleset.slot_count == 1 or pool.size() == 1:
		return [int(pool[_rng.randi_range(0, pool.size() - 1)])]
	if not _ruleset.allow_repeats:
		return _random_legal_guess()
	# Two random distinct spells, paired: e.g. A A B B. Good information for
	# repeat-allowed Mastermind and different every duel.
	var a_idx := _rng.randi_range(0, pool.size() - 1)
	var b_idx := (a_idx + 1 + _rng.randi_range(0, pool.size() - 2)) % pool.size()
	var a := int(pool[a_idx])
	var b := int(pool[b_idx])
	var out: Array = []
	for i in range(_ruleset.slot_count):
		out.append(a if i < (_ruleset.slot_count + 1) / 2 else b)
	return out


func _random_legal_guess() -> Array:
	return DmbAutoCast.random_pattern(
		_ruleset.slot_count, _ruleset.attack_magic_pool, _ruleset.allow_repeats, _rng
	)


static func _as_int_array(arr: Array) -> Array:
	var out: Array = []
	for v in arr:
		out.append(int(v))
	return out


func generate_code() -> Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = _seed + 999
	return DmbAutoCast.random_pattern(
		_ruleset.slot_count, _ruleset.secret_magic_pool, _ruleset.allow_repeats, rng
	)


func is_legal_guess(guess: Array) -> bool:
	return DmbCode.is_valid_code_for_ruleset(guess, _ruleset, _ruleset.attack_magic_pool)


## Offline solve used by tests and balance tooling.
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

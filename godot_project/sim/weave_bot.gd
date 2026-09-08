class_name DmbWeaveBot
extends RefCounted

## Deduction AI for asymmetric battles.
##
## Tracks every Ward (ward_pool^ward_size, or permutations) consistent with the
## feedback its own casts received, then chooses an attack of `weave_size` slots:
##   * "random":            a legal random attack, ignores feedback
##   * "candidate_filter":  an attack built by tiling a remaining candidate Ward
##                          across the weave (so every attempt is plausible)
##   * "capped_minimax":    among a capped sample of such attacks, the one that
##                          best splits the remaining candidates
## Planning is incremental (`begin_planning` / `think(msec)` / `planned_guess`).

var combatant: DmbCombatant
var target_ward_size: int = 4
var target_ward_pool: Array = []
var target_allow_repeats: bool = true

var _rng := RandomNumberGenerator.new()
var _all: Array = []
var _candidates: Array = []
var _guess_count: int = 0

var _planned: Array = []
var _plan_ready: bool = false
var _plan_pool: Array = []
var _plan_index: int = 0
var _plan_best: Array = []
var _plan_best_worst: int = 1 << 30


func _init(p_combatant: DmbCombatant, p_target: DmbCombatant, seed: int = 0) -> void:
	combatant = p_combatant
	target_ward_size = p_target.ward_size
	target_ward_pool = p_target.ward_pool.duplicate()
	target_allow_repeats = p_target.allow_repeats
	_rng.seed = seed
	_all = DmbCandidateGen.generate_codes(target_ward_pool, target_ward_size, target_allow_repeats)
	_reset()


func candidate_count() -> int:
	return _candidates.size()


func guess_count() -> int:
	return _guess_count


func register_feedback(attack: Array, fracture: int, echo: int) -> void:
	var kept: Array = []
	for c in _candidates:
		var r := DmbFeedback.score_attack(c, attack)
		if int(r["fracture"]) == fracture and int(r["echo"]) == echo:
			kept.append(c)
	_candidates = kept if not kept.is_empty() else _all_copy()
	_plan_ready = false
	_planned = []


func begin_planning() -> void:
	_plan_ready = false
	_planned = []
	_plan_pool = []
	if combatant.bot_logic == "random" or (combatant.bot_mistake_rate > 0.0 and _rng.randf() < combatant.bot_mistake_rate):
		_planned = _random_attack()
		_plan_ready = true
		return
	if _guess_count == 0:
		_planned = _opening_attack()
		_plan_ready = true
		return
	if _candidates.size() <= 2 or combatant.bot_logic != "capped_minimax":
		_planned = _tile(_candidates[_rng.randi_range(0, _candidates.size() - 1)])
		_plan_ready = true
		return
	var sample := _candidates.duplicate()
	sample.shuffle()
	var cap := maxi(2, combatant.bot_solver_cap)
	if sample.size() > cap:
		sample = sample.slice(0, cap)
	for c in sample:
		_plan_pool.append(_tile(c))
	_plan_index = 0
	_plan_best = []
	_plan_best_worst = 1 << 30


func think(budget_msec: float = 3.0) -> bool:
	if _plan_ready:
		return true
	if _plan_pool.is_empty():
		begin_planning()
		if _plan_ready:
			return true
	var start := Time.get_ticks_usec()
	var budget := int(budget_msec * 1000.0)
	while _plan_index < _plan_pool.size():
		_evaluate(_plan_pool[_plan_index])
		_plan_index += 1
		if Time.get_ticks_usec() - start > budget:
			break
	if _plan_index >= _plan_pool.size():
		_planned = _plan_best.duplicate() if not _plan_best.is_empty() else _tile(_candidates[0])
		_plan_ready = true
	return _plan_ready


func is_plan_ready() -> bool:
	return _plan_ready


func planned_guess() -> Array:
	if not _plan_ready:
		if _plan_pool.is_empty() and _planned.is_empty():
			begin_planning()
		while not think(1000.0):
			pass
	var g := _planned.duplicate()
	_guess_count += 1
	_plan_ready = false
	_planned = []
	_plan_pool = []
	return g


func make_guess() -> Array:
	begin_planning()
	return planned_guess()


func generate_ward() -> Array:
	if not combatant.fixed_ward.is_empty():
		return combatant.fixed_ward.duplicate()
	var rng := RandomNumberGenerator.new()
	rng.seed = _rng.seed + 999
	return DmbAutoCast.random_pattern(combatant.ward_size, combatant.ward_pool, combatant.allow_repeats, rng)


func is_legal_attack(attack: Array) -> bool:
	if attack.size() != combatant.weave_size:
		return false
	for a in attack:
		if not (int(a) in combatant.attack_pool):
			return false
	return true


# --- internals ---------------------------------------------------------------

func _evaluate(attack: Array) -> void:
	var partitions: Dictionary = {}
	for c in _candidates:
		var r := DmbFeedback.score_attack(c, attack)
		var key := int(r["fracture"]) * 32 + int(r["echo"])
		partitions[key] = partitions.get(key, 0) + 1
	var worst := 0
	for k in partitions:
		worst = maxi(worst, int(partitions[k]))
	if _plan_best.is_empty() or worst < _plan_best_worst:
		_plan_best = attack.duplicate()
		_plan_best_worst = worst


## Tile a candidate Ward across this combatant's weave, substituting the nearest
## legal spell when the candidate uses one we cannot cast.
func _tile(ward: Array) -> Array:
	var out: Array = []
	for j in range(combatant.weave_size):
		var s := int(ward[j % ward.size()])
		if not (s in combatant.attack_pool):
			s = int(combatant.attack_pool[_rng.randi_range(0, combatant.attack_pool.size() - 1)])
		out.append(s)
	return out


func _opening_attack() -> Array:
	var pool := combatant.attack_pool
	if pool.size() == 1 or combatant.weave_size == 1:
		return _tile([int(pool[_rng.randi_range(0, pool.size() - 1)])])
	var a_idx := _rng.randi_range(0, pool.size() - 1)
	var b_idx := (a_idx + 1 + _rng.randi_range(0, pool.size() - 2)) % pool.size()
	var out: Array = []
	var half := (combatant.weave_size + 1) / 2
	for j in range(combatant.weave_size):
		out.append(int(pool[a_idx]) if j < half else int(pool[b_idx]))
	return out


func _random_attack() -> Array:
	return DmbAutoCast.random_pattern(combatant.weave_size, combatant.attack_pool, true, _rng)


func _all_copy() -> Array:
	var out: Array = []
	for c in _all:
		out.append(c.duplicate())
	return out


func _reset() -> void:
	_candidates = _all_copy()
	_guess_count = 0

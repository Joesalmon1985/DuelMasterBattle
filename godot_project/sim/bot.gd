class_name DmbRandomBot
extends RefCounted

var _ruleset: DmbDuelRuleset
var _rng: RandomNumberGenerator


func _init(ruleset: DmbDuelRuleset = null, seed: int = 0) -> void:
	_ruleset = ruleset if ruleset != null else DmbEncounters.default_encounter()
	_rng = RandomNumberGenerator.new()
	_rng.seed = seed


func generate_code() -> Array:
	var pool: Array = _ruleset.secret_magic_pool
	var code: Array = []
	if _ruleset.allow_repeats:
		for _i in range(_ruleset.slot_count):
			code.append(int(pool[_rng.randi_range(0, pool.size() - 1)]))
	else:
		var picked: Array = _pick_without_repeats(pool, _ruleset.slot_count)
		code = picked
	return code


func make_guess() -> Array:
	var pool: Array = _ruleset.attack_magic_pool
	if _ruleset.allow_repeats:
		var guess: Array = []
		for _i in range(_ruleset.slot_count):
			guess.append(int(pool[_rng.randi_range(0, pool.size() - 1)]))
		return guess
	return _pick_without_repeats(pool, _ruleset.slot_count)


func _pick_without_repeats(pool: Array, count: int) -> Array:
	var indices: Array = []
	for i in range(pool.size()):
		indices.append(i)
	indices.shuffle()
	var out: Array = []
	for i in range(count):
		out.append(int(pool[indices[i]]))
	return out


func register_feedback(_guess: Array, _exact: int, _colour_only: int) -> void:
	pass


func is_legal_guess(guess: Array) -> bool:
	return DmbCode.is_valid_code_for_ruleset(guess, _ruleset, _ruleset.attack_magic_pool)

class_name DmbRandomBot
extends RefCounted

var _rng: RandomNumberGenerator


func _init(seed: int = 0) -> void:
	_rng = RandomNumberGenerator.new()
	_rng.seed = seed


func generate_code() -> Array:
	var code: Array = []
	for _i in range(DmbConstants.CODE_LENGTH):
		code.append(_rng.randi_range(DmbConstants.MIN_COLOUR, DmbConstants.MAX_COLOUR))
	return code


func make_guess() -> Array:
	return generate_code()


func is_legal_guess(guess: Array) -> bool:
	return DmbCode.is_valid_code(guess)

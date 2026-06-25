class_name DmbCode
extends RefCounted

class CodeValidationError:
	extends RefCounted
	var message: String
	func _init(msg: String) -> void:
		message = msg


static func validate_colour(colour: int) -> void:
	if colour < DmbConstants.MIN_COLOUR or colour > DmbConstants.MAX_COLOUR:
		push_error("colour out of range")
		assert(false, "colour must be %d-%d, got %d" % [DmbConstants.MIN_COLOUR, DmbConstants.MAX_COLOUR, colour])


static func validate_code(code: Array) -> void:
	validate_code_length(code, DmbConstants.CODE_LENGTH)


static func validate_code_length(code: Array, length: int) -> void:
	if code.size() != length:
		assert(false, "code must have length %d, got %d" % [length, code.size()])
	for i in range(code.size()):
		validate_colour(int(code[i]))


static func validate_colour_in_pool(colour: int, pool: Array) -> void:
	validate_colour(colour)
	for p in pool:
		if int(p) == colour:
			return
	assert(false, "colour %d not in allowed pool" % colour)


static func validate_code_for_ruleset(code: Array, ruleset: DmbDuelRuleset, pool: Array) -> void:
	validate_code_length(code, ruleset.slot_count)
	for i in range(code.size()):
		var c := int(code[i])
		var ok := false
		for p in pool:
			if int(p) == c:
				ok = true
				break
		assert(ok, "colour at index %d not in allowed pool" % i)


static func is_valid_code(code: Array) -> bool:
	if code.size() != DmbConstants.CODE_LENGTH:
		return false
	for c in code:
		var col := int(c)
		if col < DmbConstants.MIN_COLOUR or col > DmbConstants.MAX_COLOUR:
			return false
	return true


static func is_valid_code_for_ruleset(code: Array, ruleset: DmbDuelRuleset, pool: Array) -> bool:
	if code.size() != ruleset.slot_count:
		return false
	for c in code:
		var col := int(c)
		if col < DmbConstants.MIN_COLOUR or col > DmbConstants.MAX_COLOUR:
			return false
		var ok := false
		for p in pool:
			if int(p) == col:
				ok = true
				break
		if not ok:
			return false
	return true

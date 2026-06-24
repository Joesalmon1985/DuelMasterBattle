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
	if code.size() != DmbConstants.CODE_LENGTH:
		assert(false, "code must have length %d, got %d" % [DmbConstants.CODE_LENGTH, code.size()])
	for i in range(code.size()):
		validate_colour(int(code[i]))


static func is_valid_code(code: Array) -> bool:
	if code.size() != DmbConstants.CODE_LENGTH:
		return false
	for c in code:
		var col := int(c)
		if col < DmbConstants.MIN_COLOUR or col > DmbConstants.MAX_COLOUR:
			return false
	return true

extends HBoxContainer
class_name FeedbackDisplay

const _Art = preload("res://client/scripts/art.gd")

var _guess_label: Label
var _feedback_label: Label


func _ready() -> void:
	_guess_label = Label.new()
	_guess_label.name = "GuessLabel"
	add_child(_guess_label)
	_feedback_label = Label.new()
	_feedback_label.name = "FeedbackLabel"
	add_child(_feedback_label)


func show_guess(guess: Array, exact: int, colour_only: int) -> void:
	if _guess_label == null:
		_ready()
	var parts: PackedStringArray = []
	for c in guess:
		var id := int(c)
		parts.append("%s" % DmbColourData.SYMBOLS[id])
	_guess_label.text = "[%s]" % " ".join(parts)
	var unaffected := DmbConstants.CODE_LENGTH - exact - colour_only
	_feedback_label.text = "● Hit:%d  ○ Weakness:%d  - Unaffected:%d" % [exact, colour_only, unaffected]
	_feedback_label.tooltip_text = (
		"Hit = correct magic, correct point. "
		+ "Weakness = correct magic, wrong point. "
		+ "Unaffected = no matching weakness revealed."
	)

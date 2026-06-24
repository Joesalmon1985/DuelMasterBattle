extends HBoxContainer
class_name FeedbackDisplay

@onready var _guess_label: Label = $GuessLabel
@onready var _feedback_label: Label = $FeedbackLabel


func _ready() -> void:
	if not has_node("GuessLabel"):
		_guess_label = Label.new()
		_guess_label.name = "GuessLabel"
		add_child(_guess_label)
	if not has_node("FeedbackLabel"):
		_feedback_label = Label.new()
		_feedback_label.name = "FeedbackLabel"
		add_child(_feedback_label)


func show_guess(guess: Array, exact: int, colour_only: int) -> void:
	var parts: PackedStringArray = []
	for c in guess:
		parts.append(str(c))
	_guess_label.text = "[%s]" % " ".join(parts)
	_feedback_label.text = "●%d ○%d" % [exact, colour_only]

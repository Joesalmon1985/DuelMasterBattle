extends Button
class_name PegSlot

signal slot_pressed(slot_index: int)

@export var slot_index: int = 0

var _colour_id: int = -1


func _ready() -> void:
	custom_minimum_size = Vector2(48, 48)
	text = "?"
	pressed.connect(_on_pressed)


func _on_pressed() -> void:
	slot_pressed.emit(slot_index)


func set_colour(colour_id: int) -> void:
	_colour_id = colour_id
	if colour_id < 0:
		text = "?"
		modulate = Color.WHITE
	else:
		text = str(colour_id)
		modulate = DmbColourData.COLOURS[colour_id]


func get_colour_id() -> int:
	return _colour_id


func set_hidden_mode(hidden_text: String = "****") -> void:
	text = hidden_text
	modulate = Color.DARK_GRAY
	disabled = true

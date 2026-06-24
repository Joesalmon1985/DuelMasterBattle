extends Button
class_name PegSlot

signal slot_pressed(slot_index: int)

@export var slot_index: int = 0
@export var point_label: String = ""

var _colour_id: int = -1


func _ready() -> void:
	custom_minimum_size = Vector2(56, 56)
	text = "?"
	tooltip_text = "Empty slot"
	pressed.connect(_on_pressed)


func _on_pressed() -> void:
	slot_pressed.emit(slot_index)


func set_colour(colour_id: int) -> void:
	_colour_id = colour_id
	if colour_id < 0:
		text = "?"
		tooltip_text = "Empty slot — click to choose magic"
		modulate = Color.WHITE
	else:
		var name: String = DmbColourData.NAMES[colour_id]
		var sym: String = DmbColourData.SYMBOLS[colour_id]
		text = "%s\n%d" % [sym, colour_id]
		var point: String = point_label
		if point == "" and slot_index < DmbColourData.POINT_NAMES.size():
			point = DmbColourData.POINT_NAMES[slot_index]
		tooltip_text = "%s: %d %s (%s)" % [point, colour_id, name, sym]
		modulate = DmbColourData.COLOURS[colour_id]


func get_colour_id() -> int:
	return _colour_id


func set_hidden_mode(hidden_text: String = "****") -> void:
	text = hidden_text
	modulate = Color.DARK_GRAY
	disabled = true

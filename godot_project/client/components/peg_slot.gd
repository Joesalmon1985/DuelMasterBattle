extends Button
class_name PegSlot

const _VT = preload("res://client/scripts/visual_theme.gd")
const _LocusSocket = preload("res://client/components/locus_socket.gd")

## Compatibility wrapper — composes LocusSocket for legacy slot_pressed API.

signal slot_pressed(slot_index: int)

@export var slot_index: int = 0
@export var point_label: String = ""

var _socket

func _ready() -> void:
	flat = true
	text = ""
	custom_minimum_size = Vector2(_VT.TOUCH_ESSENCE, _VT.TOUCH_ESSENCE + 20)
	_socket = _LocusSocket.new()
	_socket.set_anchors_preset(Control.PRESET_FULL_RECT)
	_socket.slot_index = slot_index
	_socket.locus_name = point_label
	add_child(_socket)
	_socket.socket_pressed.connect(func(idx): slot_pressed.emit(idx))


func set_colour(colour_id: int) -> void:
	_socket.set_colour(colour_id)


func get_colour_id() -> int:
	return _socket.get_colour_id()


func set_hidden_mode(hidden_text: String = "•••") -> void:
	_socket.set_hidden_mode(hidden_text)


func get_locus_socket():
	return _socket

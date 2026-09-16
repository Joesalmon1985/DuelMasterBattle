extends Control
class_name DmbScenarioPanel

@export var release_mode: bool = false

var _seed_edit: LineEdit
var _visible_in_dev := true


func _ready() -> void:
	if release_mode:
		visible = false
		_visible_in_dev = false
		return
	_seed_edit = LineEdit.new()
	_seed_edit.text = "7"
	_seed_edit.placeholder_text = "seed"
	add_child(_seed_edit)


func is_developer_controls_visible() -> bool:
	return _visible_in_dev and not release_mode

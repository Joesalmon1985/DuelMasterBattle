extends Control
class_name WorldInteractionLabel

## One anchored semantic interaction surface. This slice is LABEL only:
## it shows the resolver's current label, follows its entity and the camera,
## and can be tapped. It does not observe, speak, move John, or touch quests.

const _Resolver = preload("res://sim/world/world_interaction_resolver.gd")
const _VT = preload("res://client/scripts/visual_theme.gd")

signal activated(knowledge_key: String)

const STATE_LABEL := "LABEL"

var _semantic: Dictionary = {}
var _entity_id := ""
var _anchor: Node2D
var _adv: Node
var _camera: Camera2D
var _offset := Vector2.ZERO
var _button: Button
var _tracked_world := Vector2.ZERO
var _press_frame := -1


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_button = Button.new()
	_button.focus_mode = Control.FOCUS_NONE
	_button.mouse_filter = Control.MOUSE_FILTER_STOP
	_button.custom_minimum_size = Vector2(148, 48)
	_VT.style_secondary_button(_button)
	_button.pressed.connect(press)
	_button.gui_input.connect(_on_button_gui)
	add_child(_button)


func bind(adv: Node, semantic: Dictionary, entity_id: String, anchor: Node2D, camera: Camera2D, offset: Vector2) -> void:
	_adv = adv
	_semantic = semantic.duplicate(true)
	_entity_id = entity_id
	_anchor = anchor
	_camera = camera
	_offset = offset
	if adv != null and not adv.state_changed.is_connected(_on_state_changed):
		adv.state_changed.connect(_on_state_changed)
	refresh()
	_follow()


func knowledge_key() -> String:
	return str(_semantic.get("knowledge_key", ""))


func entity_id() -> String:
	return _entity_id


func display_text() -> String:
	return _button.text if _button != null else ""


func interaction_state() -> String:
	return STATE_LABEL


func tracked_world_position() -> Vector2:
	return _tracked_world


func screen_anchor() -> Vector2:
	if _camera == null or not is_instance_valid(_camera):
		return _tracked_world
	var center := _camera.get_screen_center_position()
	var view := get_viewport().get_visible_rect().size
	return (_tracked_world - center) * _camera.zoom + view * 0.5


## Production tap. The button uses this path for both mouse and emulated touch,
## matching TouchPad. Tests may call it directly.
func press() -> void:
	if _press_frame == Engine.get_process_frames():
		return
	_press_frame = Engine.get_process_frames()
	activated.emit(knowledge_key())


func _on_button_gui(event: InputEvent) -> void:
	# TouchPad listens for mouse. This button also accepts a raw screen touch
	# so a device with mouse emulation off still focuses the semantic entity.
	# Same-frame mouse emulation must not activate twice.
	if event is InputEventScreenTouch and event.pressed:
		press()
		_button.accept_event()


func refresh() -> void:
	if _button == null or _adv == null:
		return
	var resolved: Dictionary = _Resolver.resolve(_semantic, _adv)
	_button.text = str(resolved.get("label", ""))


func _on_state_changed() -> void:
	refresh()


func _process(_delta: float) -> void:
	_follow()


func _follow() -> void:
	if not is_instance_valid(_anchor):
		return
	_tracked_world = _anchor.global_position + _offset
	var screen := screen_anchor()
	var w := _button.size.x if _button != null and _button.size.x > 1.0 else 148.0
	var h := _button.size.y if _button != null and _button.size.y > 1.0 else 48.0
	global_position = screen - Vector2(w * 0.5, h)


func _exit_tree() -> void:
	if _adv != null and is_instance_valid(_adv) and _adv.state_changed.is_connected(_on_state_changed):
		_adv.state_changed.disconnect(_on_state_changed)

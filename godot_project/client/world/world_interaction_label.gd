extends Control
class_name WorldInteractionLabel

## One anchored semantic interaction surface.
## LABEL, OBSERVATION, SPEECH and RESPONSES are states of this control.
## It presents lines and choices. It does not decide quest consequences.

const _Resolver = preload("res://sim/world/world_interaction_resolver.gd")
const _VT = preload("res://client/scripts/visual_theme.gd")

signal activated(knowledge_key: String)
signal interact_requested(knowledge_key: String)
signal response_chosen(knowledge_key: String, index: int)
signal conversation_dismissed(knowledge_key: String)

const STATE_LABEL := "LABEL"
const STATE_OBSERVATION := "OBSERVATION"
const STATE_SPEECH := "SPEECH"
const STATE_RESPONSES := "RESPONSES"

var _state := STATE_LABEL

var _semantic: Dictionary = {}
var _entity_id := ""
var _anchor: Node2D
var _adv: Node
var _camera: Camera2D
var _offset := Vector2.ZERO
var _button: Button
var _responses: VBoxContainer
var _response_buttons: Array = []
var _speech_lines: Array = []
var _speech_index := 0
var _pending_options: Array = []
var _selected_response := -1
var _tracked_world := Vector2.ZERO
var _press_frame := -1


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_button = Button.new()
	_button.focus_mode = Control.FOCUS_NONE
	_button.mouse_filter = Control.MOUSE_FILTER_STOP
	_button.custom_minimum_size = Vector2(280, 72)
	_button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_VT.style_secondary_button(_button)
	_button.pressed.connect(press)
	_button.gui_input.connect(_on_button_gui)
	add_child(_button)
	_responses = VBoxContainer.new()
	_responses.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_responses.visible = false
	_responses.add_theme_constant_override("separation", 6)
	add_child(_responses)


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
	return _state


func selected_response() -> int:
	return _selected_response


func response_labels() -> Array:
	var out: Array = []
	for raw in _response_buttons:
		if is_instance_valid(raw):
			out.append(str(raw.text))
	return out


func tracked_world_position() -> Vector2:
	return _tracked_world


func screen_anchor() -> Vector2:
	if _camera == null or not is_instance_valid(_camera):
		return _tracked_world
	var center := _camera.get_screen_center_position()
	var view := get_viewport().get_visible_rect().size
	return (_tracked_world - center) * _camera.zoom + view * 0.5


func screen_rect() -> Rect2:
	if _button != null and _button.size.x > 1.0 and _button.size.y > 1.0:
		return _button.get_global_rect()
	var screen := screen_anchor()
	return Rect2(screen - Vector2(140, 72), Vector2(280, 72))


## Production tap. The button uses this path for both mouse and emulated touch,
## matching TouchPad. Tests may call it directly. A speech tap advances one
## beat. A response is chosen only by press_response().
func press() -> void:
	if _press_frame == Engine.get_process_frames():
		return
	_press_frame = Engine.get_process_frames()
	if _state == STATE_SPEECH:
		_advance_speech()
		activated.emit(knowledge_key())
		return
	if _state == STATE_RESPONSES:
		activated.emit(knowledge_key())
		return
	if _state == STATE_OBSERVATION:
		collapse()
		activated.emit(knowledge_key())
		return
	interact_requested.emit(knowledge_key())
	activated.emit(knowledge_key())


func open_observation() -> void:
	_clear_responses()
	_show_observation()


func begin_speech(lines: Array, options_after: Array = []) -> void:
	_clear_responses()
	_speech_lines = []
	for raw in lines:
		var text := str(raw).strip_edges()
		if text != "":
			_speech_lines.append(text)
	_speech_index = 0
	_pending_options = options_after.duplicate(true)
	if _speech_lines.is_empty():
		if _pending_options.is_empty():
			collapse()
		else:
			_show_responses(_pending_options)
			_pending_options = []
		return
	_state = STATE_SPEECH
	_button.visible = true
	_button.text = str(_speech_lines[0])


func press_response(index: int) -> void:
	if _state != STATE_RESPONSES:
		return
	if _press_frame == Engine.get_process_frames():
		return
	var found := false
	for raw in _response_buttons:
		if is_instance_valid(raw) and int(raw.get_meta("index")) == index:
			found = true
			break
	if not found:
		return
	_press_frame = Engine.get_process_frames()
	_selected_response = index
	_clear_responses()
	response_chosen.emit(knowledge_key(), index)
	activated.emit(knowledge_key())


func notify_player_moved() -> void:
	var resolved: Dictionary = _Resolver.resolve(_semantic, _adv)
	if bool(resolved.get("dismiss_on_move", true)):
		collapse()


func collapse() -> void:
	var was_talking := _state == STATE_SPEECH or _state == STATE_RESPONSES
	_clear_conversation()
	_selected_response = -1
	_state = STATE_LABEL
	if _button != null:
		_button.visible = true
	refresh()
	if was_talking:
		conversation_dismissed.emit(knowledge_key())


func _show_observation() -> void:
	var resolved: Dictionary = _Resolver.resolve(_semantic, _adv, false)
	_state = STATE_OBSERVATION
	if _button != null:
		_button.visible = true
		_button.text = str(resolved.get("observe_far", ""))


func _advance_speech() -> void:
	if _speech_index + 1 < _speech_lines.size():
		_speech_index += 1
		_button.text = str(_speech_lines[_speech_index])
		return
	if not _pending_options.is_empty():
		var options := _pending_options
		_pending_options = []
		_show_responses(options)
		return
	collapse()


func _show_responses(options: Array) -> void:
	_clear_responses()
	_state = STATE_RESPONSES
	_selected_response = -1
	if _button != null:
		_button.visible = false
	_responses.visible = true
	for raw in options:
		if not (raw is Dictionary):
			continue
		var option: Dictionary = raw
		var button := Button.new()
		button.focus_mode = Control.FOCUS_NONE
		button.mouse_filter = Control.MOUSE_FILTER_STOP
		button.custom_minimum_size = Vector2(280, 72)
		button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		button.clip_text = false
		button.text = str(option.get("label", ""))
		button.set_meta("index", int(option.get("index", _response_buttons.size())))
		_VT.style_secondary_button(button)
		button.pressed.connect(_on_response_pressed.bind(button))
		button.gui_input.connect(_on_response_gui.bind(button))
		_responses.add_child(button)
		_response_buttons.append(button)
	if _response_buttons.is_empty():
		collapse()


func _on_response_pressed(button: Button) -> void:
	press_response(int(button.get_meta("index")))


func _on_response_gui(event: InputEvent, button: Button) -> void:
	if event is InputEventScreenTouch and event.pressed:
		press_response(int(button.get_meta("index")))
		button.accept_event()


func _clear_conversation() -> void:
	_speech_lines = []
	_speech_index = 0
	_pending_options = []
	_clear_responses()


func _clear_responses() -> void:
	for raw in _response_buttons:
		if is_instance_valid(raw):
			raw.queue_free()
	_response_buttons.clear()
	if _responses != null:
		_responses.visible = false


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
	if _state != STATE_LABEL:
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
	var w := 280.0
	var h := 72.0
	if _state == STATE_RESPONSES and not _response_buttons.is_empty():
		h = float(_response_buttons.size()) * 78.0
	elif _button != null and _button.size.x > 1.0 and _button.size.y > 1.0:
		w = _button.size.x
		h = _button.size.y
	global_position = screen - Vector2(w * 0.5, h)


func _exit_tree() -> void:
	if _adv != null and is_instance_valid(_adv) and _adv.state_changed.is_connected(_on_state_changed):
		_adv.state_changed.disconnect(_on_state_changed)

extends HBoxContainer
class_name EssenceTray

const _VT = preload("res://client/scripts/visual_theme.gd")
const _EssenceToken = preload("res://client/components/essence_token.gd")
const _PlayabilityHaptics = preload("res://client/scripts/playability_haptics.gd")

signal essence_selected(essence_id: int)
signal essence_drag_started(essence_id: int, global_pos: Vector2)
signal essence_drag_moved(global_pos: Vector2)
signal essence_drag_ended(global_pos: Vector2)

var _tokens: Array = []
var _allowed: Dictionary = {}
var _highlighted: bool = false
var _drag_id: int = -1
var _drag_start: Vector2 = Vector2.ZERO
var _drag_active: bool = false
var _busy: bool = false


func _ready() -> void:
	alignment = BoxContainer.ALIGNMENT_CENTER
	add_theme_constant_override("separation", _VT.SLOT_SEPARATION)
	for i in range(DmbConstants.NUM_COLOURS):
		var token := _EssenceToken.new()
		token.visible = false
		add_child(token)
		_tokens.append(token)
		var idx := i
		token.gui_input.connect(func(ev): _on_token_input(idx, ev))


func set_allowed_magics(pool: Array) -> void:
	_allowed.clear()
	for m in pool:
		_allowed[int(m)] = true
	for i in range(_tokens.size()):
		var token = _tokens[i]
		var show := _allowed.has(i)
		token.visible = show
		if show:
			token.set_essence(i)
		else:
			token.set_essence(-1)


func set_highlighted(on: bool) -> void:
	_highlighted = on
	for token in _tokens:
		if token.visible:
			token.modulate = Color(1.25, 1.2, 1.0) if on else Color.WHITE


func set_busy(on: bool) -> void:
	_busy = on
	for token in _tokens:
		if token.has_method("set_disabled_overlay"):
			token.set_disabled_overlay(on)


func get_token_global_rect(essence_id: int) -> Rect2:
	if essence_id < 0 or essence_id >= _tokens.size():
		return Rect2()
	var token = _tokens[essence_id]
	return token.get_global_rect()


func _on_token_input(essence_id: int, event: InputEvent) -> void:
	if _busy or not _allowed.has(essence_id):
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			_drag_id = essence_id
			_drag_start = event.position
			_drag_active = false
		else:
			if _drag_active:
				essence_drag_ended.emit(event.global_position)
				_drag_active = false
				_drag_id = -1
			elif _drag_start.distance_to(event.position) < _VT.DRAG_THRESHOLD_PX:
				essence_selected.emit(essence_id)
				_PlayabilityHaptics.pulse_light()
			_drag_id = -1
	elif event is InputEventMouseMotion and _drag_id >= 0:
		if not _drag_active and event.position.distance_to(_drag_start) >= _VT.DRAG_THRESHOLD_PX:
			_drag_active = true
			essence_drag_started.emit(_drag_id, event.global_position)
		if _drag_active:
			essence_drag_moved.emit(event.global_position)

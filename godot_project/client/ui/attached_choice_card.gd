extends PanelContainer
class_name DmbAttachedChoiceCard

## World-anchored contextual choice card (Observe / Buff… / Destroy / Challenge).

signal action_chosen(action_id: String, payload: Dictionary)
signal closed()

const MIN_TOUCH := 48.0

var _target_id: String = ""
var _title: Label
var _body: VBoxContainer
var _follow: Node2D
var _camera: Camera2D


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 8)
	margin.add_theme_constant_override("margin_right", 8)
	margin.add_theme_constant_override("margin_top", 6)
	margin.add_theme_constant_override("margin_bottom", 6)
	add_child(margin)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 6)
	margin.add_child(col)
	_title = Label.new()
	_title.add_theme_font_size_override("font_size", 14)
	_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	col.add_child(_title)
	_body = VBoxContainer.new()
	_body.add_theme_constant_override("separation", 4)
	col.add_child(_body)
	visible = false


func open_for(target_id: String, title: String, actions: Array, follow: Node2D = null) -> void:
	_target_id = target_id
	_follow = follow
	_title.text = title
	for c in _body.get_children():
		c.queue_free()
	for action_any in actions:
		var action: Dictionary = action_any
		var btn := Button.new()
		btn.text = str(action.get("label", action.get("id", "?")))
		btn.custom_minimum_size = Vector2(160, MIN_TOUCH)
		var aid := str(action.get("id", ""))
		var payload: Dictionary = action.duplicate(true)
		btn.pressed.connect(func():
			action_chosen.emit(aid, payload)
		)
		_body.add_child(btn)
	var close_btn := Button.new()
	close_btn.text = "Close"
	close_btn.custom_minimum_size = Vector2(160, MIN_TOUCH)
	close_btn.pressed.connect(close)
	_body.add_child(close_btn)
	visible = true
	_clamp_to_viewport()


func open_buff_submenu(target_id: String, title: String, follow: Node2D = null) -> void:
	open_for(target_id, title, [
		{"id": "buff_shield", "label": "Shield", "buff_kind": "shield"},
		{"id": "buff_frequency", "label": "Attack speed", "buff_kind": "frequency"},
		{"id": "buff_range", "label": "Range", "buff_kind": "range"},
		{"id": "back", "label": "Back"},
	], follow)


func close() -> void:
	visible = false
	_target_id = ""
	_follow = null
	closed.emit()


func target_id() -> String:
	return _target_id


func _process(_delta: float) -> void:
	if not visible or _follow == null or not is_instance_valid(_follow):
		return
	var gp: Vector2 = _follow.get_global_transform_with_canvas().origin
	position = gp + Vector2(24, -80)
	_clamp_to_viewport()


func _clamp_to_viewport() -> void:
	var vr := get_viewport().get_visible_rect()
	var sz := size
	if sz == Vector2.ZERO:
		sz = Vector2(180, 160)
	position.x = clampf(position.x, vr.position.x + 8.0, vr.position.x + vr.size.x - sz.x - 8.0)
	position.y = clampf(position.y, vr.position.y + 8.0, vr.position.y + vr.size.y - sz.y - 8.0)

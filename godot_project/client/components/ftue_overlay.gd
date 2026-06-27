extends Control
class_name FtueOverlay

const _VT = preload("res://client/scripts/visual_theme.gd")

signal step_completed(step_id: String)

var _arrow: Label
var _hint: Label
var _glow: ColorRect
var _active_step: String = ""


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	visible = false
	_glow = ColorRect.new()
	_glow.color = Color(_VT.COLOR_ACCENT_GOLD.r, _VT.COLOR_ACCENT_GOLD.g, _VT.COLOR_ACCENT_GOLD.b, 0.18)
	_glow.visible = false
	_glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_glow)
	_arrow = Label.new()
	_arrow.text = "▼"
	_arrow.add_theme_font_size_override("font_size", 36)
	_arrow.add_theme_color_override("font_color", _VT.COLOR_ACCENT_GOLD)
	_arrow.visible = false
	_arrow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_arrow)
	_hint = Label.new()
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_VT.apply_label_secondary(_hint)
	_hint.add_theme_font_size_override("font_size", _VT.FONT_CAPTION)
	_hint.visible = false
	_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_hint)


func show_step(step_id: String, target: Control, hint_text: String = "") -> void:
	if target == null or not is_instance_valid(target):
		hide_step()
		return
	_active_step = step_id
	visible = true
	var rect := target.get_global_rect()
	_glow.visible = true
	_glow.global_position = rect.position - Vector2(8, 8)
	_glow.size = rect.size + Vector2(16, 16)
	_arrow.visible = true
	_arrow.global_position = Vector2(rect.position.x + rect.size.x * 0.5 - 16, rect.position.y - 40)
	if hint_text != "":
		_hint.visible = true
		_hint.text = hint_text
		_hint.custom_minimum_size = Vector2(minf(280, rect.size.x + 80), 0)
		_hint.global_position = Vector2(
			rect.position.x + rect.size.x * 0.5 - _hint.custom_minimum_size.x * 0.5,
			_arrow.global_position.y - 36
		)
	else:
		_hint.visible = false


func complete_step(step_id: String) -> void:
	if _active_step != step_id:
		return
	step_completed.emit(step_id)
	hide_step()


func hide_step() -> void:
	_active_step = ""
	visible = false
	_glow.visible = false
	_arrow.visible = false
	_hint.visible = false


func get_active_step() -> String:
	return _active_step

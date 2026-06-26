extends Control
class_name CastTimer
const _VT = preload("res://client/scripts/visual_theme.gd")

const _Art = preload("res://client/scripts/art.gd")

var progress: float = 0.0
var warning: bool = false

var _ring: TextureRect
var _fill: ColorRect
var _label: Label


func _ready() -> void:
	custom_minimum_size = Vector2(72, 72)
	_ring = TextureRect.new()
	_ring.set_anchors_preset(Control.PRESET_FULL_RECT)
	_ring.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_ring.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_ring.texture = _Art.load_texture(_Art.ui_chrome_path("timer_ring"))
	_ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_ring)
	_fill = ColorRect.new()
	_fill.set_anchors_preset(Control.PRESET_FULL_RECT)
	_fill.offset_left = 8
	_fill.offset_top = 8
	_fill.offset_right = -8
	_fill.offset_bottom = -8
	_fill.color = _VT.COLOR_ACCENT_GOLD
	_fill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_fill)
	_label = Label.new()
	_label.set_anchors_preset(Control.PRESET_CENTER)
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(_label)
	_label.add_theme_font_size_override("font_size", _VT.FONT_CAPTION)
	add_child(_label)


func set_progress(ratio: float, label_text: String = "") -> void:
	progress = clampf(ratio, 0.0, 1.0)
	_fill.scale.y = progress
	_fill.pivot_offset = Vector2(_fill.size.x * 0.5, _fill.size.y)
	_label.text = label_text
	if warning:
		_fill.color = Color(1.0, 0.45, 0.4)
	else:
		_fill.color = _VT.COLOR_ACCENT_GOLD


func set_warning(on: bool) -> void:
	warning = on
	set_progress(progress, _label.text)

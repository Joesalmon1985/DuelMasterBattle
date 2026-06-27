extends Control
class_name CastTimer
const _VT = preload("res://client/scripts/visual_theme.gd")

const _Art = preload("res://client/scripts/art.gd")

var progress: float = 0.0
var warning: bool = false
var tier_seconds: float = 999.0

var _ring: TextureRect
var _fill: ColorRect
var _label: Label
var _pulse_tween: Tween


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
	_fill.color = _VT.COLOR_ACCENT_CYAN
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
	_apply_fill_color()


func set_warning(on: bool) -> void:
	warning = on
	_apply_fill_color()
	if on and (_pulse_tween == null or not _pulse_tween.is_valid()):
		_pulse_tween = create_tween().set_loops()
		_pulse_tween.tween_property(_fill, "modulate", Color(1.3, 0.8, 0.8), 0.25)
		_pulse_tween.tween_property(_fill, "modulate", Color.WHITE, 0.25)
	elif not on:
		if _pulse_tween != null and _pulse_tween.is_valid():
			_pulse_tween.kill()
		_pulse_tween = null
		_fill.modulate = Color.WHITE


func set_tier_seconds(seconds_left: float) -> void:
	tier_seconds = seconds_left
	_apply_fill_color()


func _apply_fill_color() -> void:
	if warning or tier_seconds <= 3.0:
		_fill.color = Color(1.0, 0.45, 0.35)
	elif tier_seconds <= 5.0:
		_fill.color = Color(1.0, 0.72, 0.35)
	elif progress >= 0.99:
		_fill.color = _VT.COLOR_ACCENT_GOLD
	else:
		_fill.color = _VT.COLOR_ACCENT_CYAN

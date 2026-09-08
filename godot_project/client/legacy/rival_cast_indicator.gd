extends Control
class_name RivalCastIndicator

const _VT = preload("res://client/scripts/visual_theme.gd")
const _Art = preload("res://client/scripts/art.gd")

var _ring: TextureRect
var _fill: ColorRect
var _pulse_tween: Tween


func _ready() -> void:
	custom_minimum_size = Vector2(48, 48)
	_ring = TextureRect.new()
	_ring.set_anchors_preset(Control.PRESET_FULL_RECT)
	_ring.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_ring.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_ring.texture = _Art.load_texture(_Art.ui_chrome_path("timer_ring"))
	_ring.modulate = Color(0.7, 0.85, 1.0)
	_ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_ring)
	_fill = ColorRect.new()
	_fill.set_anchors_preset(Control.PRESET_FULL_RECT)
	_fill.offset_left = 6
	_fill.offset_top = 6
	_fill.offset_right = -6
	_fill.offset_bottom = -6
	_fill.color = _VT.COLOR_ACCENT_CYAN
	_fill.scale.y = 0.0
	_fill.pivot_offset = Vector2(18, 36)
	_fill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_fill)


func set_progress(ratio: float, casting: bool) -> void:
	var r := clampf(ratio, 0.0, 1.0)
	_fill.scale.y = r
	visible = casting or r > 0.01
	if casting and (_pulse_tween == null or not _pulse_tween.is_valid()):
		_start_pulse()
	elif not casting:
		_stop_pulse()
		modulate = Color.WHITE


func _start_pulse() -> void:
	_stop_pulse()
	_pulse_tween = create_tween().set_loops()
	_pulse_tween.tween_property(self, "modulate", Color(1.2, 1.3, 1.5), 0.4)
	_pulse_tween.tween_property(self, "modulate", Color.WHITE, 0.4)


func _stop_pulse() -> void:
	if _pulse_tween != null and _pulse_tween.is_valid():
		_pulse_tween.kill()
	_pulse_tween = null

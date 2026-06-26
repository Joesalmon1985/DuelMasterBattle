extends Button
class_name CastButton
const _VT = preload("res://client/scripts/visual_theme.gd")

const _Art = preload("res://client/scripts/art.gd")

signal cast_pressed

var _ready_glow: bool = false
var _warning: bool = false
var _pulse_tween: Tween


func _ready() -> void:
	custom_minimum_size = Vector2(_VT.TOUCH_CAST, _VT.TOUCH_CAST)
	text = "Cast"
	add_theme_font_size_override("font_size", _VT.FONT_BUTTON)
	add_theme_color_override("font_color", _VT.COLOR_TEXT_PRIMARY)
	_apply_style(false)
	pressed.connect(func(): cast_pressed.emit())


func _apply_style(pressed_state: bool) -> void:
	var tex := _Art.load_texture(_Art.ui_chrome_path("button_gem_pressed" if pressed_state else "button_gem"))
	if tex != null:
		icon = tex
		expand_icon = true
		text = ""
	add_theme_stylebox_override("normal", _VT.gem_button_style(false))
	add_theme_stylebox_override("hover", _VT.gem_button_style(false))
	add_theme_stylebox_override("pressed", _VT.gem_button_style(true))
	add_theme_stylebox_override("disabled", _VT.secondary_button_style())


func set_cast_ready(on: bool) -> void:
	_ready_glow = on
	if on and not disabled:
		_start_pulse(Color(1.2, 1.1, 0.7))
	else:
		_stop_pulse()
		modulate = Color.WHITE


func set_auto_cast_warning(on: bool) -> void:
	_warning = on
	if on and not disabled:
		_start_pulse(Color(1.4, 0.7, 0.6))
	elif not _ready_glow:
		_stop_pulse()


func _start_pulse(tint: Color) -> void:
	_stop_pulse()
	_pulse_tween = create_tween().set_loops()
	_pulse_tween.tween_property(self, "modulate", tint, 0.35)
	_pulse_tween.tween_property(self, "modulate", Color.WHITE, 0.35)


func _stop_pulse() -> void:
	if _pulse_tween != null and _pulse_tween.is_valid():
		_pulse_tween.kill()
	_pulse_tween = null


func bounce_press() -> void:
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector2(0.92, 0.92), _VT.DUR_BUTTON_PRESS * 0.5)
	tw.tween_property(self, "scale", Vector2.ONE, _VT.DUR_BUTTON_PRESS * 0.5)

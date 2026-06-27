extends Button
class_name CastButton
const _VT = preload("res://client/scripts/visual_theme.gd")

const _Art = preload("res://client/scripts/art.gd")
const _PlayabilityHaptics = preload("res://client/scripts/playability_haptics.gd")

signal cast_pressed

enum CastVisualState { DISABLED, CHARGING, READY, WARN_5, WARN_3, WARN_1 }

var _visual_state: CastVisualState = CastVisualState.DISABLED
var _pulse_tween: Tween
var _ready_flash_done: bool = false


func _ready() -> void:
	custom_minimum_size = Vector2(_VT.TOUCH_CAST, _VT.TOUCH_CAST)
	text = "Cast"
	add_theme_font_size_override("font_size", _VT.FONT_BUTTON)
	add_theme_color_override("font_color", _VT.COLOR_TEXT_PRIMARY)
	_apply_chrome(false)
	pressed.connect(_on_pressed)


func _on_pressed() -> void:
	cast_pressed.emit()
	_PlayabilityHaptics.pulse_medium()


func _apply_chrome(pressed_state: bool) -> void:
	var tex := _Art.load_texture(_Art.ui_chrome_path("button_gem_pressed" if pressed_state else "button_gem"))
	if tex != null:
		icon = tex
		expand_icon = true
		text = ""


func set_visual_state(state: CastVisualState) -> void:
	if _visual_state == state and state != CastVisualState.READY:
		return
	var prev := _visual_state
	_visual_state = state
	match state:
		CastVisualState.DISABLED:
			_apply_style_grey()
			_stop_pulse()
			modulate = Color(0.75, 0.75, 0.85)
		CastVisualState.CHARGING:
			_apply_style_grey()
			_start_pulse(Color(1.0, 1.0, 1.15), 0.55)
		CastVisualState.READY:
			_apply_style_gold()
			if prev != CastVisualState.READY:
				_ready_flash_done = false
				_flash_ready()
				_PlayabilityHaptics.pulse_medium()
			else:
				_start_pulse(Color(1.15, 1.05, 0.75), 0.45)
		CastVisualState.WARN_5:
			_apply_style_gold()
			_start_pulse(Color(1.2, 1.0, 0.65), 0.28)
		CastVisualState.WARN_3:
			_apply_style_gold()
			_start_pulse(Color(1.35, 0.75, 0.55), 0.22)
			_PlayabilityHaptics.pulse_warning()
		CastVisualState.WARN_1:
			_apply_style_gold()
			_start_pulse(Color(1.5, 0.55, 0.45), 0.14)


func set_cast_ready(on: bool) -> void:
	if on and not disabled:
		set_visual_state(CastVisualState.READY)
	elif _visual_state == CastVisualState.READY:
		set_visual_state(CastVisualState.CHARGING if not disabled else CastVisualState.DISABLED)


func set_auto_cast_warning(on: bool) -> void:
	if on and not disabled:
		set_visual_state(CastVisualState.WARN_3)
	elif _visual_state in [CastVisualState.WARN_5, CastVisualState.WARN_3, CastVisualState.WARN_1]:
		set_visual_state(CastVisualState.READY if not disabled else CastVisualState.DISABLED)


func set_auto_cast_tier(seconds_left: float) -> void:
	if disabled:
		set_visual_state(CastVisualState.DISABLED)
		return
	if seconds_left <= 1.0:
		set_visual_state(CastVisualState.WARN_1)
	elif seconds_left <= 3.0:
		set_visual_state(CastVisualState.WARN_3)
	elif seconds_left <= 5.0:
		set_visual_state(CastVisualState.WARN_5)
	else:
		set_visual_state(CastVisualState.DISABLED)


func bounce_press() -> void:
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector2(0.92, 0.92), _VT.DUR_BUTTON_PRESS * 0.5)
	tw.tween_property(self, "scale", Vector2.ONE, _VT.DUR_BUTTON_PRESS * 0.5)


func _apply_style_grey() -> void:
	add_theme_stylebox_override("normal", _VT.gem_button_style(false))
	add_theme_stylebox_override("hover", _VT.gem_button_style(false))
	add_theme_stylebox_override("pressed", _VT.gem_button_style(true))
	add_theme_stylebox_override("disabled", _VT.secondary_button_style())
	_apply_chrome(false)


func _apply_style_gold() -> void:
	var s := _VT.gem_button_style(false)
	s.bg_color = Color("#5a4a18")
	s.border_color = _VT.COLOR_ACCENT_GOLD
	s.border_width_top = 4
	s.border_width_bottom = 4
	s.border_width_left = 4
	s.border_width_right = 4
	add_theme_stylebox_override("normal", s)
	add_theme_stylebox_override("hover", s)
	add_theme_stylebox_override("pressed", _VT.gem_button_style(true))
	add_theme_stylebox_override("disabled", _VT.secondary_button_style())
	_apply_chrome(false)


func _flash_ready() -> void:
	_stop_pulse()
	modulate = Color(1.4, 1.25, 0.85)
	var tw := create_tween()
	tw.tween_property(self, "modulate", Color.WHITE, 0.18)
	tw.tween_callback(func(): _start_pulse(Color(1.15, 1.05, 0.75), 0.45))


func _start_pulse(tint: Color, duration: float) -> void:
	_stop_pulse()
	_pulse_tween = create_tween().set_loops()
	_pulse_tween.tween_property(self, "modulate", tint, duration)
	_pulse_tween.tween_property(self, "modulate", Color.WHITE, duration)


func _stop_pulse() -> void:
	if _pulse_tween != null and _pulse_tween.is_valid():
		_pulse_tween.kill()
	_pulse_tween = null


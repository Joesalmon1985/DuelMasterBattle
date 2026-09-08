extends Control
class_name TouchPad

## On-screen D-pad (bottom-left) and action button (bottom-right) for phones.
## Emits direction_changed while a direction is held and action_pressed on tap.

const _VT = preload("res://client/scripts/visual_theme.gd")

signal direction_changed(dir: Vector2i)
signal action_pressed

const PAD_SIZE := 210.0
const BTN := 70.0

var _pad: Control
var _action: Button
var _dir: Vector2i = Vector2i.ZERO
var _enabled: bool = true
var _pointer: int = -1


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_pad = _Pad.new()
	_pad.owner_pad = self
	_pad.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	_pad.offset_left = 24
	_pad.offset_top = -PAD_SIZE - 40
	_pad.offset_right = 24 + PAD_SIZE
	_pad.offset_bottom = -40
	_pad.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_pad)
	_action = Button.new()
	_action.text = "✦"
	_action.focus_mode = Control.FOCUS_NONE
	_action.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_action.offset_left = -24 - 120
	_action.offset_right = -24
	_action.offset_top = -40 - 120 - 40
	_action.offset_bottom = -40 - 40
	var s := _VT.gem_button_style()
	s.set_corner_radius_all(60)
	_action.add_theme_stylebox_override("normal", s)
	_action.add_theme_stylebox_override("hover", s)
	var sp := _VT.gem_button_style(true)
	sp.set_corner_radius_all(60)
	_action.add_theme_stylebox_override("pressed", sp)
	var sd := _VT.disabled_button_style()
	sd.set_corner_radius_all(60)
	_action.add_theme_stylebox_override("disabled", sd)
	_action.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	_action.add_theme_font_size_override("font_size", 40)
	_action.add_theme_color_override("font_color", _VT.COLOR_ACCENT_GOLD)
	_action.pressed.connect(func():
		if _enabled:
			action_pressed.emit()
	)
	add_child(_action)


func set_enabled(on: bool) -> void:
	_enabled = on
	_action.disabled = not on
	_pad.modulate.a = 1.0 if on else 0.45
	if not on and _dir != Vector2i.ZERO:
		_dir = Vector2i.ZERO
		direction_changed.emit(_dir)


func set_action_label(text: String) -> void:
	_action.text = text if text != "" else "✦"
	_action.modulate = Color.WHITE if text != "" else Color(0.7, 0.7, 0.8)


func _set_dir(d: Vector2i) -> void:
	if d != _dir:
		_dir = d
		_pad.queue_redraw()
		if _enabled:
			direction_changed.emit(_dir)


class _Pad:
	extends Control
	var owner_pad
	var _down: bool = false

	func _gui_input(event: InputEvent) -> void:
		if event is InputEventMouseButton:
			if event.button_index == MOUSE_BUTTON_LEFT:
				_down = event.pressed
				if _down:
					owner_pad._set_dir(_dir_from(event.position))
				else:
					owner_pad._set_dir(Vector2i.ZERO)
		elif event is InputEventMouseMotion and _down:
			owner_pad._set_dir(_dir_from(event.position))

	func _dir_from(p: Vector2) -> Vector2i:
		var c := size * 0.5
		var d := p - c
		if d.length() < size.x * 0.12:
			return Vector2i.ZERO
		if absf(d.x) > absf(d.y):
			return Vector2i(signi(int(d.x)), 0)
		return Vector2i(0, signi(int(d.y)))

	func _draw() -> void:
		var c := size * 0.5
		var r := size.x * 0.5
		draw_circle(c, r, Color(0.08, 0.06, 0.14, 0.55))
		draw_arc(c, r - 2, 0, TAU, 48, Color(0.42, 0.36, 0.7, 0.8), 3.0, true)
		var arm := r * 0.55
		var w := r * 0.34
		var active: Vector2i = owner_pad._dir
		for d in [Vector2i(0, -1), Vector2i(0, 1), Vector2i(-1, 0), Vector2i(1, 0)]:
			var col := Color(0.55, 0.5, 0.85, 0.35)
			if d == active:
				col = Color(1.0, 0.79, 0.28, 0.85)
			var centre := c + Vector2(d) * arm
			var rect := Rect2(centre - Vector2(w, w) * 0.5, Vector2(w, w))
			draw_rect(rect, col, true)
			# arrow glyph
			var tip := centre + Vector2(d) * w * 0.28
			var base := centre - Vector2(d) * w * 0.18
			var perp := Vector2(-d.y, d.x) * w * 0.25
			draw_colored_polygon(PackedVector2Array([tip, base + perp, base - perp]), Color(0.1, 0.08, 0.16, 0.9))

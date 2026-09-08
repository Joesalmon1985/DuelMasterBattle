extends Control
class_name CastButton

## The big cast button. Draws its own circular timer ring so "when can I cast"
## and "how long do I have" live in one place under the thumb.
##
## States:
##   CHARGING  – window locked; ring fills gold, label counts down "Ready in 3"
##   BLOCKED   – window open but guess incomplete; label tells the player why
##   READY     – castable; gold glow, label "CAST"
##   WARNING   – ready and < 10 s to auto-cast; red pulse, label counts down
##   DISABLED  – not dueling / no casts left

const _VT = preload("res://client/scripts/visual_theme.gd")
const _PlayabilityHaptics = preload("res://client/scripts/playability_haptics.gd")

signal cast_pressed
signal blocked_pressed

enum State { DISABLED, CHARGING, BLOCKED, READY, WARNING }

var state: int = State.DISABLED
var charge_ratio: float = 0.0       # 0..1 progress toward the window opening
var remaining_ratio: float = 1.0    # 1..0 time left before auto-cast (only when open)
var seconds_text: String = ""
var hint_text: String = ""

var _button: Button
var _main_lbl: Label
var _sub_lbl: Label
var _pulse: Tween
var _was_ready: bool = false


func _ready() -> void:
	custom_minimum_size = Vector2(_VT.TOUCH_CAST_RING, _VT.TOUCH_CAST_RING)
	_button = Button.new()
	_button.focus_mode = Control.FOCUS_NONE
	_button.set_anchors_preset(Control.PRESET_FULL_RECT)
	_button.add_theme_stylebox_override("normal", StyleBoxEmpty.new())
	_button.add_theme_stylebox_override("hover", StyleBoxEmpty.new())
	_button.add_theme_stylebox_override("pressed", StyleBoxEmpty.new())
	_button.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	_button.add_theme_stylebox_override("disabled", StyleBoxEmpty.new())
	_button.pressed.connect(_on_pressed)
	add_child(_button)
	_main_lbl = Label.new()
	_main_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_main_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_main_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_main_lbl.add_theme_font_size_override("font_size", 30)
	_main_lbl.add_theme_color_override("font_color", _VT.COLOR_TEXT_PRIMARY)
	add_child(_main_lbl)
	_sub_lbl = Label.new()
	_sub_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_sub_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_sub_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_sub_lbl.add_theme_font_size_override("font_size", _VT.FONT_CAPTION)
	_sub_lbl.add_theme_color_override("font_color", _VT.COLOR_TEXT_SECONDARY)
	add_child(_sub_lbl)
	resized.connect(_layout)
	_layout()


func _layout() -> void:
	_main_lbl.position = Vector2(0, size.y * 0.5 - 30)
	_main_lbl.size = Vector2(size.x, 40)
	_sub_lbl.position = Vector2(0, size.y * 0.5 + 8)
	_sub_lbl.size = Vector2(size.x, 22)


func _on_pressed() -> void:
	if state == State.READY or state == State.WARNING:
		cast_pressed.emit()
		_PlayabilityHaptics.pulse_medium()
		bounce()
	else:
		blocked_pressed.emit()
		shake()


func set_state(new_state: int, p_charge: float, p_remaining: float, p_seconds: String, p_hint: String) -> void:
	var became_ready := (new_state == State.READY or new_state == State.WARNING) and not _was_ready
	_was_ready = new_state == State.READY or new_state == State.WARNING
	var changed := new_state != state
	state = new_state
	charge_ratio = clampf(p_charge, 0.0, 1.0)
	remaining_ratio = clampf(p_remaining, 0.0, 1.0)
	seconds_text = p_seconds
	hint_text = p_hint
	_button.disabled = state == State.DISABLED
	match state:
		State.READY:
			_main_lbl.text = "CAST"
			_sub_lbl.text = seconds_text
		State.WARNING:
			_main_lbl.text = "CAST"
			_sub_lbl.text = seconds_text
		State.CHARGING:
			_main_lbl.text = seconds_text
			_sub_lbl.text = "weaving"
		State.BLOCKED:
			_main_lbl.text = "CAST"
			_sub_lbl.text = hint_text
		_:
			_main_lbl.text = ""
			_sub_lbl.text = hint_text
	if changed:
		_apply_pulse()
	if became_ready:
		_flash_ready()
		_PlayabilityHaptics.pulse_medium()
	queue_redraw()


func _apply_pulse() -> void:
	if _pulse != null and _pulse.is_valid():
		_pulse.kill()
	_pulse = null
	modulate = Color.WHITE
	match state:
		State.READY:
			_pulse = create_tween().set_loops()
			_pulse.tween_property(self, "modulate", Color(1.12, 1.08, 0.9), 0.6)
			_pulse.tween_property(self, "modulate", Color.WHITE, 0.6)
		State.WARNING:
			_pulse = create_tween().set_loops()
			_pulse.tween_property(self, "modulate", Color(1.35, 0.85, 0.8), 0.22)
			_pulse.tween_property(self, "modulate", Color.WHITE, 0.22)
		State.DISABLED:
			modulate = Color(0.7, 0.7, 0.78)


func _flash_ready() -> void:
	pivot_offset = size * 0.5
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector2(1.1, 1.1), 0.1)
	tw.tween_property(self, "scale", Vector2.ONE, 0.16).set_trans(Tween.TRANS_BACK)


func bounce() -> void:
	pivot_offset = size * 0.5
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector2(0.92, 0.92), 0.06)
	tw.tween_property(self, "scale", Vector2.ONE, 0.1)


func shake() -> void:
	var base := position
	var tw := create_tween()
	tw.tween_property(self, "position:x", base.x + 6, 0.04)
	tw.tween_property(self, "position:x", base.x - 6, 0.04)
	tw.tween_property(self, "position:x", base.x, 0.04)


func _draw() -> void:
	var c := size * 0.5
	var r := minf(size.x, size.y) * 0.5 - 4
	var ring_w := r * 0.16
	# base disc
	var disc_col := Color("#2a2350")
	var border_col := Color("#4a3f7a")
	match state:
		State.READY:
			disc_col = Color("#4a3a12")
			border_col = _VT.COLOR_ACCENT_GOLD
		State.WARNING:
			disc_col = Color("#4a1a1a")
			border_col = Color("#ff6b6b")
		State.BLOCKED:
			disc_col = Color("#2a2350")
			border_col = _VT.COLOR_ACCENT_GOLD.darkened(0.35)
		State.DISABLED:
			disc_col = Color("#1b1633")
			border_col = Color("#3a3160")
	draw_circle(c, r, disc_col)
	# track
	draw_arc(c, r - ring_w * 0.5, 0, TAU, 64, Color(0, 0, 0, 0.35), ring_w, true)
	# progress ring
	var start := -PI * 0.5
	match state:
		State.CHARGING:
			draw_arc(c, r - ring_w * 0.5, start, start + TAU * charge_ratio, 64, _VT.COLOR_ACCENT_CYAN, ring_w, true)
		State.BLOCKED, State.READY, State.WARNING:
			var col := _VT.COLOR_ACCENT_GOLD if state != State.WARNING else Color("#ff6b6b")
			if remaining_ratio > 0.001:
				draw_arc(c, r - ring_w * 0.5, start, start + TAU * remaining_ratio, 64, col, ring_w, true)
	# outer border
	draw_arc(c, r, 0, TAU, 64, border_col, 3.0, true)

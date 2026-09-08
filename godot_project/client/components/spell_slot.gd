extends Button
class_name SpellSlot

## A touch-friendly button showing one spell (essence) — or an empty locus.
## Used for the spell tray, the ward/attack loci and the rival's hidden ward.
##
## Visual states: empty / filled / selected (gold ring) / hidden ("?") / dim.

const _VT = preload("res://client/scripts/visual_theme.gd")
const _Art = preload("res://client/scripts/art.gd")

signal slot_tapped(slot_index: int)

@export var slot_index: int = -1
@export var caption: String = ""
@export var slot_size: float = 84.0

var spell_id: int = -1
var selected_ring: bool = false
var hidden_mode: bool = false
var dim: bool = false
var wrong_hint: bool = false

var _icon: TextureRect
var _caption_lbl: Label
var _qmark: Label
var _pulse_tween: Tween


func _ready() -> void:
	focus_mode = Control.FOCUS_NONE
	custom_minimum_size = Vector2(slot_size, slot_size + (22 if caption != "" else 0))
	text = ""
	clip_contents = false
	_apply_styles()
	_icon = TextureRect.new()
	_icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	add_child(_icon)
	_qmark = Label.new()
	_qmark.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_qmark.text = "?"
	_qmark.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_qmark.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_qmark.add_theme_font_size_override("font_size", int(slot_size * 0.5))
	_qmark.add_theme_color_override("font_color", _VT.COLOR_TEXT_SECONDARY)
	_qmark.visible = false
	add_child(_qmark)
	_caption_lbl = Label.new()
	_caption_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_caption_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_caption_lbl.add_theme_font_size_override("font_size", 17 if slot_size >= 80 else 15)
	_caption_lbl.add_theme_color_override("font_color", _VT.COLOR_TEXT_SECONDARY)
	_caption_lbl.text = caption
	_caption_lbl.visible = caption != ""
	add_child(_caption_lbl)
	pressed.connect(func(): slot_tapped.emit(slot_index))
	resized.connect(_layout)
	_layout()
	_refresh()


func _layout() -> void:
	var s := minf(size.x, slot_size)
	var icon_px := s * 0.78
	var top := (slot_size - icon_px) * 0.5
	_icon.position = Vector2((size.x - icon_px) * 0.5, top)
	_icon.size = Vector2(icon_px, icon_px)
	_qmark.position = Vector2(0, 0)
	_qmark.size = Vector2(size.x, slot_size)
	_caption_lbl.position = Vector2(0, slot_size - 4)
	_caption_lbl.size = Vector2(size.x, 22)


func _apply_styles() -> void:
	add_theme_stylebox_override("normal", _style(false))
	add_theme_stylebox_override("hover", _style(false))
	add_theme_stylebox_override("pressed", _style(true))
	add_theme_stylebox_override("disabled", _style(false))
	add_theme_stylebox_override("focus", StyleBoxEmpty.new())


func _style(pressed_state: bool) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.set_corner_radius_all(int(slot_size * 0.22))
	s.content_margin_bottom = 0
	if hidden_mode:
		s.bg_color = Color("#241d40")
		s.border_color = Color("#4a3f7a")
		s.set_border_width_all(2)
	elif spell_id >= 0:
		s.bg_color = Color("#2a2350") if not pressed_state else Color("#1c1838")
		s.border_color = DmbColourData.essence_colour(spell_id).lerp(Color.WHITE, 0.15)
		s.set_border_width_all(3)
	else:
		s.bg_color = Color("#1b1633") if not pressed_state else Color("#14102a")
		s.border_color = Color("#4a3f7a")
		s.set_border_width_all(2)
	if selected_ring:
		s.border_color = _VT.COLOR_ACCENT_GOLD
		s.set_border_width_all(4)
		s.shadow_color = Color(_VT.COLOR_ACCENT_GOLD.r, _VT.COLOR_ACCENT_GOLD.g, _VT.COLOR_ACCENT_GOLD.b, 0.45)
		s.shadow_size = 8
	if wrong_hint:
		s.border_color = Color("#ff6b6b")
		s.set_border_width_all(3)
	# Only round/border the icon square, not the caption strip below it.
	s.expand_margin_bottom = -(size.y - slot_size) if size.y > slot_size else 0.0
	return s


func set_spell(id: int) -> void:
	spell_id = id
	hidden_mode = false
	_refresh()


func set_hidden() -> void:
	spell_id = -1
	hidden_mode = true
	_refresh()


func set_selected(on: bool) -> void:
	if selected_ring == on:
		return
	selected_ring = on
	_refresh()
	if on:
		_start_pulse()
	else:
		_stop_pulse()


func set_dim(on: bool) -> void:
	dim = on
	_refresh()


func set_caption(text_value: String) -> void:
	caption = text_value
	if _caption_lbl:
		_caption_lbl.text = text_value
		_caption_lbl.visible = text_value != ""
	custom_minimum_size = Vector2(slot_size, slot_size + (22 if caption != "" else 0))


func flash_wrong() -> void:
	wrong_hint = true
	_refresh()
	var tw := create_tween()
	tw.tween_interval(0.35)
	tw.tween_callback(func():
		wrong_hint = false
		_refresh()
	)


func pop() -> void:
	pivot_offset = Vector2(size.x * 0.5, slot_size * 0.5)
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector2(1.12, 1.12), 0.08)
	tw.tween_property(self, "scale", Vector2.ONE, 0.12).set_trans(Tween.TRANS_BACK)


func _refresh() -> void:
	if _icon == null:
		return
	_apply_styles()
	if hidden_mode:
		_icon.texture = null
		_icon.visible = false
		_qmark.visible = true
		tooltip_text = "Hidden — deduce this spell"
	elif spell_id >= 0:
		_icon.texture = _Art.load_texture(_Art.magic_icon_path(spell_id))
		_icon.visible = true
		_qmark.visible = false
		tooltip_text = "%s (%s)" % [DmbColourData.essence_name(spell_id), DmbColourData.SHAPE_NAMES[spell_id]]
	else:
		_icon.texture = null
		_icon.visible = false
		_qmark.visible = false
		tooltip_text = "Empty — tap a spell to fill"
	modulate = Color(0.55, 0.55, 0.62) if dim else Color.WHITE


func _start_pulse() -> void:
	_stop_pulse()
	_pulse_tween = create_tween().set_loops()
	_pulse_tween.tween_property(self, "modulate", Color(1.12, 1.1, 1.0), 0.5)
	_pulse_tween.tween_property(self, "modulate", Color.WHITE, 0.5)


func _stop_pulse() -> void:
	if _pulse_tween != null and _pulse_tween.is_valid():
		_pulse_tween.kill()
	_pulse_tween = null
	modulate = Color(0.55, 0.55, 0.62) if dim else Color.WHITE

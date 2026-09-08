extends Button
class_name LocusSocket

const _VT = preload("res://client/scripts/visual_theme.gd")
const _Art = preload("res://client/scripts/art.gd")
const _EssenceToken = preload("res://client/components/essence_token.gd")

signal socket_pressed(slot_index: int)
signal socket_clear_requested(slot_index: int)
signal socket_long_press(slot_index: int)

@export var slot_index: int = 0
@export var locus_name: String = ""

var _colour_id: int = -1
var _token_host: Control
var _token
var _rune_icon: TextureRect
var _name_lbl: Label
var _clear_btn: Button
var _peek_panel: PanelContainer
var _peek_lbl: Label
var _auto_fill: bool = false
var _selected: bool = false
var _busy: bool = false
var _drop_highlight: bool = false
var _press_ms: int = 0
var _long_press_fired: bool = false


func _ready() -> void:
	custom_minimum_size = Vector2(_VT.TOUCH_ESSENCE, _VT.TOUCH_ESSENCE + 20)
	flat = true
	add_theme_stylebox_override("normal", _VT.panel_style())
	add_theme_stylebox_override("hover", _VT.panel_style())
	add_theme_stylebox_override("pressed", _VT.gem_button_style(true))
	add_theme_stylebox_override("disabled", _VT.secondary_button_style())
	text = ""
	button_down.connect(_on_button_down)
	button_up.connect(_on_button_up)
	var vbox := VBoxContainer.new()
	vbox.set_anchors_preset(Control.PRESET_FULL_RECT)
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_theme_constant_override("separation", 4)
	vbox.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(vbox)
	_rune_icon = TextureRect.new()
	_rune_icon.custom_minimum_size = Vector2(28, 28)
	_rune_icon.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
	_rune_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_rune_icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vbox.add_child(_rune_icon)
	_token_host = Control.new()
	_token_host.custom_minimum_size = Vector2(56, 56)
	_token_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vbox.add_child(_token_host)
	_token = _EssenceToken.new()
	_token.set_anchors_preset(Control.PRESET_CENTER)
	_token_host.add_child(_token)
	_name_lbl = Label.new()
	_name_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(_name_lbl)
	_name_lbl.add_theme_font_size_override("font_size", _VT.FONT_CAPTION)
	_name_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vbox.add_child(_name_lbl)
	_clear_btn = Button.new()
	_clear_btn.text = "✕"
	_clear_btn.custom_minimum_size = Vector2(24, 24)
	_clear_btn.add_theme_font_size_override("font_size", 14)
	_clear_btn.add_theme_stylebox_override("normal", _VT.secondary_button_style())
	_clear_btn.visible = false
	_clear_btn.pressed.connect(_on_clear_pressed)
	add_child(_clear_btn)
	_clear_btn.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_clear_btn.offset_left = -28
	_clear_btn.offset_top = -4
	_clear_btn.offset_right = -4
	_clear_btn.offset_bottom = 20
	_peek_panel = PanelContainer.new()
	_peek_panel.visible = false
	_peek_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_peek_panel.add_theme_stylebox_override("panel", _VT.panel_style())
	add_child(_peek_panel)
	_peek_lbl = Label.new()
	_VT.apply_label_primary(_peek_lbl)
	_peek_lbl.add_theme_font_size_override("font_size", _VT.FONT_SECONDARY)
	_peek_panel.add_child(_peek_lbl)
	_refresh_rune()


func _process(_delta: float) -> void:
	if _press_ms > 0 and not _long_press_fired:
		_press_ms += int(_delta * 1000.0)
		if _press_ms >= _VT.LONG_PRESS_MS:
			_long_press_fired = true
			_show_peek()
			socket_long_press.emit(slot_index)


func _on_button_down() -> void:
	if disabled or _busy:
		return
	_press_ms = 1
	_long_press_fired = false


func _on_button_up() -> void:
	if disabled or _busy:
		return
	if not _long_press_fired:
		socket_pressed.emit(slot_index)
	_hide_peek()
	_press_ms = 0


func _on_clear_pressed() -> void:
	socket_clear_requested.emit(slot_index)


func set_locus(index: int, name: String) -> void:
	slot_index = index
	locus_name = name
	_name_lbl.text = name
	_refresh_rune()


func _refresh_rune() -> void:
	var path := _Art.locus_rune_path(slot_index, _colour_id >= 0)
	var tex := _Art.load_texture(path)
	if tex == null:
		tex = _Art.load_texture(_Art.locus_icon_path(slot_index))
	_rune_icon.texture = tex


func set_colour(colour_id: int) -> void:
	_colour_id = colour_id
	if colour_id < 0:
		_token.set_essence(-1)
		_clear_btn.visible = false
		tooltip_text = "Empty locus — tap to choose essence"
	else:
		_token.set_essence(colour_id)
		_clear_btn.visible = not disabled and not _busy
		tooltip_text = "%s: %s" % [locus_name, DmbColourData.NAMES[colour_id]]
	_refresh_rune()


func get_colour_id() -> int:
	return _colour_id


func is_hidden_mode() -> bool:
	return disabled and _name_lbl.text == "•••"


func set_hidden_mode(hidden_text: String = "•••") -> void:
	_token.set_essence(-1)
	_name_lbl.text = hidden_text
	disabled = true
	_clear_btn.visible = false
	modulate = Color(0.6, 0.6, 0.7)


func set_auto_filled(on: bool) -> void:
	_auto_fill = on
	if on:
		modulate = Color(1.2, 1.0, 0.8)


func set_selected(on: bool) -> void:
	_selected = on
	_apply_highlight()


func set_busy(on: bool) -> void:
	_busy = on
	if on:
		disabled = true
		_clear_btn.visible = false
	else:
		disabled = is_hidden_mode()
		if _colour_id >= 0:
			_clear_btn.visible = not disabled
	_apply_highlight()


func set_drop_highlight(on: bool) -> void:
	_drop_highlight = on
	_apply_highlight()


func _apply_highlight() -> void:
	if _busy:
		modulate = Color(0.75, 0.75, 0.85)
	elif _drop_highlight:
		modulate = Color(1.2, 1.35, 1.5)
	elif _selected:
		modulate = Color(1.15, 1.15, 1.35)
	elif _auto_fill:
		modulate = Color(1.2, 1.0, 0.8)
	elif not is_hidden_mode():
		modulate = Color.WHITE


func pulse() -> void:
	if _busy:
		return
	var tw := create_tween()
	tw.tween_property(self, "modulate", Color(1.3, 1.3, 1.5), 0.12)
	tw.tween_property(self, "modulate", Color.WHITE, 0.18)


func shake() -> void:
	var tw := create_tween()
	var base := position
	tw.tween_property(self, "position:x", base.x + 6, 0.05)
	tw.tween_property(self, "position:x", base.x - 6, 0.05)
	tw.tween_property(self, "position:x", base.x, 0.05)


func _show_peek() -> void:
	if _colour_id < 0:
		_peek_lbl.text = "%s — empty" % locus_name
	else:
		_peek_lbl.text = "%s: %s" % [locus_name, DmbColourData.NAMES[_colour_id]]
	_peek_panel.visible = true
	_peek_panel.global_position = global_position + Vector2(-8, -size.y - 48)


func _hide_peek() -> void:
	_peek_panel.visible = false

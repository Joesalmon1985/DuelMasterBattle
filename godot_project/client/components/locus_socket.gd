extends Button
class_name LocusSocket

const _VT = preload("res://client/scripts/visual_theme.gd")
const _Art = preload("res://client/scripts/art.gd")
const _EssenceToken = preload("res://client/components/essence_token.gd")

signal socket_pressed(slot_index: int)

@export var slot_index: int = 0
@export var locus_name: String = ""

var _colour_id: int = -1
var _token_host: Control
var _token
var _rune_icon: TextureRect
var _name_lbl: Label
var _auto_fill: bool = false


func _ready() -> void:
	custom_minimum_size = Vector2(_VT.TOUCH_ESSENCE, _VT.TOUCH_ESSENCE + 20)
	flat = true
	add_theme_stylebox_override("normal", _VT.panel_style())
	add_theme_stylebox_override("hover", _VT.panel_style())
	add_theme_stylebox_override("pressed", _VT.gem_button_style(true))
	add_theme_stylebox_override("disabled", _VT.secondary_button_style())
	text = ""
	pressed.connect(_on_pressed)
	var vbox := VBoxContainer.new()
	vbox.set_anchors_preset(Control.PRESET_FULL_RECT)
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_theme_constant_override("separation", 4)
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
	vbox.add_child(_name_lbl)
	_refresh_rune()


func _on_pressed() -> void:
	socket_pressed.emit(slot_index)


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
		tooltip_text = "Empty locus — tap to choose essence"
	else:
		_token.set_essence(colour_id)
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
	modulate = Color(0.6, 0.6, 0.7)


func set_auto_filled(on: bool) -> void:
	_auto_fill = on
	if on:
		modulate = Color(1.2, 1.0, 0.8)


func pulse() -> void:
	var tw := create_tween()
	tw.tween_property(self, "modulate", Color(1.3, 1.3, 1.5), 0.12)
	tw.tween_property(self, "modulate", Color.WHITE, 0.18)


func shake() -> void:
	var tw := create_tween()
	var base := position
	tw.tween_property(self, "position:x", base.x + 6, 0.05)
	tw.tween_property(self, "position:x", base.x - 6, 0.05)
	tw.tween_property(self, "position:x", base.x, 0.05)

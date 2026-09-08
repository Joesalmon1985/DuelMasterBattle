extends Control
class_name EssenceToken
const _VT = preload("res://client/scripts/visual_theme.gd")

const _Art = preload("res://client/scripts/art.gd")

signal token_pressed(essence_id: int)

var essence_id: int = -1
var _core: TextureRect
var _glow: TextureRect
var _frame: PanelContainer
var _label: Label
var _disabled_overlay: ColorRect


func _ready() -> void:
	custom_minimum_size = Vector2(_VT.TOUCH_ESSENCE, _VT.TOUCH_ESSENCE)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_frame = PanelContainer.new()
	_frame.set_anchors_preset(Control.PRESET_FULL_RECT)
	_frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := _VT.gem_button_style()
	style.bg_color = Color(0.15, 0.12, 0.28, 0.9)
	_frame.add_theme_stylebox_override("panel", style)
	add_child(_frame)
	_glow = TextureRect.new()
	_glow.set_anchors_preset(Control.PRESET_FULL_RECT)
	_glow.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_glow.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_glow.modulate = Color(1, 1, 1, 0.35)
	add_child(_glow)
	_core = TextureRect.new()
	_core.set_anchors_preset(Control.PRESET_CENTER)
	_core.custom_minimum_size = Vector2(48, 48)
	_core.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
	_core.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_core.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_core)
	_label = Label.new()
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	_label.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	_label.offset_top = -18
	_VT.apply_label_secondary(_label)
	_label.add_theme_font_size_override("font_size", _VT.FONT_CAPTION)
	add_child(_label)
	_disabled_overlay = ColorRect.new()
	_disabled_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_disabled_overlay.color = Color(0, 0, 0, 0.55)
	_disabled_overlay.visible = false
	_disabled_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_disabled_overlay)
	gui_input.connect(_on_gui_input)


func _on_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if essence_id >= 0:
			token_pressed.emit(essence_id)
			_play_pop()


func set_essence(id: int) -> void:
	essence_id = id
	if id < 0:
		_core.texture = null
		_glow.texture = null
		_label.text = ""
		modulate = Color.WHITE
		return
	var core_path := _Art.essence_layer_path(id, "core")
	var glow_path := _Art.essence_layer_path(id, "inner_glow")
	_core.texture = _Art.load_texture(core_path)
	if _core.texture == null:
		_core.texture = _Art.load_texture(_Art.magic_icon_path(id))
	_glow.texture = _Art.load_texture(glow_path)
	_label.text = DmbColourData.SYMBOLS[id]
	modulate = DmbColourData.COLOURS[id].lerp(Color.WHITE, 0.35)
	tooltip_text = DmbColourData.NAMES[id]


func set_disabled_overlay(on: bool) -> void:
	_disabled_overlay.visible = on


func _play_pop() -> void:
	var tw := create_tween()
	tw.tween_property(self, "scale", Vector2(1.12, 1.12), _VT.DUR_ESSENCE_POP * 0.5)
	tw.tween_property(self, "scale", Vector2.ONE, _VT.DUR_ESSENCE_POP * 0.5)

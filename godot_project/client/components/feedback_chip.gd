extends Control
class_name FeedbackChip

const _VT = preload("res://client/scripts/visual_theme.gd")

const _Art = preload("res://client/scripts/art.gd")

var feedback_kind: String = "fracture"
var count: int = 0

var _icon: TextureRect
var _count_lbl: Label
var _name_lbl: Label
var _built: bool = false


func _ready() -> void:
	if _built:
		return
	_built = true
	custom_minimum_size = Vector2(88, 72)
	var hbox := HBoxContainer.new()
	hbox.set_anchors_preset(Control.PRESET_FULL_RECT)
	hbox.alignment = BoxContainer.ALIGNMENT_CENTER
	hbox.add_theme_constant_override("separation", 6)
	add_child(hbox)
	_icon = TextureRect.new()
	_icon.custom_minimum_size = Vector2(36, 36)
	_icon.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
	_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	hbox.add_child(_icon)
	var vbox := VBoxContainer.new()
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	hbox.add_child(vbox)
	_count_lbl = Label.new()
	_VT.apply_label_primary(_count_lbl)
	_count_lbl.add_theme_font_size_override("font_size", 26)
	vbox.add_child(_count_lbl)
	_name_lbl = Label.new()
	_VT.apply_label_secondary(_name_lbl)
	_name_lbl.add_theme_font_size_override("font_size", _VT.FONT_CAPTION)
	vbox.add_child(_name_lbl)


func _ensure_nodes() -> void:
	if _count_lbl != null:
		return
	_ready()


func setup(kind: String, value: int) -> void:
	_ensure_nodes()
	feedback_kind = kind
	count = value
	var label := DmbColourData.FEEDBACK_FRACTURE
	var tint := _VT.COLOR_FRACTURE
	var effect_name := "fracture_glyph"
	if kind == "echo":
		label = DmbColourData.FEEDBACK_ECHO
		tint = _VT.COLOR_ECHO
		effect_name = "echo_ring"
	elif kind == "fade":
		label = DmbColourData.FEEDBACK_FADE
		tint = _VT.COLOR_FADE
		effect_name = "fade_mote"
	_count_lbl.text = "×%d" % value
	_name_lbl.text = label
	_icon.modulate = tint
	var tex := _Art.load_texture(_Art.effect_part_path(effect_name))
	if tex == null:
		tex = _Art.load_texture(_Art.feedback_icon_path(kind))
	_icon.texture = tex
	visible = value > 0 or kind == "fade"


func get_display_label() -> String:
	_ensure_nodes()
	return _name_lbl.text


func pop_in() -> void:
	scale = Vector2(0.3, 0.3)
	modulate.a = 0.0
	var tw := create_tween()
	tw.set_parallel(true)
	tw.tween_property(self, "scale", Vector2.ONE, _VT.DUR_FEEDBACK * 0.6).set_trans(Tween.TRANS_BACK)
	tw.tween_property(self, "modulate:a", 1.0, _VT.DUR_FEEDBACK * 0.5)

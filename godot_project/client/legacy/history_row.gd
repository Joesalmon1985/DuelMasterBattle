extends HBoxContainer
class_name HistoryRow

const _Art = preload("res://client/scripts/art.gd")
const _FeedbackChip = preload("res://client/components/feedback_chip.gd")

var _attack_icons: HBoxContainer
var _chips: HBoxContainer


func _ready() -> void:
	add_theme_constant_override("separation", 8)
	_attack_icons = HBoxContainer.new()
	_attack_icons.add_theme_constant_override("separation", 4)
	add_child(_attack_icons)
	_chips = HBoxContainer.new()
	_chips.add_theme_constant_override("separation", 6)
	add_child(_chips)


func show_attack(pattern: Array, fracture: int, echo: int, fade: int = -1) -> void:
	if _chips == null:
		_ready()
	for c in _attack_icons.get_children():
		c.queue_free()
	for c in _chips.get_children():
		c.queue_free()
	for c in pattern:
		var id := int(c)
		var icon := TextureRect.new()
		icon.custom_minimum_size = Vector2(22, 22)
		icon.texture = _Art.load_texture(_Art.essence_layer_path(id, "core"))
		if icon.texture == null:
			icon.texture = _Art.load_texture(_Art.magic_icon_path(id))
		icon.modulate = DmbColourData.COLOURS[id]
		icon.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		_attack_icons.add_child(icon)
	if fade < 0:
		fade = maxi(0, pattern.size() - fracture - echo)
	_add_chip("fracture", fracture)
	_add_chip("echo", echo)
	_add_chip("fade", fade)


func get_feedback_text() -> String:
	var parts: PackedStringArray = []
	for chip in _chips.get_children():
		if chip.has_method("get_display_label"):
			parts.append("%s:%d" % [chip.get_display_label(), chip.count])
	return " ".join(parts)


func _add_chip(kind: String, value: int) -> void:
	var chip := _FeedbackChip.new()
	chip.setup(kind, value)
	_chips.add_child(chip)

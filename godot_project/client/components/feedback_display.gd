extends HBoxContainer
class_name FeedbackDisplay

const _Art = preload("res://client/scripts/art.gd")

const COLOR_FRACTURE := Color("#4caf50")
const COLOR_ECHO := Color("#ffb300")
const COLOR_FADE := Color("#9e9e9e")

var _guess_label: Label
var _feedback_box: HBoxContainer
var _highlight_style: StyleBoxFlat


func _ready() -> void:
	_guess_label = Label.new()
	_guess_label.name = "GuessLabel"
	add_child(_guess_label)
	_feedback_box = HBoxContainer.new()
	_feedback_box.name = "FeedbackBox"
	_feedback_box.add_theme_constant_override("separation", 10)
	add_child(_feedback_box)
	_highlight_style = StyleBoxFlat.new()
	_highlight_style.bg_color = Color(1.0, 1.0, 0.6, 0.35)
	_highlight_style.set_content_margin_all(4)


func show_attack(pattern: Array, fracture: int, echo: int, fade: int = -1) -> void:
	if _guess_label == null:
		_ready()
	var parts: PackedStringArray = []
	for c in pattern:
		var id := int(c)
		parts.append("%s" % DmbColourData.SYMBOLS[id])
	_guess_label.text = "[%s]" % " ".join(parts)
	if fade < 0:
		fade = maxi(0, pattern.size() - fracture - echo)
	_build_feedback_icons(fracture, echo, fade)
	tooltip_text = (
		"Fracture = correct essence, correct locus. "
		+ "Echo = correct essence, wrong locus. "
		+ "Fade = no useful match."
	)


func show_guess(guess: Array, exact: int, colour_only: int) -> void:
	var fade := guess.size() - exact - colour_only
	show_attack(guess, exact, colour_only, fade)


func set_highlighted(on: bool) -> void:
	if on:
		add_theme_stylebox_override("panel", _highlight_style)
	else:
		remove_theme_stylebox_override("panel")


func get_feedback_text() -> String:
	if _feedback_box == null:
		return ""
	var parts: PackedStringArray = []
	for cell in _feedback_box.get_children():
		for child in cell.get_children():
			if child is Label:
				parts.append(child.text)
	return " ".join(parts)


func _build_feedback_icons(fracture: int, echo: int, fade: int) -> void:
	for c in _feedback_box.get_children():
		c.queue_free()
	_add_feedback_cell("fracture", fracture, COLOR_FRACTURE, DmbColourData.FEEDBACK_FRACTURE)
	_add_feedback_cell("echo", echo, COLOR_ECHO, DmbColourData.FEEDBACK_ECHO)
	_add_feedback_cell("fade", fade, COLOR_FADE, DmbColourData.FEEDBACK_FADE)


func _add_feedback_cell(kind: String, count: int, tint: Color, label: String) -> void:
	var cell := HBoxContainer.new()
	cell.add_theme_constant_override("separation", 2)
	var icon_kind := kind
	if kind == "fracture":
		icon_kind = "hit"
	elif kind == "echo":
		icon_kind = "weakness"
	elif kind == "fade":
		icon_kind = "unaffected"
	var tex_path := _Art.feedback_icon_path(icon_kind)
	var tex := _Art.load_texture(tex_path)
	if tex != null:
		var icon := TextureRect.new()
		icon.custom_minimum_size = Vector2(18, 18)
		icon.texture = tex
		icon.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon.modulate = tint
		cell.add_child(icon)
	var lbl := Label.new()
	lbl.text = "%s:%d" % [label, count]
	lbl.modulate = tint
	cell.add_child(lbl)
	_feedback_box.add_child(cell)

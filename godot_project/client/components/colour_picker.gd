extends HBoxContainer
class_name ColourPicker

signal colour_selected(colour_id: int)

var _buttons: Array = []


func _ready() -> void:
	for i in range(DmbConstants.NUM_COLOURS):
		var btn := Button.new()
		btn.custom_minimum_size = Vector2(40, 40)
		btn.text = str(i)
		btn.tooltip_text = DmbColourData.NAMES[i]
		var style := StyleBoxFlat.new()
		style.bg_color = DmbColourData.COLOURS[i]
		btn.add_theme_stylebox_override("normal", style)
		btn.add_theme_color_override("font_color", Color.WHITE if i == 9 else Color.BLACK)
		var idx := i
		btn.pressed.connect(func(): colour_selected.emit(idx))
		add_child(btn)
		_buttons.append(btn)


func set_interactive(enabled: bool) -> void:
	for b in _buttons:
		b.disabled = not enabled

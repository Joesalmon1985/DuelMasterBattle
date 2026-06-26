extends PanelContainer
class_name MagicPicker

const _Art = preload("res://client/scripts/art.gd")

signal magic_selected(magic_id: int)

const COLS := 5
const BTN_SIZE := Vector2(72, 56)

var _grid: GridContainer
var _buttons: Array = []
var _open := false
var _allowed: Dictionary = {}


func _ready() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 8)
	margin.add_theme_constant_override("margin_right", 8)
	margin.add_theme_constant_override("margin_top", 8)
	margin.add_theme_constant_override("margin_bottom", 8)
	add_child(margin)
	_grid = GridContainer.new()
	_grid.columns = COLS
	margin.add_child(_grid)
	for i in range(DmbConstants.NUM_COLOURS):
		var btn := Button.new()
		btn.custom_minimum_size = BTN_SIZE
		btn.text = "%d\n%s\n%s" % [i, DmbColourData.SYMBOLS[i], DmbColourData.NAMES[i].substr(0, 4)]
		btn.tooltip_text = "%d: %s" % [i, DmbColourData.NAMES[i]]
		var style := StyleBoxFlat.new()
		style.bg_color = DmbColourData.COLOURS[i]
		style.set_corner_radius_all(4)
		btn.add_theme_stylebox_override("normal", style)
		btn.add_theme_color_override("font_color", Color.WHITE if i in [4, 7, 8] else Color.BLACK)
		var icon_path := _Art.magic_icon_path(i)
		var tex := _Art.load_texture(icon_path)
		if tex:
			btn.icon = tex
			btn.expand_icon = true
		var idx := i
		btn.pressed.connect(func(): _on_magic_pressed(idx))
		_grid.add_child(btn)
		_buttons.append(btn)
	for i in range(DmbConstants.NUM_COLOURS):
		_allowed[i] = true


func set_allowed_magics(pool: Array) -> void:
	_allowed.clear()
	for m in pool:
		_allowed[int(m)] = true
	for i in range(_buttons.size()):
		_buttons[i].visible = _allowed.has(i)


func _visible_magic_count() -> int:
	var n := 0
	for i in range(_buttons.size()):
		if _buttons[i].visible:
			n += 1
	return n


func _on_magic_pressed(magic_id: int) -> void:
	magic_selected.emit(magic_id)
	close()


func open_bottom_sheet(parent: Control) -> void:
	visible = true
	_open = true
	var visible_count := _visible_magic_count()
	var rows := ceili(float(visible_count) / COLS)
	var panel_h := rows * BTN_SIZE.y + 32
	anchor_left = 0.0
	anchor_right = 1.0
	anchor_top = 1.0
	anchor_bottom = 1.0
	offset_left = 8.0
	offset_right = -8.0
	offset_top = -panel_h - 8.0
	offset_bottom = -8.0


func open_at(global_pos: Vector2) -> void:
	visible = true
	_open = true
	anchor_left = 0.0
	anchor_top = 0.0
	anchor_right = 0.0
	anchor_bottom = 0.0
	var vp := get_viewport().get_visible_rect().size
	var visible_count := _visible_magic_count()
	var rows := ceili(float(visible_count) / COLS)
	var panel_size := Vector2(COLS * BTN_SIZE.x + 24, rows * BTN_SIZE.y + 24)
	global_position = global_pos
	if global_position.x + panel_size.x > vp.x:
		global_position.x = maxf(0, vp.x - panel_size.x)
	if global_position.y + panel_size.y > vp.y:
		global_position.y = maxf(0, vp.y - panel_size.y)


func close() -> void:
	visible = false
	_open = false


func is_open() -> bool:
	return _open


func set_interactive(enabled: bool) -> void:
	for b in _buttons:
		b.disabled = not enabled

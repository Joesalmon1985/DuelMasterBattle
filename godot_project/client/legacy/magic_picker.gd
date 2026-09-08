extends PanelContainer
class_name MagicPicker
const _VT = preload("res://client/scripts/visual_theme.gd")

const _Art = preload("res://client/scripts/art.gd")

signal magic_selected(magic_id: int)

const COLS := 5
const BTN_SIZE := Vector2(_VT.TOUCH_ESSENCE, _VT.TOUCH_ESSENCE)

var _grid: GridContainer
var _buttons: Array = []
var _open := false
var _allowed: Dictionary = {}
var _tween: Tween


func _ready() -> void:
	visible = false
	modulate.a = 0.0
	mouse_filter = Control.MOUSE_FILTER_STOP
	add_theme_stylebox_override("panel", _VT.panel_style())
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
		btn.text = DmbColourData.SYMBOLS[i]
		btn.tooltip_text = "%d: %s" % [i, DmbColourData.NAMES[i]]
		var style := _VT.gem_button_style()
		style.bg_color = DmbColourData.COLOURS[i]
		style.set_corner_radius_all(12)
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


func _panel_size() -> Vector2:
	var visible_count := _visible_magic_count()
	var rows := ceili(float(visible_count) / COLS)
	return Vector2(COLS * BTN_SIZE.x + 24, rows * BTN_SIZE.y + 24)


func _on_magic_pressed(magic_id: int) -> void:
	magic_selected.emit(magic_id)
	close()


func open_above_anchor(anchor_ctrl: Control) -> void:
	if anchor_ctrl == null:
		open_bottom_sheet(anchor_ctrl)
		return
	var panel_size := _panel_size()
	var rect := anchor_ctrl.get_global_rect()
	var vp := get_viewport().get_visible_rect().size
	var pos := Vector2(
		rect.position.x + rect.size.x * 0.5 - panel_size.x * 0.5,
		rect.position.y - panel_size.y - 12.0
	)
	pos.x = clampf(pos.x, 8.0, vp.x - panel_size.x - 8.0)
	if pos.y < 8.0:
		pos.y = rect.position.y + rect.size.y + 12.0
	_open_at(pos, panel_size)


func open_bottom_sheet(_parent: Control) -> void:
	var visible_count := _visible_magic_count()
	var rows := ceili(float(visible_count) / COLS)
	var panel_h := rows * BTN_SIZE.y + 32
	anchor_left = 0.0
	anchor_right = 1.0
	anchor_top = 1.0
	anchor_bottom = 1.0
	offset_left = 8.0
	offset_right = -8.0
	offset_top = -panel_h - _VT.SAFE_BOTTOM_INSET
	offset_bottom = -_VT.SAFE_BOTTOM_INSET
	_animate_open()


func open_at(global_pos: Vector2) -> void:
	var panel_size := _panel_size()
	_open_at(global_pos, panel_size)


func _open_at(global_pos: Vector2, panel_size: Vector2) -> void:
	anchor_left = 0.0
	anchor_top = 0.0
	anchor_right = 0.0
	anchor_bottom = 0.0
	global_position = global_pos
	size = panel_size
	var vp := get_viewport().get_visible_rect().size
	if global_position.x + panel_size.x > vp.x:
		global_position.x = maxf(8.0, vp.x - panel_size.x - 8.0)
	if global_position.y + panel_size.y > vp.y:
		global_position.y = maxf(8.0, vp.y - panel_size.y - 8.0)
	_animate_open()


func _animate_open() -> void:
	visible = true
	_open = true
	if _tween != null and _tween.is_valid():
		_tween.kill()
	modulate.a = 0.0
	scale = Vector2(0.92, 0.92)
	_tween = create_tween().set_parallel(true)
	_tween.tween_property(self, "modulate:a", 1.0, _VT.DUR_PICKER_OPEN)
	_tween.tween_property(self, "scale", Vector2.ONE, _VT.DUR_PICKER_OPEN).set_trans(Tween.TRANS_BACK)


func close() -> void:
	if not _open:
		return
	if _tween != null and _tween.is_valid():
		_tween.kill()
	_tween = create_tween()
	_tween.tween_property(self, "modulate:a", 0.0, _VT.DUR_PICKER_OPEN * 0.8)
	_tween.tween_callback(func():
		visible = false
		_open = false
	)


func is_open() -> bool:
	return _open


func get_global_rect_picker() -> Rect2:
	return get_global_rect() if _open else Rect2()


func set_interactive(enabled: bool) -> void:
	for b in _buttons:
		b.disabled = not enabled

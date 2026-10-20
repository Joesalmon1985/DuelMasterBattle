extends Control

const Tile = preload("res://client/minigames/tile_widget.gd")

## A die with pips (or a carved stone, as the stonemason calls it), drawn. Items of a "dice" area: {value 1-6 (0: not thrown), held, selected,
## disabled, colour (a face colour index), action (sent when tapped: holding or freeing a die)}.

const PIPS := {1: [Vector2(0.5, 0.5)], 2: [Vector2(0.25, 0.25), Vector2(0.75, 0.75)], 3: [Vector2(0.25, 0.25), Vector2(0.5, 0.5), Vector2(0.75, 0.75)],
	4: [Vector2(0.25, 0.25), Vector2(0.75, 0.25), Vector2(0.25, 0.75), Vector2(0.75, 0.75)],
	5: [Vector2(0.25, 0.25), Vector2(0.75, 0.25), Vector2(0.5, 0.5), Vector2(0.25, 0.75), Vector2(0.75, 0.75)],
	6: [Vector2(0.25, 0.22), Vector2(0.75, 0.22), Vector2(0.25, 0.5), Vector2(0.75, 0.5), Vector2(0.25, 0.78), Vector2(0.75, 0.78)]}

var value := 0
var held := false
var selected := false
var face := Color(0.93, 0.9, 0.82)
var action: Dictionary = {}
var table: Node = null
var _px := 64.0


func setup(item: Dictionary, px: float, p_table: Node) -> void:
	value = int(item.get("value", 0))
	held = bool(item.get("held", false))
	selected = bool(item.get("selected", false))
	if item.has("colour"):
		face = (Tile.colour_of(item["colour"]) as Color).lightened(0.3)
	var act: Dictionary = item.get("action", {}) if typeof(item.get("action", {})) == TYPE_DICTIONARY else {}
	action = {} if bool(item.get("disabled", false)) else act
	table = p_table
	_px = px
	custom_minimum_size = Vector2(px, px)
	mouse_filter = Control.MOUSE_FILTER_STOP if not action.is_empty() else Control.MOUSE_FILTER_IGNORE
	queue_redraw()


func _gui_input(event: InputEvent) -> void:
	if action.is_empty() or table == null:
		return
	if (event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT) or (event is InputEventScreenTouch and event.pressed):
		accept_event()
		table.widget_act(action)


func _draw() -> void:
	var r := Rect2(Vector2(3, 3), size - Vector2(6, 6))
	var style := StyleBoxFlat.new()
	style.bg_color = face if value > 0 else Color(0.3, 0.28, 0.35)
	style.set_corner_radius_all(int(size.x * 0.2))
	var bw := 4 if (held or selected) else 2
	style.border_width_left = bw
	style.border_width_right = bw
	style.border_width_top = bw
	style.border_width_bottom = bw
	style.border_color = Color(0.95, 0.85, 0.45) if (held or selected) else Color(0.2, 0.18, 0.25)
	draw_style_box(style, r)
	if value <= 0:
		return
	var pr := size.x * 0.075
	for p in PIPS.get(value, []):
		draw_circle(r.position + Vector2(p.x * r.size.x, p.y * r.size.y), pr, Color(0.12, 0.1, 0.14))
	if held:
		var font := get_theme_default_font()
		draw_string(font, Vector2(4, size.y - 4), "held", HORIZONTAL_ALIGNMENT_LEFT, -1, int(clampf(size.x * 0.17, 9.0, 14.0)), Color(0.5, 0.35, 0.1))

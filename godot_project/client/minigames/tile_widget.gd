extends Control

## A coloured tile with a short text: a tally (Rummikub), a disc (Skull), a carrot or a swatch, a sign for the reaction game, an object for the
## memory game, a throw for Rock Paper Scissors. Drawn, never loaded. Items of a "tiles" area: {text, colour (an index into PALETTE, or "#rrggbb"),
## down (face down), selected, disabled, action (sent when tapped), pattern (a swatch's weave), sub (a small second line)}.

const PALETTE := [Color(0.85, 0.3, 0.25), Color(0.3, 0.55, 0.9), Color(0.95, 0.8, 0.3), Color(0.35, 0.7, 0.4), Color(0.6, 0.4, 0.75), Color(0.95, 0.6, 0.25),
	Color(0.5, 0.5, 0.55), Color(0.3, 0.75, 0.75)]

var text := ""
var sub := ""
var colour := Color(0.4, 0.38, 0.45)
var down := false
var selected := false
var pattern := ""
var action: Dictionary = {}
var table: Node = null
var _px := 64.0


func setup(p_text: String, p_colour: Color, px: float, p_action: Dictionary = {}, p_table: Node = null) -> void:
	text = p_text
	colour = p_colour
	_px = px
	action = p_action
	table = p_table
	custom_minimum_size = Vector2(px, px)
	mouse_filter = Control.MOUSE_FILTER_STOP if not action.is_empty() else Control.MOUSE_FILTER_IGNORE
	queue_redraw()


static func colour_of(v: Variant) -> Color:
	if typeof(v) == TYPE_STRING and str(v).begins_with("#"):
		return Color(str(v))
	if typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT:
		var i := int(v)
		return PALETTE[i % PALETTE.size()] if i >= 0 else Color(0.4, 0.38, 0.45)
	return Color(0.4, 0.38, 0.45)


## Fill from a "tiles" area item (the table builds the row).
func from_item(item: Dictionary, px: float, p_table: Node) -> void:
	var act: Dictionary = item.get("action", {}) if typeof(item.get("action", {})) == TYPE_DICTIONARY else {}
	if bool(item.get("disabled", false)):
		act = {}
	setup(str(item.get("text", "")), colour_of(item.get("colour", -1)), px, act, p_table)
	down = bool(item.get("down", false))
	selected = bool(item.get("selected", false))
	pattern = str(item.get("pattern", ""))
	sub = str(item.get("sub", ""))
	name = "Tile_%s" % str(item.get("id", item.get("text", ""))).replace(":", "_").replace(" ", "_")


func _gui_input(event: InputEvent) -> void:
	if action.is_empty() or table == null:
		return
	if (event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT) or (event is InputEventScreenTouch and event.pressed):
		accept_event()
		table.widget_act(action)


func _draw() -> void:
	var r := Rect2(Vector2(2, 2), size - Vector2(4, 4))
	var base := colour if not down else Color(0.22, 0.2, 0.3)
	var style := StyleBoxFlat.new()
	style.bg_color = base
	style.set_corner_radius_all(int(size.x * 0.14))
	style.border_width_left = 3
	style.border_width_right = 3
	style.border_width_top = 3
	style.border_width_bottom = 3
	style.border_color = Color(0.95, 0.85, 0.45) if selected else base.darkened(0.35)
	draw_style_box(style, r)
	if down:
		for i in 4:
			var y := r.position.y + r.size.y * (0.2 + 0.2 * i)
			draw_line(Vector2(r.position.x + 8, y), Vector2(r.end.x - 8, y), Color(0.35, 0.32, 0.45), 2.0)
		return
	if pattern != "":
		_draw_pattern(r)
	var font := get_theme_default_font()
	var fs := int(clampf(size.x * (0.34 if text.length() <= 2 else (0.22 if text.length() <= 6 else 0.16)), 10.0, 40.0))
	var ink := Color(0.08, 0.06, 0.1) if base.get_luminance() > 0.45 else Color(0.96, 0.94, 0.9)
	var tw := font.get_string_size(text, HORIZONTAL_ALIGNMENT_CENTER, -1, fs).x
	draw_string(font, Vector2(r.position.x + (r.size.x - tw) * 0.5, r.position.y + r.size.y * (0.56 if sub == "" else 0.48)), text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, ink)
	if sub != "":
		var ss := int(clampf(size.x * 0.16, 9.0, 18.0))
		var sw := font.get_string_size(sub, HORIZONTAL_ALIGNMENT_CENTER, -1, ss).x
		draw_string(font, Vector2(r.position.x + (r.size.x - sw) * 0.5, r.end.y - size.y * 0.14), sub, HORIZONTAL_ALIGNMENT_LEFT, -1, ss, ink)


func _draw_pattern(r: Rect2) -> void:
	var c := colour.darkened(0.3)
	match pattern:
		"stripe":
			for i in range(0, int(r.size.x), 10):
				draw_line(Vector2(r.position.x + i, r.position.y), Vector2(r.position.x + i, r.end.y), c, 3.0)
		"check":
			for i in range(0, int(r.size.x), 12):
				draw_line(Vector2(r.position.x + i, r.position.y), Vector2(r.position.x + i, r.end.y), c, 2.0)
				draw_line(Vector2(r.position.x, r.position.y + i), Vector2(r.end.x, r.position.y + i), c, 2.0)
		"dot":
			for y in range(8, int(r.size.y), 12):
				for x in range(8, int(r.size.x), 12):
					draw_circle(r.position + Vector2(x, y), 2.5, c)
		"herringbone", "chevron":
			for i in range(0, int(r.size.y), 10):
				draw_line(Vector2(r.position.x, r.position.y + i), Vector2(r.position.x + r.size.x * 0.5, r.position.y + i + 6), c, 2.0)
				draw_line(Vector2(r.position.x + r.size.x * 0.5, r.position.y + i + 6), Vector2(r.end.x, r.position.y + i), c, 2.0)
		"twill", "diamond", "wave":
			for i in range(-int(r.size.y), int(r.size.x), 10):
				draw_line(Vector2(r.position.x + i, r.end.y), Vector2(r.position.x + i + r.size.y, r.position.y), c, 2.0)
		"paisley":
			draw_arc(r.get_center(), r.size.x * 0.3, 0.0, TAU * 0.75, 16, c, 3.0)
		_:
			pass

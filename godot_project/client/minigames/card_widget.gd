extends Control

## A playing card, drawn: rank and suit (s, h, d, c) for the card games, or a colour and a number for Hanabi. Items of a "cards" area:
## {rank, suit, colour (a colour index for Hanabi), number, down (face down), selected, disabled, label (a small caption), action (sent when tapped)}.

const SUIT_COLOUR := {"s": Color(0.1, 0.08, 0.12), "c": Color(0.1, 0.08, 0.12), "h": Color(0.8, 0.15, 0.15), "d": Color(0.8, 0.15, 0.15)}
const HANABI := [Color(0.9, 0.4, 0.2), Color(0.35, 0.6, 0.95), Color(0.35, 0.7, 0.35), Color(0.95, 0.9, 0.5), Color(0.6, 0.6, 0.65)]

var rank := ""
var suit := ""
var colour := -1
var number := 0
var down := false
var selected := false
var label := ""
var action: Dictionary = {}
var table: Node = null
var _w := 56.0


func setup(item: Dictionary, w: float, p_table: Node) -> void:
	rank = str(item.get("rank", ""))
	suit = str(item.get("suit", ""))
	colour = int(item.get("colour", -1))
	number = int(item.get("number", 0))
	down = bool(item.get("down", false))
	selected = bool(item.get("selected", false))
	label = str(item.get("label", ""))
	var act: Dictionary = item.get("action", {}) if typeof(item.get("action", {})) == TYPE_DICTIONARY else {}
	action = {} if bool(item.get("disabled", false)) else act
	table = p_table
	_w = w
	custom_minimum_size = Vector2(w, w * 1.42 + (14.0 if label != "" else 0.0))
	mouse_filter = Control.MOUSE_FILTER_STOP if not action.is_empty() else Control.MOUSE_FILTER_IGNORE
	queue_redraw()


func _gui_input(event: InputEvent) -> void:
	if action.is_empty() or table == null:
		return
	if (event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT) or (event is InputEventScreenTouch and event.pressed):
		accept_event()
		table.widget_act(action)


static func suit_glyph(s: String) -> String:
	match s:
		"s": return "S"
		"h": return "H"
		"d": return "D"
		"c": return "C"
	return ""


func _draw_suit(centre: Vector2, r: float, col: Color) -> void:
	match suit:
		"h":
			draw_circle(centre + Vector2(-r * 0.45, -r * 0.3), r * 0.5, col)
			draw_circle(centre + Vector2(r * 0.45, -r * 0.3), r * 0.5, col)
			draw_colored_polygon(PackedVector2Array([centre + Vector2(-r * 0.92, -r * 0.1), centre + Vector2(r * 0.92, -r * 0.1), centre + Vector2(0, r * 0.95)]), col)
		"d":
			draw_colored_polygon(PackedVector2Array([centre + Vector2(0, -r), centre + Vector2(r * 0.7, 0), centre + Vector2(0, r), centre + Vector2(-r * 0.7, 0)]), col)
		"c":
			draw_circle(centre + Vector2(0, -r * 0.45), r * 0.42, col)
			draw_circle(centre + Vector2(-r * 0.45, r * 0.15), r * 0.42, col)
			draw_circle(centre + Vector2(r * 0.45, r * 0.15), r * 0.42, col)
			draw_rect(Rect2(centre + Vector2(-r * 0.12, r * 0.1), Vector2(r * 0.24, r * 0.8)), col)
		"s":
			draw_colored_polygon(PackedVector2Array([centre + Vector2(0, -r), centre + Vector2(r * 0.9, r * 0.2), centre + Vector2(-r * 0.9, r * 0.2)]), col)
			draw_circle(centre + Vector2(-r * 0.45, r * 0.25), r * 0.42, col)
			draw_circle(centre + Vector2(r * 0.45, r * 0.25), r * 0.42, col)
			draw_rect(Rect2(centre + Vector2(-r * 0.12, r * 0.2), Vector2(r * 0.24, r * 0.75)), col)
		_:
			pass


func _draw() -> void:
	var h := _w * 1.42
	var r := Rect2(Vector2(1, 1), Vector2(_w - 2, h - 2))
	var style := StyleBoxFlat.new()
	style.set_corner_radius_all(int(_w * 0.12))
	style.border_width_left = 2
	style.border_width_right = 2
	style.border_width_top = 2
	style.border_width_bottom = 2
	style.border_color = Color(0.95, 0.85, 0.45) if selected else Color(0.2, 0.18, 0.25)
	if selected:
		style.border_width_left = 4
		style.border_width_right = 4
		style.border_width_top = 4
		style.border_width_bottom = 4
	if down:
		style.bg_color = Color(0.32, 0.22, 0.42)
		draw_style_box(style, r)
		for i in range(6, int(h) - 6, 8):
			draw_line(Vector2(6, i), Vector2(_w - 6, i), Color(0.45, 0.33, 0.55), 1.5)
	else:
		style.bg_color = Color(0.96, 0.94, 0.88)
		draw_style_box(style, r)
		var font := get_theme_default_font()
		if colour >= 0:  # a Hanabi card: a colour field with its number
			var col: Color = HANABI[colour % HANABI.size()]
			draw_rect(Rect2(Vector2(5, 5), Vector2(_w - 10, h - 10)), col)
			var t := str(number) if number > 0 else "?"
			var fs := int(_w * 0.5)
			var tw := font.get_string_size(t, HORIZONTAL_ALIGNMENT_CENTER, -1, fs).x
			draw_string(font, Vector2((_w - tw) * 0.5, h * 0.62), t, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(0.08, 0.06, 0.1))
		else:
			var col: Color = SUIT_COLOUR.get(suit, Color(0.1, 0.08, 0.12))
			var fs := int(_w * 0.36)
			draw_string(font, Vector2(5, fs + 3), rank, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)
			_draw_suit(Vector2(_w * 0.5, h * 0.62), _w * 0.2, col)
			var sg := suit_glyph(suit)
			var sw := font.get_string_size(sg, HORIZONTAL_ALIGNMENT_CENTER, -1, int(fs * 0.7)).x
			draw_string(font, Vector2(_w - sw - 5, h - 6), sg, HORIZONTAL_ALIGNMENT_LEFT, -1, int(fs * 0.7), col)
	if label != "":
		var font2 := get_theme_default_font()
		var ls := int(clampf(_w * 0.2, 9.0, 14.0))
		var lw := font2.get_string_size(label, HORIZONTAL_ALIGNMENT_CENTER, -1, ls).x
		draw_string(font2, Vector2((_w - lw) * 0.5, h + 12), label, HORIZONTAL_ALIGNMENT_LEFT, -1, ls, Color(0.85, 0.8, 0.7))

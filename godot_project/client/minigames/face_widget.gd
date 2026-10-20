extends Control

## Guess Who: a board of the village's people. Each face shows the person's figure (the same sprite the world draws for them, through the art
## catalogue; a drawn portrait when the sprite is missing), their name and their traits; an eliminated face is turned down. Area:
## {items: [{id, name, figure, traits: [..], down, selected, action}], size}.

var item: Dictionary = {}
var table: Node = null
var _px := 96.0


func configure(it: Dictionary, px: float, p_table: Node) -> void:
	item = it
	table = p_table
	_px = px
	name = "Face_%s" % str(it.get("id", "")).replace(":", "_")
	custom_minimum_size = Vector2(px, px * 1.5)
	clip_contents = true
	var act: Dictionary = it.get("action", {}) if typeof(it.get("action", {})) == TYPE_DICTIONARY else {}
	mouse_filter = Control.MOUSE_FILTER_STOP if (not act.is_empty() and not bool(it.get("disabled", false))) else Control.MOUSE_FILTER_IGNORE


func _gui_input(event: InputEvent) -> void:
	var act: Dictionary = item.get("action", {}) if typeof(item.get("action", {})) == TYPE_DICTIONARY else {}
	if act.is_empty() or table == null or bool(item.get("disabled", false)):
		return
	if (event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT) or (event is InputEventScreenTouch and event.pressed):
		accept_event()
		table.widget_act(act)


func _figure_frame() -> Array:
	## [texture, source rect] of the person's standing picture, or [] when the catalogue has none.
	if table == null or table.world == null or not ("_art" in table.world) or table.world._art == null:
		return []
	var art = table.world._art
	var e := {"definition": str(item.get("figure", "")), "kind": "worker", "class": "worker", "anim": "idle", "facing": "e", "_static": true}
	var it: Dictionary = art._item_for(e)
	if it.is_empty():
		return []
	var tex: Texture2D = art._frame_texture(it, e)
	if tex == null:
		return []
	return [tex, art._source_rect(it, tex, e)]


func _draw() -> void:
	var down := bool(item.get("down", false))
	var sel := bool(item.get("selected", false))
	var r := Rect2(Vector2(2, 2), Vector2(_px - 4, _px - 4))
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.2, 0.18, 0.26) if down else Color(0.82, 0.76, 0.62)
	style.set_corner_radius_all(int(_px * 0.1))
	style.border_width_left = 3
	style.border_width_right = 3
	style.border_width_top = 3
	style.border_width_bottom = 3
	style.border_color = Color(0.95, 0.85, 0.45) if sel else Color(0.2, 0.18, 0.25)
	draw_style_box(style, r)
	var font := get_theme_default_font()
	if not down:
		var frame := _figure_frame()
		if not frame.is_empty():
			var tex: Texture2D = frame[0]
			var src: Rect2 = frame[1]
			var scale := minf((r.size.x - 12.0) / src.size.x, (r.size.y - 12.0) / src.size.y)
			var dst := Rect2(r.get_center() - src.size * scale * 0.5, src.size * scale)
			draw_texture_rect_region(tex, dst, src)
		else:
			var ini := str(item.get("name", "?")).substr(0, 1)
			draw_circle(r.get_center() + Vector2(0, -r.size.y * 0.12), r.size.x * 0.28, Color(0.55, 0.45, 0.6))
			var fs := int(_px * 0.4)
			var tw := font.get_string_size(ini, HORIZONTAL_ALIGNMENT_CENTER, -1, fs).x
			draw_string(font, r.get_center() + Vector2(-tw * 0.5, fs * 0.3 - r.size.y * 0.12), ini, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(0.96, 0.94, 0.9))
	else:
		var x := "x"
		var fs2 := int(_px * 0.5)
		var xw := font.get_string_size(x, HORIZONTAL_ALIGNMENT_CENTER, -1, fs2).x
		draw_string(font, r.get_center() + Vector2(-xw * 0.5, fs2 * 0.35), x, HORIZONTAL_ALIGNMENT_LEFT, -1, fs2, Color(0.5, 0.45, 0.55))
	var nm := str(item.get("name", ""))
	var ns := int(clampf(_px * 0.12, 9.0, 13.0))
	var ink := Color(0.9, 0.86, 0.75) if not down else Color(0.5, 0.47, 0.55)
	draw_string(font, Vector2(3, _px + ns + 1), _fit(font, nm, ns, _px - 6.0), HORIZONTAL_ALIGNMENT_LEFT, -1, ns, ink)
	var traits: Array = item.get("traits", [])
	if not traits.is_empty() and not down:
		var ts := int(ns * 0.85)
		var line1 := ", ".join(PackedStringArray(traits.slice(0, 2)))
		var line2 := ", ".join(PackedStringArray(traits.slice(2, 4)))
		draw_string(font, Vector2(3, _px + ns + ts + 4), _fit(font, line1, ts, _px - 6.0), HORIZONTAL_ALIGNMENT_LEFT, -1, ts, Color(0.75, 0.7, 0.6))
		draw_string(font, Vector2(3, _px + ns + ts * 2 + 7), _fit(font, line2, ts, _px - 6.0), HORIZONTAL_ALIGNMENT_LEFT, -1, ts, Color(0.75, 0.7, 0.6))


## The longest prefix of `text` that fits `width` at this size, with an ellipsis when it was cut.
static func _fit(font: Font, text: String, size_px: int, width: float) -> String:
	if font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, size_px).x <= width:
		return text
	var n := text.length()
	while n > 1 and font.get_string_size(text.substr(0, n) + "..", HORIZONTAL_ALIGNMENT_LEFT, -1, size_px).x > width:
		n -= 1
	return text.substr(0, n) + ".."

extends Control
class_name DmbWorldMapPanel

## Read-only strategic map. Exact HexBoard corner geometry + clear symbols.

const VisualLanguage = preload("res://client/world/visual_language.gd")
const ResponsiveModal = preload("res://client/ui/responsive_modal.gd")

signal closed

var _payload: Dictionary = {}
var _canvas: Control
var _legend: HFlowContainer
var _title: Label
var _margin: MarginContainer
var _panel: PanelContainer
var _close_btn: Button
var _fit_origin := Vector2.ZERO
var _fit_size := 18.0
var _hex_lookup: Dictionary = {}
var _node_pos: Dictionary = {}  # node_id -> Vector2 unscaled map coords


func _ready() -> void:
	visible = false
	var parts: Dictionary = ResponsiveModal.build_shell(self, "World Map")
	_margin = parts["margin"]
	_panel = parts["panel"]
	_title = parts["title"]
	_close_btn = parts["close_btn"]
	_close_btn.pressed.connect(hide_map)
	var body: VBoxContainer = parts["body"]
	_canvas = Control.new()
	_canvas.name = "MapCanvas"
	_canvas.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_canvas.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_canvas.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_canvas.draw.connect(_on_draw_map)
	_canvas.resized.connect(_on_canvas_resized)
	body.add_child(_canvas)
	_legend = HFlowContainer.new()
	_legend.name = "MapLegend"
	_legend.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_legend.add_theme_constant_override("h_separation", 10)
	_legend.add_theme_constant_override("v_separation", 4)
	body.add_child(_legend)
	_build_legend()
	resized.connect(_relayout)
	_relayout()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED or what == NOTIFICATION_VISIBILITY_CHANGED:
		if visible:
			_relayout()


func show_map(payload: Dictionary) -> void:
	_payload = payload
	_rebuild_lookups()
	visible = true
	_title.text = "World Map — Turn view"
	_relayout()
	call_deferred("_relayout")
	call_deferred("_deferred_redraw")


func _deferred_redraw() -> void:
	if _canvas != null:
		_canvas.queue_redraw()


func hide_map() -> void:
	visible = false
	closed.emit()


func map_canvas() -> Control:
	return _canvas


func close_button() -> Button:
	return _close_btn


func _relayout() -> void:
	if _margin == null or _panel == null:
		return
	var vp := get_viewport_rect().size
	if vp.x < 1.0 or vp.y < 1.0:
		return
	ResponsiveModal.apply_margins(_margin, vp)
	ResponsiveModal.apply_panel_bounds(_panel, vp, 0.94, 0.88)
	_recompute_fit()
	if _canvas != null:
		_canvas.queue_redraw()


func _on_canvas_resized() -> void:
	_recompute_fit()
	_canvas.queue_redraw()


func _rebuild_lookups() -> void:
	_hex_lookup.clear()
	for h in _payload.get("hexes", []):
		if typeof(h) != TYPE_DICTIONARY:
			continue
		_hex_lookup[str(h.get("id", ""))] = h
	_node_pos.clear()
	for n in _payload.get("nodes", []):
		if typeof(n) != TYPE_DICTIONARY:
			continue
		var nid := str(n.get("id", ""))
		var mp = n.get("map_position")
		if typeof(mp) == TYPE_ARRAY and mp.size() >= 2:
			_node_pos[nid] = Vector2(float(mp[0]), float(mp[1]))


func _recompute_fit() -> void:
	if _canvas == null:
		_fit_origin = Vector2(40, 40)
		_fit_size = 18.0
		return
	var available := _canvas.size
	if available.x < 8.0 or available.y < 8.0:
		available = _panel.size - Vector2(24, 110)
	var padding := 16.0
	var corners := PackedVector2Array()
	# Prefer exact node vertices; fall back to hex corners.
	if not _node_pos.is_empty():
		for p in _node_pos.values():
			corners.append(_axial_to_pixel(p.x, p.y, 1.0))
	else:
		for h in _payload.get("hexes", []):
			if typeof(h) != TYPE_DICTIONARY:
				continue
			var c := _axial_to_pixel(float(h.get("q", 0)), float(h.get("r", 0)), 1.0)
			for i in 6:
				var angle := TAU * float(i) / 6.0 + PI / 6.0
				corners.append(c + Vector2(cos(angle), sin(angle)))
	if corners.is_empty():
		_fit_origin = Vector2(40, 40)
		_fit_size = 18.0
		return
	var bb_min := corners[0]
	var bb_max := corners[0]
	for p in corners:
		bb_min = Vector2(minf(bb_min.x, p.x), minf(bb_min.y, p.y))
		bb_max = Vector2(maxf(bb_max.x, p.x), maxf(bb_max.y, p.y))
	var unit_w := maxf(0.001, bb_max.x - bb_min.x)
	var unit_h := maxf(0.001, bb_max.y - bb_min.y)
	var usable := Vector2(maxf(1.0, available.x - padding * 2.0), maxf(1.0, available.y - padding * 2.0))
	_fit_size = minf(usable.x / unit_w, usable.y / unit_h)
	_fit_size = clampf(_fit_size, 8.0, 64.0)
	var board_w := unit_w * _fit_size
	var board_h := unit_h * _fit_size
	_fit_origin = Vector2(
		(available.x - board_w) * 0.5 - bb_min.x * _fit_size,
		(available.y - board_h) * 0.5 - bb_min.y * _fit_size
	)


func _on_draw_map() -> void:
	var hexes: Array = _payload.get("hexes", [])
	if hexes.is_empty():
		return
	_recompute_fit()
	var origin := _fit_origin
	var size := _fit_size
	var site_r := clampf(size * 0.12, 3.0, 8.0)
	var road_w := clampf(size * 0.14, 1.5, 5.0)
	var font_px := int(clampf(size * 0.42, 9.0, 18.0))
	var token_r := clampf(size * 0.32, 6.0, 14.0)

	# 1) Terrain hexes + subtle cues
	for h in hexes:
		if typeof(h) != TYPE_DICTIONARY:
			continue
		var q := float(h.get("q", 0))
		var r := float(h.get("r", 0))
		var center := origin + _axial_to_pixel(q, r, size)
		var terrain := str(h.get("terrain", ""))
		_canvas.draw_colored_polygon(_hex_points(center, size * 0.96), _terrain_color(terrain))
		_draw_terrain_cue(center, size, terrain)

	# 2) Token roundels + numbers (always; hazard never replaces)
	for h in hexes:
		if typeof(h) != TYPE_DICTIONARY:
			continue
		var num = h.get("number")
		if num == null:
			continue
		var center := origin + _axial_to_pixel(float(h.get("q", 0)), float(h.get("r", 0)), size)
		_canvas.draw_circle(center, token_r, Color(0.12, 0.12, 0.14, 0.85))
		_canvas.draw_arc(center, token_r, 0.0, TAU, 24, Color(0.92, 0.92, 0.9, 0.7), 1.2, true)
		var label := str(int(num)) if typeof(num) == TYPE_FLOAT or typeof(num) == TYPE_INT else str(num)
		var half := float(label.length()) * float(font_px) * 0.28
		_canvas.draw_string(
			ThemeDB.fallback_font,
			center + Vector2(-half, float(font_px) * 0.35),
			label,
			HORIZONTAL_ALIGNMENT_LEFT,
			-1,
			font_px,
			Color.WHITE
		)

	# 3) Roads along exact vertex edges
	for road in _payload.get("roads", []):
		if typeof(road) != TYPE_DICTIONARY:
			continue
		var a := _node_pixel(str(road.get("a", "")), origin, size)
		var b := _node_pixel(str(road.get("b", "")), origin, size)
		_canvas.draw_line(a, b, VisualLanguage.faction_color(str(road.get("faction_id", ""))), road_w)

	# 4) Settlements / sites on vertices
	for n in _payload.get("nodes", []):
		if typeof(n) != TYPE_DICTIONARY:
			continue
		if not bool(n.get("is_settlement", false)):
			continue
		var p := _node_pixel(str(n.get("id", "")), origin, size)
		_draw_site(p, site_r, str(n.get("site_kind", "settlement")), str(n.get("faction_id", "")))

	# 5) Hazards — upper-right quadrant; stack if multiple
	var hazard_groups: Dictionary = {}
	for haz in _payload.get("hazards", []):
		if typeof(haz) != TYPE_DICTIONARY:
			continue
		var hid := str(haz.get("hex_id", ""))
		if not hazard_groups.has(hid):
			hazard_groups[hid] = []
		hazard_groups[hid].append(haz)
	for hid in hazard_groups.keys():
		var hx = _hex_lookup.get(hid)
		if hx == null:
			continue
		var c := origin + _axial_to_pixel(float(hx.get("q", 0)), float(hx.get("r", 0)), size)
		var group: Array = hazard_groups[hid]
		var base := c + Vector2(size * 0.42, -size * 0.38)
		var diamond_r := clampf(size * 0.16, 3.5, 7.0)
		if group.size() == 1:
			_draw_hazard_at(base, diamond_r)
		else:
			_draw_hazard_at(base, diamond_r)
			var count_lbl := "×%d" % group.size()
			_canvas.draw_string(
				ThemeDB.fallback_font,
				base + Vector2(diamond_r + 2.0, float(font_px) * 0.25),
				count_lbl,
				HORIZONTAL_ALIGNMENT_LEFT,
				-1,
				max(9, font_px - 2),
				VisualLanguage.HAZARD
			)

	# 6) John — distinct from settlements; slight offset if on a settled vertex
	var john: Dictionary = _payload.get("john", {})
	var jnid := str(john.get("node_id", ""))
	if jnid != "":
		var jp := _node_pixel(jnid, origin, size)
		var on_settle := false
		for n in _payload.get("nodes", []):
			if typeof(n) == TYPE_DICTIONARY and str(n.get("id", "")) == jnid and bool(n.get("is_settlement", false)):
				on_settle = true
				break
		if on_settle:
			jp += Vector2(site_r * 1.4, -site_r * 1.2)
		var jr := clampf(size * 0.14, 3.5, 7.5)
		_canvas.draw_circle(jp, jr * 1.15, Color(1, 1, 1))
		_canvas.draw_circle(jp, jr * 0.65, Color(0.2, 0.8, 1.0))


func _draw_hazard_at(pos: Vector2, radius: float) -> void:
	var diamond := VisualLanguage.hazard_diamond(radius)
	var shifted := PackedVector2Array()
	for v in diamond:
		shifted.append(v + pos)
	_canvas.draw_colored_polygon(shifted, VisualLanguage.HAZARD)


func _draw_site(pos: Vector2, r: float, kind: String, faction_id: String) -> void:
	var col := VisualLanguage.faction_color(faction_id)
	match kind:
		"ruin":
			var grey := Color(0.55, 0.55, 0.55)
			_canvas.draw_line(pos + Vector2(-r, -r), pos + Vector2(r, r), grey, 2.0)
			_canvas.draw_line(pos + Vector2(r, -r), pos + Vector2(-r, r), grey, 2.0)
			_canvas.draw_rect(Rect2(pos - Vector2(r, r), Vector2(r * 2.0, r * 2.0)), grey, false, 1.2)
		"historic_core":
			_canvas.draw_colored_polygon(_octagon(pos, r * 1.15), col)
			_canvas.draw_arc(pos, r * 1.35, 0.0, TAU, 16, Color.WHITE, 1.5, true)
		"city":
			_canvas.draw_rect(Rect2(pos - Vector2(r * 1.1, r * 1.1), Vector2(r * 2.2, r * 2.2)), col, true)
			_canvas.draw_rect(Rect2(pos - Vector2(r * 0.55, r * 0.55), Vector2(r * 1.1, r * 1.1)), Color(1, 1, 1, 0.85), true)
		"legacy":
			_canvas.draw_rect(Rect2(pos - Vector2(r, r), Vector2(r * 2.0, r * 2.0)), col, true)
			_canvas.draw_arc(pos, r * 1.45, 0.0, TAU, 16, Color(0.9, 0.85, 0.55), 1.4, true)
		_:
			# settlement — small filled square
			_canvas.draw_rect(Rect2(pos - Vector2(r, r), Vector2(r * 2.0, r * 2.0)), col, true)


func _octagon(center: Vector2, r: float) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in 8:
		var a := TAU * float(i) / 8.0 + PI / 8.0
		pts.append(center + Vector2(cos(a), sin(a)) * r)
	return pts


func _draw_terrain_cue(center: Vector2, size: float, terrain: String) -> void:
	var s := size * 0.18
	var ink := Color(0, 0, 0, 0.28)
	match terrain:
		"woodland":
			_canvas.draw_colored_polygon(PackedVector2Array([
				center + Vector2(0, -s * 1.1),
				center + Vector2(s * 0.7, s * 0.5),
				center + Vector2(-s * 0.7, s * 0.5),
			]), ink)
		"ore_mountains":
			_canvas.draw_colored_polygon(PackedVector2Array([
				center + Vector2(-s, s * 0.5),
				center + Vector2(0, -s),
				center + Vector2(s, s * 0.5),
			]), ink)
		"clay_mountains":
			_canvas.draw_line(center + Vector2(-s, s * 0.3), center + Vector2(s, -s * 0.2), ink, 1.2)
			_canvas.draw_line(center + Vector2(-s * 0.5, s * 0.55), center + Vector2(s * 0.6, s * 0.1), ink, 1.2)
		"fields":
			_canvas.draw_line(center + Vector2(-s, -s * 0.3), center + Vector2(s, -s * 0.3), ink, 1.0)
			_canvas.draw_line(center + Vector2(-s, 0), center + Vector2(s, 0), ink, 1.0)
			_canvas.draw_line(center + Vector2(-s, s * 0.3), center + Vector2(s, s * 0.3), ink, 1.0)
		"grazing_land":
			_canvas.draw_line(center + Vector2(-s * 0.4, s * 0.2), center + Vector2(0, -s * 0.5), ink, 1.0)
			_canvas.draw_line(center + Vector2(0, -s * 0.5), center + Vector2(s * 0.4, s * 0.2), ink, 1.0)
		"desert":
			_canvas.draw_circle(center + Vector2(-s * 0.35, 0), 1.2, ink)
			_canvas.draw_circle(center + Vector2(s * 0.2, s * 0.25), 1.2, ink)
			_canvas.draw_circle(center + Vector2(s * 0.35, -s * 0.2), 1.0, ink)
		_:
			pass


func _build_legend() -> void:
	for c in _legend.get_children():
		c.queue_free()
	_legend_item("■ Settlement", Color("#3A6EA5"))
	_legend_item("▣ City / Historic core", Color("#3A6EA5"))
	_legend_item("○ Legacy ring", Color(0.9, 0.85, 0.55))
	_legend_item("✕ Ruin", Color(0.55, 0.55, 0.55))
	_legend_item("─ Road", Color("#3A6EA5"))
	_legend_item("◆ Hazard", VisualLanguage.HAZARD)
	_legend_item("◎ You", Color(0.2, 0.8, 1.0))


func _legend_item(text: String, col: Color) -> void:
	var lbl := Label.new()
	lbl.text = text
	lbl.add_theme_font_size_override("font_size", 11)
	lbl.add_theme_color_override("font_color", col.lightened(0.15))
	_legend.add_child(lbl)


func _axial_to_pixel(q: float, r: float, size: float) -> Vector2:
	var x := size * (sqrt(3.0) * q + sqrt(3.0) / 2.0 * r)
	var y := size * (3.0 / 2.0 * r)
	return Vector2(x, y)


func _hex_points(center: Vector2, size: float) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in 6:
		var angle := TAU * float(i) / 6.0 + PI / 6.0
		pts.append(center + Vector2(cos(angle), sin(angle)) * size)
	return pts


func _terrain_color(terrain: String) -> Color:
	match terrain:
		"woodland":
			return Color(0.25, 0.45, 0.22)
		"ore_mountains":
			return Color(0.45, 0.45, 0.5)
		"clay_mountains":
			return Color(0.55, 0.4, 0.3)
		"fields":
			return Color(0.7, 0.65, 0.3)
		"grazing_land":
			return Color(0.45, 0.6, 0.35)
		"desert":
			return Color(0.75, 0.7, 0.45)
		_:
			return Color(0.35, 0.5, 0.3)


func _node_pixel(node_id: String, origin: Vector2, size: float) -> Vector2:
	## Exact HexBoard corner via exported map_position. No hex-centre average.
	if _node_pos.has(node_id):
		var mp: Vector2 = _node_pos[node_id]
		return origin + _axial_to_pixel(mp.x, mp.y, size)
	# Last resort: payload john.map_position or zero — should not happen for radius-2.
	push_warning("world_map missing map_position for %s" % node_id)
	return origin

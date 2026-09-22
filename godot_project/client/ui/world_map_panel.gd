extends Control
class_name DmbWorldMapPanel

## Read-only strategic map. Responsive full-screen modal; pause while open.

const VisualLanguage = preload("res://client/world/visual_language.gd")
const ResponsiveModal = preload("res://client/ui/responsive_modal.gd")

signal closed

var _payload: Dictionary = {}
var _canvas: Control
var _title: Label
var _margin: MarginContainer
var _panel: PanelContainer
var _close_btn: Button
var _fit_origin := Vector2.ZERO
var _fit_size := 18.0
var _hex_lookup: Dictionary = {}
var _node_hexes: Dictionary = {}


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
	_node_hexes.clear()
	for n in _payload.get("nodes", []):
		if typeof(n) != TYPE_DICTIONARY:
			continue
		var nid := str(n.get("id", ""))
		var touching: Array = n.get("touching_hexes", [])
		if touching.is_empty():
			touching = n.get("hexes", [])
		_node_hexes[nid] = touching


func _recompute_fit() -> void:
	var hexes: Array = _payload.get("hexes", [])
	if hexes.is_empty() or _canvas == null:
		_fit_origin = Vector2(40, 40)
		_fit_size = 18.0
		return
	var available := _canvas.size
	if available.x < 8.0 or available.y < 8.0:
		# Before first layout pass, estimate from panel.
		available = _panel.size - Vector2(24, 80)
	var padding := 20.0
	var min_q := 1e9
	var max_q := -1e9
	var min_r := 1e9
	var max_r := -1e9
	for h in hexes:
		if typeof(h) != TYPE_DICTIONARY:
			continue
		var q := float(h.get("q", 0))
		var r := float(h.get("r", 0))
		min_q = minf(min_q, q)
		max_q = maxf(max_q, q)
		min_r = minf(min_r, r)
		max_r = maxf(max_r, r)
	# Probe unit geometry at size=1.
	var corners := PackedVector2Array()
	for h in hexes:
		if typeof(h) != TYPE_DICTIONARY:
			continue
		var c := _axial_to_pixel(float(h.get("q", 0)), float(h.get("r", 0)), 1.0)
		for i in 6:
			var angle := TAU * float(i) / 6.0 + PI / 6.0
			corners.append(c + Vector2(cos(angle), sin(angle)))
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
	var marker_r := clampf(size * 0.28, 4.0, 14.0)
	var road_w := clampf(size * 0.18, 2.0, 8.0)
	var font_px := int(clampf(size * 0.55, 10.0, 22.0))
	for h in hexes:
		if typeof(h) != TYPE_DICTIONARY:
			continue
		var q := float(h.get("q", 0))
		var r := float(h.get("r", 0))
		var center := origin + _axial_to_pixel(q, r, size)
		var col := _terrain_color(str(h.get("terrain", "")))
		_canvas.draw_colored_polygon(_hex_points(center, size * 0.95), col)
		var num = h.get("number")
		if num != null:
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
	for road in _payload.get("roads", []):
		if typeof(road) != TYPE_DICTIONARY:
			continue
		var a := _node_pixel(str(road.get("a", "")), origin, size)
		var b := _node_pixel(str(road.get("b", "")), origin, size)
		_canvas.draw_line(a, b, VisualLanguage.faction_color(str(road.get("faction_id", ""))), road_w)
	for n in _payload.get("nodes", []):
		if typeof(n) != TYPE_DICTIONARY:
			continue
		if not bool(n.get("is_settlement", false)):
			continue
		var p := _node_pixel(str(n.get("id", "")), origin, size)
		_canvas.draw_circle(p, marker_r, VisualLanguage.faction_color(str(n.get("faction_id", ""))))
	for haz in _payload.get("hazards", []):
		if typeof(haz) != TYPE_DICTIONARY:
			continue
		var hid := str(haz.get("hex_id", ""))
		var hx = _hex_lookup.get(hid)
		if hx == null:
			continue
		var c := origin + _axial_to_pixel(float(hx.get("q", 0)), float(hx.get("r", 0)), size)
		var diamond := VisualLanguage.hazard_diamond(clampf(size * 0.4, 6.0, 16.0))
		var shifted := PackedVector2Array()
		for v in diamond:
			shifted.append(v + c)
		_canvas.draw_colored_polygon(shifted, VisualLanguage.HAZARD)
	var john: Dictionary = _payload.get("john", {})
	var jp := _node_pixel(str(john.get("node_id", "")), origin, size)
	_canvas.draw_circle(jp, marker_r * 0.9, Color(1, 1, 1))
	_canvas.draw_circle(jp, marker_r * 0.55, Color(0.2, 0.8, 1.0))


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
	## Prefer average of touching hex centres when payload includes them.
	var touching: Array = _node_hexes.get(node_id, [])
	if touching is Array and touching.size() > 0:
		var acc := Vector2.ZERO
		var count := 0
		for hid in touching:
			var hx = _hex_lookup.get(str(hid))
			if hx == null:
				continue
			acc += _axial_to_pixel(float(hx.get("q", 0)), float(hx.get("r", 0)), size)
			count += 1
		if count > 0:
			return origin + acc / float(count)
	# Fallback schematic scatter — documented limitation when hex links absent.
	var n := 0
	if ":" in node_id:
		n = int(node_id.get_slice(":", 1))
	var angle := float(n) * 0.47
	var rad := size * (2.2 + float(n % 7) * 0.35)
	return origin + Vector2(cos(angle), sin(angle)) * rad

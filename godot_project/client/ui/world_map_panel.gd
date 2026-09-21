extends Control
class_name DmbWorldMapPanel

## Crude read-only strategic map. Pause while open. Not a command UI.

const VisualLanguage = preload("res://client/world/visual_language.gd")

signal closed

var _payload: Dictionary = {}
var _canvas: Control
var _title: Label


func _ready() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.55)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(420, 480)
	panel.position = Vector2(-210, -240)
	add_child(panel)
	var v := VBoxContainer.new()
	panel.add_child(v)
	_title = Label.new()
	_title.text = "World Map"
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(_title)
	_canvas = Control.new()
	_canvas.custom_minimum_size = Vector2(400, 400)
	_canvas.draw.connect(_on_draw_map)
	v.add_child(_canvas)
	var close_btn := Button.new()
	close_btn.text = "Close"
	close_btn.pressed.connect(hide_map)
	v.add_child(close_btn)


func show_map(payload: Dictionary) -> void:
	_payload = payload
	visible = true
	_title.text = "World Map — Turn view"
	_canvas.queue_redraw()


func hide_map() -> void:
	visible = false
	closed.emit()


func _on_draw_map() -> void:
	var hexes: Array = _payload.get("hexes", [])
	if hexes.is_empty():
		return
	var origin := Vector2(200, 200)
	var size := 18.0
	# Draw hexes
	for h in hexes:
		var q := float(h.get("q", 0))
		var r := float(h.get("r", 0))
		var center := origin + _axial_to_pixel(q, r, size)
		var col := _terrain_color(str(h.get("terrain", "")))
		_canvas.draw_colored_polygon(_hex_points(center, size * 0.95), col)
		var num = h.get("number")
		if num != null:
			_canvas.draw_string(ThemeDB.fallback_font, center + Vector2(-6, 4), str(num), HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color.WHITE)
	# Roads
	var node_pos := {}
	for n in _payload.get("nodes", []):
		# Approximate node position as average of touching hexes — use axial of first matching hex label if present
		pass
	# Draw roads as lines between settlement nodes using hex centres of node ids hashed
	for road in _payload.get("roads", []):
		var a := _node_pixel(str(road.get("a", "")), origin, size)
		var b := _node_pixel(str(road.get("b", "")), origin, size)
		_canvas.draw_line(a, b, VisualLanguage.faction_color(str(road.get("faction_id", ""))), 3.0)
	# Settlements
	for n in _payload.get("nodes", []):
		if not bool(n.get("is_settlement", false)):
			continue
		var p := _node_pixel(str(n.get("id", "")), origin, size)
		_canvas.draw_circle(p, 5.0, VisualLanguage.faction_color(str(n.get("faction_id", ""))))
	# Hazards
	for haz in _payload.get("hazards", []):
		var hid := str(haz.get("hex_id", ""))
		var hx = null
		for h in hexes:
			if str(h.get("id", "")) == hid:
				hx = h
				break
		if hx == null:
			continue
		var c := origin + _axial_to_pixel(float(hx.get("q", 0)), float(hx.get("r", 0)), size)
		var diamond := VisualLanguage.hazard_diamond(7.0)
		var shifted := PackedVector2Array()
		for v in diamond:
			shifted.append(v + c)
		_canvas.draw_colored_polygon(shifted, VisualLanguage.HAZARD)
	# John
	var john: Dictionary = _payload.get("john", {})
	var jp := _node_pixel(str(john.get("node_id", "")), origin, size)
	_canvas.draw_circle(jp, 4.0, Color(1, 1, 1))
	_canvas.draw_circle(jp, 2.5, Color(0.2, 0.8, 1.0))


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
	# Deterministic scatter from node number around board centre.
	var n := 0
	if ":" in node_id:
		n = int(node_id.get_slice(":", 1))
	var angle := float(n) * 0.47
	var rad := 40.0 + float(n % 7) * 8.0
	return origin + Vector2(cos(angle), sin(angle)) * rad
